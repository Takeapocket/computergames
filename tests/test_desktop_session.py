import json

import pytest

from ai.match import starting_state_for
from core.game_state import GameState
from core.rules import RULES_VERSION
from core.types import Player, Position
from desktop_qt.session import GameSession
from record.game_record import GameRecord


def test_session_uses_current_rules_default_layout_and_roundtrips_existing_record(tmp_path):
    session = GameSession()
    initial = starting_state_for("balanced_v1").serialize()
    assert session.state.serialize() == initial
    assert session.record.metadata["rules_version"] == RULES_VERSION
    assert not session.dirty
    session.set_dice(3)
    session.apply_move(session.legal_moves()[0])
    assert session.dice is None and session.dirty
    path = tmp_path / "中文 棋谱.json"
    session.save(path)
    assert not session.dirty
    assert GameRecord.load(path).restore_state().serialize() == session.state.serialize()
    loaded = GameSession()
    loaded.load(path)
    assert loaded.record.to_dict() == session.record.to_dict()
    loaded.undo()
    assert loaded.state.serialize() == initial
    assert loaded.dice == 3 and loaded.dirty


@pytest.mark.parametrize("dice", [True, 0, 7, 3.0, "3", None])
def test_invalid_dice_keeps_session_unchanged(dice):
    session = GameSession()
    session.set_dice(2)
    revision = session.revision
    with pytest.raises(ValueError):
        session.set_dice(dice)
    assert session.dice == 2 and session.revision == revision
    assert not session.dirty


def test_failed_append_keeps_both_state_and_record_unchanged(monkeypatch):
    session = GameSession()
    session.set_dice(4)
    before = session.state.serialize(), session.record.to_dict(), session.revision

    def fail(*args, **kwargs):
        raise ValueError("injected record validation failure")

    monkeypatch.setattr(GameRecord, "append", fail)
    with pytest.raises(ValueError, match="injected"):
        session.apply_move(session.legal_moves()[0])
    assert (session.state.serialize(), session.record.to_dict(), session.revision) == before
    assert session.dice == 4 and not session.dirty


def test_save_failure_preserves_dirty_record_and_existing_file(tmp_path, monkeypatch):
    session = GameSession()
    session.set_dice(1)
    session.apply_move(session.legal_moves()[0])
    path = tmp_path / "record.json"
    path.write_text("existing file", encoding="utf-8")

    def fail(*args, **kwargs):
        raise OSError("injected replace failure")

    monkeypatch.setattr("record.game_record.os.replace", fail)
    with pytest.raises(OSError, match="injected"):
        session.save(path)
    assert session.dirty
    assert path.read_text(encoding="utf-8") == "existing file"


def test_corrupt_load_does_not_replace_active_session(tmp_path):
    session = GameSession()
    session.set_dice(2)
    session.apply_move(session.legal_moves()[0])
    before = session.state.serialize(), session.record.to_dict(), session.revision
    data = session.record.to_dict()
    data["steps"][0]["dice"] = 7
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        session.load(path)
    assert (session.state.serialize(), session.record.to_dict(), session.revision) == before
    assert session.dirty


def test_explicit_old_rules_load_read_only_and_keep_version_on_save(tmp_path):
    record = GameRecord.from_state(starting_state_for("balanced_v1"))
    record.metadata["rules_version"] = "einstein-nearest-v1"
    path = tmp_path / "old.json"
    record.save(path)
    session = GameSession()
    session.load(path)
    assert session.continuation_error is not None
    assert session.legal_moves() == []
    with pytest.raises(ValueError, match="只能查看"):
        session.set_dice(3)
    with pytest.raises(ValueError, match="只能查看"):
        session.undo()
    session.save(tmp_path / "copy.json")
    assert GameRecord.load(tmp_path / "copy.json").metadata == record.metadata


def test_unversioned_legacy_record_remains_compatible(tmp_path):
    record = GameRecord.from_state(starting_state_for("balanced_v1"))
    record.metadata.pop("rules_version")
    record.metadata["legacy_note"] = "保留原始元数据"
    path = tmp_path / "legacy.json"
    record.save(path)
    session = GameSession()
    session.load(path)
    assert session.continuation_error is None
    session.set_dice(6)
    session.apply_move(session.legal_moves()[0])
    assert session.record.metadata == record.metadata


def test_caller_move_capture_snapshot_cannot_mutate_session(tmp_path):
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(4, 3)},
    )
    path = tmp_path / "capture.json"
    GameRecord.from_state(state).save(path)
    session = GameSession()
    session.load(path)
    session.set_dice(1)
    move = next(move for move in session.legal_moves() if move.is_capture)
    session.apply_move(move)
    move.captured_piece.alive = False
    assert session.record.steps[0].move.captured_piece.alive is True
    assert session.state.history[0].captured_piece.alive is True


def test_undo_never_crosses_record_initial_history(tmp_path):
    state = starting_state_for("balanced_v1")
    state.apply_move(state.legal_moves(state.current_player, 2)[0], dice=2)
    path = tmp_path / "snapshot_with_history.json"
    GameRecord.from_state(state).save(path)
    session = GameSession()
    session.load(path)
    with pytest.raises(ValueError, match="没有可撤回"):
        session.undo()
    session.set_dice(3)
    session.apply_move(session.legal_moves()[0])
    session.undo()
    assert session.state.serialize() == state.serialize()
    with pytest.raises(ValueError, match="没有可撤回"):
        session.undo()


def test_terminal_board_rejects_move_but_can_undo_last_record_step(tmp_path):
    state = GameState.from_layout(
        red={1: Position(3, 3)}, blue={1: Position(4, 2)},
    )
    path = tmp_path / "near_end.json"
    GameRecord.from_state(state).save(path)
    session = GameSession()
    session.load(path)
    session.set_dice(1)
    session.apply_move(next(move for move in session.legal_moves() if move.to_pos == Position(4, 4)))
    assert session.state.get_winner() is Player.RED
    assert session.legal_moves() == []
    with pytest.raises(ValueError, match="finished"):
        session.set_dice(1)
    session.save(path)
    session.load(path)
    assert session.state.get_winner() is Player.RED
    session.undo()
    assert session.state.get_winner() is None


def test_recorded_timeout_result_stays_read_only(tmp_path):
    record = GameRecord.from_state(starting_state_for("balanced_v1"))
    record.result = {"winner": "blue", "reason": "timeout", "game_index": 1}
    path = tmp_path / "timeout.json"
    record.save(path)
    session = GameSession()
    session.load(path)
    assert session.continuation_error is not None
    assert session.legal_moves() == []
    with pytest.raises(ValueError, match="已经记录"):
        session.set_dice(4)
