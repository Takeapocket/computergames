import random

from ai.match import default_starting_state
from ai.rollout_ai import RolloutAI
from core.game_state import GameState
from core.types import Player, Position


def test_rollout_ai_returns_legal_move():
    state = default_starting_state()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)


def test_rollout_ai_does_not_mutate_state():
    state = default_starting_state()
    before = state.serialize()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    ai.choose_move(state, 6)

    assert state.serialize() == before


def test_rollout_ai_is_deterministic_with_same_seed():
    state_a = default_starting_state()
    state_b = default_starting_state()
    ai_a = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))
    ai_b = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))

    assert ai_a.choose_move(state_a, 6) == ai_b.choose_move(state_b, 6)


def test_rollout_ai_returns_none_when_no_legal_moves():
    state = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    assert ai.choose_move(state, 1) is None


def test_rollout_ai_timeout_fallback_returns_legal_move():
    state = default_starting_state()
    ai = RolloutAI(rollouts_per_move=1000, max_rollout_turns=100, max_step_time_ms=0, rng=random.Random(2))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
    assert ai.fallback_count >= 1
