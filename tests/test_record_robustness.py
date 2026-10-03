import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.game_state import GameState
from core.move import Move
from core.types import Piece, Player, Position
from record.auto_save import auto_save, has_auto_save, is_invalid_auto_save_file, load_auto_save
from record.game_record import GameRecord
from record.match_record import MatchRecord


def _capture_record():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(0, 1)},
        blue={1: Position(1, 1), 2: Position(4, 4)},
    )
    record = GameRecord.from_state(state)
    for dice, destination in (
        (1, Position(1, 1)),
        (2, Position(3, 3)),
        (2, Position(1, 1)),
        (2, Position(2, 2)),
        (2, Position(2, 2)),
    ):
        move = next(m for m in state.legal_moves(state.current_player, dice) if m.to_pos == destination)
        applied = state.apply_move(move, dice)
        record.append(dice=dice, move=applied, state_after=state)
    return record, state


def test_history_round_trip_preserves_multiple_enemy_and_self_captures():
    record, state = _capture_record()
    restored = GameState.deserialize(state.serialize())
    assert restored.serialize() == state.serialize()
    while restored.history:
        restored.undo_move()
    assert restored.serialize() == record.initial_state
    loaded_record = GameRecord.from_dict(record.to_dict())
    assert loaded_record.restore_state().serialize() == state.serialize()


@pytest.mark.parametrize("corruption", ["missing_piece", "current_player", "capture_flag", "capture_position", "capture_alive", "geometry"])
def test_deserialize_rejects_inconsistent_history(corruption):
    _, state = _capture_record()
    raw = state.serialize()
    move = raw["history"][-1]
    if corruption == "missing_piece":
        move["piece_id"] = 6
    elif corruption == "current_player":
        raw["current_player"] = "red"
    elif corruption == "capture_flag":
        move["is_capture"] = False
    elif corruption == "capture_position":
        move["captured_piece"]["position"] = {"row": 0, "col": 0}
    elif corruption == "capture_alive":
        move["captured_piece"]["alive"] = False
    else:
        move["from_pos"] = {"row": 0, "col": 0}
    with pytest.raises(ValueError):
        GameState.deserialize(raw)


def test_record_rejects_invalid_history_in_initial_snapshot():
    state = GameState.from_layout(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    raw = GameRecord.from_state(state).to_dict()
    raw["initial_state"]["history"] = [Move(Player.BLUE, 6, Position(4, 4), Position(3, 3)).to_dict()]
    with pytest.raises(ValueError, match="record"):
        GameRecord.from_dict(raw)


@pytest.mark.parametrize("corruption", ["missing_piece", "capture_snapshot", "capture_flag", "occupied_origin"])
def test_failed_undo_leaves_caller_state_unchanged(corruption):
    _, state = _capture_record()
    move = state.history[-1]
    if corruption == "missing_piece":
        state.history[-1] = replace(move, piece_id=6)
    elif corruption == "capture_snapshot":
        move.captured_piece.position = Position(-1, 0)
    elif corruption == "capture_flag":
        state.history[-1] = replace(move, is_capture=False)
    else:
        state.pieces[Player.RED][3] = Piece(Player.RED, 3, move.from_pos)
    before = state.serialize()
    with pytest.raises(ValueError):
        state.undo_move()
    assert state.serialize() == before


@pytest.mark.parametrize("corruption", ["missing_capture", "wrong_capture", "wrong_flag"])
def test_record_rejects_capture_metadata_that_differs_from_core(corruption):
    record, _ = _capture_record()
    raw = record.to_dict()
    move = raw["steps"][0]["move"]
    if corruption == "missing_capture":
        move["captured_piece"] = None
        move["is_capture"] = False
    elif corruption == "wrong_capture":
        move["captured_piece"]["piece_id"] = 2
    else:
        move["is_capture"] = False
    with pytest.raises(ValueError, match="capture metadata"):
        GameRecord.from_dict(raw)


@pytest.mark.parametrize("value", [True, 0.99, "0", float("inf")])
def test_state_coordinates_reject_numeric_coercion(value):
    raw = GameState.from_layout(red={1: Position(0, 0)}).serialize()
    raw["pieces"]["red"]["1"]["position"]["row"] = value
    with pytest.raises(ValueError):
        GameState.deserialize(raw)


@pytest.mark.parametrize("value", [True, 1.7, "1", float("inf")])
def test_state_piece_ids_and_dice_reject_numeric_coercion(value):
    state = GameState.from_layout(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    raw = state.serialize()
    raw["pieces"]["red"]["1"]["piece_id"] = value
    with pytest.raises(ValueError):
        GameState.deserialize(raw)
    with pytest.raises(ValueError):
        state.legal_moves(Player.RED, value)
    with pytest.raises(ValueError):
        GameState.from_layout(red={value: Position(0, 0)})


@pytest.mark.parametrize("value", ["false", 0, 1, None])
def test_state_alive_flags_require_booleans(value):
    raw = GameState.from_layout(red={1: Position(0, 0)}).serialize()
    raw["pieces"]["red"]["1"]["alive"] = value
    with pytest.raises(ValueError):
        GameState.deserialize(raw)


def test_duplicate_piece_mapping_cannot_overwrite_a_piece():
    raw = GameState.from_layout(red={1: Position(0, 0)}).serialize()
    raw["pieces"]["red"]["01"] = copy.deepcopy(raw["pieces"]["red"]["1"])
    raw["pieces"]["red"]["01"]["position"] = {"row": 1, "col": 1}
    with pytest.raises(ValueError):
        GameState.deserialize(raw)


@pytest.mark.parametrize("field,value", [("turn", 1.2), ("dice", True), ("dice", "1"), ("step_seconds", True), ("step_seconds", "1"), ("step_seconds", 10**400)])
def test_record_step_fields_reject_coercion_and_overflow(field, value):
    record, _ = _capture_record()
    raw = record.to_dict()
    raw["steps"][0][field] = value
    with pytest.raises(ValueError, match=field):
        GameRecord.from_dict(raw)


@pytest.mark.parametrize("value", [10**400, True, "240", float("inf")])
def test_corrupt_timer_files_are_detected_without_crashing(tmp_path, value):
    record, _ = _capture_record()
    raw = record.to_dict()
    raw["metadata"]["auto_save"] = {
        "timer_current_player": "blue",
        "timer_remaining": {"red": value, "blue": 240.0},
        "timer_paused": False,
    }
    path = tmp_path / "auto_save.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert has_auto_save(path=path) is False
    assert is_invalid_auto_save_file(path=path) is True
    with pytest.raises(ValueError, match="metadata"):
        load_auto_save(path=path)


def test_invalid_timer_snapshot_cannot_replace_existing_save(tmp_path):
    record, _ = _capture_record()
    path = tmp_path / "auto_save.json"
    path.write_text("existing save", encoding="utf-8")
    snapshot = SimpleNamespace(
        current_player=Player.BLUE,
        remaining_seconds={Player.RED: 10**400, Player.BLUE: 240.0},
        paused=False,
    )
    with pytest.raises(ValueError):
        auto_save(record, snapshot, path=path)
    assert path.read_text(encoding="utf-8") == "existing save"


def test_match_timer_options_round_trip_and_legacy_presence_tracking():
    match = MatchRecord(Player.RED, "甲", time_limit_seconds=600.0, auto_timeout_enabled=True)
    raw = match.to_dict()
    assert "_stored_timer_fields" not in raw
    restored = MatchRecord.from_dict(raw)
    assert restored.time_limit_seconds == 600.0
    assert restored.auto_timeout_enabled is True
    assert restored._stored_timer_fields == {"time_limit_seconds", "auto_timeout_enabled"}
    raw.pop("time_limit_seconds")
    raw.pop("auto_timeout_enabled")
    legacy = MatchRecord.from_dict(raw)
    assert legacy.time_limit_seconds == 240.0
    assert legacy.auto_timeout_enabled is False
    assert legacy._stored_timer_fields == frozenset()


@pytest.mark.parametrize("field,value", [("total_games", True), ("target_wins", 4.5), ("current_game_index", "1"), ("games_won_us", 0.5), ("time_limit_seconds", 10**400), ("time_limit_seconds", 0), ("time_limit_seconds", "600"), ("auto_timeout_enabled", "false")])
def test_match_rejects_invalid_numeric_options(field, value):
    raw = MatchRecord(Player.RED, "甲").to_dict()
    raw[field] = value
    with pytest.raises(ValueError):
        MatchRecord.from_dict(raw)


@pytest.mark.parametrize("phase", ["setup", "playing"])
def test_match_rejects_index_that_skips_completed_games(phase):
    raw = MatchRecord(Player.RED, "甲").to_dict()
    raw.update(current_game_index=7, phase=phase)
    with pytest.raises(ValueError, match="current_game_index"):
        MatchRecord.from_dict(raw)


def test_match_valid_indices_include_finished_and_exhausted_records():
    game = GameRecord.from_state(GameState.from_layout())
    finished = MatchRecord(Player.RED, "甲")
    for _ in range(4):
        finished.append_finished_game(game, "us")
    assert MatchRecord.from_dict(finished.to_dict()).current_game_index == 4
    exhausted = MatchRecord(Player.RED, "甲", total_games=2, target_wins=2)
    exhausted.append_finished_game(game, "us")
    exhausted.append_finished_game(game, "them")
    assert MatchRecord.from_dict(exhausted.to_dict()).current_game_index == 2
