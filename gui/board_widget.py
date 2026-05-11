from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable

from core.game_state import GameState
from core.types import BOARD_SIZE, Player, Position


class BoardWidget(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        on_square_click: Callable[[Position], None],
        *,
        cell_size: int = 82,
    ) -> None:
        self.cell_size = cell_size
        self._on_square_click = on_square_click
        self._state: GameState | None = None
        self._selected: Position | None = None
        self._legal_destinations: set[Position] = set()
        self._edit_mode = False
        self._edit_zone_cells: set[Position] = set()
        self._on_edit_cell_click: Callable[[Position], None] | None = None
        board_px = BOARD_SIZE * cell_size

        super().__init__(
            master,
            width=board_px,
            height=board_px,
            background="#f6f3eb",
            highlightthickness=0,
        )
        self.bind("<Button-1>", self._handle_click)

    def set_state(
        self,
        state: GameState,
        *,
        selected: Position | None = None,
        legal_destinations: Iterable[Position] = (),
    ) -> None:
        self._state = state
        self._selected = selected
        self._legal_destinations = set(legal_destinations)
        self._render()

    def set_edit_mode(
        self,
        enabled: bool,
        *,
        zone_cells: Iterable[Position] = (),
        on_cell_click: Callable[[Position], None] | None = None,
    ) -> None:
        self._edit_mode = bool(enabled)
        self._edit_zone_cells = set(zone_cells)
        self._on_edit_cell_click = on_cell_click if enabled else None
        self._render()

    def _handle_click(self, event: tk.Event) -> None:
        row = int(event.y // self.cell_size)
        col = int(event.x // self.cell_size)
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            position = Position(row, col)
            if self._edit_mode and self._on_edit_cell_click is not None:
                self._on_edit_cell_click(position)
                return
            self._on_square_click(position)

    def _render(self) -> None:
        self.delete("all")
        self._draw_cells()
        if self._state is None:
            return
        self._draw_pieces()

    def _draw_cells(self) -> None:
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                position = Position(row, col)
                x0 = col * self.cell_size
                y0 = row * self.cell_size
                x1 = x0 + self.cell_size
                y1 = y0 + self.cell_size
                fill = "#fff8eb" if (row + col) % 2 == 0 else "#efe1c8"
                if self._edit_mode and position in self._edit_zone_cells:
                    fill = "#dbeafe"
                if position == self._selected:
                    fill = "#ffe08a"
                elif position in self._legal_destinations:
                    fill = "#cfe8c9"
                self.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#5f5548", width=1)

    def _draw_pieces(self) -> None:
        if self._state is None:
            return

        for player in (Player.RED, Player.BLUE):
            for piece in self._state.pieces[player].values():
                if not piece.alive:
                    continue
                self._draw_piece(player, piece.piece_id, piece.position)

    def _draw_piece(self, player: Player, piece_id: int, position: Position) -> None:
        padding = 12
        x0 = position.col * self.cell_size + padding
        y0 = position.row * self.cell_size + padding
        x1 = (position.col + 1) * self.cell_size - padding
        y1 = (position.row + 1) * self.cell_size - padding
        fill = "#bf2f2f" if player is Player.RED else "#2459a6"

        self.create_oval(x0, y0, x1, y1, fill=fill, outline="#1f1f1f", width=2)
        self.create_text(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            text=str(piece_id),
            fill="white",
            font=("Segoe UI", 22, "bold"),
        )
