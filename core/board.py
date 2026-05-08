from __future__ import annotations

from core.types import BOARD_SIZE, Piece, Player, Position


def create_empty_board() -> list[list[Piece | None]]:
    return [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def get_piece_at(
    pieces: dict[Player, dict[int, Piece]],
    position: Position,
) -> Piece | None:
    for player_pieces in pieces.values():
        for piece in player_pieces.values():
            if piece.alive and piece.position == position:
                return piece
    return None
