from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest

from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
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


def test_board_widget_preview_move_none_does_not_add_extra_items(tk_root) -> None:
    board = BoardWidget(tk_root, lambda position: None, cell_size=10)
    state = GameState.from_layout()
    board.set_state(state)
    baseline = len(board.find_all())

    board.set_state(state, preview_move=None)

    assert len(board.find_all()) == baseline


def test_board_widget_preview_move_draws_ghost_oval_and_text(tk_root) -> None:
    board = BoardWidget(tk_root, lambda position: None, cell_size=10)
    state = GameState.from_layout()
    board.set_state(state)
    baseline = len(board.find_all())

    move = Move(
        player=Player.RED,
        piece_id=1,
        from_pos=Position(0, 0),
        to_pos=Position(1, 1),
    )
    board.set_state(state, preview_move=move)

    preview_items = board.find_withtag("preview")
    assert len(preview_items) == 2  # oval + text
    assert len(board.find_all()) == baseline + 2

    types = sorted(board.type(item) for item in preview_items)
    assert types == ["oval", "text"]


def test_board_widget_preview_move_ghost_lands_on_to_pos(tk_root) -> None:
    cell_size = 20
    board = BoardWidget(tk_root, lambda position: None, cell_size=cell_size)
    state = GameState.from_layout()

    move = Move(
        player=Player.BLUE,
        piece_id=3,
        from_pos=Position(4, 4),
        to_pos=Position(2, 3),
    )
    board.set_state(state, preview_move=move)

    oval = next(item for item in board.find_withtag("preview") if board.type(item) == "oval")
    x0, y0, x1, y1 = board.coords(oval)
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    expected_cx = (move.to_pos.col + 0.5) * cell_size
    expected_cy = (move.to_pos.row + 0.5) * cell_size
    assert cx == pytest.approx(expected_cx)
    assert cy == pytest.approx(expected_cy)
    assert board.itemcget(oval, "stipple") == "gray50"
