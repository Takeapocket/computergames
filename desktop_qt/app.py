"""Qt preview entry point, including an executable-level acceptance check."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time
import uuid

from desktop_qt.version import VERSION


def _self_test(application, window, report_path: Path, screenshot: Path | None) -> int:
    from ai.match import ai_version_signature
    from ai.release_defaults import DEFAULT_PARAMS_PATH, RELEASE_DEFAULT_ROLLOUT_KWARGS
    from core.rules import RULES_VERSION
    from record.game_record import GameRecord
    from PySide6.QtCore import QEvent, qVersion

    def fail_without_dialog(title, error):
        raise RuntimeError(f"{title}: {error}") from error

    window._show_error = fail_without_dialog
    report = {"version": VERSION, "frozen": bool(getattr(sys, "frozen", False)),
              "executable": sys.executable, "qt_version": qVersion(),
              "rules_version": RULES_VERSION, "p14_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
              "default_params_sha256": hashlib.sha256(DEFAULT_PARAMS_PATH.read_bytes()).hexdigest(),
              "checks": {}, "status": "failed"}
    try:
        if hasattr(window.session, "confirm_opening"):
            from ai.opening_layouts import PRESETS
            from core.types import Player
            window.session.start_match(our_side=Player.RED, our_role="甲")
            preset = PRESETS["balanced_v1"]
            window.session.confirm_opening(preset.red, preset.blue, layout_id="balanced_v1")
        initial = window.session.state.serialize()
        window.session.set_dice(3)
        window.refresh_view()
        window.request_recommendation()
        deadline = time.monotonic() + 20
        while window.recommendation_pending and time.monotonic() < deadline:
            application.processEvents()
            if application.property("self_test_error"):
                raise RuntimeError(application.property("self_test_error"))
            time.sleep(.01)
        if window.recommendation_pending or window.recommended_move is None:
            raise RuntimeError("P14 recommendation did not complete")
        if window.recommended_move not in window.session.legal_moves():
            raise RuntimeError("recommendation is not a legal core move")
        report["checks"]["legal_recommendation"] = True
        signature = ai_version_signature(window._recommender)
        expected = {"name": "rollout", "rules_version": RULES_VERSION, **RELEASE_DEFAULT_ROLLOUT_KWARGS}
        if any(signature.get(key) != value for key, value in expected.items()):
            raise RuntimeError("actual recommender signature differs from P14 defaults")
        report["actual_ai_signature"] = signature
        report["recommendation_source"] = window._recommendation.source
        report["internal_fallback"] = bool(window._recommender.last_used_fallback)
        if window._recommendation.source != "rollout":
            raise RuntimeError("primary P14 failed; worker returned an external fallback")
        report["checks"]["primary_p14_recommender"] = True
        report["checks"]["no_tk_import"] = "tkinter" not in sys.modules
        if screenshot is not None:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            application.processEvents()
            if not window.grab().save(str(screenshot), "PNG"):
                raise OSError("could not save screenshot")
            report["screenshot"] = str(screenshot)
        window.apply_recommendation()
        if len(window.session.record.steps) != 1:
            raise RuntimeError("recommendation was not applied exactly once")
        state_after = window.session.state.serialize()
        saved = window.data_dir / "records" / f"self-test-{uuid.uuid4().hex}.json"
        if not window.save_record(saved):
            raise OSError("GUI save failed")
        loaded = GameRecord.load(saved)
        if loaded.restore_state().serialize() != state_after:
            raise RuntimeError("legacy GameRecord reader disagrees with saved state")
        window.session.new_game()
        if not window.load_record(saved) or window.session.state.serialize() != state_after:
            raise RuntimeError("GUI load roundtrip failed")
        report["checks"]["record_roundtrip"] = True
        window.session.undo()
        if window.session.state.serialize() != initial:
            raise RuntimeError("undo did not restore starting position")
        report["checks"]["undo"] = True
        # Save the actual state so shutdown follows the ordinary clean-close path.
        if not window.save_record(saved.with_name(f"undo-{saved.name}")):
            raise OSError("post-undo save failed")
        if not report["checks"]["no_tk_import"]:
            raise RuntimeError("Qt application unexpectedly imported Tk")
        if hasattr(window.session, "confirm_opening"):
            from desktop_qt.acceptance import run_flow_acceptance
            report["flow_acceptance"] = run_flow_acceptance(window.data_dir)
            report["checks"]["complete_match_flow"] = True
        report["data_dir"] = str(window.data_dir)
        report["status"] = "passed"
    except Exception as exc:
        logging.exception("Desktop self-test failed")
        report["error"] = f"{type(exc).__name__}: {exc}"
        # A failed automated run must not hang on an unsaved-state dialog.
        window.session.dirty = False
    finally:
        if report["status"] == "passed":
            window.close()
        else:
            # Automation must report a failed save without waiting on close dialogs.
            # This branch is never used by the operator's normal close action.
            window._closed = True
            window._worker.close()
            window._poll_timer.stop()
            if hasattr(window, "_clock_timer"):
                window._clock_timer.stop()
            window.hide()
        window.deleteLater()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        application.processEvents()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    return 0 if report["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Einstein Chess desktop preview")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--self-test", type=Path, metavar="REPORT_JSON")
    parser.add_argument("--screenshot", type=Path, metavar="PNG")
    args = parser.parse_args(argv)
    if args.self_test and args.self_test.exists():
        parser.error("self-test report already exists; choose a new path")
    if args.self_test or args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEvent, QTimer, Qt
    from PySide6.QtGui import QFont, QFontDatabase, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox
    from desktop_qt.paths import resolve_data_dir
    from desktop_qt.window import PrototypeWindow
    from desktop_qt.match_session import MatchSession

    application = QApplication([sys.argv[0]])
    application.setApplicationName("EinsteinChessPreview")
    application.setApplicationVersion(VERSION)
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and sys.platform == "win32":
        # The generic offscreen plugin does not enumerate Windows system fonts.
        # Use installed fonts for QA only; no Microsoft font files are redistributed.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "seguisym.ttf"):
            if (fonts / filename).exists():
                QFontDatabase.addApplicationFont(str(fonts / filename))
    application.setFont(QFont("Microsoft YaHei UI", 10))
    icon = Path(__file__).resolve().parent / "assets" / "app.ico"
    if icon.exists():
        application.setWindowIcon(QIcon(str(icon)))
    try:
        data_dir = resolve_data_dir(args.data_dir)
    except OSError as exc:
        if args.self_test:
            args.self_test.parent.mkdir(parents=True, exist_ok=True)
            with args.self_test.open("x", encoding="utf-8") as stream:
                json.dump({"status": "failed", "error": str(exc), "stage": "data_directory"}, stream, ensure_ascii=False)
            return 1
        if args.screenshot:
            raise
        QMessageBox.critical(None, "数据目录不可写", f"请把程序放在可写目录，或使用 --data-dir 指定目录。\n\n{exc}")
        return 1
    if args.self_test:
        # Automated acceptance must never replace the operator\'s recovery files.
        data_dir = resolve_data_dir(data_dir / f"self-test-{uuid.uuid4().hex}")
    handler = RotatingFileHandler(data_dir / "logs" / "desktop.log", maxBytes=512_000,
                                 backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(message)s", force=True)

    def exception_hook(kind, value, traceback):
        logging.error("Unhandled UI exception", exc_info=(kind, value, traceback))
        if args.self_test or args.screenshot:
            application.setProperty("self_test_error", str(value))
            return
        QMessageBox.critical(None, "操作未完成", f"{value}\n\n详细信息已写入 {data_dir / 'logs' / 'desktop.log'}")

    sys.excepthook = exception_hook
    window = PrototypeWindow(session=MatchSession(data_dir), data_dir=data_dir)
    screen = application.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        window.resize(min(window.width(), max(760, available.width() - 32)),
                      min(window.height(), max(440, available.height() - 48)))
    if args.self_test or args.screenshot:
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    application.processEvents()
    if args.self_test:
        return _self_test(application, window, args.self_test, args.screenshot)
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(args.screenshot), "PNG"):
            raise OSError("could not save screenshot")
        window.close()
        window.deleteLater()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return 0
    QTimer.singleShot(0, window.offer_recovery)
    logging.info("Desktop %s started; data=%s", VERSION, data_dir)
    code = application.exec()
    window.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
