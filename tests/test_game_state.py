import pytest

from core.game_state import GameState
from core.move import Move
from core.types import Piece, Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


def test_piece_at_returns_living_piece_on_position():
    state = make_state(red={1: Position(0, 0)})

    piece = state.piece_at(Position(0, 0))

    assert piece is not None
    assert piece.player is Player.RED
    assert piece.piece_id == 1


def test_apply_capture_marks_opponent_piece_dead():
    state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    state.apply_move(move, dice=1)

    assert state.pieces[Player.BLUE][2].alive is False
    assert state.pieces[Player.BLUE][2].position == Position(3, 3)
    assert state.pieces[Player.RED][1].position == Position(3, 3)
    assert state.current_player is Player.BLUE


def test_apply_self_capture_marks_own_piece_dead():
    """规则第 4 条：自残合法。移动后本方被吃子 alive=False，移动棋子占据该格。"""
    state = make_state(red={1: Position(2, 2), 2: Position(3, 3)}, blue={6: Position(0, 4)})
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    state.apply_move(move, dice=1)

    assert move.is_capture
    assert state.pieces[Player.RED][2].alive is False
    assert state.pieces[Player.RED][1].position == Position(3, 3)
    assert state.current_player is Player.BLUE


def test_undo_after_capture_restores_complete_serialized_state():
    state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    before = state.serialize()
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    state.apply_move(move, dice=1)
    state.undo_move()

    assert state.serialize() == before


def test_undo_after_self_capture_restores_complete_serialized_state():
    """R-0 后自残合法；undo 必须把被吃的本方棋子恢复 alive 且原位、移动棋子回 from_pos。"""
    state = make_state(red={1: Position(2, 2), 2: Position(3, 3)}, blue={6: Position(0, 4)})
    before = state.serialize()
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    state.apply_move(move, dice=1)
    state.undo_move()

    assert state.serialize() == before


def test_arriving_at_target_corner_wins_immediately():
    state = make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4)})
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(4, 4))

    state.apply_move(move, dice=1)

    assert state.get_winner() is Player.RED


def test_capturing_all_opponent_pieces_wins_immediately():
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(3, 3)})
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    state.apply_move(move, dice=1)

    assert state.get_winner() is Player.RED


def test_undo_without_history_returns_none():
    state = make_state(red={1: Position(0, 0)})

    assert state.undo_move() is None


def test_apply_move_rejects_wrong_current_player():
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)}, current_player=Player.BLUE)
    move = state.legal_moves_for_piece(Player.RED, 1)[0]

    try:
        state.apply_move(move, dice=1)
    except ValueError as exc:
        assert "current player" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_apply_move_rejects_piece_not_selected_by_dice():
    state = make_state(red={1: Position(0, 0), 2: Position(2, 2)}, blue={6: Position(0, 4)})
    move = state.legal_moves_for_piece(Player.RED, 2)[0]

    with pytest.raises(ValueError, match="dice"):
        state.apply_move(move, dice=1)


def test_apply_move_rejects_malformed_move_with_wrong_piece_id():
    state = make_state(red={2: Position(2, 2), 4: Position(4, 3)}, blue={6: Position(0, 4)})
    malformed_move = Move(
        player=Player.RED,
        piece_id=4,
        from_pos=Position(2, 2),
        to_pos=Position(3, 2),
    )

    with pytest.raises(ValueError, match="move is not legal"):
        state.apply_move(malformed_move, dice=3)


def test_apply_move_rejects_moves_after_target_corner_win():
    state = make_state(red={1: Position(4, 4), 2: Position(0, 0)}, blue={1: Position(1, 1)})
    move = state.legal_moves_for_piece(Player.RED, 2)[0]

    with pytest.raises(ValueError, match="game is already finished"):
        state.apply_move(move, dice=2)


def test_apply_move_rejects_moves_after_capture_all_win():
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(3, 3)})
    winning_move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))
    state.apply_move(winning_move, dice=1)

    illegal_followup = Move(
        player=Player.BLUE,
        piece_id=1,
        from_pos=Position(3, 3),
        to_pos=Position(2, 2),
    )

    with pytest.raises(ValueError, match="game is already finished"):
        state.apply_move(illegal_followup, dice=1)


def test_mutating_returned_capture_move_does_not_corrupt_history():
    state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    move = next(move for move in state.legal_moves_for_piece(Player.RED, 1) if move.to_pos == Position(3, 3))

    applied = state.apply_move(move, dice=1)
    assert applied.captured_piece is not None
    applied.captured_piece.alive = True
    applied.captured_piece.position = Position(0, 0)

    state.undo_move()

    assert state.pieces[Player.BLUE][2].alive is True
    assert state.pieces[Player.BLUE][2].position == Position(3, 3)


def test_apply_move_canonicalizes_captured_piece_from_legal_move():
    state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    legal_move = next(
        move
        for move in state.legal_moves(Player.RED, 1)
        if move.to_pos == Position(3, 3)
    )
    forged_move = Move(
        player=legal_move.player,
        piece_id=legal_move.piece_id,
        from_pos=legal_move.from_pos,
        to_pos=legal_move.to_pos,
        is_capture=True,
        captured_piece=Piece(Player.BLUE, 2, Position(0, 0), alive=False),
    )

    applied = state.apply_move(forged_move, dice=1)

    assert applied.captured_piece is not None
    assert applied.captured_piece.position == Position(3, 3)
    assert applied.captured_piece.alive is True
    state.undo_move()
    assert state.pieces[Player.BLUE][2].position == Position(3, 3)
    assert state.pieces[Player.BLUE][2].alive is True


def test_apply_known_legal_move_matches_public_apply_for_legal_capture():
    public_state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    trusted_state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    public_move = next(
        move
        for move in public_state.legal_moves(Player.RED, 1)
        if move.to_pos == Position(3, 3)
    )
    trusted_move = next(
        move
        for move in trusted_state.legal_moves(Player.RED, 1)
        if move.to_pos == Position(3, 3)
    )

    public_applied = public_state.apply_move(public_move, dice=1)
    trusted_applied = trusted_state._apply_known_legal_move(trusted_move)

    assert trusted_state.serialize() == public_state.serialize()
    assert trusted_applied.to_dict() == public_applied.to_dict()
    public_state.undo_move()
    trusted_state.undo_move()
    assert trusted_state.serialize() == public_state.serialize()


def test_apply_known_legal_move_rejects_wrong_current_player():
    state = make_state(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.BLUE,
    )
    move = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    ).legal_moves(Player.RED, 1)[0]

    with pytest.raises(ValueError, match="current player"):
        state._apply_known_legal_move(move)


def test_apply_known_legal_move_rejects_stale_piece_position():
    state = make_state(current_player=Player.RED)
    move = Move(
        player=Player.RED,
        piece_id=1,
        from_pos=Position(1, 1),
        to_pos=Position(1, 2),
    )

    with pytest.raises(ValueError, match="known legal move is stale"):
        state._apply_known_legal_move(move)


def test_apply_known_legal_move_rejects_moves_after_win():
    state = make_state(
        red={1: Position(4, 4), 2: Position(0, 0)},
        blue={1: Position(1, 1)},
        current_player=Player.RED,
    )
    move = Move(
        player=Player.RED,
        piece_id=2,
        from_pos=Position(0, 0),
        to_pos=Position(1, 0),
    )

    with pytest.raises(ValueError, match="game is already finished"):
        state._apply_known_legal_move(move)


def test_from_layout_rejects_overlapping_living_pieces():
    with pytest.raises(ValueError, match="overlap"):
        GameState.from_layout(
            red={1: Position(0, 0)},
            blue={1: Position(0, 0)},
        )
