from __future__ import annotations

import tkinter as tk

from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


DEFAULT_RED_LAYOUT: dict[int, Position] = {
    1: Position(0, 0),
    2: Position(0, 1),
    3: Position(0, 2),
    4: Position(1, 0),
    5: Position(1, 1),
    6: Position(2, 0),
}

DEFAULT_BLUE_LAYOUT: dict[int, Position] = {
    1: Position(4, 4),
    2: Position(4, 3),
    3: Position(4, 2),
    4: Position(3, 4),
    5: Position(3, 3),
    6: Position(2, 4),
}


def create_default_state() -> GameState:
    return GameState.from_layout(
        red=DEFAULT_RED_LAYOUT,
        blue=DEFAULT_BLUE_LAYOUT,
        current_player=Player.RED,
    )


def player_label(player: Player) -> str:
    return "红方" if Player.from_value(player) is Player.RED else "蓝方"


def format_position(position: Position) -> str:
    return f"({position.row},{position.col})"


def format_move_label(move: Move) -> str:
    capture = " 吃子" if move.is_capture else ""
    return (
        f"{player_label(move.player)} {move.piece_id}: "
        f"{format_position(move.from_pos)} -> {format_position(move.to_pos)}{capture}"
    )


def main() -> None:
    from gui.main_window import MainWindow

    root = tk.Tk()
    root.title("爱恩斯坦棋 - 最小 GUI")
    root.minsize(800, 520)

    window = MainWindow(root)
    window.pack(fill=tk.BOTH, expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
