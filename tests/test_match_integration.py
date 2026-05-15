"""R-2 七盘制比赛模式集成测试。"""
from __future__ import annotations

import tkinter as tk

import pytest

from ai.opening_layouts import PRESETS
from core.game_state import GameState
from core.types import Player, Position
from gui.main_window import MainWindow
from record.auto_save import has_auto_save_match, load_auto_save_match
from record.game_record import GameRecord
from tests.tk_support import make_hidden_tk_root


def _stub_game() -> GameRecord:
    """构造一个最小但合法的已结束 GameRecord，给 MatchRecord.games[] 占位用。"""
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
    )
    return GameRecord.from_state(state)


@pytest.fixture(scope="module")
def _tk_root():
    root = make_hidden_tk_root()
    yield root


@pytest.fixture
def tk_root(_tk_root):
    top = tk.Toplevel(_tk_root)
    top.withdraw()
    yield top
    if top.winfo_exists():
        top.destroy()


@pytest.fixture(autouse=True)
def _isolated_auto_save_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )


def _enter_match(window, monkeypatch, *, our_side=Player.RED, our_role="甲"):
    monkeypatch.setattr(window, "_show_match_setup_dialog", lambda: (our_side, our_role))
    window._enter_match_mode()


def _fill_opening_and_confirm(window, *, our_side=Player.RED):
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


def test_match_mode_entry_creates_match_record(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()

    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    assert window._match is not None
    assert window._match.our_side is Player.RED
    assert window._match.our_role == "甲"
    assert window._match.current_game_index == 1
    assert window._phase == "setup"
    assert window.opening_panel.side_controls_enabled is False


def test_match_first_game_uses_jia_first_mover(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()

    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)

    assert window._phase == "playing"
    assert window.state.current_player is Player.RED
    assert window._match.phase == "playing"
    assert window.record.metadata["first_mover_color"] == "red"
    assert window.record.metadata["match_id"] == window._match.match_id
    assert window.record.metadata["game_index"] == 1
    assert window.record.metadata["our_role"] == "甲"


def test_match_second_game_switches_first_mover(tk_root, monkeypatch):
    """我方甲红 → 第 2 盘乙方先手 → state.current_player 应为蓝。"""
    window = MainWindow(tk_root)
    window.pack()

    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    window._match.append_finished_game(GameRecord.from_state(window.state), "us")
    window._start_new_game_in_match()
    _fill_opening_and_confirm(window, our_side=Player.RED)

    assert window._match.current_game_index == 2
    assert window.state.current_player is Player.BLUE
    assert window.record.metadata["first_mover_color"] == "blue"
    assert window.record.metadata["game_index"] == 2


def test_match_blue_yi_first_mover(tk_root, monkeypatch):
    """我方蓝乙 → 第 1 盘对方=甲方=红方先手。"""
    window = MainWindow(tk_root)
    window.pack()

    _enter_match(window, monkeypatch, our_side=Player.BLUE, our_role="乙")
    _fill_opening_and_confirm(window, our_side=Player.BLUE)

    assert window.state.current_player is Player.RED


def test_match_sticky_layout_after_our_win(tk_root, monkeypatch):
    """上盘我方胜 → 第 2 盘 OpeningPanel 保留我方布局，对方清空。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    window._match.append_finished_game(GameRecord.from_state(window.state), "us")
    window._start_new_game_in_match()

    red, blue = window.opening_panel.get_layouts()
    assert red == dict(PRESETS["balanced_v1"].red)
    assert blue == {}


def test_match_layout_resets_after_our_loss(tk_root, monkeypatch):
    """上盘我方负 → 第 2 盘我方布局重置为预设，对方清空。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    window._match.append_finished_game(GameRecord.from_state(window.state), "them")
    window._start_new_game_in_match()

    red, blue = window.opening_panel.get_layouts()
    assert red == dict(PRESETS["balanced_v1"].red)
    assert blue == {}


def test_match_4_0_finishes(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    for _ in range(4):
        window._match.append_finished_game(GameRecord.from_state(window.state), "us")

    assert window._match.is_finished()
    assert window._match.winner() == "us"
    assert window._match.games_won_us == 4
    assert window._match.phase == "finished"


def test_match_finalize_winner_writes_result(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)
    monkeypatch.setattr(window, "_show_match_finished_dialog", lambda: None)
    monkeypatch.setattr(window, "_show_round_finished_dialog", lambda: None)

    window._finalize_match_game(Player.RED, reason="target_corner")

    assert window._match.games_won_us == 1
    finished_record = window._match.games[0]
    assert finished_record.result["winner"] == "red"
    assert finished_record.result["winner_side"] == "us"
    assert finished_record.result["reason"] == "target_corner"
    assert finished_record.result["game_index"] == 1


def test_match_finalize_opponent_win(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)
    monkeypatch.setattr(window, "_show_round_finished_dialog", lambda: None)

    window._finalize_match_game(Player.BLUE, reason="capture_all")

    assert window._match.games_won_them == 1
    assert window._match.games_won_us == 0
    assert window._match.games[0].result["winner_side"] == "them"
    assert window._match.games[0].result["reason"] == "capture_all"


def test_match_auto_save_persists_after_finalize(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    match_path = window._auto_save_match_path

    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    monkeypatch.setattr(window, "_show_round_finished_dialog", lambda: None)
    _fill_opening_and_confirm(window, our_side=Player.RED)
    window._finalize_match_game(Player.RED, reason="target_corner")

    assert has_auto_save_match(path=match_path)
    loaded = load_auto_save_match(path=match_path)
    assert loaded.our_role == "甲"
    assert loaded.games_won_us == 1
    # finalize 后调用了 _show_round_finished_dialog（被 mock 成 noop），
    # 没有自动推进到下一盘 setup；phase 取决于 append_finished_game 内部逻辑
    assert loaded.phase == "setup"


def test_reset_game_clears_match_state(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    assert window._match is not None
    window._reset_game()

    assert window._match is None
    assert window._mode == "debug"
    assert window._our_side is None
    assert window.opening_panel.side_controls_enabled is True
    assert not has_auto_save_match(path=window._auto_save_match_path)


def test_debug_mode_legacy_opening_flow_still_works(tk_root):
    """未进入比赛模式时确认开局 → legacy 行为：红方先手 + _mode=match + 无 MatchRecord。"""
    window = MainWindow(tk_root)
    window.pack()
    panel = window.opening_panel
    panel.set_our_side(Player.RED)
    for piece_id, pos in PRESETS["balanced_v1"].blue.items():
        panel._blue_layout[piece_id] = pos
    panel.confirm()

    assert window._match is None
    assert window._mode == "match"
    assert window._our_side is Player.RED
    assert window.state.current_player is Player.RED


def test_match_finished_dialog_only_fires_once(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    calls = []
    monkeypatch.setattr(
        "gui.main_window.messagebox.showinfo",
        lambda *args, **kwargs: calls.append(args),
    )

    for _ in range(4):
        window._match.append_finished_game(GameRecord.from_state(window.state), "us")

    window._show_match_finished_dialog()
    window._show_match_finished_dialog()

    assert len(calls) == 1


def test_match_refresh_shows_match_status_in_panel(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    assert window.match_mode_panel.is_match_status_visible is True
    assert "第 1 盘" in window.match_mode_panel.round_status_var.get()
    assert "我方 0" in window.match_mode_panel.score_var.get()
    assert window.match_mode_panel.role_var.get() == "我方身份：甲方"


def test_match_restore_from_setup_phase(tk_root, monkeypatch, tmp_path):
    """match auto-save phase=setup → 启动后恢复到 setup phase 等待录入。"""
    from record.auto_save import auto_save_match
    from record.match_record import MatchRecord

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=2,
        games_won_us=1,
        games=[_stub_game()],
    )
    auto_save_match(match, path=tmp_path / "auto_save_match.json")

    monkeypatch.setattr(
        "gui.main_window.messagebox.askyesno",
        lambda *args, **kwargs: True,
    )
    window = MainWindow(tk_root)
    window.pack()

    assert window._match is not None
    assert window._match.current_game_index == 2
    assert window._match.games_won_us == 1
    assert window._mode == "match"
    assert window._phase == "setup"


def test_match_restore_setup_phase_clears_stale_single_game_auto_save(
    tk_root, monkeypatch, tmp_path
):
    """R-1/R-2/R-3 二审 #3：恢复整轮 setup 时若仍残留单盘 auto-save（finalize 后崩在 clear 之前），
    必须一并清掉，否则下次启动会反复弹'是否恢复'。"""
    from record.auto_save import (
        auto_save as _auto_save,
        auto_save_match,
        has_auto_save,
    )
    from record.match_record import MatchRecord
    from gui.timer_panel import TimerSnapshot

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )

    # 1) 残留的单盘 auto-save（模拟 finalize 已写过 match 但崩在 _clear_auto_save 之前）
    stub_record = _stub_game()
    snapshot = TimerSnapshot(
        current_player=Player.RED,
        remaining_seconds={Player.RED: 240.0, Player.BLUE: 240.0},
        current_step_seconds=0.0,
        paused=True,
        timeout_players=(),
    )
    _auto_save(stub_record, snapshot, path=tmp_path / "auto_save.json")
    assert has_auto_save(path=tmp_path / "auto_save.json")

    # 2) 整轮 auto-save，phase=setup（finalize 后 current_game_index 已推进到第 2 盘）
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=2,
        games_won_us=1,
        games=[_stub_game()],
    )
    auto_save_match(match, path=tmp_path / "auto_save_match.json")

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *a, **k: True)
    window = MainWindow(tk_root)
    window.pack()

    # 整轮恢复成功
    assert window._match is not None
    assert window._match.current_game_index == 2
    assert window._phase == "setup"
    # 关键：残留的单盘 auto-save 已被清，不会再被下次启动当作"未完成对局"再次弹窗
    assert not has_auto_save(path=tmp_path / "auto_save.json")


def test_match_restore_from_finished_phase_clears_and_returns_to_debug(tk_root, monkeypatch, tmp_path):
    """match auto-save phase=finished → 提示后清理 + 回 debug。"""
    from record.auto_save import auto_save_match, has_auto_save_match
    from record.match_record import MatchRecord

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=4,
        games_won_us=4,
        phase="finished",
        games=[_stub_game() for _ in range(4)],
    )
    auto_save_match(match, path=tmp_path / "auto_save_match.json")

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)
    window = MainWindow(tk_root)
    window.pack()

    assert window._match is None
    assert window._mode == "debug"
    assert not has_auto_save_match(path=tmp_path / "auto_save_match.json")


# ---- R-2 review Important #19：补齐关键集成测试 ----


def test_enter_match_mode_clears_stale_single_game_auto_save(tk_root, monkeypatch, tmp_path):
    """旧的单盘 auto-save 不应在进入新一轮 match 时残留。"""
    from record.auto_save import auto_save as _auto_save, has_auto_save
    from gui.timer_panel import TimerSnapshot

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )
    window = MainWindow(tk_root)
    window.pack()

    # 在已启动窗口中放入一个旧的单盘 auto-save，模拟进入新一轮前的残留文件。
    stub_record = _stub_game()
    snapshot = TimerSnapshot(
        current_player=Player.RED,
        remaining_seconds={Player.RED: 240.0, Player.BLUE: 240.0},
        current_step_seconds=0.0,
        paused=True,
        timeout_players=(),
    )
    _auto_save(stub_record, snapshot, path=tmp_path / "auto_save.json")
    assert has_auto_save(path=tmp_path / "auto_save.json") is True

    # 进入比赛模式 → 旧的单盘 auto-save 必须被清掉，避免下次启动时混合恢复。
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")

    assert has_auto_save(path=tmp_path / "auto_save.json") is False
    assert window._match is not None
    assert window._match.current_game_index == 1


def test_match_restore_playing_phase_with_missing_game_auto_save_prompts(
    tk_root, monkeypatch, tmp_path
):
    """match.phase == 'playing' 但单盘 auto-save 缺失：必须弹窗确认而不是静默丢盘内数据。"""
    from record.auto_save import auto_save_match, has_auto_save_match
    from record.match_record import MatchRecord

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )
    # 整轮记录处于第 2 盘 playing，但本盘 auto-save 缺失
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=2,
        games_won_us=1,
        phase="playing",
        games=[_stub_game()],
    )
    auto_save_match(match, path=tmp_path / "auto_save_match.json")

    askyesno_calls: list[tuple] = []

    def fake_askyesno(title, msg, **kwargs):
        askyesno_calls.append((title, msg))
        if title == "恢复未完成对局":
            return True  # 确认恢复
        if title == "本盘进度缺失":
            return False  # 用户选"否"：放弃整轮恢复
        return False

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", fake_askyesno)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)
    window = MainWindow(tk_root)
    window.pack()

    # 用户选"否" → 整轮被放弃
    titles = [call[0] for call in askyesno_calls]
    assert "本盘进度缺失" in titles
    assert window._match is None
    assert window._mode == "debug"
    assert not has_auto_save_match(path=tmp_path / "auto_save_match.json")


def test_match_restore_playing_phase_with_missing_game_user_accepts(
    tk_root, monkeypatch, tmp_path
):
    """用户选'是'：保留整轮记录，回到当前盘 setup 阶段重新录入。"""
    from record.auto_save import auto_save_match
    from record.match_record import MatchRecord

    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_PATH",
        tmp_path / "auto_save.json",
        raising=False,
    )
    monkeypatch.setattr(
        "gui.main_window.AUTO_SAVE_MATCH_PATH",
        tmp_path / "auto_save_match.json",
        raising=False,
    )
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=2,
        games_won_us=1,
        phase="playing",
        games=[_stub_game()],
    )
    auto_save_match(match, path=tmp_path / "auto_save_match.json")

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)
    window = MainWindow(tk_root)
    window.pack()

    assert window._match is not None
    assert window._match.current_game_index == 2
    assert window._match.games_won_us == 1
    assert window._phase == "setup"


def test_load_record_during_active_match_prompts(tk_root, monkeypatch, tmp_path):
    """比赛进行中通过菜单加载棋谱，必须先弹窗确认。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    assert window._match is not None

    askyesno_calls: list[tuple] = []

    def fake_askyesno(title, msg, **kwargs):
        askyesno_calls.append((title, msg))
        return False  # 用户拒绝 → 不应改变 self._match

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", fake_askyesno)
    monkeypatch.setattr("gui.main_window.filedialog.askopenfilename", lambda **kw: "")
    window._load_record()

    titles = [call[0] for call in askyesno_calls]
    assert "比赛进行中" in titles
    # 用户拒绝 → match 状态保持
    assert window._match is not None
    assert window._mode == "match"


def test_load_record_during_active_match_exits_match_when_confirmed(
    tk_root, monkeypatch, tmp_path
):
    """用户选'是'后：match 被退出，但因为没真选文件，最终 mode 应已回到 debug。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    assert window._match is not None

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("gui.main_window.filedialog.askopenfilename", lambda **kw: "")
    window._load_record()

    # 用户确认 → match 已被清，模式回 debug；后续棋谱未实际加载（filedialog 返回空）
    assert window._match is None
    assert window._mode == "debug"


def test_finalize_match_game_persists_match_before_clearing_game(
    tk_root, monkeypatch, tmp_path
):
    """R-2 review Important #13：finalize 顺序应是先存 match、再清 game auto-save。"""
    from record.auto_save import has_auto_save, has_auto_save_match, load_auto_save_match

    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)

    # 模拟超时触发的 finalize：直接调用，winner=对方
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)
    window._finalize_match_game(Player.BLUE, reason="timeout")

    # match auto-save 持久化了已结束盘
    assert has_auto_save_match(path=window._auto_save_match_path)
    loaded = load_auto_save_match(path=window._auto_save_match_path)
    assert loaded.games_won_them == 1
    assert len(loaded.games) == 1
    # game auto-save 已清
    assert not has_auto_save(path=window._auto_save_path)


def test_timeout_during_match_advances_score(tk_root, monkeypatch):
    """R-2 review Important #16 + #19：超时触发后比分应该推进，并把 timeout 原因写进 record。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)

    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)
    # 模拟红方（我方）超时
    window._handle_timeout(Player.RED)

    assert window._match.games_won_them == 1
    assert window._match.games_won_us == 0
    # 上一盘已被 finalize，结果记录里 reason == "timeout"
    finished_game = window._match.games[-1]
    assert finished_game.result["reason"] == "timeout"
    assert finished_game.result["winner_side"] == "them"
    # 单盘 auto-save 已清（finalize 调用过 _clear_auto_save）
    from record.auto_save import has_auto_save
    assert not has_auto_save(path=window._auto_save_path)


def test_handle_timeout_in_match_reschedules_timer_refresh(tk_root, monkeypatch):
    """R-1/R-2/R-3 二审 #1：match 模式 timeout 触发 finalize 后必须重排定时器刷新，
    否则后续盘的计时面板不会再自动更新，也不会再检测下一次超时。"""
    window = MainWindow(tk_root)
    window.pack()
    _enter_match(window, monkeypatch, our_side=Player.RED, our_role="甲")
    _fill_opening_and_confirm(window, our_side=Player.RED)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *a, **k: None)

    # 模拟刚刚 _refresh_timer 被 fire 触发的状态：取消构造时挂的 after，并把 id 置 None
    if window._timer_after_id is not None:
        try:
            window.after_cancel(window._timer_after_id)
        except tk.TclError:
            pass
    window._timer_after_id = None

    window._handle_timeout(Player.RED)

    # 必须有新的 after 被排上，否则后续计时刷新链就死了
    assert window._timer_after_id is not None, (
        "after match-mode timeout, _schedule_timer_refresh must re-arm the periodic refresh"
    )
    pending = str(tk_root.tk.call("after", "info"))
    assert window._timer_after_id in pending, (
        f"after-id {window._timer_after_id} not in pending after-info {pending}"
    )
