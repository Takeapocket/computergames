"""Phase 1 MCTS 候选 AI 的单元测试。

设计依据：docs/superpowers/specs/2026-05-13-mcts-phase1-design.md 第 10 节。
"""
from __future__ import annotations

import random

from ai.match import build_ai, default_starting_state
from ai.mcts import MCTSAI, mcts_choose_move
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


def _new_ai(*, seed: int = 0, max_iterations: int = 64, time_limit_ms: float = 10_000.0) -> MCTSAI:
    """构造一个可复现、不会因机器忙就提前退出的 MCTSAI 测试实例。"""
    return MCTSAI(
        time_limit_ms=time_limit_ms,
        max_iterations=max_iterations,
        rng=random.Random(seed),
    )


def test_mcts_returns_legal_move_from_default_state():
    state = default_starting_state()
    ai = _new_ai(seed=2026)

    move = ai.choose_move(state, 6)

    assert move is not None
    legal = state.legal_moves(state.current_player, 6)
    assert move in legal


def test_mcts_does_not_mutate_state():
    state = default_starting_state()
    before = state.serialize()

    ai = _new_ai(seed=1)
    ai.choose_move(state, 4)

    assert state.serialize() == before


def test_mcts_returns_none_when_no_legal_moves():
    # 与 rollout_ai 测试同样的最小局面：双方各一枚棋子，红方 piece 1 已在自家角，
    # dice=1 触发 piece 1 但 (1,0)/(0,1)/(1,1) 在这个布局下没法走。
    state = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    # 终局已判定（红 piece 1 在 (4,4) 是红的 target_corner）→ 算红胜，没有 legal_moves。
    # 这里直接验证 MCTS 也返回 None：state.legal_moves 为空。
    assert state.legal_moves(state.current_player, 1) == []

    ai = _new_ai(seed=0)
    assert ai.choose_move(state, 1) is None


def test_mcts_short_circuits_when_only_one_legal_move():
    # 单一合法走法（且这步直接胜）→ 应立即返回，无需迭代。
    state = GameState.from_layout(
        red={1: Position(4, 3)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(state.current_player, 1)
    assert len(legal) == 1
    assert legal[0].to_pos == Position(4, 4)  # 红角点 = 胜

    ai = _new_ai(seed=7, max_iterations=1024)
    move = ai.choose_move(state, 1)

    assert move == legal[0]
    assert ai.last_iterations == 0  # 单一走法直接短路


def test_mcts_finds_immediate_winning_move_among_alternatives():
    # 红 piece 1 在 (3,3)，dice=1 强制选 piece 1。
    # 合法走法 (4,3)/(3,4)/(4,4)；其中 (4,4) 是红方目标角，直接胜。
    state = GameState.from_layout(
        red={1: Position(3, 3)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(state.current_player, 1)
    assert {m.to_pos for m in legal} == {Position(4, 3), Position(3, 4), Position(4, 4)}

    # 用充足迭代验证 MCTS 收敛到胜招。
    ai = _new_ai(seed=42, max_iterations=128)
    move = ai.choose_move(state, 1)

    assert move is not None
    assert move.to_pos == Position(4, 4)


def test_mcts_is_deterministic_with_same_seed():
    state_a = default_starting_state()
    state_b = default_starting_state()
    ai_a = _new_ai(seed=2026)
    ai_b = _new_ai(seed=2026)

    move_a = ai_a.choose_move(state_a, 6)
    move_b = ai_b.choose_move(state_b, 6)

    assert move_a == move_b


def test_mcts_timeout_returns_legal_move_without_crash():
    state = default_starting_state()
    # 极小时间预算：可能跑不到 1 次完整迭代，但必须有 fallback 不抛异常、不返回 None。
    ai = MCTSAI(time_limit_ms=0.0, rng=random.Random(3))

    move = ai.choose_move(state, 6)

    assert move is not None
    assert move in state.legal_moves(state.current_player, 6)


def test_mcts_never_returns_illegal_move_over_many_states():
    rng = random.Random(99)
    state = default_starting_state()
    ai = _new_ai(seed=11, max_iterations=32)

    # 用随机骰子走若干步，每一步都 MCTS 选招；保证每个返回都是合法的。
    for _ in range(30):
        winner = state.get_winner()
        if winner is not None:
            break
        dice = rng.randint(1, 6)
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            break
        move = ai.choose_move(state, dice)
        assert move is not None
        assert move in legal
        state.apply_move(move, dice=dice)


def test_mcts_root_visit_counts_match_iteration_count():
    state = default_starting_state()
    ai = _new_ai(seed=5, max_iterations=50)

    # 走一手让结构有变；任何合法选招都行。
    ai.choose_move(state, 3)

    assert ai.last_iterations == 50
    assert ai.last_max_depth >= 1


def test_mcts_choose_move_function_equivalent_to_class():
    state = default_starting_state()
    a = MCTSAI(time_limit_ms=10_000.0, max_iterations=32, rng=random.Random(8))
    move_class = a.choose_move(state, 5)
    move_fn = mcts_choose_move(
        state,
        5,
        time_limit_ms=10_000.0,
        max_iterations=32,
        rng=random.Random(8),
    )
    assert move_class == move_fn


def test_build_ai_mcts_eval_v1():
    ai = build_ai("mcts_eval_v1", seed=42)
    assert isinstance(ai, MCTSAI)
    assert ai.name == "mcts_eval_v1"
    # 必备字段能被 ai_version_signature 拿到
    assert hasattr(ai, "time_limit_ms")
    assert hasattr(ai, "c_uct")
    assert hasattr(ai, "scale")


def test_build_ai_mcts_eval_v1_accepts_kwargs():
    ai = build_ai(
        "mcts_eval_v1",
        seed=42,
        time_limit_ms=123.0,
        c_uct=1.0,
        scale=50.0,
        max_iterations=10,
    )
    assert isinstance(ai, MCTSAI)
    assert ai.time_limit_ms == 123.0
    assert ai.c_uct == 1.0
    assert ai.scale == 50.0
    assert ai.max_iterations == 10


def test_mcts_returns_legal_move_for_every_dice_from_default_state():
    state = default_starting_state()
    for dice in range(1, 7):
        ai = _new_ai(seed=dice, max_iterations=16)
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            assert ai.choose_move(state, dice) is None
            continue
        move = ai.choose_move(state, dice)
        assert move in legal


def test_mcts_returns_move_object_compatible_with_apply_move():
    state = default_starting_state()
    ai = _new_ai(seed=13)

    move = ai.choose_move(state, 4)
    assert isinstance(move, Move)
    # 应用回原 state（拷贝防污染）
    sim = GameState.deserialize(state.serialize())
    applied = sim.apply_move(move, dice=4)
    assert applied.player is Player.RED
