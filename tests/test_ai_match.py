import random

import pytest

from ai.match import MatchResult, default_starting_state
from core.types import Player, Position


def test_default_starting_state_has_six_pieces_per_side():
    state = default_starting_state()

    assert sum(1 for p in state.pieces[Player.RED].values() if p.alive) == 6
    assert sum(1 for p in state.pieces[Player.BLUE].values() if p.alive) == 6
    assert state.current_player is Player.RED


def test_default_starting_state_red_layout():
    state = default_starting_state()

    expected_red_positions = {
        1: Position(0, 0),
        2: Position(0, 1),
        3: Position(0, 2),
        4: Position(1, 0),
        5: Position(2, 0),
        6: Position(3, 1),
    }
    for piece_id, position in expected_red_positions.items():
        assert state.pieces[Player.RED][piece_id].position == position


def test_default_starting_state_blue_layout():
    state = default_starting_state()

    expected_blue_positions = {
        1: Position(4, 4),
        2: Position(4, 3),
        3: Position(4, 2),
        4: Position(3, 4),
        5: Position(2, 4),
        6: Position(1, 3),
    }
    for piece_id, position in expected_blue_positions.items():
        assert state.pieces[Player.BLUE][piece_id].position == position


def test_default_starting_state_no_piece_is_initially_stuck():
    from core.rules import generate_legal_moves_for_piece

    state = default_starting_state()
    for player_pieces in state.pieces.values():
        for piece in player_pieces.values():
            if piece.alive:
                moves = generate_legal_moves_for_piece(piece, state.piece_at)
                assert moves, (
                    f"piece {piece.player.value}/{piece.piece_id} at {piece.position} "
                    "should have at least one legal move"
                )


def test_default_starting_state_is_independent_per_call():
    state_a = default_starting_state()
    state_b = default_starting_state()
    state_a.pieces[Player.RED][1].alive = False

    assert state_b.pieces[Player.RED][1].alive is True


def test_starting_state_for_opening_preset_keeps_default_layout_unchanged():
    from ai.match import STARTING_LAYOUT_ID, starting_state_for
    from ai.opening_layouts import PRESETS

    default_state = starting_state_for(STARTING_LAYOUT_ID)
    preset_state = starting_state_for("balanced_v1")

    assert default_state.pieces[Player.RED][6].position == Position(3, 1)
    assert preset_state.pieces[Player.RED][6].position == PRESETS["balanced_v1"].red[6]
    assert preset_state.pieces[Player.BLUE][6].position == PRESETS["balanced_v1"].blue[6]


def test_match_result_step_time_aggregates():
    record_placeholder = None  # 暂用 None；play_one_game 测试会传真的 GameRecord
    result = MatchResult(
        winner=Player.RED,
        turns=3,
        illegal_moves=0,
        crashes=0,
        record=record_placeholder,
        step_times_ms=[1.0, 3.0, 2.0],
    )

    assert result.avg_step_time_ms == pytest.approx(2.0)
    assert result.max_step_time_ms == pytest.approx(3.0)


def test_match_result_step_time_aggregates_empty():
    result = MatchResult(
        winner=None,
        turns=0,
        illegal_moves=0,
        crashes=0,
        record=None,
        step_times_ms=[],
    )

    assert result.avg_step_time_ms == 0.0
    assert result.max_step_time_ms == 0.0


from ai.match import play_one_game
from ai.random_ai import RandomAI


class _AlwaysCrashAI:
    name = "crash_bot"

    def choose_move(self, state, dice):
        raise RuntimeError("boom")


class _IllegalMoveAI:
    """总是给出非法 Move（捏造一个不在 legal_moves 里的目的地）。"""

    name = "illegal_bot"

    def choose_move(self, state, dice):
        from core.move import Move
        from core.types import Position

        # 强行造一个出界的走法，apply_move 会抛 ValueError
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        sample = legal[0]
        return Move(
            player=sample.player,
            piece_id=sample.piece_id,
            from_pos=sample.from_pos,
            to_pos=Position(99, 99),
            is_capture=False,
            captured_piece=None,
        )


class _NeverMoveAI:
    name = "never_bot"

    def choose_move(self, state, dice):
        return None


class _ImmediateDeadlineAI:
    name = "deadline_bot"
    max_step_time_ms = 0.0

    def choose_move(self, state, dice):
        legal = state.legal_moves(state.current_player, dice)
        return legal[0] if legal else None


def test_play_one_game_random_vs_random_terminates_with_winner_or_draw():
    red_ai = RandomAI(rng=random.Random(2026))
    blue_ai = RandomAI(rng=random.Random(2027))
    dice_rng = random.Random(2028)

    result = play_one_game(red_ai=red_ai, blue_ai=blue_ai, dice_rng=dice_rng, max_turns=200)

    assert result.illegal_moves == 0
    assert result.crashes == 0
    assert 0 < result.turns <= 200
    assert result.record is not None
    assert len(result.record.steps) == result.turns


def test_play_one_game_is_deterministic_with_same_seeds():
    def run():
        return play_one_game(
            red_ai=RandomAI(rng=random.Random(2026)),
            blue_ai=RandomAI(rng=random.Random(2027)),
            dice_rng=random.Random(2028),
            max_turns=200,
        )

    a = run()
    b = run()

    assert a.winner == b.winner
    assert a.turns == b.turns
    assert [s.move.to_dict() for s in a.record.steps] == [s.move.to_dict() for s in b.record.steps]


def test_play_one_game_crash_is_counted_and_opponent_wins():
    result = play_one_game(
        red_ai=_AlwaysCrashAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    assert result.crashes == 1
    assert result.winner is Player.BLUE


def test_play_one_game_illegal_move_is_counted_and_opponent_wins():
    result = play_one_game(
        red_ai=_IllegalMoveAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    assert result.illegal_moves == 1
    assert result.winner is Player.BLUE


def test_play_one_game_no_legal_move_forfeits_to_opponent():
    result = play_one_game(
        red_ai=_NeverMoveAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    # 没合法走法返回 None：当前方判负，不计 illegal/crash
    assert result.crashes == 0
    assert result.illegal_moves == 0
    assert result.winner is Player.BLUE


def test_play_one_game_step_times_recorded():
    result = play_one_game(
        red_ai=RandomAI(rng=random.Random(2026)),
        blue_ai=RandomAI(rng=random.Random(2027)),
        dice_rng=random.Random(2028),
        max_turns=50,
    )

    # 每个 turn 都有 step_time，包含最终那一步
    assert len(result.step_times_ms) == result.turns
    assert all(t >= 0.0 for t in result.step_times_ms)


def test_play_one_game_counts_ai_step_deadline_timeouts():
    result = play_one_game(
        red_ai=_ImmediateDeadlineAI(),
        blue_ai=_ImmediateDeadlineAI(),
        dice_rng=random.Random(2028),
        max_turns=1,
    )

    assert result.timeouts == 1


from ai.match import build_ai


def test_build_ai_random_returns_random_ai():
    ai = build_ai("random", seed=42)
    assert ai.name == "random"
    assert hasattr(ai, "choose_move")


def test_build_ai_random_seeded_is_deterministic():
    ai_a = build_ai("random", seed=42)
    ai_b = build_ai("random", seed=42)
    state = default_starting_state()

    moves_a = [ai_a.choose_move(state, dice=d) for d in [1, 2, 3, 4, 5, 6]]
    moves_b = [ai_b.choose_move(state, dice=d) for d in [1, 2, 3, 4, 5, 6]]

    assert moves_a == moves_b


def test_build_ai_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="unknown AI"):
        build_ai("does_not_exist", seed=0)
