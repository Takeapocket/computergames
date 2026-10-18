from __future__ import annotations

import gc
import json
import threading
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from core.game_state import GameState
from core.types import Player, Position
from gui.app import create_default_state
from gui.main_window import MainWindow
from record.auto_save import auto_save, auto_save_match, load_auto_save, load_auto_save_match
from record.game_record import GameRecord
from record.match_record import MatchRecord
from tests.tk_support import make_hidden_tk_root


def _wait_until(predicate, *, root=None, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if root is not None:
            root.update()
        if predicate():
            return
    pytest.fail("asynchronous operation did not reach the expected state")


@pytest.fixture
def windows(tmp_path, monkeypatch):
    root = tk.Toplevel(make_hidden_tk_root())
    root.withdraw()
    created = []
    monkeypatch.setattr("gui.main_window.AUTO_SAVE_PATH", tmp_path / "auto_save.json")
    monkeypatch.setattr("gui.main_window.AUTO_SAVE_MATCH_PATH", tmp_path / "auto_save_match.json")
    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr("gui.main_window.messagebox.showerror", lambda *args, **kwargs: None)

    def create(**kwargs):
        window = MainWindow(root, **kwargs)
        window.pack()
        created.append(window)
        return window

    yield create
    for window in created:
        if window.winfo_exists():
            window.destroy()
    root.destroy()
    created.clear()
    gc.collect()


def _install_match(window, *, total_seconds=240.0, auto_timeout_enabled=False):
    window._match = MatchRecord(our_side=Player.RED, our_role="甲", time_limit_seconds=total_seconds, auto_timeout_enabled=auto_timeout_enabled)
    window._match.start_playing()
    window._mode = "match"
    window._our_side = Player.RED
    window._phase = "playing"
    window.record.metadata.update(_metadata(window._match))
    window._show_playing_phase()
    assert window._auto_save_current_match()
    assert window._auto_save_current_game()


def _metadata(match):
    return {"match_id": match.match_id, "game_index": match.current_game_index, "our_side": match.our_side.value, "our_role": match.our_role, "first_mover_color": match.first_mover_color(match.current_game_index).value, "time_limit_seconds": match.time_limit_seconds, "auto_timeout_enabled": match.auto_timeout_enabled}


def _write_pair(tmp_path, record, *, timeout=False, match=None):
    match = match or MatchRecord(our_side=Player.RED, our_role="甲")
    match.start_playing()
    record.metadata.update(_metadata(match))
    state = record.restore_state()
    timer = SimpleNamespace(current_player=state.current_player, remaining_seconds={Player.RED: 0.0 if timeout else 230.0, Player.BLUE: 240.0}, paused=True)
    auto_save_match(match, path=tmp_path / "auto_save_match.json")
    auto_save(record, timer, path=tmp_path / "auto_save.json")
    return match


def test_gui_ignores_old_result_and_stays_responsive_while_ai_runs(windows):
    started, release = threading.Event(), threading.Event()
    calls = []

    def choose(state, dice):
        calls.append(dice)
        if dice == 6:
            started.set()
            assert release.wait(5)
        return state.legal_moves(state.current_player, dice)[0]

    window = windows()
    window._recommender = SimpleNamespace(choose_move=choose)
    window._phase = "playing"
    before = window.state.serialize()
    try:
        window._handle_dice_change("6")
        assert started.wait(2)
        heartbeat = []
        window.after(0, lambda: heartbeat.append(True))
        window.winfo_toplevel().update()
        assert heartbeat == [True]
        assert "计算中" in window.match_mode_panel.recommendation_var.get()
        window._handle_dice_change("5")
        release.set()
        _wait_until(lambda: window._recommendation_cache_key == window._recommendation_key(), root=window.winfo_toplevel())
        assert calls == [6, 5]
        assert window._recommendation_cache_move in window.state.legal_moves(Player.RED, 5)
        assert window.state.serialize() == before
        assert window.record.steps == []
    finally:
        release.set()


def test_destroy_with_running_worker_cancels_tk_callbacks(windows):
    started, release = threading.Event(), threading.Event()

    def choose(state, dice):
        started.set()
        assert release.wait(5)
        return state.legal_moves(state.current_player, dice)[0]

    window = windows()
    window._recommender = SimpleNamespace(choose_move=choose)
    window._phase = "playing"
    window._handle_dice_change("6")
    assert started.wait(2)
    callbacks = (window._timer_after_id, window._recommendation_after_id)
    worker = window._recommendation_worker
    window.destroy()
    release.set()
    worker._thread.join(timeout=2)
    assert not worker._thread.is_alive()
    assert worker.drain() == []
    pending = str(window.master.tk.call("after", "info"))
    assert all(callback not in pending for callback in callbacks)
    window.master.update()


@pytest.mark.parametrize("winning_score", [0, 3])
def test_match_save_failure_keeps_recovery_and_retry_scores_once(windows, monkeypatch, winning_score):
    window = windows()
    _install_match(window)
    if winning_score:
        for _ in range(winning_score):
            game = GameRecord.from_state(create_default_state())
            window._match.append_finished_game(game, "them")
        window._match.start_playing()
        window.record.metadata.update(_metadata(window._match))
    import gui.main_window as module
    original_save = module.auto_save_match
    transitions = []
    monkeypatch.setattr(window, "_show_round_finished_dialog", lambda: transitions.append("round"))
    monkeypatch.setattr(window, "_show_match_finished_dialog", lambda: transitions.append("finished"))
    monkeypatch.setattr(module, "auto_save_match", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))
    window.timer.reset(current_player=Player.RED, remaining_seconds={Player.RED: 0.0, Player.BLUE: 240.0})
    window._finalize_match_game(Player.BLUE, reason="timeout")
    assert window._finalization_pending
    assert window._auto_save_path.exists()
    assert transitions == []
    assert not window._can_select_moves()
    assert not window._can_undo_move()
    assert window.controls.save_button.cget("text") == "重试保存"
    saved, _ = load_auto_save(path=window._auto_save_path)
    assert saved.result["reason"] == "timeout"
    window._save_record()
    assert window._match.games_won_them == winning_score + 1
    assert len(window._match.games) == winning_score + 1
    monkeypatch.setattr(module, "auto_save_match", original_save)
    window._save_record()
    assert not window._finalization_pending
    assert not window._auto_save_path.exists()
    assert window._match.games_won_them == winning_score + 1
    assert len(window._match.games) == winning_score + 1
    assert transitions == (["finished"] if winning_score == 3 else ["round"])


@pytest.mark.parametrize("failed_save", ["auto_save_match", "auto_save"])
def test_opening_confirmation_preserves_autosave_failure_notice(windows, monkeypatch, failed_save):
    window = windows()
    window._match = MatchRecord(our_side=Player.RED, our_role="甲")
    window._mode = "match"
    window._our_side = Player.RED

    def fail_save(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(f"gui.main_window.{failed_save}", fail_save)
    from ai.opening_layouts import BLUE_ZONE

    for piece_id, position in enumerate(sorted(BLUE_ZONE, key=lambda pos: (pos.row, pos.col)), start=1):
        window.opening_panel.set_selected_piece(piece_id)
        window.opening_panel.handle_board_click(position)
    window.opening_panel.confirm()

    assert window._phase == "playing"
    assert "自动保存失败" in window.status_message
    assert "disk full" in window.status_message
    if failed_save == "auto_save_match":
        assert window._auto_save_path.exists()
    else:
        assert window._auto_save_match_path.exists()


def test_loading_single_game_after_finished_match_unlocks_controls(windows, monkeypatch, tmp_path):
    window = windows()
    window._match = MatchRecord(our_side=Player.RED, our_role="甲", games_won_us=4, current_game_index=4, phase="finished")
    path = tmp_path / "loaded.json"
    GameRecord.from_state(create_default_state()).save(path)
    monkeypatch.setattr("gui.main_window.filedialog.askopenfilename", lambda **kwargs: str(path))
    window._load_record()
    assert window._match is None
    assert window._phase == "playing"
    assert window._can_enter_dice()
    assert window.controls.dice_spinbox.cget("state") == tk.NORMAL


@pytest.mark.parametrize("timeout", [False, True])
def test_restart_recovers_uncommitted_terminal_or_timeout_score_once(windows, tmp_path, timeout):
    if timeout:
        record = GameRecord.from_state(create_default_state())
        record.result = {"winner": "blue", "winner_side": "them", "reason": "timeout", "game_index": 1}
    else:
        state = GameState.from_layout(red={1: Position(3, 3)}, blue={1: Position(4, 0)})
        record = GameRecord.from_state(state)
        move = next(move for move in state.legal_moves(Player.RED, 1) if move.to_pos == Position(4, 4))
        applied = state.apply_move(move, dice=1)
        record.append(dice=1, move=applied, state_after=state)
    _write_pair(tmp_path, record, timeout=timeout)
    window = windows()
    assert window._match is not None
    assert (window._match.games_won_us, window._match.games_won_them) == ((0, 1) if timeout else (1, 0))
    assert window._match.current_game_index == 2
    assert window._phase == "setup"
    saved = load_auto_save_match(path=window._auto_save_match_path)
    assert len(saved.games) == 1
    assert saved.games[0].result["reason"] == ("timeout" if timeout else "target_corner")
    assert not window._auto_save_path.exists()


def test_restart_rejects_conflicting_timer_side_without_deleting_files(windows, tmp_path):
    record = GameRecord.from_state(create_default_state())
    _write_pair(tmp_path, record)
    record.metadata.update(load_auto_save(path=tmp_path / "auto_save.json")[0].metadata)
    auto_save(record, SimpleNamespace(current_player=Player.BLUE, remaining_seconds={Player.RED: 230.0, Player.BLUE: 240.0}, paused=True), path=tmp_path / "auto_save.json")
    originals = {name: (tmp_path / name).read_bytes() for name in ("auto_save.json", "auto_save_match.json")}
    window = windows()
    assert window._match is None
    assert window._phase == "setup"
    assert {name: (tmp_path / name).read_bytes() for name in originals} == originals


def test_restart_between_games_restores_match_timer_options(windows, tmp_path):
    match = MatchRecord(our_side=Player.RED, our_role="甲", time_limit_seconds=600.0, auto_timeout_enabled=True)
    match.append_finished_game(GameRecord.from_state(create_default_state()), "us")
    auto_save_match(match, path=tmp_path / "auto_save_match.json")
    window = windows()
    assert window._match.current_game_index == 2
    assert window._phase == "setup"
    assert window._total_seconds == 600.0
    assert window.timer.total_seconds == 600.0
    assert window._auto_timeout_enabled is True


def test_legacy_active_match_adopts_single_game_timer_options_and_resaves(windows, tmp_path):
    record = GameRecord.from_state(create_default_state())
    _write_pair(tmp_path, record)
    match_path = tmp_path / "auto_save_match.json"
    legacy = json.loads(match_path.read_text(encoding="utf-8"))
    legacy.pop("time_limit_seconds")
    legacy.pop("auto_timeout_enabled")
    match_path.write_text(json.dumps(legacy), encoding="utf-8")
    record.metadata.update({"time_limit_seconds": 600.0, "auto_timeout_enabled": True})
    auto_save(
        record,
        SimpleNamespace(current_player=Player.RED, remaining_seconds={Player.RED: 590.0, Player.BLUE: 600.0}, paused=True),
        path=tmp_path / "auto_save.json",
    )

    window = windows()

    assert window._match is not None
    assert window._phase == "playing"
    assert window._total_seconds == 600.0
    assert window.timer.total_seconds == 600.0
    assert window._auto_timeout_enabled is True
    restored = load_auto_save_match(path=match_path)
    assert restored.time_limit_seconds == 600.0
    assert restored.auto_timeout_enabled is True


def test_loaded_record_cannot_undo_before_its_initial_snapshot(windows, monkeypatch, tmp_path):
    state = create_default_state()
    state.apply_move(state.legal_moves(Player.RED, 6)[0], dice=6)
    record = GameRecord.from_state(state)
    assert record.steps == []
    assert state.history
    path = tmp_path / "snapshot.json"
    record.save(path)
    window = windows()
    monkeypatch.setattr("gui.main_window.filedialog.askopenfilename", lambda **kwargs: str(path))
    window._load_record()
    before = window.state.serialize()
    assert not window._can_undo_move()
    window._undo_move()
    assert window.state.serialize() == before
    assert window.record.steps == []


def test_loaded_other_rules_record_cannot_continue_or_mutate_progress(windows, monkeypatch, tmp_path):
    state = GameState.from_layout(
        red={3: Position(0, 0), 6: Position(4, 3)},
        blue={1: Position(3, 3)},
    )
    record = GameRecord.from_state(state)
    record.metadata["rules_version"] = "legacy-absolute-nearest-v1"
    path = tmp_path / "other-rules.json"
    record.save(path)
    saved_bytes = path.read_bytes()
    window = windows()
    window._recommender = SimpleNamespace(
        choose_move=lambda state, dice: state.legal_moves(state.current_player, dice)[0],
    )
    monkeypatch.setattr("gui.main_window.filedialog.askopenfilename", lambda **kwargs: str(path))
    window._load_record()
    window.timer.pause()
    window._handle_dice_change("4")
    window.selected_move_index = next(
        index for index, move in enumerate(window._current_moves()) if move.piece_id == 6
    )
    before_state = window.state.serialize()
    before_record = window.record.to_dict()
    before_timer = window.timer.snapshot()

    window._apply_selected_move()

    assert "无法继续对局" in window.status_message
    assert window.state.serialize() == before_state
    assert window.record.to_dict() == before_record
    assert window.timer.snapshot() == before_timer
    assert not window._record_dirty
    assert not window._awaiting_dice
    assert path.read_bytes() == saved_bytes
    assert not window._auto_save_path.exists()
