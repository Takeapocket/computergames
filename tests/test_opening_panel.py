from __future__ import annotations

import tkinter as tk

import pytest

from core.types import Player, Position
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


def test_opening_panel_preset_populates_red_when_our_side_is_red(tk_root, tmp_path) -> None:
    from ai.opening_layouts import PRESETS
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.select_layout("aggressive_v1")

    red, blue = panel.get_layouts()

    assert red == PRESETS["aggressive_v1"].red
    assert blue == {}
    assert panel.red_layout_source == "preset:aggressive_v1"


def test_opening_panel_preset_populates_blue_when_our_side_is_blue(tk_root, tmp_path) -> None:
    from ai.opening_layouts import PRESETS
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    panel.set_our_side(Player.BLUE)
    panel.select_layout("defensive_v1")

    red, blue = panel.get_layouts()

    assert red == {}
    assert blue == PRESETS["defensive_v1"].blue
    assert panel.blue_layout_source == "preset:defensive_v1"


def test_opening_panel_places_and_removes_opponent_piece(tk_root, tmp_path) -> None:
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.set_edit_target("opponent")
    panel.set_selected_piece(3)

    assert panel.handle_board_click(Position(4, 4)) is True
    assert panel.get_layouts()[1][3] == Position(4, 4)

    assert panel.handle_board_click(Position(4, 4)) is True
    assert 3 not in panel.get_layouts()[1]


def test_opening_panel_rejects_click_outside_current_zone(tk_root, tmp_path) -> None:
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.set_edit_target("opponent")
    panel.set_selected_piece(1)

    assert panel.handle_board_click(Position(0, 0)) is False

    assert panel.get_layouts()[1] == {}
    assert "出发区" in panel.status_var.get()


def test_opening_panel_confirm_rejects_incomplete_opponent_layout(tk_root, tmp_path) -> None:
    from gui.opening_panel import OpeningPanel

    confirmed = []
    panel = OpeningPanel(tk_root, on_confirm=confirmed.append, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.confirm()

    assert confirmed == []
    assert "蓝方" in panel.status_var.get()


def test_opening_panel_confirm_emits_red_blue_selection(tk_root, tmp_path) -> None:
    from ai.opening_layouts import BLUE_ZONE
    from gui.opening_panel import OpeningPanel

    confirmed = []
    panel = OpeningPanel(tk_root, on_confirm=confirmed.append, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.set_edit_target("opponent")
    for piece_id, position in enumerate(sorted(BLUE_ZONE, key=lambda pos: (pos.row, pos.col)), start=1):
        panel.set_selected_piece(piece_id)
        assert panel.handle_board_click(position) is True

    panel.confirm()

    assert len(confirmed) == 1
    selection = confirmed[0]
    assert selection.our_side is Player.RED
    assert set(selection.red_layout) == set(range(1, 7))
    assert set(selection.blue_layout) == set(range(1, 7))
    assert selection.red_layout_source == "preset:balanced_v1"
    assert selection.blue_layout_source == "manual_entry"


def test_reset_for_match_game_first_game_loads_preset(tk_root, tmp_path) -> None:
    from ai.opening_layouts import PRESETS
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda s: None, layout_directory=tmp_path)
    panel.reset_for_match_game(our_side=Player.RED, keep_our_layout=False)

    red, blue = panel.get_layouts()
    assert red == dict(PRESETS["balanced_v1"].red)
    assert blue == {}
    assert panel.red_layout_source == "preset:balanced_v1"
    assert panel.blue_layout_source == "manual_entry"
    assert panel.edit_target_var.get() == "opponent"


def test_reset_for_match_game_keep_layout_after_win(tk_root, tmp_path) -> None:
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda s: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.select_layout("aggressive_v1")
    # 录入一些对方布局
    panel.set_edit_target("opponent")
    panel.set_selected_piece(1)
    panel.handle_board_click(Position(4, 4))

    red_before, _ = panel.get_layouts()
    panel.reset_for_match_game(our_side=Player.RED, keep_our_layout=True)

    red_after, blue_after = panel.get_layouts()
    assert red_after == red_before  # 我方布局保留
    assert blue_after == {}  # 对方布局清空


def test_reset_for_match_game_loss_resets_to_preset(tk_root, tmp_path) -> None:
    from ai.opening_layouts import PRESETS
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda s: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    panel.select_layout("aggressive_v1")
    # 手动改动我方布局
    panel.set_edit_target("self")
    panel.set_selected_piece(1)
    panel.handle_board_click(Position(0, 0))  # 移除红 1（aggressive_v1 红 6 在 (0,0)，红 1 在 (1,1)）
    # 重置回 balanced 预设（模拟"上盘负"）
    panel.layout_var.set("balanced_v1")
    panel.reset_for_match_game(our_side=Player.RED, keep_our_layout=False)

    red, blue = panel.get_layouts()
    assert red == dict(PRESETS["balanced_v1"].red)
    assert blue == {}


def test_reset_for_match_game_blue_loads_blue_preset(tk_root, tmp_path) -> None:
    from ai.opening_layouts import PRESETS
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda s: None, layout_directory=tmp_path)
    panel.reset_for_match_game(our_side=Player.BLUE, keep_our_layout=False)

    red, blue = panel.get_layouts()
    assert blue == dict(PRESETS["balanced_v1"].blue)
    assert red == {}
    assert panel.blue_layout_source == "preset:balanced_v1"
    assert panel.our_side is Player.BLUE


def test_set_side_controls_enabled_disables_radios(tk_root, tmp_path) -> None:
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda s: None, layout_directory=tmp_path)
    assert panel.side_controls_enabled is True

    panel.set_side_controls_enabled(False)
    assert panel.side_controls_enabled is False
    assert str(panel._red_side_radio.cget("state")) == "disabled"
    assert str(panel._blue_side_radio.cget("state")) == "disabled"

    panel.set_side_controls_enabled(True)
    assert panel.side_controls_enabled is True


def test_opening_panel_save_reports_os_error(tk_root, tmp_path, monkeypatch) -> None:
    from gui import opening_panel
    from gui.opening_panel import OpeningPanel

    def fail_save(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(opening_panel, "save_layout", fail_save)
    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)

    assert panel.save_current_layout("custom_v1", "Custom V1") is False
    assert "disk full" in panel.status_var.get()


def test_opening_panel_saves_self_layout_without_opponent_entry(tk_root, tmp_path) -> None:
    from ai.opening_layouts import load_layout
    from gui.opening_panel import OpeningPanel

    panel = OpeningPanel(tk_root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    panel.set_our_side(Player.RED)
    red, blue = panel.get_layouts()

    assert red
    assert blue == {}
    assert panel.save_current_layout("my_red", "My Red") is True

    saved = load_layout("my_red", directory=tmp_path)
    assert saved.red == red
    assert saved.blue == {
        piece_id: Position(4 - position.row, 4 - position.col)
        for piece_id, position in red.items()
    }
