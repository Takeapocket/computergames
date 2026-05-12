from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fail_unstubbed_tk_messageboxes(monkeypatch):
    """测试里不允许弹真实 Tk 对话框；需要弹窗语义的测试必须显式 stub。"""
    from gui.main_window import messagebox

    def unexpected_dialog(*args, **kwargs):
        title = args[0] if args else kwargs.get("title", "")
        raise AssertionError(f"Unexpected Tk messagebox during tests: {title}")

    monkeypatch.setattr(messagebox, "askyesno", unexpected_dialog)
    monkeypatch.setattr(messagebox, "showinfo", unexpected_dialog)
    monkeypatch.setattr(messagebox, "showerror", unexpected_dialog)
