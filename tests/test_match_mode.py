"""Tests for MatchModePanel R-2 display extensions."""
from __future__ import annotations

import tkinter as tk

import pytest

from gui.match_mode import MatchModePanel
from tests.tk_support import make_hidden_tk_root


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


def test_panel_constructs_without_match_status_visible(tk_root):
    panel = MatchModePanel(tk_root)
    assert panel.is_match_status_visible is False
    assert panel.round_status_var.get() == ""
    assert panel.score_var.get() == ""
    assert panel.first_mover_var.get() == ""
    assert panel.role_var.get() == ""


def test_set_match_status_shows_match_fields(tk_root):
    panel = MatchModePanel(tk_root)
    panel.set_match_status(
        game_index=3,
        total_games=7,
        games_won_us=2,
        games_won_them=1,
        first_mover_label="我方",
        our_role="甲",
    )
    assert panel.is_match_status_visible is True
    assert panel.round_status_var.get() == "本轮：第 3 盘 / 共 7 盘"
    assert panel.score_var.get() == "比分：我方 2 — 对方 1"
    assert panel.first_mover_var.get() == "本盘先手：我方"
    assert panel.role_var.get() == "我方身份：甲方"


def test_set_match_status_then_update_keeps_visible(tk_root):
    panel = MatchModePanel(tk_root)
    panel.set_match_status(
        game_index=1,
        total_games=7,
        games_won_us=0,
        games_won_them=0,
        first_mover_label="对方",
        our_role="乙",
    )
    panel.set_match_status(
        game_index=2,
        total_games=7,
        games_won_us=0,
        games_won_them=1,
        first_mover_label="我方",
        our_role="乙",
    )
    assert panel.is_match_status_visible is True
    assert panel.round_status_var.get() == "本轮：第 2 盘 / 共 7 盘"
    assert panel.score_var.get() == "比分：我方 0 — 对方 1"
    assert panel.first_mover_var.get() == "本盘先手：我方"


def test_hide_match_status_clears_vars(tk_root):
    panel = MatchModePanel(tk_root)
    panel.set_match_status(
        game_index=1,
        total_games=7,
        games_won_us=0,
        games_won_them=0,
        first_mover_label="我方",
        our_role="甲",
    )
    panel.hide_match_status()
    assert panel.is_match_status_visible is False
    assert panel.round_status_var.get() == ""
    assert panel.score_var.get() == ""
    assert panel.first_mover_var.get() == ""
    assert panel.role_var.get() == ""


def test_hide_when_already_hidden_is_noop(tk_root):
    panel = MatchModePanel(tk_root)
    panel.hide_match_status()  # 初始就是 hidden
    assert panel.is_match_status_visible is False


def test_existing_panel_methods_still_work(tk_root):
    panel = MatchModePanel(tk_root)
    panel.set_current_player("红方")
    panel.set_phase("请录入骰子")
    panel.set_selected_pieces([2, 3])
    panel.set_recommendation("greedy_risk：红1 (0,0)→(1,1)")
    panel.set_record_dirty(True)
    panel.set_can_undo(False)

    assert panel.current_player_var.get() == "当前行动方：红方"
    assert panel.phase_var.get() == "当前阶段：请录入骰子"
    assert panel.selected_pieces_var.get() == "可走棋子：2、3"
    assert panel.recommendation_var.get() == "推荐走法：greedy_risk：红1 (0,0)→(1,1)"
    assert panel.record_status_var.get() == "棋谱状态：● 未保存"
    assert panel.can_undo_var.get() == "悔棋：不可用"
