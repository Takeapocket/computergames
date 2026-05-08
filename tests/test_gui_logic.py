from core.move import Move
from core.types import BOARD_SIZE, Player, Position
from gui.app import create_default_state, format_move_label


def test_default_state_has_full_non_overlapping_layout():
    state = create_default_state()

    assert state.current_player is Player.RED
    assert len(state.pieces[Player.RED]) == 6
    assert len(state.pieces[Player.BLUE]) == 6

    living_positions = [
        piece.position
        for player_pieces in state.pieces.values()
        for piece in player_pieces.values()
        if piece.alive
    ]
    assert len(living_positions) == 12
    assert len(set(living_positions)) == len(living_positions)
    assert all(0 <= position.row < BOARD_SIZE and 0 <= position.col < BOARD_SIZE for position in living_positions)


def test_default_state_generates_initial_legal_moves():
    state = create_default_state()

    assert state.legal_piece_ids(Player.RED, 6) == [6]
    moves = state.legal_moves(Player.RED, 6)

    assert moves
    assert all(move.player is Player.RED for move in moves)
    assert all(move.piece_id == 6 for move in moves)


def test_format_move_label_describes_normal_move():
    move = Move(
        player=Player.RED,
        piece_id=3,
        from_pos=Position(2, 2),
        to_pos=Position(3, 2),
    )

    assert format_move_label(move) == "红方 3: (2,2) -> (3,2)"


def test_format_move_label_describes_capture_move():
    move = Move(
        player=Player.BLUE,
        piece_id=4,
        from_pos=Position(3, 3),
        to_pos=Position(2, 2),
        is_capture=True,
    )

    assert format_move_label(move) == "蓝方 4: (3,3) -> (2,2) 吃子"
