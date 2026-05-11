from __future__ import annotations

from collections.abc import Callable, Mapping

from core.move import Move
from core.types import BOARD_SIZE, MAX_PIECE_ID, MIN_PIECE_ID, Piece, Player, Position


def is_inside_board(position: Position) -> bool:
    return 0 <= position.row < BOARD_SIZE and 0 <= position.col < BOARD_SIZE


def target_corner(player: Player) -> Position:
    return Position(BOARD_SIZE - 1, BOARD_SIZE - 1) if player is Player.RED else Position(0, 0)


def move_deltas(player: Player) -> tuple[tuple[int, int], ...]:
    if player is Player.RED:
        return ((1, 0), (0, 1), (1, 1))
    return ((-1, 0), (0, -1), (-1, -1))


def legal_piece_ids_for_dice(pieces: Mapping[int, Piece], dice: int) -> list[int]:
    if not MIN_PIECE_ID <= dice <= MAX_PIECE_ID:
        raise ValueError("dice must be between 1 and 6")

    exact_piece = pieces.get(dice)
    if exact_piece is not None and exact_piece.alive:
        return [dice]

    living_ids = sorted(piece_id for piece_id, piece in pieces.items() if piece.alive)
    if not living_ids:
        return []

    nearest_distance = min(abs(piece_id - dice) for piece_id in living_ids)
    return [piece_id for piece_id in living_ids if abs(piece_id - dice) == nearest_distance]


def generate_legal_moves_for_piece(
    piece: Piece,
    piece_at: Callable[[Position], Piece | None],
) -> list[Move]:
    if not piece.alive:
        return []

    moves: list[Move] = []
    for row_delta, col_delta in move_deltas(piece.player):
        to_pos = Position(piece.position.row + row_delta, piece.position.col + col_delta)
        if not is_inside_board(to_pos):
            continue

        occupant = piece_at(to_pos)
        captured_piece = occupant.copy() if occupant is not None else None
        moves.append(
            Move(
                player=piece.player,
                piece_id=piece.piece_id,
                from_pos=piece.position,
                to_pos=to_pos,
                is_capture=captured_piece is not None,
                captured_piece=captured_piece,
            )
        )
    return moves


def get_winner(pieces: Mapping[Player, Mapping[int, Piece]]) -> Player | None:
    for player in (Player.RED, Player.BLUE):
        if any(piece.alive and piece.position == target_corner(player) for piece in pieces[player].values()):
            return player

    for player in (Player.RED, Player.BLUE):
        opponent = player.opponent
        if any(piece.alive for piece in pieces[player].values()) and not any(
            piece.alive for piece in pieces[opponent].values()
        ):
            return player

    return None
