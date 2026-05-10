import random

import pytest

from ai import AIPlayer, RandomAI
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


from ai.greedy_ai import GreedyAI


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
    from ai.match import build_ai

    ai = build_ai("greedy", seed=2026)

    assert ai.name == "greedy"
    assert hasattr(ai, "choose_move")


def test_build_ai_supports_greedy_risk():
    from ai.match import ai_version_signature, build_ai

    ai = build_ai("greedy_risk", seed=2026)

    assert ai.name == "greedy_risk"
    assert ai.expected_risk_weight > 0
    assert ai.expected_win_risk_weight > ai.expected_risk_weight
    assert ai_version_signature(ai)["expected_risk_weight"] == ai.expected_risk_weight
    assert ai_version_signature(ai)["expected_win_risk_weight"] == ai.expected_win_risk_weight
