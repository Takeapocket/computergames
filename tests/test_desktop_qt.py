"""Qt preview behavior; the original development environment may omit Qt."""
from __future__ import annotations

import os
from pathlib import Path
from threading import Event
from time import monotonic

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QMessageBox

from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from core.types import Player, Position
from desktop_qt.board import move_label, position_label
from desktop_qt.session import GameSession
from desktop_qt.match_session import MatchSession
from desktop_qt.dialogs import NewMatchDialog, OpeningDialog
from ai.opening_layouts import PRESETS
from desktop_qt.window import PrototypeWindow
from gui.recommendation_worker import RecommendationResult


class FirstLegalAI:
    def choose_move(self, state, dice):
        return state.legal_moves(state.current_player, dice)[0]


class ControlledWorker:
    def __init__(self):
        self.requests = []
        self.results = []
        self.closed = False

    def submit(self, request):
        self.requests.append(request)

    def invalidate(self):
        pass

    def drain(self):
        results, self.results = self.results, []
        return results

    def close(self):
        self.closed = True

    def complete(self, request, *, generation=None):
        move = request.state.legal_moves(request.state.current_player, request.dice)[0]
        self.results.append(RecommendationResult(
            request.generation if generation is None else generation, request.key, move, "rollout"))


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def make_window(application, tmp_path, monkeypatch):
    windows = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Discard)

    def create(**kwargs):
        kwargs.setdefault("recommender", FirstLegalAI())
        kwargs.setdefault("fallback", FirstLegalAI())
        window = PrototypeWindow(data_dir=tmp_path, **kwargs)
        windows.append(window)
        return window

    yield create
    for window in windows:
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


def test_dice_board_input_and_history_use_core_rules(make_window, application):
    window = make_window()
    assert not window.execute_button.isEnabled()
    window.set_dice(3)
    assert window.move_combo.count() == 3
    expected = window.session.legal_moves()[0]
    window.show()
    application.processEvents()
    point = window.board.cell_rect(expected.to_pos).center().toPoint()
    QTest.mouseClick(window.board, Qt.MouseButton.LeftButton, pos=point)
    assert window.session.record.steps[-1].move == expected
    assert window.history_table.rowCount() == 1
    assert window.session.state.current_player is Player.BLUE
    assert not window.execute_button.isEnabled()
    assert window.session.dice is None
    assert window.session.dirty


def test_stale_dice_result_cannot_be_applied_even_when_dice_changes_back(make_window):
    worker = ControlledWorker()
    window = make_window(worker=worker)
    window.set_dice(3)
    window.request_recommendation()
    old_request = worker.requests[-1]
    assert window.recommendation_pending
    assert window.execute_button.isEnabled()
    window.set_dice(4)
    window.set_dice(3)
    worker.complete(old_request)
    window._poll_recommendation()
    assert window.recommended_move is None
    assert not window.recommendation_pending
    window.apply_recommendation()
    assert not window.session.record.steps


def test_result_generation_and_revision_are_both_checked(make_window):
    worker = ControlledWorker()
    window = make_window(worker=worker)
    window.set_dice(3)
    window.request_recommendation()
    request = worker.requests[-1]
    worker.complete(request, generation=request.generation - 1)
    window._poll_recommendation()
    assert window.recommendation_pending
    assert window.recommended_move is None
    worker.complete(request)
    window._poll_recommendation()
    assert not window.recommendation_pending
    assert window.recommended_move is not None
    window.apply_recommendation()
    assert len(window.session.record.steps) == 1
    assert window.recommended_move is None
    window.undo()
    assert not window.session.record.steps
    assert window.recommended_move is None


def test_external_session_update_is_invalidated_by_refresh(make_window):
    worker = ControlledWorker()
    window = make_window(worker=worker)
    window.set_dice(3)
    window.request_recommendation()
    request = worker.requests[-1]
    worker.complete(request)
    window._poll_recommendation()
    window.session.set_dice(4)
    assert window.recommended_move is None
    window.refresh_view()
    assert window.board.recommendation is None
    assert window.dice_buttons[3].isChecked()


def test_save_load_compatibility_and_new_game_keep_current_default(make_window, tmp_path):
    window = make_window()
    window.set_dice(3)
    window.execute_selected_move()
    expected = window.session.state.serialize()
    path = tmp_path / "中文棋谱.json"
    assert window.save_record(path)
    assert not window.session.dirty
    window.new_game()
    assert window.load_record(path)
    assert window.session.state.serialize() == expected
    assert window.history_table.rowCount() == 1
    assert window.record_path == path
    assert not window.session.dirty


def test_failed_save_keeps_dirty_record_and_visible_error(make_window, monkeypatch, tmp_path):
    window = make_window()
    window.set_dice(3)
    window.execute_selected_move()
    before = window.session.state.serialize()

    def fail(path):
        raise OSError("disk unavailable")

    monkeypatch.setattr(window.session, "save", fail)
    assert not window.save_record(tmp_path / "fail.json")
    assert window.session.dirty
    assert window.session.state.serialize() == before
    assert "disk unavailable" in window.status_label.text()
    assert window.record_path is None


def test_failed_load_keeps_current_record_and_recommendation(make_window, tmp_path):
    worker = ControlledWorker()
    window = make_window(worker=worker)
    window.set_dice(3)
    window.request_recommendation()
    worker.complete(worker.requests[-1])
    window._poll_recommendation()
    recommended = window.recommended_move
    before = window.session.state.serialize()
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")
    assert not window.load_record(path)
    assert window.session.state.serialize() == before
    assert window.recommended_move == recommended
    assert "棋谱打开失败" in window.status_label.text()


def test_cancel_close_keeps_worker_alive_and_discard_closes_it(make_window, monkeypatch):
    worker = ControlledWorker()
    window = make_window(worker=worker)
    window.set_dice(3)
    window.execute_selected_move()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert not worker.closed
    assert not window._closed
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Discard)
    assert window.close()
    assert worker.closed


def test_real_worker_delivers_result_without_touching_widgets(make_window, application):
    window = make_window()
    window.set_dice(3)
    window.request_recommendation()
    deadline = monotonic() + 3
    while window.recommendation_pending and monotonic() < deadline:
        application.processEvents()
        QTest.qWait(10)
    assert not window.recommendation_pending
    assert window.recommended_move in window.session.legal_moves()
    assert window.apply_button.isEnabled()


def test_close_does_not_wait_for_running_ai(make_window, application):
    started = Event()
    finish = Event()

    class SlowAI:
        def choose_move(self, state, dice):
            started.set()
            finish.wait(3)
            return state.legal_moves(state.current_player, dice)[0]

    window = make_window(recommender=SlowAI())
    window.set_dice(3)
    window.request_recommendation()
    assert started.wait(1)
    try:
        start = monotonic()
        assert window.close()
        assert monotonic() - start < .5
        application.processEvents()
    finally:
        finish.set()


def test_default_p14_constructor_receives_release_parameters(application, tmp_path, monkeypatch):
    seen = []

    def factory(kind, **kwargs):
        seen.append((kind, kwargs))
        return FirstLegalAI()

    monkeypatch.setattr("desktop_qt.window.build_ai", factory)
    window = PrototypeWindow(data_dir=tmp_path)
    try:
        assert seen == [("rollout", {"seed": 0, **RELEASE_DEFAULT_ROLLOUT_KWARGS}), ("greedy_risk", {"seed": 0})]
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_old_rules_record_displays_but_disables_continuation(make_window, tmp_path):
    import json

    session = GameSession()
    payload = session.record.to_dict()
    payload["metadata"]["rules_version"] = "historical-rules"
    path = tmp_path / "historical.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    window = make_window()
    assert window.load_record(path)
    assert window.session.continuation_error
    assert not window.roll_button.isEnabled()
    assert not window.recommend_button.isEnabled()
    assert not window.execute_button.isEnabled()
    assert all(not button.isEnabled() for button in window.dice_buttons)


def test_recorded_timeout_displays_finished_without_claiming_old_rules(make_window, tmp_path):
    session = GameSession()
    session.record.result = {"winner": "blue", "reason": "timeout", "game_index": 1}
    path = tmp_path / "timeout.json"
    session.record.save(path)
    window = make_window()
    assert window.load_record(path)
    assert window.session.state.get_winner() is None
    assert window.turn_label.text() == "本盘已结束"
    assert window.step_label.text() == "本盘结束"
    assert "只读棋谱" in window.status_label.text()
    assert "历史规则" not in window.status_label.text()
    assert not window.roll_button.isEnabled()
    assert not window.recommend_button.isEnabled()


def test_display_coordinates_do_not_change_core_positions():
    session = GameSession()
    session.set_dice(3)
    move = session.legal_moves()[0]
    assert position_label(Position(0, 2)) == "C1"
    assert "C1" in move_label(move)
    assert move.from_pos == Position(0, 2)


@pytest.mark.parametrize("width,height", [(1020, 700), (800, 500)])
def test_small_window_can_scroll_to_controls_and_record(make_window, application, width, height):
    window = make_window()
    window.resize(width, height)
    window.set_dice(3)
    window.execute_selected_move()
    window.show()
    application.processEvents()
    assert window.width() == width
    assert window.height() == height
    scroll = window.content_scroll
    assert scroll.verticalScrollBar().maximum() > 0
    if width == 1020:
        assert scroll.horizontalScrollBar().maximum() == 0
    # Both the right-side actions and the bottom record remain reachable.
    for widget in (window.recommend_button, window.history_table, window.status_label, window.save_button):
        scroll.ensureWidgetVisible(widget)
        application.processEvents()
        center = widget.mapTo(scroll.viewport(), widget.rect().center())
        assert scroll.viewport().rect().contains(center)


def test_match_setup_blocks_dice_moves_and_recommendation(make_window, tmp_path):
    worker = ControlledWorker()
    session = MatchSession(tmp_path)
    window = make_window(session=session, worker=worker)
    assert window.setup_button.isEnabled()
    assert not window.dice_buttons[0].isEnabled()
    assert not window.recommend_button.isEnabled()
    assert not window.execute_button.isEnabled()
    window.request_recommendation()
    assert not worker.requests
    assert "开局" in window.turn_label.text()
    assert "04:00" in window.red_clock_label.text()


def test_opening_dialog_rejects_duplicate_ids_and_roundtrips_layout(application, tmp_path):
    dialog = OpeningDialog(tmp_path / "layouts")
    original = dialog.layouts()
    spins = list(dialog.cells[Player.RED].values())
    spins[0].setValue(spins[1].value())
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert not dialog.save_button.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.set_layout(PRESETS["aggressive_v1"].red, PRESETS["defensive_v1"].blue)
    expected = dialog.layouts()
    dialog._save_layout()
    files = list((tmp_path / "layouts").glob("*.json"))
    assert len(files) == 1
    dialog.set_layout(*original)
    assert dialog.load_file(files[0])
    assert dialog.layouts() == expected
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.deleteLater()


def test_new_match_dialog_defaults_keep_four_minutes_manual_timeout(application):
    dialog = NewMatchDialog()
    values = dialog.options()
    assert values["total_seconds"] == 240
    assert not values["auto_timeout_enabled"]
    assert values["mode"] == "single"
    assert not dialog.role_combo.isEnabled()
    dialog.mode_combo.setCurrentIndex(1)
    assert dialog.role_combo.isEnabled()
    assert dialog.options()["our_role"] == "甲"
    dialog.deleteLater()


def test_new_match_and_opening_dialog_use_role_color_and_selected_layout(make_window, tmp_path, monkeypatch):
    session = MatchSession(tmp_path)
    window = make_window(session=session)

    def choose_match(dialog):
        dialog.mode_combo.setCurrentIndex(1)
        dialog.side_combo.setCurrentIndex(1)
        dialog.role_combo.setCurrentText("甲")
        return QDialog.DialogCode.Accepted

    def choose_opening(dialog):
        assert not dialog.first_combo.isEnabled()
        assert Player.from_value(dialog.first_combo.currentData()) is Player.BLUE
        dialog.set_layout(PRESETS["aggressive_v1"].red, PRESETS["defensive_v1"].blue)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(NewMatchDialog, "exec", choose_match)
    monkeypatch.setattr(OpeningDialog, "exec", choose_opening)
    window.new_game()
    assert session.phase == "playing"
    assert session.state.current_player is Player.BLUE
    assert session.match.our_side is Player.BLUE
    assert session.match.our_role == "甲"
    assert session.state.pieces[Player.RED][1].position == PRESETS["aggressive_v1"].red[1]
    assert window.pause_button.isEnabled()
    assert "0 : 0" in window.match_label.text()
    assert "蓝方先手" in window.flow_hint.text()


def test_pause_stops_clock_keeps_legacy_input_and_invalidates_worker(make_window, tmp_path):
    seconds = [0.0]
    session = MatchSession(tmp_path, now=lambda: seconds[0])
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    worker = ControlledWorker()
    window = make_window(session=session, worker=worker)
    window.set_dice(3)
    window.request_recommendation()
    request = worker.requests[-1]
    seconds[0] = 2.5
    window.toggle_pause()
    seconds[0] = 12.5
    window._refresh_clock()
    assert session.timer.snapshot().remaining_seconds[Player.RED] == 237.5
    assert window.recommend_button.isEnabled()
    assert window.execute_button.isEnabled()
    worker.complete(request)
    window._poll_recommendation()
    assert window.recommended_move is None
    window.toggle_pause()
    assert window.dice_buttons[0].isEnabled()
    assert session.timer.snapshot().remaining_seconds[Player.RED] == 237.5


def test_manual_timeout_confirmation_and_next_game_flow(make_window, tmp_path, monkeypatch):
    seconds = [0.0]
    session = MatchSession(tmp_path, now=lambda: seconds[0])
    session.start_match(our_side=Player.RED, our_role="甲", total_seconds=1)
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    window = make_window(session=session)
    seconds[0] = 2
    window._refresh_clock()
    assert session.phase == "playing"
    assert window.timeout_button.isEnabled()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Cancel)
    window.confirm_timeout()
    assert session.phase == "playing"
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes)
    window.confirm_timeout()
    assert session.phase == "finished"
    assert session.match.games_won_them == 1
    assert window.next_game_button.isEnabled()
    monkeypatch.setattr(OpeningDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window.next_game()
    assert session.phase == "setup"
    assert session.match.current_game_index == 2
    assert session.state.current_player is Player.BLUE
    assert window.setup_button.isEnabled()
    assert not window.recommend_button.isEnabled()


def test_auto_timeout_timer_refresh_ends_game_and_discards_recommendation(make_window, tmp_path):
    seconds = [0.0]
    session = MatchSession(tmp_path, now=lambda: seconds[0])
    session.start_single(total_seconds=1, auto_timeout_enabled=True)
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    worker = ControlledWorker()
    window = make_window(session=session, worker=worker)
    window.set_dice(1)
    window.request_recommendation()
    request = worker.requests[-1]
    seconds[0] = 2
    window._refresh_clock()
    worker.complete(request)
    window._poll_recommendation()
    assert session.phase == "finished"
    assert window.recommended_move is None
    assert not window.execute_button.isEnabled()
    assert not window.undo_button.isEnabled()


def test_save_failure_remains_visible_until_retry(make_window, tmp_path, monkeypatch):
    import desktop_qt.match_session as module
    session = MatchSession(tmp_path)
    session.start_match()
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    window = make_window(session=session)
    original = module.auto_save

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(module, "auto_save", fail)
    window.set_dice(3)
    window.execute_selected_move()
    assert "disk full" in window.save_error_label.text()
    assert not window.retry_save_button.isHidden()
    window._status("其他状态消息")
    window._refresh_clock()
    assert "disk full" in window.save_error_label.text()
    monkeypatch.setattr(module, "auto_save", original)
    window.retry_save()
    assert session.save_error is None
    assert window.retry_save_button.isHidden()


def test_existing_recovery_cancel_new_or_close_preserves_file(make_window, tmp_path, monkeypatch):
    previous = MatchSession(tmp_path)
    previous.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    before = previous.auto_save_path.read_bytes()
    session = MatchSession(tmp_path)
    window = make_window(session=session)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Cancel)
    window.new_game()
    assert not session.has_started
    assert previous.auto_save_path.read_bytes() == before
    assert window.close()
    assert previous.auto_save_path.read_bytes() == before


def test_recovery_restore_and_corruption_preserve_current_state(make_window, tmp_path, monkeypatch):
    previous = MatchSession(tmp_path)
    previous.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    previous.set_dice(3)
    previous.apply_move(previous.legal_moves()[0])
    previous.toggle_pause()
    session = MatchSession(tmp_path)
    window = make_window(session=session)
    assert window.restore_recovery()
    assert session.state.serialize() == previous.state.serialize()
    assert session.timer.is_paused
    assert "暂停" in window.status_label.text()
    expected = session.state.serialize()
    previous.auto_save_path.write_text("{ broken", encoding="utf-8")
    damaged = previous.auto_save_path.read_bytes()
    assert not window.restore_recovery()
    assert session.state.serialize() == expected
    assert previous.auto_save_path.read_bytes() == damaged
    assert "保留" in window.status_label.text()


def test_match_export_does_not_claim_in_progress_game_is_included(make_window, tmp_path, monkeypatch):
    from record.match_record import MatchRecord
    session = MatchSession(tmp_path)
    session.start_match()
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    window = make_window(session=session)
    window.set_dice(3)
    window.execute_selected_move()
    path = tmp_path / "整轮.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), "JSON"))
    assert window._save_match_dialog()
    exported = MatchRecord.load(path)
    assert not exported.games
    assert "进行中本盘" in window.status_label.text()
    assert session.dirty


def test_match_opening_requires_opponent_reentry_and_preserves_winning_layout(application, tmp_path):
    dialog = OpeningDialog(tmp_path / "layouts", fixed_first=True, our_side=Player.BLUE,
                           retained_our_layout=PRESETS["defensive_v1"].blue)
    red, blue = dialog.layouts()
    assert red == {}
    assert blue == PRESETS["defensive_v1"].blue
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("balanced_v1"))
    assert dialog.layouts() == (PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "核对" in dialog.validation_label.text()
    dialog.deleteLater()


def test_initial_recovery_cancel_prompt_does_not_write_checkpoint(make_window, tmp_path, monkeypatch):
    previous = MatchSession(tmp_path)
    previous.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    before = previous.auto_save_path.read_bytes()
    session = MatchSession(tmp_path)
    window = make_window(session=session)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    window.offer_recovery()
    window._last_checkpoint = monotonic() - 3
    window._refresh_clock()
    assert previous.auto_save_path.read_bytes() == before
    assert not session.has_started
    assert window.close()
    assert previous.auto_save_path.read_bytes() == before


def test_match_setup_uses_selected_preset_after_loss(application, tmp_path):
    dialog = OpeningDialog(tmp_path / "layouts", fixed_first=True, our_side=Player.RED,
                           preset_id="aggressive_v1")
    assert dialog.layouts() == (PRESETS["aggressive_v1"].red, {})
    assert dialog.selected_preset_id == "aggressive_v1"
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.deleteLater()


def test_cancel_after_corrupt_startup_recovery_preserves_bytes(make_window, tmp_path, monkeypatch):
    path = tmp_path / "recovery" / "auto_save.json"
    path.parent.mkdir()
    path.write_text("{ broken", encoding="utf-8")
    before = path.read_bytes()
    session = MatchSession(tmp_path)
    window = make_window(session=session)
    assert not window.restore_recovery()
    assert not session.has_started
    assert window.close()
    assert path.read_bytes() == before


def test_close_requires_retry_for_unsaved_final_match_even_after_single_export(make_window, tmp_path, monkeypatch):
    import desktop_qt.match_session as module
    seconds = [0.0]
    session = MatchSession(tmp_path, now=lambda: seconds[0])
    session.start_match(total_seconds=1)
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    window = make_window(session=session)
    original = module.auto_save_match

    def fail(*args, **kwargs):
        raise OSError("match disk full")

    monkeypatch.setattr(module, "auto_save_match", fail)
    seconds[0] = 2
    session.forfeit_timeout(Player.RED)
    window.refresh_view()
    assert session.pending_finalize
    assert window.save_record(tmp_path / "本盘.json")
    assert not session.dirty
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert not window._closed
    assert session.pending_finalize
    assert "match disk full" in window.save_error_label.text()
    monkeypatch.setattr(module, "auto_save_match", original)
    assert window.close()
    assert not session.pending_finalize


def test_loaded_match_is_not_default_target_for_single_game_save(make_window, tmp_path):
    source = MatchSession(tmp_path / "source")
    source.start_match()
    target = tmp_path / "whole_match.json"
    source.save_match(target)
    before = target.read_bytes()
    session = MatchSession(tmp_path / "destination")
    window = make_window(session=session)
    assert window.load_record(target)
    assert window.record_path is None
    assert target.read_bytes() == before
    assert str(target) in window.status_label.text()


def test_both_clocks_expired_requires_referee_side_selection(make_window, tmp_path, monkeypatch):
    seconds = [0.0]
    session = MatchSession(tmp_path, now=lambda: seconds[0])
    session.start_single(total_seconds=1)
    session.confirm_opening(PRESETS["balanced_v1"].red, PRESETS["balanced_v1"].blue)
    window = make_window(session=session)
    seconds[0] = 2
    window.set_dice(3)
    window.execute_selected_move()
    seconds[0] = 4
    window._refresh_clock()
    assert set(session.timer.snapshot().timeout_players) == {Player.RED, Player.BLUE}
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("蓝方", False))
    window.confirm_timeout()
    assert session.phase == "playing"
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("蓝方", True))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes)
    window.confirm_timeout()
    assert session.phase == "finished"
    assert session.record.result["winner"] == Player.RED.value
    assert "蓝方超时负" in window.status_label.text()
