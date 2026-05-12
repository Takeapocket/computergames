import pytest


def test_unstubbed_main_window_messagebox_fails_in_tests() -> None:
    from gui.main_window import messagebox

    with pytest.raises(AssertionError, match="Unexpected Tk messagebox"):
        messagebox.askyesno("恢复未完成对局", "检测到上次未完成的自动保存对局，是否恢复？")
