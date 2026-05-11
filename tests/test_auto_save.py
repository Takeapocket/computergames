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
