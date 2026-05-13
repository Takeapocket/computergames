import random

from ai.expectimax_v2 import ExpectimaxV2
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
