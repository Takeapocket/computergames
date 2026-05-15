import random

import pytest

from ai import AIPlayer, RandomAI
from ai.greedy_ai import GreedyAI
from ai.match import ai_version_signature, build_ai
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_random_ai_satisfies_aiplayer_shape():
    # AIPlayer 是 typing.Protocol（无 @runtime_checkable），不能用 isinstance；
    # 这里用结构性检查保证字段齐全且可调用。
    ai = RandomAI(rng=random.Random(0))
    assert ai.name == "random"
    assert hasattr(ai, "choose_move")
    assert callable(ai.choose_move)
    # 同时确认 AIPlayer 这个名字被导出（仅作 import smoke）
    assert AIPlayer is not None


def test_random_ai_choose_move_returns_legal_move():
    ai = RandomAI(rng=random.Random(0))
    state = make_state(red={1: Position(2, 2)})

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.player is Player.RED
    legal = state.legal_moves(Player.RED, 1)
    assert move in legal


def test_random_ai_returns_none_when_no_legal_moves():
    ai = RandomAI(rng=random.Random(0))
    state = make_state(red={}, blue={1: Position(0, 0)}, current_player=Player.RED)

    assert ai.choose_move(state, dice=1) is None


def test_random_ai_is_deterministic_under_same_seed():
    state = make_state(red={1: Position(0, 0), 2: Position(1, 1), 3: Position(2, 2)})

    ai_a = RandomAI(rng=random.Random(2026))
    ai_b = RandomAI(rng=random.Random(2026))

    moves_a = [ai_a.choose_move(state, dice=d) for d in [1, 2, 3, 1, 2, 3]]
    moves_b = [ai_b.choose_move(state, dice=d) for d in [1, 2, 3, 1, 2, 3]]

    assert moves_a == moves_b


def test_random_ai_custom_name():
    ai = RandomAI(rng=random.Random(0), name="random_v2")
    assert ai.name == "random_v2"


def test_greedy_ai_is_protocol_compatible():
    ai = GreedyAI(rng=random.Random(0))
    assert ai.name == "greedy"
    assert hasattr(ai, "choose_move")


def test_greedy_ai_picks_winning_move_when_available():
    # 红 6 号在 (4,3)，dice=6 → 必走 6 号；(4,4) 是目标角并且空，应选这步胜
    state = make_state(
        red={6: Position(4, 3), 1: Position(0, 0)},
        blue={1: Position(0, 4)},
    )
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=6)

    assert move is not None
    assert move.to_pos == Position(4, 4)


def test_greedy_ai_picks_capture_when_capture_also_advances():
    # 红 1 号在 (3,3)，蓝 5 号在 (4,4)：吃掉蓝 5 号既到目标角也吃子，必选
    state = make_state(red={1: Position(3, 3)}, blue={5: Position(4, 4)})
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.to_pos == Position(4, 4)
    assert move.is_capture is True


def test_greedy_ai_prefers_advancing_toward_target():
    # 红 1 号在 (2,2)，dice=1，三个合法走法：
    #   (3,2) 距(4,4)=2、(2,3) 距(4,4)=2、(3,3) 距(4,4)=1
    # GreedyAI 应选 (3,3)
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.to_pos == Position(3, 3)


def test_greedy_ai_returns_none_when_no_legal_moves():
    state = make_state(red={}, blue={1: Position(4, 4)}, current_player=Player.RED)
    ai = GreedyAI(rng=random.Random(0))

    assert ai.choose_move(state, dice=1) is None


def test_greedy_ai_does_not_mutate_state():
    state = make_state(red={1: Position(2, 2), 2: Position(3, 1)}, blue={1: Position(0, 4)})
    before = state.serialize()
    ai = GreedyAI(rng=random.Random(0))

    ai.choose_move(state, dice=1)
    ai.choose_move(state, dice=2)

    assert state.serialize() == before


def test_greedy_ai_is_deterministic_under_same_seed():
    state = make_state(red={1: Position(0, 0), 2: Position(1, 1)}, blue={1: Position(4, 4)})

    a = GreedyAI(rng=random.Random(42))
    b = GreedyAI(rng=random.Random(42))

    assert a.choose_move(state, dice=1) == b.choose_move(state, dice=1)
    assert a.choose_move(state, dice=2) == b.choose_move(state, dice=2)


def test_greedy_ai_randomize_ties_false_returns_first_best_move():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    ai = GreedyAI(rng=random.Random(0), randomize_ties=False, distance_weight=0.0)

    move = ai.choose_move(state, dice=1)

    assert move == state.legal_moves(Player.RED, 1)[0]


def test_greedy_ai_expected_risk_avoids_simple_capture_exposure():
    state = make_state(
        red={1: Position(1, 1)},
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(3, 4),
            4: Position(3, 3),
            5: Position(4, 0),
            6: Position(0, 4),
        },
    )

    baseline = GreedyAI(rng=random.Random(0), randomize_ties=False, expected_risk_weight=0.0)
    risk_aware = GreedyAI(rng=random.Random(0), randomize_ties=False, expected_risk_weight=60.0)

    assert baseline.choose_move(state, dice=1).to_pos == Position(2, 2)
    assert risk_aware.choose_move(state, dice=1).to_pos != Position(2, 2)


def test_build_ai_supports_greedy():
    ai = build_ai("greedy", seed=2026)

    assert ai.name == "greedy"
    assert hasattr(ai, "choose_move")


def test_build_ai_supports_greedy_risk():
    ai = build_ai("greedy_risk", seed=2026)

    assert ai.name == "greedy_risk"
    assert ai.expected_risk_weight > 0
    assert ai.expected_win_risk_weight > ai.expected_risk_weight
    assert ai_version_signature(ai)["expected_risk_weight"] == ai.expected_risk_weight
    assert ai_version_signature(ai)["expected_win_risk_weight"] == ai.expected_win_risk_weight


def test_build_ai_rollout_default_keeps_flat_release_baseline():
    ai = build_ai("rollout", seed=1)
    signature = ai_version_signature(ai)

    assert ai.rollouts_per_move == 16
    assert ai.close_sample_rollouts_per_move == 16
    assert signature["rollouts_per_move"] == 16
    assert signature["close_sample_rollouts_per_move"] == 16


def test_build_ai_rollout_registers_signature_fields():
    ai = build_ai(
        "rollout",
        seed=1,
        rollouts_per_move=3,
        max_rollout_turns=9,
        max_step_time_ms=250,
        epsilon=0.2,
        close_sample_margin=0.12,
        close_sample_rollouts_per_move=11,
        low_confidence_margin=0.07,
    )
    signature = ai_version_signature(ai)

    assert ai.name == "rollout"
    assert ai.rollouts_per_move == 3
    assert ai.max_rollout_turns == 9
    assert ai.max_step_time_ms == 250.0
    assert ai.epsilon == 0.2
    assert ai.close_sample_margin == 0.12
    assert ai.close_sample_rollouts_per_move == 11
    assert ai.low_confidence_margin == 0.07
    assert signature["name"] == "rollout"
    assert signature["rollouts_per_move"] == 3
    assert signature["max_rollout_turns"] == 9
    assert signature["max_step_time_ms"] == 250.0
    assert signature["epsilon"] == 0.2
    assert signature["close_sample_margin"] == 0.12
    assert signature["close_sample_rollouts_per_move"] == 11
    assert signature["low_confidence_margin"] == 0.07


def test_build_ai_rollout_candidates_register_expected_defaults():
    cases = {
        "rollout_32": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.15,
            "playout_policy": "greedy",
            "cutoff_eval": "draw",
        },
        "rollout_risk_playout": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.10,
            "playout_policy": "greedy_risk",
            "cutoff_eval": "draw",
        },
        "rollout_cutoff_eval": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.10,
            "playout_policy": "greedy_risk",
            "cutoff_eval": "current",
        },
    }
    for kind, expected in cases.items():
        ai = build_ai(kind, seed=1)
        signature = ai_version_signature(ai)

        assert ai.name == kind
        for key, value in expected.items():
            assert getattr(ai, key) == value
            assert signature[key] == value


def test_build_ai_rollout_candidate_kwargs_can_override_defaults():
    ai = build_ai("rollout_32", seed=1, rollouts_per_move=2, max_step_time_ms=20)

    assert ai.rollouts_per_move == 2
    assert ai.max_step_time_ms == 20.0


def test_build_ai_expectimax_v2_registers_signature_fields():
    ai = build_ai("expectimax_v2", seed=1, depth=2, time_limit_ms=300, randomize_ties=False)
    signature = ai_version_signature(ai)

    assert signature["name"] == "expectimax_v2"
    assert signature["depth"] == 2
    assert signature["time_limit_ms"] == 300.0
    assert signature["randomize_ties"] is False
    assert signature["expected_risk_weight"] == 0.0
    assert signature["expected_win_risk_weight"] == 0.0
