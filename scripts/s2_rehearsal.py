"""S2 GUI 全流程演练（headless）。

按 `reports/r2-rehearsal.md` §2 的手测清单，把 8 个 GUI 全流程场景转成无人值守
脚本。每个 scenario 返回 (name, passed, detail)；主函数汇总打印并按整体 exit
code 退出，便于 `reports/gui-rehearsal.md` 引用脚本输出作为 S2 验收证据。

运行：

    & ".venv/Scripts/python.exe" scripts/s2_rehearsal.py

设计选择：

- 用 `MainWindow(..., auto_save_path=..., auto_save_match_path=...)` 构造器注入
  路径，比 `scripts/r2_smoke.py` 的模块级 monkeypatch 更干净，并且和
  `tests/test_match_integration.py` 的 monkeypatch.setattr fixture 隔离一致。
- 对话框（match-setup / round-finished / match-finished / askyesno / showinfo）
  统统 stub 成 no-op 或固定返回，避免任何阻塞。
- 4:0 / 4:3 用 `MatchRecord.append_finished_game` 推进比分，模拟"已结束"的盘；
  这是数据模型的公开 API（不是内部状态 monkeypatch），和 `r2_smoke.py` 一致。
- 盘内"真实走子"路径用 `_fill_opening_and_confirm` + `_handle_dice_change` +
  `_handle_move_select` + `_apply_selected_move`，验证 GUI 链路真能走通而非
  绕过 core。
"""
from __future__ import annotations

import os
import sys
import shutil
import tempfile
import tkinter as tk
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import gui.main_window as mw_mod  # noqa: E402
from ai.opening_layouts import PRESETS  # noqa: E402
from core.types import Player  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402
from record.auto_save import (  # noqa: E402
    has_auto_save,
    has_auto_save_match,
    load_auto_save_match,
)
from record.game_record import GameRecord  # noqa: E402
from record.match_record import MatchRecord  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _silence_messagebox(askyesno_return: bool = True) -> Callable[[], None]:
    """把 main_window 内的 messagebox showinfo/showerror/askyesno 全部静音。"""
    original_showinfo = mw_mod.messagebox.showinfo
    original_showerror = mw_mod.messagebox.showerror
    original_askyesno = mw_mod.messagebox.askyesno
    mw_mod.messagebox.showinfo = lambda *a, **k: None  # type: ignore[assignment]
    mw_mod.messagebox.showerror = lambda *a, **k: None  # type: ignore[assignment]
    mw_mod.messagebox.askyesno = lambda *a, **k: askyesno_return  # type: ignore[assignment]

    def restore() -> None:
        mw_mod.messagebox.showinfo = original_showinfo  # type: ignore[assignment]
        mw_mod.messagebox.showerror = original_showerror  # type: ignore[assignment]
        mw_mod.messagebox.askyesno = original_askyesno  # type: ignore[assignment]

    return restore


def _new_tmp(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"s2-{prefix}-"))


def _cleanup_tmp(tmp: Path) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


def _configure_tk_library_paths() -> None:
    _set_library_path_if_present("TCL_LIBRARY", "tcl8.6", "init.tcl")
    _set_library_path_if_present("TK_LIBRARY", "tk8.6", "tk.tcl")


def _set_library_path_if_present(env_var: str, directory_name: str, marker_file: str) -> None:
    if os.environ.get(env_var):
        return
    candidate = Path(sys.base_prefix) / "tcl" / directory_name
    if (candidate / marker_file).is_file():
        os.environ[env_var] = str(candidate)


def _make_window(
    tmp: Path,
    *,
    setup_dialog_return: tuple[Player, str] | None = (Player.RED, "甲"),
    askyesno_return: bool = True,
) -> tuple[tk.Tk, MainWindow]:
    """工厂：返回 (root, MainWindow)，路径隔离到 tmp。所有 dialog 静音。"""
    restore_messagebox = _silence_messagebox(askyesno_return=askyesno_return)
    try:
        _configure_tk_library_paths()
        root = tk.Tk()
        root.withdraw()
        window = MainWindow(
            root,
            auto_save_path=tmp / "auto_save.json",
            auto_save_match_path=tmp / "auto_save_match.json",
        )
    except Exception:
        restore_messagebox()
        raise
    window._s2_restore_messagebox = restore_messagebox  # type: ignore[attr-defined]
    window.pack()
    if setup_dialog_return is not None:
        window._show_match_setup_dialog = lambda: setup_dialog_return  # type: ignore[assignment]
    # round-finished 在 r2_smoke 里串到下一盘 setup；finished 不弹任何 UI
    window._show_round_finished_dialog = lambda: window._start_new_game_in_match()  # type: ignore[assignment]
    window._show_match_finished_dialog = lambda: None  # type: ignore[assignment]
    return root, window


def _destroy(root: tk.Tk, window: MainWindow) -> None:
    if window._timer_after_id is not None:
        try:
            window.after_cancel(window._timer_after_id)
        except tk.TclError:
            pass
        window._timer_after_id = None
    try:
        root.destroy()
    except tk.TclError:
        pass
    restore_messagebox = getattr(window, "_s2_restore_messagebox", None)
    if callable(restore_messagebox):
        restore_messagebox()


def _fill_opening_and_confirm(window: MainWindow, *, our_side: Player) -> None:
    """对应 `tests/test_match_integration.py:_fill_opening_and_confirm`。"""
    panel = window.opening_panel
    opponent_side = our_side.opponent
    if opponent_side is Player.RED:
        opponent_preset = PRESETS["balanced_v1"].red
        target = panel._red_layout
    else:
        opponent_preset = PRESETS["balanced_v1"].blue
        target = panel._blue_layout
    target.clear()
    for piece_id, pos in opponent_preset.items():
        target[piece_id] = pos
    panel.confirm()


def _take_one_real_move(window: MainWindow) -> None:
    """录骰子 → 选合法走法 → 执行。用 GUI 真实链路推进一步。"""
    window._handle_dice_change("3")
    assert window._current_moves(), "no legal moves after dice=3"
    window._handle_move_select(0)
    window._apply_selected_move()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

ScenarioResult = tuple[str, bool, str]


def scenario_4_0() -> ScenarioResult:
    """场景 1：4:0 整轮"""
    tmp = _new_tmp("4-0")
    root, window = _make_window(tmp)
    try:
        window._enter_match_mode()
        assert window._match is not None
        for _ in range(4):
            window._match.append_finished_game(
                GameRecord.from_state(window.state), "us"
            )
        window._refresh()
        assert window._match.is_finished(), "match not marked finished after 4 wins"
        assert window._match.winner() == "us"
        assert window._match.games_won_us == 4
        assert window._match.games_won_them == 0
        return ("4:0 整轮", True, "winner=us, games_won=4:0")
    finally:
        _destroy(root, window)
        _cleanup_tmp(tmp)


def scenario_4_3() -> ScenarioResult:
    """场景 2：4:3 整轮（前 6 盘交替 3:3，第 7 盘我方胜）"""
    tmp = _new_tmp("4-3")
    root, window = _make_window(tmp)
    try:
        window._enter_match_mode()
        assert window._match is not None
        for i in range(6):
            outcome = "us" if i % 2 == 0 else "them"
            window._match.append_finished_game(
                GameRecord.from_state(window.state), outcome
            )
        assert window._match.games_won_us == 3
        assert window._match.games_won_them == 3
        assert window._match.current_game_index == 7
        assert not window._match.is_finished()
        # 第 7 盘我方胜
        window._match.append_finished_game(
            GameRecord.from_state(window.state), "us"
        )
        window._refresh()
        assert window._match.is_finished()
        assert window._match.winner() == "us"
        assert window._match.games_won_us == 4
        assert window._match.games_won_them == 3
        return ("4:3 整轮", True, "winner=us, games_won=4:3, 第 7 盘绝杀")
    finally:
        _destroy(root, window)
        _cleanup_tmp(tmp)


def scenario_first_mover_sequence() -> ScenarioResult:
    """场景 3：7 盘 × 4 (甲红/甲蓝/乙红/乙蓝) 的 first_mover_color 矩阵。

    甲方 1/4/5 盘先手；乙方 2/3/6/7 盘先手。
    """
    expected: dict[tuple[Player, str], dict[int, Player]] = {
        # 甲方先手盘 = 我方先手；乙方先手盘 = 对方先手
        (Player.RED, "甲"): {1: Player.RED, 2: Player.BLUE, 3: Player.BLUE,
                              4: Player.RED, 5: Player.RED, 6: Player.BLUE, 7: Player.BLUE},
        (Player.BLUE, "甲"): {1: Player.BLUE, 2: Player.RED, 3: Player.RED,
                               4: Player.BLUE, 5: Player.BLUE, 6: Player.RED, 7: Player.RED},
        # 乙方：1/4/5 盘对方（甲）先手 → 对方颜色先手
        (Player.RED, "乙"): {1: Player.BLUE, 2: Player.RED, 3: Player.RED,
                              4: Player.BLUE, 5: Player.BLUE, 6: Player.RED, 7: Player.RED},
        (Player.BLUE, "乙"): {1: Player.RED, 2: Player.BLUE, 3: Player.BLUE,
                               4: Player.RED, 5: Player.RED, 6: Player.BLUE, 7: Player.BLUE},
    }
    details: list[str] = []
    for (side, role), mapping in expected.items():
        match = MatchRecord(our_side=side, our_role=role)
        for game_idx, expected_color in mapping.items():
            got = match.first_mover_color(game_idx)
            if got is not expected_color:
                return (
                    "先手序列",
                    False,
                    f"({side.value}/{role}) game {game_idx}: expected {expected_color.value}, got {got.value}",
                )
        details.append(f"{side.value}/{role}: 7/7 OK")
    return ("先手序列", True, "; ".join(details))


def scenario_timeout() -> ScenarioResult:
    """场景 4：超时判负 → 比分推进 + result.reason='timeout'"""
    tmp = _new_tmp("timeout")
    root, window = _make_window(tmp)
    try:
        window._enter_match_mode()
        _fill_opening_and_confirm(window, our_side=Player.RED)
        assert window._phase == "playing"
        # 模拟红方（我方）超时
        window._handle_timeout(Player.RED)
        assert window._match is not None
        assert window._match.games_won_them == 1
        assert window._match.games_won_us == 0
        finished_game = window._match.games[-1]
        assert finished_game.result["reason"] == "timeout"
        assert finished_game.result["winner_side"] == "them"
        # finalize 链路必须重排定时器（R-1/R-2/R-3 二审 #1）
        assert window._timer_after_id is not None, "timer refresh not rescheduled after timeout"
        # 单盘 auto_save 已清；match auto_save 保留
        assert not has_auto_save(path=window._auto_save_path)
        assert has_auto_save_match(path=window._auto_save_match_path)
        return ("超时判负", True, "比分=0:1, reason=timeout, timer 重排, auto_save 清理正确")
    finally:
        _destroy(root, window)
        _cleanup_tmp(tmp)


def scenario_match_restore_between_games() -> ScenarioResult:
    """场景 5：盘间恢复。完成 1 盘后关进程 → 重启 → 用 auto_save_match 恢复比分。"""
    tmp = _new_tmp("restore-between")
    # 第一阶段：完成第 1 盘后关掉
    root1, window1 = _make_window(tmp)
    try:
        window1._enter_match_mode()
        _fill_opening_and_confirm(window1, our_side=Player.RED)
        # 用 timeout 让对方输（我方= RED；让 BLUE 超时 → 我方胜）
        window1._handle_timeout(Player.BLUE)
        assert window1._match is not None
        assert window1._match.games_won_us == 1
        assert window1._match.current_game_index == 2
        # 此时 round-finished 已经触发并进入下一盘 setup 阶段
        assert window1._phase == "setup"
        assert has_auto_save_match(path=window1._auto_save_match_path)
    finally:
        _destroy(root1, window1)

    # 第二阶段：重启 → 在 _restore_auto_save_if_available 里 askyesno=True
    root2, window2 = _make_window(tmp, setup_dialog_return=None, askyesno_return=True)
    try:
        # MainWindow.__init__ 已经在最后调过 _restore_auto_save_if_available；
        # 由于 askyesno=True，应自动恢复 match。
        assert window2._match is not None, "match not restored"
        assert window2._match.games_won_us == 1, f"score lost: {window2._match.games_won_us}"
        assert window2._match.current_game_index == 2, "wrong game index after restore"
        assert window2._mode == "match"
        return ("盘间恢复", True, "重启后比分=1:0, 当前第 2 盘, mode=match")
    finally:
        _destroy(root2, window2)
        _cleanup_tmp(tmp)


def scenario_in_game_restore() -> ScenarioResult:
    """场景 6：盘中恢复。playing 阶段走一步 → 关 → 重启 → 验证 state/record/timer 一致。

    timer 比较语义：auto_save 是在 `_apply_selected_move` 内部写入的（瞬时快照），
    随后 BLUE 持续 tick，window1.timer.snapshot() 已经晚于 save 几毫秒；所以正确
    比较是 "auto_save 文件里的值" vs "restore 后 window2 的值"，而不是 window1 后
    续读的 snapshot。
    """
    import json

    tmp = _new_tmp("restore-ingame")

    root1, window1 = _make_window(tmp)
    try:
        window1._enter_match_mode()
        _fill_opening_and_confirm(window1, our_side=Player.RED)
        _take_one_real_move(window1)
        assert window1._phase == "playing"
        assert len(window1.record.steps) == 1
        assert has_auto_save(path=window1._auto_save_path)
        assert has_auto_save_match(path=window1._auto_save_match_path)
        steps_before = len(window1.record.steps)
        current_player_before = window1.state.current_player
        # 直接从 auto_save 文件读取保存时刻的 timer 值
        saved_payload = json.loads((tmp / "auto_save.json").read_text(encoding="utf-8"))
        saved_timer = saved_payload["metadata"]["auto_save"]["timer_remaining"]
    finally:
        _destroy(root1, window1)

    root2, window2 = _make_window(tmp, setup_dialog_return=None, askyesno_return=True)
    try:
        assert window2._match is not None, "match not restored"
        assert window2._phase == "playing", f"phase wrong after restore: {window2._phase}"
        assert len(window2.record.steps) == steps_before, "record.steps lost across restart"
        assert window2.state.current_player is current_player_before, "current_player drift"
        remaining_after = dict(window2.timer.snapshot().remaining_seconds)
        # restore 后立即读 → 与 auto_save 文件的瞬时快照应该一致（容差给 0.5s
        # 防 Tk after 回调在 destroy 前最后一帧抖动）
        for player in (Player.RED, Player.BLUE):
            saved = float(saved_timer[player.value])
            after = remaining_after[player]
            assert abs(saved - after) < 0.5, (
                f"timer drift for {player.value}: saved={saved} restored={after}"
            )
        return ("盘中恢复", True, f"steps={steps_before}, current={current_player_before.value}, timer 与 auto_save 一致")
    finally:
        _destroy(root2, window2)
        _cleanup_tmp(tmp)


def scenario_undo_scope() -> ScenarioResult:
    """场景 7：悔棋仅作用于当前盘 — 第 1 盘已 finalize，其 GameRecord 在 match.games[] 中不被悔棋触动。"""
    tmp = _new_tmp("undo-scope")
    root, window = _make_window(tmp)
    try:
        window._enter_match_mode()
        _fill_opening_and_confirm(window, our_side=Player.RED)
        # 让 BLUE 超时 → 我方胜第 1 盘
        window._handle_timeout(Player.BLUE)
        assert window._match is not None
        assert window._match.games_won_us == 1
        assert len(window._match.games) == 1
        # 第 1 盘的 finalized GameRecord
        game1_steps = len(window._match.games[0].steps)
        # round-finished 已串到 _start_new_game_in_match，现在在第 2 盘 setup
        assert window._phase == "setup"
        # 进入第 2 盘 playing
        _fill_opening_and_confirm(window, our_side=Player.RED)
        _take_one_real_move(window)
        assert len(window.record.steps) == 1
        # 悔第 2 盘的那一步
        window._undo_move()
        assert len(window.record.steps) == 0, "undo did not retract current-game step"
        # 第 1 盘的 GameRecord 不被悔棋触动
        assert len(window._match.games[0].steps) == game1_steps, (
            "previous-game record mutated by current-game undo"
        )
        return ("悔棋边界", True, f"第 1 盘 steps={game1_steps} 保留；第 2 盘 1 步可悔")
    finally:
        _destroy(root, window)
        _cleanup_tmp(tmp)


def scenario_match_finished_state() -> ScenarioResult:
    """场景 8：整轮 4 胜后 GUI 状态 — match 仍非空（不自动 reset）、可菜单切回 debug。"""
    tmp = _new_tmp("finished")
    root, window = _make_window(tmp)
    try:
        window._enter_match_mode()
        for _ in range(4):
            window._match.append_finished_game(
                GameRecord.from_state(window.state), "us"
            )
        window._refresh()
        assert window._match is not None
        assert window._match.is_finished()
        assert window._mode == "match", "should still be in match mode after round end"
        # 模拟用户菜单 → 调试模式
        window._reset_game()
        assert window._match is None
        assert window._mode == "debug"
        assert window.opening_panel.side_controls_enabled is True
        return ("整轮结束后行为", True, "4:0 finished → match 保留 → reset 回 debug 并恢复 side 控件")
    finally:
        _destroy(root, window)
        _cleanup_tmp(tmp)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SCENARIOS: list[Callable[[], ScenarioResult]] = [
    scenario_4_0,
    scenario_4_3,
    scenario_first_mover_sequence,
    scenario_timeout,
    scenario_match_restore_between_games,
    scenario_in_game_restore,
    scenario_undo_scope,
    scenario_match_finished_state,
]


def run_all() -> int:
    print("=" * 70)
    print("S2 GUI Full-Flow Headless Rehearsal")
    print("=" * 70)
    results: list[tuple[str, bool, str]] = []
    for i, fn in enumerate(SCENARIOS, 1):
        prefix = f"[{i}/{len(SCENARIOS)}]"
        try:
            name, passed, detail = fn()
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc(limit=4)
            results.append((fn.__name__, False, f"EXCEPTION: {exc}\n{tb}"))
            print(f"{prefix} {fn.__name__}: FAIL (exception)")
            print(tb)
            continue
        results.append((name, passed, detail))
        marker = "PASS" if passed else "FAIL"
        print(f"{prefix} {name}: {marker}")
        print(f"      {detail}")
    print("-" * 70)
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"Total: {passed_count}/{total} scenarios passed")
    print("=" * 70)
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(run_all())
