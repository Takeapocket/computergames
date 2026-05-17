from __future__ import annotations

import pytest

from core.game_state import GameState
from core.types import Player, Position
from gui.timer_panel import TimerSnapshot
from record.game_record import GameRecord


def make_record_with_one_step() -> GameRecord:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(
        dice=1,
        move=move,
        state_after=state,
        step_seconds=12.5,
        remaining_seconds={Player.RED: 227.5, Player.BLUE: 240.0},
    )
    return record


def make_timer_snapshot() -> TimerSnapshot:
    return TimerSnapshot(
        current_player=Player.BLUE,
        remaining_seconds={Player.RED: 227.5, Player.BLUE: 240.0},
        current_step_seconds=0.0,
        paused=True,
        timeout_players=(),
    )


def test_auto_save_round_trip_preserves_record_and_timer_metadata(tmp_path) -> None:
    from record.auto_save import auto_save, has_auto_save, load_auto_save

    path = tmp_path / "auto_save.json"
    record = make_record_with_one_step()
    snapshot = make_timer_snapshot()

    auto_save(record, snapshot, path=path)

    assert has_auto_save(path=path) is True
    loaded_record, timer_metadata = load_auto_save(path=path)
    assert loaded_record.to_dict() == {
        **record.to_dict(),
        "metadata": {
            **record.metadata,
            "auto_save": timer_metadata,
        },
    }
    assert timer_metadata == {
        "timer_current_player": "blue",
        "timer_remaining": {"red": 227.5, "blue": 240.0},
        "timer_paused": True,
    }
    assert loaded_record.restore_state().serialize() == record.restore_state().serialize()


@pytest.mark.parametrize("payload", ["", "   "])
def test_has_auto_save_rejects_empty_files(tmp_path, payload: str) -> None:
    from record.auto_save import has_auto_save

    path = tmp_path / "auto_save.json"
    path.write_text(payload, encoding="utf-8")

    assert has_auto_save(path=path) is False


def test_has_auto_save_returns_false_for_missing_file(tmp_path) -> None:
    from record.auto_save import has_auto_save

    assert has_auto_save(path=tmp_path / "missing.json") is False


def test_clear_auto_save_removes_existing_file(tmp_path) -> None:
    from record.auto_save import clear_auto_save, has_auto_save

    path = tmp_path / "auto_save.json"
    path.write_text("{}", encoding="utf-8")

    clear_auto_save(path=path)

    assert has_auto_save(path=path) is False


def test_load_auto_save_rejects_missing_timer_metadata(tmp_path) -> None:
    from record.auto_save import load_auto_save

    path = tmp_path / "auto_save.json"
    make_record_with_one_step().save(path)

    with pytest.raises(ValueError, match="auto-save metadata"):
        load_auto_save(path=path)


# ---- R-2 match-level auto-save ----

def _make_match():
    from record.match_record import MatchRecord
    return MatchRecord(our_side=Player.RED, our_role="甲")


def test_auto_save_match_roundtrip(tmp_path):
    from record.auto_save import (
        auto_save_match,
        clear_auto_save_match,
        has_auto_save_match,
        load_auto_save_match,
    )

    path = tmp_path / "auto_save_match.json"
    assert has_auto_save_match(path=path) is False

    match = _make_match()
    match.append_finished_game(make_record_with_one_step(), "us")
    auto_save_match(match, path=path)
    assert has_auto_save_match(path=path) is True

    loaded = load_auto_save_match(path=path)
    assert loaded.our_side is Player.RED
    assert loaded.our_role == "甲"
    assert loaded.games_won_us == 1
    assert loaded.phase == "setup"
    assert len(loaded.games) == 1
    assert loaded.current_game_index == 2

    clear_auto_save_match(path=path)
    assert has_auto_save_match(path=path) is False


def test_auto_save_match_preserves_finished_phase(tmp_path):
    from record.auto_save import auto_save_match, load_auto_save_match

    match = _make_match()
    for _ in range(4):
        match.append_finished_game(make_record_with_one_step(), "us")
    path = tmp_path / "auto_save_match.json"
    auto_save_match(match, path=path)

    loaded = load_auto_save_match(path=path)
    assert loaded.phase == "finished"
    assert loaded.winner() == "us"
    assert len(loaded.games) == 4


def test_clear_auto_save_match_missing_path_ok(tmp_path):
    from record.auto_save import clear_auto_save_match

    clear_auto_save_match(path=tmp_path / "does-not-exist.json")


def test_has_auto_save_match_empty_file_is_false(tmp_path):
    from record.auto_save import has_auto_save_match

    path = tmp_path / "auto_save_match.json"
    path.write_text("", encoding="utf-8")
    assert has_auto_save_match(path=path) is False


# ---- R-2 review Critical #3 + Important #11：原子写 + 损坏 JSON 拒绝 ----


def test_atomic_write_preserves_existing_file_on_failure(tmp_path, monkeypatch):
    """中途崩溃（os.replace 之前）不应破坏原文件。"""
    import record.auto_save as auto_save_mod
    from record.auto_save import auto_save

    path = tmp_path / "auto_save.json"
    record = make_record_with_one_step()
    snapshot = make_timer_snapshot()
    # 先写一次合法内容
    auto_save(record, snapshot, path=path)
    original = path.read_text(encoding="utf-8")

    # 模拟 _atomic_write_text 内部失败：把 os.replace 替换成抛 OSError
    real_replace = auto_save_mod.os.replace

    def boom(src, dst):  # noqa: ANN001
        raise OSError("disk full simulation")

    monkeypatch.setattr(auto_save_mod.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        auto_save(record, snapshot, path=path)

    # 原文件未被损坏
    assert path.read_text(encoding="utf-8") == original
    # 同目录无残留 .tmp- 临时文件
    tmps = [p for p in path.parent.iterdir() if p.name.startswith(".tmp-")]
    assert tmps == []

    monkeypatch.setattr(auto_save_mod.os, "replace", real_replace)


def test_has_auto_save_rejects_corrupt_json(tmp_path):
    """has_auto_save 不应把损坏的 JSON 当成有效的 auto-save。"""
    from record.auto_save import has_auto_save

    path = tmp_path / "auto_save.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert has_auto_save(path=path) is False


def test_has_auto_save_match_rejects_corrupt_json(tmp_path):
    from record.auto_save import has_auto_save_match

    path = tmp_path / "auto_save_match.json"
    path.write_text("not even json", encoding="utf-8")
    assert has_auto_save_match(path=path) is False


def test_is_invalid_auto_save_file_detects_corrupt_json(tmp_path):
    from record.auto_save import is_invalid_auto_save_file

    path = tmp_path / "auto_save.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert is_invalid_auto_save_file(path=path) is True


def test_is_invalid_auto_save_file_is_false_for_missing_file(tmp_path):
    from record.auto_save import is_invalid_auto_save_file

    assert is_invalid_auto_save_file(path=tmp_path / "missing.json") is False


def test_is_invalid_match_auto_save_file_detects_corrupt_json(tmp_path):
    from record.auto_save import is_invalid_match_auto_save_file

    path = tmp_path / "auto_save_match.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert is_invalid_match_auto_save_file(path=path) is True


def test_auto_save_match_atomic_write_preserves_existing(tmp_path, monkeypatch):
    """match auto-save 也走原子写。"""
    import record.auto_save as auto_save_mod
    from record.auto_save import auto_save_match
    from record.match_record import MatchRecord

    path = tmp_path / "auto_save_match.json"
    match = MatchRecord(our_side=Player.RED, our_role="甲")
    match.append_finished_game(make_record_with_one_step(), "us")
    auto_save_match(match, path=path)
    original = path.read_text(encoding="utf-8")

    def boom(src, dst):  # noqa: ANN001
        raise OSError("simulated failure")

    monkeypatch.setattr(auto_save_mod.os, "replace", boom)
    with pytest.raises(OSError):
        auto_save_match(match, path=path)
    assert path.read_text(encoding="utf-8") == original
