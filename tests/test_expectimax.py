import random

import pytest

from ai.expectimax_ai import ExpectimaxAI
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


# --- protocol ---


def test_expectimax_satisfies_aiplayer_shape():
    ai = ExpectimaxAI(depth=1, rng=random.Random(0))
    assert ai.name == "expectimax"
    assert hasattr(ai, "choose_move")
    assert callable(ai.choose_move)


def test_expectimax_returns_none_when_no_legal_moves():
    ai = ExpectimaxAI(depth=1, rng=random.Random(0))
    state = make_state(red={}, blue={1: Position(0, 0)}, current_player=Player.RED)
    assert ai.choose_move(state, dice=1) is None


# --- basic behavior ---


def test_expectimax_picks_winning_move():
    state = make_state(
        red={6: Position(4, 3), 1: Position(0, 0)},
        blue={1: Position(0, 4)},
    )
    ai = ExpectimaxAI(depth=1, rng=random.Random(0))

    move = ai.choose_move(state, dice=6)

    assert move is not None
    assert move.to_pos == Position(4, 4)


def test_expectimax_does_not_mutate_state():
    state = make_state(red={1: Position(2, 2), 2: Position(3, 1)}, blue={1: Position(0, 4)})
    before = state.serialize()
    ai = ExpectimaxAI(depth=1, rng=random.Random(0))

    ai.choose_move(state, dice=1)
    ai.choose_move(state, dice=2)

    assert state.serialize() == before


def test_expectimax_is_deterministic():
    state = make_state(red={1: Position(0, 0), 2: Position(1, 1)}, blue={1: Position(4, 4)})

    a = ExpectimaxAI(depth=1, rng=random.Random(42))
    b = ExpectimaxAI(depth=1, rng=random.Random(42))

    assert a.choose_move(state, dice=1) == b.choose_move(state, dice=1)
    assert a.choose_move(state, dice=2) == b.choose_move(state, dice=2)


# --- depth behavior ---


def test_expectimax_depth_zero_equivalent_to_greedy():
    """depth=0 时只评估自己走完后的局面，不枚举对手回应。"""
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    ai = ExpectimaxAI(depth=0, rng=random.Random(0))

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.player is Player.RED
    assert move in state.legal_moves(Player.RED, 1)


def test_expectimax_depth_rejects_negative():
    with pytest.raises(ValueError, match="depth"):
        ExpectimaxAI(depth=-1)


# --- threat avoidance (depth=1 key advantage) ---


def test_expectimax_depth1_avoids_leaving_piece_exposed_to_capture():
    """红 3 在 (2,2)，dice=3。合法走法：(3,2), (2,3), (3,3)。
    蓝 2 在 (4,2) 可 up → (3,2) 吃红 3。
    (3,2) 暴露被吃风险，(2,3) 和 (3,3) 安全。
    Expectimax depth=1 应避免 (3,2)。
    """
    state = make_state(
        red={3: Position(2, 2)},
        blue={2: Position(4, 2)},
    )
    ai = ExpectimaxAI(
        depth=1,
        rng=random.Random(0),
        expected_risk_weight=3.0,
        expected_win_risk_weight=500.0,
    )

    move = ai.choose_move(state, dice=3)

    assert move is not None
    assert move.to_pos != Position(3, 2), "should avoid exposing piece to capture"


def test_expectimax_depth1_with_risk_eval_avoids_opponent_win_path():
    """蓝 1 在 (0,1)，蓝目标 (0,0)→蓝可 left 一步到 (0,0) 获胜。
    红 3 在 (1,0)，dice=3。合法走法：(2,0), (1,1), (2,1)。
    这三种走法都无法阻止蓝一步获胜——无论红走什么，蓝 dice=1 都能到 (0,0)。
    但带 risk 评估的 Expectimax 应至少能正确返回合法走法，不崩溃。
    """
    state = make_state(
        red={3: Position(1, 0)},
        blue={1: Position(0, 1)},
    )
    ai = ExpectimaxAI(
        depth=1,
        rng=random.Random(0),
        expected_risk_weight=3.0,
        expected_win_risk_weight=500.0,
    )

    move = ai.choose_move(state, dice=3)

    assert move is not None
    assert move in state.legal_moves(Player.RED, 3)


def test_expectimax_custom_depth():
    ai = ExpectimaxAI(depth=2, rng=random.Random(0))
    assert ai.depth == 2


# --- timeout fallback uses RNG ---


def test_expectimax_timeout_uses_rng_when_no_moves_scored():
    """deadline 在任何 move 评分前触发 → fallback 必须用 RNG，不能确定性返回 legal[0]。"""
    state = make_state(
        red={1: Position(2, 2), 2: Position(2, 1), 3: Position(1, 2)},
        blue={1: Position(4, 4)},
    )
    dice = 2
    legal = state.legal_moves(Player.RED, dice)
    assert len(legal) > 1, "测试要求 >1 条合法走法以观测随机性"

    # 负的 time_limit_ms ⇒ deadline 已过去 ⇒ 第一个 move 还没评分就 break
    moves_seen = set()
    for seed in range(8):
        ai = ExpectimaxAI(depth=1, rng=random.Random(seed), time_limit_ms=-1.0)
        move = ai.choose_move(state, dice)
        assert move is not None
        assert move in legal
        moves_seen.add((move.piece_id, move.to_pos))

    assert len(moves_seen) >= 2, f"timeout fallback 似乎是确定性的，看到的走法集合={moves_seen}"


# --- randomize_ties toggle ---


def test_expectimax_randomize_ties_false_is_deterministic_across_rngs():
    """randomize_ties=False 时不咨询 RNG，不同 seed 应产生相同走法。"""
    state = make_state(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
    )

    ai_a = ExpectimaxAI(depth=1, randomize_ties=False, rng=random.Random(0))
    ai_b = ExpectimaxAI(depth=1, randomize_ties=False, rng=random.Random(999))

    move_a = ai_a.choose_move(state, dice=1)
    move_b = ai_b.choose_move(state, dice=1)

    assert move_a == move_b


def test_expectimax_default_randomize_ties_is_true():
    ai = ExpectimaxAI(depth=1, rng=random.Random(0))
    assert ai.randomize_ties is True
