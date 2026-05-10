"""Tests for the MainWindow widget that require an actual Tk display."""
from __future__ import annotations

import tkinter as tk

import pytest

from core.types import Player
from gui.main_window import MainWindow


@pytest.fixture(scope="module")
def _tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def tk_root(_tk_root):
    top = tk.Toplevel(_tk_root)
    yield top
    if top.winfo_exists():
        top.destroy()


def test_main_window_destroy_cancels_pending_timer_callback(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    scheduled_id = window._timer_after_id
    assert scheduled_id, "setup: timer should be scheduled after construction"

    window.destroy()

    pending = str(tk_root.tk.call("after", "info"))
    assert scheduled_id not in pending, (
        f"after callback {scheduled_id} still pending in {pending}; "
        "destroy() must cancel via after_cancel"
    )


def test_undo_button_disabled_when_history_empty(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert str(window.controls.undo_button["state"]) == "disabled"


def test_undo_button_enabled_after_move_applied(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    moves = window._current_moves()
    assert moves, "setup: at least one legal move with default dice 6"
    window.selected_move_index = 0
    window._apply_selected_move()

    assert str(window.controls.undo_button["state"]) == "normal"


def test_undo_button_disabled_again_after_undo(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0
    window._apply_selected_move()
    window._undo_move()

    assert str(window.controls.undo_button["state"]) == "disabled"


def test_record_dirty_false_on_fresh_window(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert window._record_dirty is False
    assert "已保存" in window.match_mode_panel.record_status_var.get()


def test_record_dirty_true_after_apply(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0
    window._apply_selected_move()

    assert window._record_dirty is True
    assert "未保存" in window.match_mode_panel.record_status_var.get()


def test_record_dirty_true_after_undo(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0
    window._apply_selected_move()
    window._undo_move()

    assert window._record_dirty is True


def test_record_dirty_false_after_reset(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0
    window._apply_selected_move()
    window._reset_game()

    assert window._record_dirty is False


def test_phase_starts_in_awaiting_dice(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert window._awaiting_dice is True
    assert "录入骰子" in window.match_mode_panel.phase_var.get()


def test_phase_after_dice_input_is_select(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._handle_dice_change("3")

    assert window._awaiting_dice is False
    assert "走法" in window.match_mode_panel.phase_var.get() or "选择" in window.match_mode_panel.phase_var.get()


def test_phase_returns_to_awaiting_dice_after_apply(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._handle_dice_change("6")

    moves = window._current_moves()
    window.selected_move_index = 0
    window._apply_selected_move()

    assert window._awaiting_dice is True
    assert "录入骰子" in window.match_mode_panel.phase_var.get()


def test_phase_returns_to_awaiting_dice_after_reset(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._handle_dice_change("6")
    moves = window._current_moves()
    window.selected_move_index = 0
    window._apply_selected_move()

    window._reset_game()

    assert window._awaiting_dice is True


def test_main_window_uses_default_total_seconds(tk_root):
    window = MainWindow(tk_root)

    assert window.timer.total_seconds == 240.0


def test_main_window_accepts_custom_total_seconds(tk_root):
    window = MainWindow(tk_root, total_seconds=600.0)

    assert window.timer.total_seconds == 600.0


def test_parse_args_default_total_seconds():
    from gui.app import parse_args

    args = parse_args([])

    assert args.total_seconds == 240.0


def test_parse_args_custom_total_seconds():
    from gui.app import parse_args

    args = parse_args(["--total-seconds", "600"])

    assert args.total_seconds == 600.0


def test_default_mode_is_debug(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert window._mode == "debug"
    assert window._our_side is None


def test_set_mode_to_match_with_red_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._set_mode("match", our_side=Player.RED)

    assert window._mode == "match"
    assert window._our_side is Player.RED


def test_set_mode_to_match_with_blue_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._set_mode("match", our_side=Player.BLUE)

    assert window._our_side is Player.BLUE


def test_set_mode_back_to_debug_clears_our_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)

    window._set_mode("debug")

    assert window._mode == "debug"
    assert window._our_side is None


def test_main_window_creates_menu_with_mode_cascade(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    menubar_name = tk_root["menu"]
    assert menubar_name, "expected menubar attached to toplevel"
    menubar = tk_root.nametowidget(menubar_name)
    # `index("模式")` returns the integer position; raises TclError if missing.
    assert menubar.index("模式") is not None


def test_pick_side_dialog_returns_red_when_red_chosen(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()

    monkeypatch.setattr(window, "_show_pick_side_dialog", lambda: Player.RED)
    window._enter_match_mode()

    assert window._mode == "match"
    assert window._our_side is Player.RED


def test_pick_side_dialog_cancel_keeps_debug_mode(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()

    monkeypatch.setattr(window, "_show_pick_side_dialog", lambda: None)
    window._enter_match_mode()

    assert window._mode == "debug"
    assert window._our_side is None


def test_phase_in_match_my_turn_awaiting_dice(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)

    assert window._awaiting_dice is True
    assert "请录入骰子" in window.match_mode_panel.phase_var.get()
    assert "等待对方" not in window.match_mode_panel.phase_var.get()


def test_phase_in_match_opponent_turn_awaiting_dice(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)

    assert window.state.current_player is Player.RED
    assert "等待对方" in window.match_mode_panel.phase_var.get()
    assert "骰子" in window.match_mode_panel.phase_var.get()


def test_phase_in_match_opponent_turn_after_dice_input(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)
    window._handle_dice_change("3")

    assert "等待对方" in window.match_mode_panel.phase_var.get()
    assert "走法" in window.match_mode_panel.phase_var.get()


def test_phase_in_debug_mode_does_not_use_opponent_text(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "等待对方" not in window.match_mode_panel.phase_var.get()


def test_apply_move_records_source_self_in_match_mode_my_turn(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)
    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "self"


def test_apply_move_records_source_opponent_in_match_mode_opponent_turn(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)
    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "opponent"


def test_apply_move_records_source_unknown_in_debug_mode(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "unknown"


def test_main_window_has_match_mode_panel(tk_root):
    from gui.match_mode import MatchModePanel

    window = MainWindow(tk_root)
    window.pack()

    assert hasattr(window, "match_mode_panel")
    assert isinstance(window.match_mode_panel, MatchModePanel)


def test_match_mode_panel_displays_current_player(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "红方" in window.match_mode_panel.current_player_var.get()


def test_match_mode_panel_displays_phase(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "请录入骰子" in window.match_mode_panel.phase_var.get()


def test_match_mode_panel_displays_record_status(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "已保存" in window.match_mode_panel.record_status_var.get()


def test_match_mode_panel_waits_for_dice_before_showing_recommendation(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "等待骰子" in window.match_mode_panel.recommendation_var.get()


def test_match_mode_panel_displays_greedy_recommendation_after_dice_input(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._handle_dice_change("6")

    recommendation = window.match_mode_panel.recommendation_var.get()
    assert "greedy_risk" in recommendation
    assert "红方 6:" in recommendation
    assert "->" in recommendation
    assert "未启用" not in recommendation


def test_match_mode_panel_record_status_changes_on_apply(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    moves = window._current_moves()
    assert moves
    window.selected_move_index = 0
    window._apply_selected_move()

    assert "未保存" in window.match_mode_panel.record_status_var.get()


def test_remaining_seconds_from_record_returns_last_step_data(tk_root):
    from record.game_record import GameRecord

    window = MainWindow(tk_root)
    window.pack()
    state = window.state
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)
    record.append(
        dice=6,
        move=move,
        state_after=state,
        remaining_seconds={Player.RED: 200.0, Player.BLUE: 240.0},
    )

    result = window._remaining_seconds_from_record(record)

    assert result == {Player.RED: 200.0, Player.BLUE: 240.0}


def test_remaining_seconds_from_record_returns_none_for_empty_record(tk_root):
    from record.game_record import GameRecord

    window = MainWindow(tk_root)
    window.pack()
    record = GameRecord.from_state(window.state)

    assert window._remaining_seconds_from_record(record) is None


def test_save_then_load_round_trip_restores_timer_remaining(tk_root, tmp_path):
    from record.game_record import GameRecord
    from gui.app import create_default_state

    # 制作含计时数据的棋谱并保存到磁盘
    state = create_default_state()
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)
    record.append(
        dice=6,
        move=move,
        state_after=state,
        step_seconds=15.0,
        remaining_seconds={Player.RED: 225.0, Player.BLUE: 240.0},
    )
    path = tmp_path / "test_record.json"
    record.save(path)

    # 模拟 _load_record 关键路径（绕过 filedialog）
    window = MainWindow(tk_root)
    window.pack()
    loaded = GameRecord.load(path)
    window.record = loaded
    window.state = loaded.restore_state()
    window.timer.reset(
        current_player=window.state.current_player,
        remaining_seconds=window._remaining_seconds_from_record(window.record),
    )

    snapshot = window.timer.snapshot()
    assert snapshot.remaining_seconds[Player.RED] == 225.0
    assert snapshot.remaining_seconds[Player.BLUE] == 240.0
