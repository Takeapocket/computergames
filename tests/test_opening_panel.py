from __future__ import annotations

import tkinter as tk

import pytest

from core.types import Player, Position


@pytest.fixture(scope="module")
def _tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def tk_root(_tk_root):
    top = tk.Toplevel(_tk_root)
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
