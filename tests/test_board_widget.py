from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest

from core.game_state import GameState
from core.types import Position
from gui.board_widget import BoardWidget


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
    top.withdraw()
    yield top
    if top.winfo_exists():
        top.destroy()


def test_board_widget_edit_mode_routes_click_to_edit_callback(tk_root) -> None:
    normal_clicks: list[Position] = []
    edit_clicks: list[Position] = []
    board = BoardWidget(tk_root, normal_clicks.append, cell_size=10)
    board.set_state(GameState.from_layout())
    board.set_edit_mode(True, zone_cells={Position(0, 0)}, on_cell_click=edit_clicks.append)

    board._handle_click(SimpleNamespace(x=5, y=5))

    assert edit_clicks == [Position(0, 0)]
    assert normal_clicks == []


def test_board_widget_normal_mode_keeps_original_click_callback(tk_root) -> None:
    normal_clicks: list[Position] = []
    edit_clicks: list[Position] = []
    board = BoardWidget(tk_root, normal_clicks.append, cell_size=10)
    board.set_state(GameState.from_layout())
    board.set_edit_mode(True, zone_cells={Position(0, 0)}, on_cell_click=edit_clicks.append)
    board.set_edit_mode(False)

    board._handle_click(SimpleNamespace(x=15, y=5))

    assert normal_clicks == [Position(0, 1)]
    assert edit_clicks == []


def test_board_widget_edit_mode_highlights_zone_cells(tk_root) -> None:
    board = BoardWidget(tk_root, lambda position: None, cell_size=10)
    board.set_state(GameState.from_layout())
    board.set_edit_mode(True, zone_cells={Position(0, 0)}, on_cell_click=lambda position: None)

    first_rectangle = board.find_all()[0]

    assert board.itemcget(first_rectangle, "fill") == "#dbeafe"
