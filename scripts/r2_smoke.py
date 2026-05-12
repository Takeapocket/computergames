"""Headless smoke for R-2 - exits cleanly after assertions."""
import sys
import tempfile
import tkinter as tk
from pathlib import Path

sys.path.insert(0, ".")

# 先把 auto-save 路径换成临时目录，避免触发恢复 dialog
_tmp = Path(tempfile.mkdtemp(prefix="r2-smoke-"))
import gui.main_window as mw_mod

mw_mod.AUTO_SAVE_PATH = _tmp / "auto_save.json"
mw_mod.AUTO_SAVE_MATCH_PATH = _tmp / "auto_save_match.json"

from core.types import Player
from gui.main_window import MainWindow
from record.game_record import GameRecord


def main():
    root = tk.Tk()
    root.withdraw()
    window = MainWindow(root)
    window.pack()

    assert window._phase == "setup"
    assert window._mode == "debug"
    assert window._match is None
    print("[1/6] init OK; setup phase, debug mode")

    # 进入比赛模式
    window._show_match_setup_dialog = lambda: (Player.RED, "甲")
    window._enter_match_mode()
    assert window._match is not None
    assert window._match.our_role == "甲"
    assert window._phase == "setup"
    print(f"[2/6] match entry OK; role={window._match.our_role}, side={window._match.our_side.value}")
    print(f"      panel score: {window.match_mode_panel.score_var.get()}")
    print(f"      panel first_mover: {window.match_mode_panel.first_mover_var.get()}")

    # 模拟连胜 4 盘
    window._show_match_finished_dialog = lambda: None
    window._show_round_finished_dialog = lambda: window._start_new_game_in_match()
    for _ in range(4):
        window._match.append_finished_game(GameRecord.from_state(window.state), "us")
    window._refresh()
    assert window._match.is_finished()
    assert window._match.winner() == "us"
    print(f"[3/6] 4:0 sweep OK; winner={window._match.winner()}")

    # 重置回 debug
    window._reset_game()
    assert window._match is None
    assert window._mode == "debug"
    assert window.opening_panel.side_controls_enabled is True
    print("[4/6] reset OK; back to debug")

    # 蓝乙第一盘 → 对方红方先手
    window._show_match_setup_dialog = lambda: (Player.BLUE, "乙")
    window._enter_match_mode()
    assert window._match.first_mover_color(1) is Player.RED
    print(f"[5/6] blue-yi first mover OK: color={window._match.first_mover_color(1).value}")

    # 第 4 盘乙方先手（=甲方=红方对方→蓝方）
    assert window._match.first_mover_color(4) is Player.RED
    # 我方蓝乙：盘 4 甲方先手 → 甲是对方 → 对方=红方先手 ✓
    print(f"      blue-yi game 4 first mover color={window._match.first_mover_color(4).value}")

    # 第 2 盘乙方先手 → 我方=乙→我方先手→蓝方
    assert window._match.first_mover_color(2) is Player.BLUE
    print(f"[6/6] blue-yi game 2 first mover color={window._match.first_mover_color(2).value}")

    # 干净退出
    if window._timer_after_id is not None:
        try:
            window.after_cancel(window._timer_after_id)
        except tk.TclError:
            pass
    root.destroy()
    print("smoke OK")


if __name__ == "__main__":
    main()
