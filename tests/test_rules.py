import pytest

from core.game_state import GameState
from core.rules import BOARD_SIZE, is_inside_board
from core.types import Piece, Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


def test_5x5_board_boundary():
    assert BOARD_SIZE == 5
    assert is_inside_board(Position(0, 0))
    assert is_inside_board(Position(4, 4))
    assert not is_inside_board(Position(-1, 0))
    assert not is_inside_board(Position(0, -1))
    assert not is_inside_board(Position(5, 0))
    assert not is_inside_board(Position(0, 5))


def test_red_moves_toward_down_right_and_down_right_diagonal():
    state = make_state(red={1: Position(2, 2)})

    moves = state.legal_moves_for_piece(Player.RED, 1)

    destinations = {move.to_pos for move in moves}
    assert destinations == {Position(3, 2), Position(2, 3), Position(3, 3)}


def test_blue_moves_toward_up_left_and_up_left_diagonal():
    state = make_state(blue={1: Position(2, 2)}, current_player=Player.BLUE)

    moves = state.legal_moves_for_piece(Player.BLUE, 1)

    destinations = {move.to_pos for move in moves}
    assert destinations == {Position(1, 2), Position(2, 1), Position(1, 1)}


def test_piece_cannot_move_to_own_piece_square():
    state = make_state(red={1: Position(2, 2), 2: Position(3, 2)})

    moves = state.legal_moves_for_piece(Player.RED, 1)

    destinations = {move.to_pos for move in moves}
    assert Position(3, 2) not in destinations
    assert destinations == {Position(2, 3), Position(3, 3)}


def test_piece_can_capture_opponent_piece():
    state = make_state(red={1: Position(2, 2)}, blue={3: Position(3, 3)})

    moves = state.legal_moves_for_piece(Player.RED, 1)
    capture = next(move for move in moves if move.to_pos == Position(3, 3))

    assert capture.is_capture
    assert capture.captured_piece == Piece(
        player=Player.BLUE,
        piece_id=3,
        position=Position(3, 3),
        alive=True,
    )


def test_dice_selects_exact_living_piece():
    state = make_state(red={1: Position(0, 0), 3: Position(1, 1), 6: Position(2, 2)})

    assert state.legal_piece_ids(Player.RED, 3) == [3]


def test_dice_selects_nearest_living_piece_when_exact_piece_dead():
    state = make_state(red={1: Position(0, 0), 4: Position(1, 1), 6: Position(2, 2)})

    assert state.legal_piece_ids(Player.RED, 3) == [4]


def test_dice_selects_both_nearest_pieces_when_distance_ties():
    state = make_state(red={2: Position(0, 0), 4: Position(1, 1)})

    assert state.legal_piece_ids(Player.RED, 3) == [2, 4]


def test_all_legal_moves_are_limited_by_dice_selected_pieces():
    state = make_state(
        red={2: Position(1, 1), 4: Position(2, 2)},
        current_player=Player.RED,
    )

    moves = state.legal_moves(Player.RED, 3)

    assert {move.piece_id for move in moves} == {2, 4}


def test_invalid_position_rejected_when_creating_piece():
    with pytest.raises(ValueError):
        Piece(player=Player.RED, piece_id=1, position=Position(5, 0))
