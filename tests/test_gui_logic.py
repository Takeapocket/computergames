from core.move import Move
from core.types import BOARD_SIZE, Piece, Player, Position
from gui.app import create_default_state, format_move_label
from gui.main_window import MainWindow
from gui.timer_panel import format_seconds


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


def test_format_move_label_can_describe_self_capture():
    move = Move(
        player=Player.RED,
        piece_id=5,
        from_pos=Position(2, 1),
        to_pos=Position(2, 2),
        is_capture=True,
        captured_piece=Piece(Player.RED, 2, Position(2, 2)),
    )

    assert format_move_label(move) == "红方 5: (2,1) -> (2,2) 吃子"
    assert format_move_label(move, distinguish_self_capture=True) == "红方 5: (2,1) -> (2,2) 自吃"


def test_recommendation_text_marks_low_confidence():
    move = Move(
        player=Player.RED,
        piece_id=5,
        from_pos=Position(2, 1),
        to_pos=Position(2, 2),
        is_capture=True,
        captured_piece=Piece(Player.RED, 2, Position(2, 2)),
    )

    class FakeRecommender:
        last_diagnostics = []
        last_low_confidence = True
        last_score_margin = 0.03

    class FakeWindow:
        _awaiting_dice = False
        _recommender = FakeRecommender()

        def _recommended_move(self):
            return move

    text = MainWindow._recommendation_text(FakeWindow(), None)

    assert "rollout：红方 5: (2,1) -> (2,2) 自吃" in text
    assert "置信：低" in text
    assert "0.03" in text


def test_recommendation_text_prefers_root_stats_over_legacy_diagnostics():
    move = Move(
        player=Player.RED,
        piece_id=5,
        from_pos=Position(2, 1),
        to_pos=Position(3, 1),
        is_capture=False,
    )
    stale = Move(
        player=Player.RED,
        piece_id=6,
        from_pos=Position(2, 0),
        to_pos=Position(3, 0),
        is_capture=False,
    )

    class FakeStats:
        def __init__(self):
            self.move = move
            self.visits = 8
            self.wins = 3.0
            self.losses = 4.0
            self.draws = 1.0
            self.cutoffs = 1.0
            self.score = 0.4375
            self.winrate = 0.375
            self.avg = -0.125
            self.low_confidence = True

    class StaleStats:
        def __init__(self):
            self.move = stale
            self.visits = 1
            self.wins = 1.0
            self.losses = 0.0
            self.draws = 0.0
            self.cutoffs = 0.0
            self.score = 1.0
            self.winrate = 1.0
            self.avg = 1.0

    class FakeRecommender:
        last_root_stats = [FakeStats()]
        last_diagnostics = [StaleStats()]
        last_low_confidence = False
        last_timed_out = False

    class FakeWindow:
        _awaiting_dice = False
        _recommender = FakeRecommender()

        def _recommended_move(self):
            return move

    text = MainWindow._recommendation_text(FakeWindow(), None)

    assert "红方 5: (2,1) -> (3,1)" in text
    assert "红方 6: (2,0) -> (3,0)" not in text
    assert "wins=3" in text
    assert "losses=4" in text
    assert "draws=1" in text
    assert "置信=低" in text


def test_format_seconds_rounds_up_to_be_kind_to_player():
    assert format_seconds(240) == "04:00"
    assert format_seconds(239.4) == "04:00"
    assert format_seconds(0.6) == "00:01"
    assert format_seconds(0) == "00:00"
    assert format_seconds(-3) == "00:00"
