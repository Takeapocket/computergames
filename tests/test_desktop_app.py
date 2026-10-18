"""Failure-path acceptance for the executable self-test, without modal prompts."""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox
from desktop_qt.app import _self_test
from desktop_qt.window import PrototypeWindow


def test_self_test_reports_save_failure_without_opening_dialog(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    window = PrototypeWindow(data_dir=tmp_path / "data")

    def fail_save(path):
        raise OSError("injected disk failure")

    monkeypatch.setattr(window.session, "save", fail_save)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: pytest.fail("automated failure must not open a modal dialog"))
    report_path = tmp_path / "failed.json"
    assert _self_test(application, window, report_path, None) == 1
    result = json.loads(report_path.read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert "injected disk failure" in result["error"]
