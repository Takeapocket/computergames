"""evaluator 权重参数化 + GreedyAI 透传，让 reproducer 可以用
``GreedyAI(stuck_penalty=0)`` 复现 4.1 baseline (0.59)。
"""

from __future__ import annotations

import random

from ai.evaluator import (
    DISTANCE_WEIGHT,
    MATERIAL_WEIGHT,
    STUCK_PIECE_PENALTY,
    count_stuck_pieces,
    evaluate,
)
from ai.greedy_ai import GreedyAI
from ai.match import ai_version_signature, build_ai
from core.game_state import GameState
from core.types import Player, Position


def _state_with_one_red_stuck() -> GameState:
    # R-0 后规则允许吃本方棋子：该状态不再有 stuck piece（piece 1 可向 2/3/4 自残脱困）。
    # 保留函数名以最小化改动；count_stuck_pieces 在该状态下应返回 0。
    return GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )


# --- evaluator 权重参数化 -----------------------------------------------------


def test_evaluate_accepts_stuck_penalty_kwarg_and_zero_disables_penalty() -> None:
    state = _state_with_one_red_stuck()
    # R-0 后 count_stuck_pieces 在非终局状态下基本恒为 0；stuck_penalty kwarg 仍被接受，
    # 但实际乘法结果恒为 0。本测试退化为契约测试：kwarg 不引发异常且 0 与默认值产生相同分数。
    assert count_stuck_pieces(state, Player.RED) == 0

    default_score = evaluate(state, Player.RED)
    no_penalty_score = evaluate(state, Player.RED, stuck_penalty=0.0)

    assert no_penalty_score == default_score


def test_evaluate_accepts_distance_and_material_weight_kwargs() -> None:
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )

    base = evaluate(state, Player.RED)
    doubled_distance = evaluate(
        state,
        Player.RED,
        distance_weight=DISTANCE_WEIGHT * 2,
        material_weight=MATERIAL_WEIGHT,
    )

    assert doubled_distance != base


# --- GreedyAI 字段 ------------------------------------------------------------


def test_greedy_ai_default_weights_match_module_constants() -> None:
    ai = GreedyAI()

    assert ai.stuck_penalty == STUCK_PIECE_PENALTY
    assert ai.distance_weight == DISTANCE_WEIGHT
    assert ai.material_weight == MATERIAL_WEIGHT


def test_greedy_ai_accepts_zero_stuck_penalty() -> None:
    ai = GreedyAI(stuck_penalty=0.0)

    assert ai.stuck_penalty == 0.0
    assert ai.distance_weight == DISTANCE_WEIGHT


def test_greedy_ai_forwards_weights_to_evaluate(monkeypatch) -> None:
    """choose_move 必须把自己持有的权重透传给 evaluate，否则 stuck_penalty=0 不起作用。"""
    captured: list[dict] = []

    def fake_evaluate(state, perspective, **kwargs):  # noqa: ARG001
        captured.append(kwargs)
        return 0.0

    monkeypatch.setattr("ai.greedy_ai.evaluate", fake_evaluate)

    ai = GreedyAI(rng=random.Random(0), stuck_penalty=0.0)
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    ai.choose_move(state, dice=1)

    assert captured, "evaluate 没有被调用"
    for kw in captured:
        assert kw.get("stuck_penalty") == 0.0
        assert kw.get("distance_weight") == DISTANCE_WEIGHT
        assert kw.get("material_weight") == MATERIAL_WEIGHT


# --- ai_version_signature -----------------------------------------------------


def test_ai_version_signature_for_greedy_default_includes_all_weights() -> None:
    ai = build_ai("greedy", seed=1)

    sig = ai_version_signature(ai)

    assert sig["name"] == "greedy"
    assert sig["stuck_penalty"] == STUCK_PIECE_PENALTY
    assert sig["distance_weight"] == DISTANCE_WEIGHT
    assert sig["material_weight"] == MATERIAL_WEIGHT


def test_ai_version_signature_for_baseline_greedy_records_zero_penalty() -> None:
    ai = build_ai("greedy", seed=1, stuck_penalty=0.0)

    sig = ai_version_signature(ai)

    assert sig["stuck_penalty"] == 0.0
    # baseline 与 production 在 metadata 里的 signature 必然不同 → reproducer 可区分
    prod = ai_version_signature(build_ai("greedy", seed=1))
    assert sig != prod


def test_build_ai_random_rejects_evaluator_kwargs() -> None:
    """random AI 不应吞 stuck_penalty 等参数（防止 reproducer 误把权重喂给 random）。"""
    import pytest

    with pytest.raises(TypeError, match="random"):
        build_ai("random", seed=1, stuck_penalty=0.0)
