import random

import pytest

from ai.evaluator import WIN_SCORE, evaluate
from ai.expectimax_v2 import (
    EXPECTIMAX_V2_MAX_SCORE,
    EXPECTIMAX_V2_MIN_SCORE,
    ExpectimaxV2,
    expectimax_v2_order_moves,
    expectimax_v2_require_score_in_bounds,
    expectimax_v2_score_in_bounds,
    expectimax_v2_state_key,
    expectimax_v2_transposition_key,
)
from ai.greedy_ai import GreedyAI
from ai.match import default_starting_state
from core.game_state import GameState
from core.types import Player, Position


def _make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_expectimax_v2_depth_zero_matches_greedy_without_tie_randomness():
    state_a = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    state_b = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    expectimax = ExpectimaxV2(depth=0, rng=random.Random(1), randomize_ties=False)
    greedy = GreedyAI(rng=random.Random(1), randomize_ties=False)

    assert expectimax.choose_move(state_a, 1) == greedy.choose_move(state_b, 1)


def test_expectimax_v2_depth_one_considers_opponent_response():
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    ai = ExpectimaxV2(depth=1, rng=random.Random(1), randomize_ties=False, time_limit_ms=1000)

    move = ai.choose_move(state, 1)

    assert move is not None
    assert move.to_pos == Position(3, 2)


def test_expectimax_v2_does_not_mutate_state():
    state = default_starting_state()
    before = state.serialize()
    ai = ExpectimaxV2(depth=1, rng=random.Random(1), time_limit_ms=1000)

    ai.choose_move(state, 6)

    assert state.serialize() == before


def test_expectimax_v2_timeout_returns_legal_move():
    state = _make_state(
        red={1: Position(2, 2), 2: Position(2, 1), 3: Position(1, 2)},
        blue={1: Position(4, 4)},
    )
    ai = ExpectimaxV2(depth=2, rng=random.Random(1), time_limit_ms=0)

    move = ai.choose_move(state, 2)

    assert move in state.legal_moves(state.current_player, 2)


def test_expectimax_v2_state_key_is_stable_across_serialization_and_ignores_history():
    state = default_starting_state()
    move = state.legal_moves(Player.RED, 6)[0]
    state.apply_move(move, dice=6)

    restored_with_history = GameState.deserialize(state.serialize())
    restored_without_history = GameState.deserialize(state.serialize(include_history=False))

    assert expectimax_v2_state_key(state) == expectimax_v2_state_key(restored_with_history)
    assert expectimax_v2_state_key(state) == expectimax_v2_state_key(restored_without_history)


def test_expectimax_v2_state_key_includes_current_player():
    red_turn = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)}, current_player=Player.RED)
    blue_turn = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)}, current_player=Player.BLUE)

    assert expectimax_v2_state_key(red_turn) != expectimax_v2_state_key(blue_turn)


def test_expectimax_v2_transposition_key_includes_search_context():
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    base = expectimax_v2_transposition_key(
        state,
        node_type="chance",
        perspective=Player.RED,
        depth=1,
        dice=None,
    )

    assert base != expectimax_v2_transposition_key(
        state,
        node_type="turn",
        perspective=Player.RED,
        depth=1,
        dice=None,
    )
    assert base != expectimax_v2_transposition_key(
        state,
        node_type="chance",
        perspective=Player.BLUE,
        depth=1,
        dice=None,
    )
    assert base != expectimax_v2_transposition_key(
        state,
        node_type="chance",
        perspective=Player.RED,
        depth=2,
        dice=None,
    )
    assert base != expectimax_v2_transposition_key(
        state,
        node_type="chance",
        perspective=Player.RED,
        depth=1,
        dice=3,
    )
    assert base != expectimax_v2_transposition_key(
        state,
        node_type="chance",
        perspective=Player.RED,
        depth=1,
        dice=None,
        evaluator_version="alternate-leaf",
    )


def test_expectimax_v2_score_bounds_cover_current_evaluator_outputs():
    assert EXPECTIMAX_V2_MIN_SCORE == -WIN_SCORE
    assert EXPECTIMAX_V2_MAX_SCORE == WIN_SCORE

    non_terminal = _make_state(red={1: Position(2, 2), 2: Position(1, 1)}, blue={1: Position(4, 4)})
    red_win = _make_state(red={1: Position(4, 4)}, blue={1: Position(0, 4)})

    scores = [
        evaluate(non_terminal, perspective=Player.RED),
        evaluate(non_terminal, perspective=Player.BLUE),
        evaluate(red_win, perspective=Player.RED),
        evaluate(red_win, perspective=Player.BLUE),
    ]

    assert all(expectimax_v2_score_in_bounds(score) for score in scores)
    assert not expectimax_v2_score_in_bounds(WIN_SCORE + 1.0)
    assert not expectimax_v2_score_in_bounds(-WIN_SCORE - 1.0)


def test_expectimax_v2_require_score_in_bounds_rejects_out_of_range_values():
    assert expectimax_v2_require_score_in_bounds(42.0, context="unit") == 42.0

    with pytest.raises(ValueError, match="unit"):
        expectimax_v2_require_score_in_bounds(WIN_SCORE + 1.0, context="unit")


def test_expectimax_v2_rejects_out_of_bounds_leaf_evaluator_score(monkeypatch):
    monkeypatch.setattr("ai.expectimax_v2.evaluate", lambda *args, **kwargs: WIN_SCORE + 1.0)
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    ai = ExpectimaxV2(depth=1)

    with pytest.raises(ValueError, match="leaf"):
        ai._chance_value(state, perspective=Player.RED, depth=0, deadline=float("inf"))


def test_expectimax_v2_small_depth_unpruned_values_stay_inside_declared_bounds():
    positions = [
        default_starting_state(),
        _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)}),
        _make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4)}),
        _make_state(red={1: Position(4, 4)}, blue={1: Position(0, 4)}),
    ]

    for state in positions:
        for perspective in (Player.RED, Player.BLUE):
            for depth in range(3):
                ai = ExpectimaxV2(depth=depth, time_limit_ms=1000)
                value = ai._chance_value(
                    state,
                    perspective=perspective,
                    depth=depth,
                    deadline=float("inf"),
                )
                assert expectimax_v2_score_in_bounds(value)


def test_expectimax_v2_chance_pruning_is_explicit_and_disabled_by_default():
    ai = ExpectimaxV2()

    assert ai.chance_pruning == "none"
    assert ai.last_search_stats.chance_prunes == 0


def test_expectimax_v2_rejects_unknown_chance_pruning_mode():
    with pytest.raises(ValueError, match="chance_pruning"):
        ExpectimaxV2(chance_pruning="star2")


def test_expectimax_v2_star1_chance_path_matches_unpruned_small_depth_values():
    positions = [
        default_starting_state(),
        _make_state(red={1: Position(2, 2), 2: Position(1, 2)}, blue={1: Position(4, 4)}),
        _make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4), 2: Position(1, 4)}),
    ]

    for state in positions:
        for perspective in (Player.RED, Player.BLUE):
            for depth in (1, 2):
                plain = ExpectimaxV2(depth=depth, time_limit_ms=1000, chance_pruning="none")
                star1 = ExpectimaxV2(depth=depth, time_limit_ms=1000, chance_pruning="star1")

                plain_value = plain._chance_value(
                    state,
                    perspective=perspective,
                    depth=depth,
                    deadline=float("inf"),
                )
                star1_value = star1._chance_value(
                    state,
                    perspective=perspective,
                    depth=depth,
                    deadline=float("inf"),
                )

                assert star1_value == pytest.approx(plain_value)
                assert star1.last_search_stats.chance_prunes == 0


def test_expectimax_v2_star1_chance_path_matches_unpruned_choice_and_preserves_state():
    red = {1: Position(2, 2), 2: Position(1, 2), 3: Position(2, 1)}
    blue = {1: Position(4, 4), 2: Position(3, 4), 3: Position(4, 3)}
    plain_state = _make_state(red=red, blue=blue)
    star1_state = _make_state(red=red, blue=blue)
    plain_before = plain_state.serialize()
    star1_before = star1_state.serialize()
    plain = ExpectimaxV2(
        depth=2,
        randomize_ties=False,
        time_limit_ms=1000,
        use_transposition_table=True,
        move_ordering=True,
        chance_pruning="none",
    )
    star1 = ExpectimaxV2(
        depth=2,
        randomize_ties=False,
        time_limit_ms=1000,
        use_transposition_table=True,
        move_ordering=True,
        chance_pruning="star1",
    )

    assert star1.choose_move(star1_state, 2) == plain.choose_move(plain_state, 2)
    assert plain_state.serialize() == plain_before
    assert star1_state.serialize() == star1_before
    assert star1.last_search_stats.timed_out is False
    assert star1.last_search_stats.chance_prunes == 0


def test_expectimax_v2_star1_chance_path_prunes_when_upper_bound_cannot_reach_cutoff():
    class ScriptedChanceExpectimax(ExpectimaxV2):
        def __init__(self):
            super().__init__(depth=1, time_limit_ms=1000, chance_pruning="star1")
            self.dice_seen = []

        def _turn_value_with_status(self, state, *, dice, perspective, depth, deadline, table):
            del state, perspective, depth, deadline, table
            self.dice_seen.append(dice)
            return EXPECTIMAX_V2_MIN_SCORE, True

    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    ai = ScriptedChanceExpectimax()

    value, complete = ai._chance_value_with_status(
        state,
        perspective=Player.RED,
        depth=1,
        deadline=float("inf"),
        table=None,
        cutoff_upper_bound=EXPECTIMAX_V2_MAX_SCORE,
    )

    assert complete is False
    assert value < EXPECTIMAX_V2_MAX_SCORE
    assert ai.dice_seen == [1]
    assert ai.last_search_stats.chance_prunes == 5
    assert ai.last_search_stats.timed_out is False


def test_expectimax_v2_star1_root_pruning_preserves_choice_and_skips_losing_candidate_dice():
    class ScriptedRootPruningExpectimax(ExpectimaxV2):
        def __init__(self, *, chance_pruning):
            super().__init__(
                depth=1,
                time_limit_ms=1000,
                randomize_ties=False,
                chance_pruning=chance_pruning,
            )
            self.dice_seen_by_root_to = {}

        def _turn_value_with_status(self, state, *, dice, perspective, depth, deadline, table):
            del perspective, depth, deadline, table
            root_to = state.history[0].to_pos
            self.dice_seen_by_root_to.setdefault(root_to, []).append(dice)
            if root_to == self.preferred_to:
                return EXPECTIMAX_V2_MAX_SCORE, True
            return EXPECTIMAX_V2_MIN_SCORE, True

    plain_state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    star1_state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    plain_before = plain_state.serialize()
    star1_before = star1_state.serialize()
    preferred_to = plain_state.legal_moves(Player.RED, 1)[0].to_pos
    plain = ScriptedRootPruningExpectimax(chance_pruning="none")
    star1 = ScriptedRootPruningExpectimax(chance_pruning="star1")
    plain.preferred_to = preferred_to
    star1.preferred_to = preferred_to

    plain_move = plain.choose_move(plain_state, 1)
    star1_move = star1.choose_move(star1_state, 1)

    assert star1_move == plain_move
    assert star1_move.to_pos == preferred_to
    assert plain_state.serialize() == plain_before
    assert star1_state.serialize() == star1_before
    assert plain.last_search_stats.chance_prunes == 0
    assert star1.last_search_stats.chance_prunes > 0
    assert plain.dice_seen_by_root_to[preferred_to] == [1, 2, 3, 4, 5, 6]
    losing_root_to = [move.to_pos for move in plain_state.legal_moves(Player.RED, 1) if move.to_pos != preferred_to]
    assert any(star1.dice_seen_by_root_to[to_pos] == [1] for to_pos in losing_root_to)
    assert star1.last_search_stats.timed_out is False
    assert star1.last_search_stats.completed_depth == 1


def test_expectimax_v2_transposition_table_is_optional_and_disabled_by_default():
    ai = ExpectimaxV2()

    assert ai.use_transposition_table is False
    assert ai.last_search_stats.nodes == 0
    assert ai.last_search_stats.tt_hits == 0
    assert ai.last_search_stats.tt_stores == 0
    assert ai.last_search_stats.timed_out is False


def test_expectimax_v2_transposition_table_matches_unoptimized_search():
    red = {1: Position(2, 2), 2: Position(1, 2), 3: Position(2, 1)}
    blue = {1: Position(4, 4), 2: Position(3, 4), 3: Position(4, 3)}
    plain_state = _make_state(red=red, blue=blue)
    tt_state = _make_state(red=red, blue=blue)
    plain_before = plain_state.serialize()
    tt_before = tt_state.serialize()
    plain = ExpectimaxV2(depth=2, randomize_ties=False, time_limit_ms=1000)
    cached = ExpectimaxV2(
        depth=2,
        randomize_ties=False,
        time_limit_ms=1000,
        use_transposition_table=True,
    )

    assert cached.choose_move(tt_state, 2) == plain.choose_move(plain_state, 2)
    assert plain_state.serialize() == plain_before
    assert tt_state.serialize() == tt_before
    assert cached.last_search_stats.nodes > 0
    assert cached.last_search_stats.tt_stores > 0
    assert cached.last_search_stats.timed_out is False


def test_expectimax_v2_transposition_table_does_not_store_timeout_values():
    state = _make_state(
        red={1: Position(2, 2), 2: Position(2, 1), 3: Position(1, 2)},
        blue={1: Position(4, 4)},
    )
    ai = ExpectimaxV2(depth=2, time_limit_ms=0, use_transposition_table=True)

    move = ai.choose_move(state, 2)

    assert move in state.legal_moves(state.current_player, 2)
    assert ai.last_search_stats.timed_out is True
    assert ai.last_search_stats.tt_stores == 0


def test_expectimax_v2_move_ordering_is_optional_and_disabled_by_default():
    ai = ExpectimaxV2()

    assert ai.move_ordering is False


def test_expectimax_v2_order_moves_prioritizes_direct_win():
    state = _make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4)})
    moves = state.legal_moves(Player.RED, 1)

    ordered = expectimax_v2_order_moves(state, moves)

    assert ordered[0].to_pos == Position(4, 4)


def test_expectimax_v2_order_moves_prioritizes_enemy_capture_before_progress():
    state = _make_state(red={1: Position(2, 2)}, blue={5: Position(3, 2), 6: Position(4, 4)})
    moves = state.legal_moves(Player.RED, 1)

    ordered = expectimax_v2_order_moves(state, moves)

    assert ordered[0].to_pos == Position(3, 2)
    assert ordered[0].captured_piece is not None
    assert ordered[0].captured_piece.player is Player.BLUE


def test_expectimax_v2_order_moves_prefers_progress_toward_target():
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    moves = state.legal_moves(Player.RED, 1)

    ordered = expectimax_v2_order_moves(state, moves)

    assert ordered[0].to_pos == Position(3, 3)


def test_expectimax_v2_order_moves_preserves_original_order_for_equal_scores():
    state = _make_state(red={1: Position(0, 1)}, blue={1: Position(4, 4)})
    moves = state.legal_moves(Player.RED, 1)

    ordered = expectimax_v2_order_moves(state, moves)

    assert [move.to_pos for move in ordered if move.to_pos in {Position(1, 1), Position(1, 2)}] == [
        Position(1, 1),
        Position(1, 2),
    ]


def test_expectimax_v2_move_ordering_changes_traversal_but_preserves_tie_fallback():
    class ConstantValueExpectimax(ExpectimaxV2):
        def __init__(self):
            super().__init__(
                depth=1,
                time_limit_ms=1000,
                randomize_ties=False,
                move_ordering=True,
            )
            self.visited_root_moves = []

        def _chance_value_with_status(self, state, *, perspective, depth, deadline, table):
            self.visited_root_moves.append(state.history[-1].to_pos)
            return 0.0, True

    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    legal = state.legal_moves(Player.RED, 1)
    ai = ConstantValueExpectimax()

    move = ai.choose_move(state, 1)

    assert ai.visited_root_moves[0] == Position(3, 3)
    assert move == legal[0]


def test_expectimax_v2_move_ordering_matches_unordered_full_search():
    red = {1: Position(2, 2), 2: Position(1, 2), 3: Position(2, 1)}
    blue = {1: Position(4, 4), 2: Position(3, 4), 3: Position(4, 3)}
    plain_state = _make_state(red=red, blue=blue)
    ordered_state = _make_state(red=red, blue=blue)
    plain = ExpectimaxV2(depth=2, randomize_ties=False, time_limit_ms=1000)
    ordered = ExpectimaxV2(depth=2, randomize_ties=False, time_limit_ms=1000, move_ordering=True)

    assert ordered.choose_move(ordered_state, 2) == plain.choose_move(plain_state, 2)


def test_expectimax_v2_iterative_deepening_is_optional_and_disabled_by_default():
    ai = ExpectimaxV2()

    assert ai.iterative_deepening is False
    assert ai.last_search_stats.completed_depth == 0


class _ScriptedIterativeExpectimax(ExpectimaxV2):
    def __init__(self, outcomes, *, depth=3):
        super().__init__(
            depth=depth,
            time_limit_ms=1000,
            randomize_ties=False,
            iterative_deepening=True,
        )
        self.outcomes = outcomes
        self.depths_seen = []

    def _search_root_at_depth(self, state, *, legal, dice, perspective, depth, deadline, table):
        del state, legal, dice, perspective, deadline, table
        self.depths_seen.append(depth)
        moves, complete = self.outcomes[depth]
        if not complete:
            self.last_search_stats.timed_out = True
        return moves, complete


def test_expectimax_v2_iterative_deepening_returns_last_completed_depth(monkeypatch):
    times = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("ai.expectimax_v2.time.perf_counter", lambda: next(times))
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    legal = state.legal_moves(Player.RED, 1)
    ai = _ScriptedIterativeExpectimax(
        {
            1: ([legal[1]], True),
            2: ([legal[2]], True),
            3: ([legal[0]], True),
        },
        depth=3,
    )

    move = ai.choose_move(state, 1)

    assert move == legal[1]
    assert ai.depths_seen == [1]
    assert ai.last_search_stats.completed_depth == 1
    assert ai.last_search_stats.timed_out is True


def test_expectimax_v2_iterative_deepening_falls_back_when_no_depth_completes(monkeypatch):
    times = iter([0.0, 2.0])
    monkeypatch.setattr("ai.expectimax_v2.time.perf_counter", lambda: next(times))
    state = _make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    legal = state.legal_moves(Player.RED, 1)
    ai = _ScriptedIterativeExpectimax({1: ([legal[2]], True)}, depth=1)

    move = ai.choose_move(state, 1)

    assert move == legal[0]
    assert ai.depths_seen == []
    assert ai.last_search_stats.completed_depth == 0
    assert ai.last_search_stats.timed_out is True


def test_expectimax_v2_iterative_deepening_does_not_mutate_state():
    state = default_starting_state()
    before = state.serialize()
    ai = ExpectimaxV2(
        depth=2,
        randomize_ties=False,
        time_limit_ms=1000,
        iterative_deepening=True,
        use_transposition_table=True,
        move_ordering=True,
    )

    ai.choose_move(state, 6)

    assert state.serialize() == before
    assert ai.last_search_stats.completed_depth == 2
