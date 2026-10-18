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


def test_piece_can_capture_own_piece():
    """规则第 4 条：目标格上有棋子（含本方）则吃掉。吃本方棋子是合法策略。"""
    state = make_state(red={1: Position(2, 2), 2: Position(3, 2)})

    moves = state.legal_moves_for_piece(Player.RED, 1)

    destinations = {move.to_pos for move in moves}
    assert destinations == {Position(3, 2), Position(2, 3), Position(3, 3)}

    self_capture = next(move for move in moves if move.to_pos == Position(3, 2))
    assert self_capture.is_capture
    assert self_capture.captured_piece == Piece(
        player=Player.RED,
        piece_id=2,
        position=Position(3, 2),
        alive=True,
    )


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


def test_dice_selects_nearest_living_piece_on_each_side_when_exact_piece_dead():
    state = make_state(red={1: Position(0, 0), 4: Position(1, 1), 6: Position(2, 2)})

    assert state.legal_piece_ids(Player.RED, 3) == [1, 4]


def test_dice_selects_both_nearest_pieces_when_distance_ties():
    state = make_state(red={2: Position(0, 0), 4: Position(1, 1)})

    assert state.legal_piece_ids(Player.RED, 3) == [2, 4]


@pytest.mark.parametrize("player", [Player.RED, Player.BLUE])
def test_dice_matches_official_missing_four_and_five_example(player):
    state = make_state(
        red={1: Position(0, 0), 2: Position(0, 1), 3: Position(1, 0), 6: Position(1, 1)},
        blue={1: Position(4, 4), 2: Position(4, 3), 3: Position(3, 4), 6: Position(3, 3)},
        current_player=player,
    )

    # Rule 2 explicitly permits 3 OR 6 after a roll of 4 when 4 and 5 are gone.
    assert state.legal_piece_ids(player, 4) == [3, 6]
    assert {move.piece_id for move in state.legal_moves(player, 4)} == {3, 6}
    farther_move = next(move for move in state.legal_moves(player, 4) if move.piece_id == 6)
    before = state.serialize()
    state.apply_move(farther_move, dice=4)
    state.undo_move()
    assert state.serialize() == before


@pytest.mark.parametrize("alive_mask", range(64))
def test_dice_mapping_for_every_surviving_piece_set(alive_mask):
    positions = [Position(0, 0), Position(0, 1), Position(0, 2),
                 Position(1, 0), Position(1, 1), Position(2, 0)]
    state = make_state(red={piece_id: positions[piece_id - 1] for piece_id in range(1, 7)})
    alive_ids = {piece_id for piece_id in range(1, 7) if alive_mask & (1 << (piece_id - 1))}
    for piece_id, piece in state.pieces[Player.RED].items():
        piece.alive = piece_id in alive_ids

    for dice in range(1, 7):
        if dice in alive_ids:
            expected = [dice]
        else:
            below = next((candidate for candidate in range(dice - 1, 0, -1) if candidate in alive_ids), None)
            above = next((candidate for candidate in range(dice + 1, 7) if candidate in alive_ids), None)
            expected = [candidate for candidate in (below, above) if candidate is not None]
        assert state.legal_piece_ids(Player.RED, dice) == expected


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
