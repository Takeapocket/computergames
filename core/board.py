from __future__ import annotations

from core.types import Piece, Player, Position


def get_piece_at(
    pieces: dict[Player, dict[int, Piece]],
    position: Position,
) -> Piece | None:
    for player_pieces in pieces.values():
        for piece in player_pieces.values():
            if piece.alive and piece.position == position:
                return piece
    return None
