"""Shared display labels; no GUI toolkit is imported here."""
from __future__ import annotations

from core.move import Move
from core.types import Player, Position


def player_label(player: Player) -> str:
    return "红方" if Player.from_value(player) is Player.RED else "蓝方"


def format_position(position: Position) -> str:
    return f"({position.row},{position.col})"


def format_move_label(move: Move, *, distinguish_self_capture: bool = False) -> str:
    capture = ""
    if move.is_capture:
        is_self_capture = (
            distinguish_self_capture
            and move.captured_piece is not None
            and move.captured_piece.player is move.player
        )
        capture = " 自吃" if is_self_capture else " 吃子"
    return (
        f"{player_label(move.player)} {move.piece_id}: "
        f"{format_position(move.from_pos)} -> {format_position(move.to_pos)}{capture}"
    )
