import gc
import tkinter as tk
from types import SimpleNamespace

import pytest

from core.game_state import GameState
from core.types import Player, Position
from gui.main_window import MainWindow
from gui.timer_panel import MatchTimer
from record.auto_save import auto_save, auto_save_match
from record.game_record import GameRecord
from record.match_record import MatchRecord
from tests.tk_support import make_hidden_tk_root


@pytest.fixture
def window(tmp_path):
    top = tk.Toplevel(make_hidden_tk_root())
    top.withdraw()
    frame = MainWindow(
        top,
        auto_save_path=tmp_path / "auto_save.json",
        auto_save_match_path=tmp_path / "auto_save_match.json",
    )
    yield frame
    if frame.winfo_exists():
        frame.destroy()
    if top.winfo_exists():
        top.destroy()
    gc.collect()


def _record_for_match(match, *, terminal=False):
    state = GameState.from_layout(
        red={1: Position(4, 4) if terminal else Position(0, 0)},
        blue={1: Position(3, 3) if terminal else Position(4, 4)},
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)
    record.metadata.update(
        match_id=match.match_id,
        game_index=1,
        our_side=match.our_side.value,
        our_role=match.our_role,
        first_mover_color="red",
        time_limit_seconds=match.time_limit_seconds,
        auto_timeout_enabled=match.auto_timeout_enabled,
    )
    return record, state


def _write_recovery_files(window, match, record, state):
    timer = SimpleNamespace(
        current_player=state.current_player,
        remaining_seconds={Player.RED: 300.0, Player.BLUE: 300.0},
        paused=True,
    )
    auto_save(record, timer, path=window._auto_save_path)
    auto_save_match(match, path=window._auto_save_match_path)
    return window._auto_save_path.read_bytes(), window._auto_save_match_path.read_bytes()


@pytest.mark.parametrize("invalid_result", ["unknown_reason", "false_capture_all", "positive_clock_timeout"])
def test_invalid_active_outcome_keeps_window_and_recovery_files(window, monkeypatch, invalid_result):
    match = MatchRecord(
        Player.RED, "甲", phase="playing", time_limit_seconds=600.0, auto_timeout_enabled=True,
    )
    record, state = _record_for_match(match, terminal=invalid_result == "false_capture_all")
    reason = "invalid" if invalid_result == "unknown_reason" else (
        "capture_all" if invalid_result == "false_capture_all" else "timeout"
    )
    winner = "blue" if invalid_result == "positive_clock_timeout" else "red"
    record.result = {"winner": winner, "reason": reason, "game_index": 1}
    game_bytes, match_bytes = _write_recovery_files(window, match, record, state)
    errors = []
    monkeypatch.setattr("gui.main_window.messagebox.showerror", lambda *args, **kwargs: errors.append(args))
    old_state, old_record, old_timer = window.state, window.record, window.timer
    old_generation = window._recommendation_generation
    assert window.opening_panel.side_controls_enabled

    assert window._restore_match_auto_save(has_game=True) is False

    assert errors
    assert window.state is old_state
    assert window.record is old_record
    assert window.timer is old_timer
    assert window._total_seconds == 240.0
    assert window._auto_timeout_enabled is False
    assert window._recommendation_generation == old_generation
    assert window._match is None
    assert window._mode == "debug"
    assert window._our_side is None
    assert window.opening_panel.side_controls_enabled
    assert window._auto_save_path.read_bytes() == game_bytes
    assert window._auto_save_match_path.read_bytes() == match_bytes


def test_playing_match_with_committed_residual_requires_missing_progress_decision(window, monkeypatch):
    match = MatchRecord(Player.RED, "甲", time_limit_seconds=600.0)
    record, state = _record_for_match(match, terminal=True)
    record.result = {"winner": "red", "winner_side": "us", "reason": "target_corner", "game_index": 1}
    match.append_finished_game(record, "us")
    match.start_playing()
    _write_recovery_files(window, match, record, state)
    prompts = []

    def accept_missing_progress(title, message, **kwargs):
        prompts.append((title, message))
        return True

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", accept_missing_progress)

    assert window._restore_match_auto_save(has_game=True) is True

    assert len(prompts) == 1
    assert prompts[0][0] == "本盘进度缺失"
    assert window._match.current_game_index == 2
    assert window._match.games_won_us == 1
    assert window._match.phase == "setup"
    assert window._phase == "setup"


def test_apply_button_timeout_replaces_the_pending_timer_callback(window, monkeypatch):
    match = MatchRecord(Player.RED, "甲", phase="playing", auto_timeout_enabled=True)
    window._match = match
    window._mode = "match"
    window._our_side = Player.RED
    window._phase = "playing"
    window._awaiting_dice = False
    window.current_dice = 1
    window.selected_move_index = 0
    window._auto_timeout_enabled = True
    window.record.metadata.update(match_id=match.match_id, game_index=1, our_side="red", our_role="甲", first_mover_color="red")
    window.timer = MatchTimer(current_player=Player.RED)
    window.timer.reset(current_player=Player.RED, remaining_seconds={Player.RED: 0.0, Player.BLUE: 240.0})
    quick_ai = SimpleNamespace(choose_move=lambda state, dice: None)
    window._recommender = quick_ai
    window._fallback_recommender = quick_ai
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *args, **kwargs: None)
    window.controls.set_can_apply(True)
    previous_id = window._timer_after_id
    before = window.state.serialize()

    window.controls.apply_button.invoke()

    assert window.state.serialize() == before
    assert not window.record.steps
    assert window._match.games_won_them == 1
    pending = set(window.tk.call("after", "info"))
    assert previous_id not in pending
    assert window._timer_after_id in pending
    refresh_callbacks = [
        callback_id for callback_id in pending
        if str(window.tk.call("after", "info", callback_id)[0]).endswith("_refresh_timer")
    ]
    assert refresh_callbacks == [window._timer_after_id]
