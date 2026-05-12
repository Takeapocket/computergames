"""evaluator 权重参数化 + GreedyAI 透传，保证 distance/material/risk 权重一致传递。

R-0 followup 清理后，本文件只保留 distance/material/risk 权重的契约测试。
"""

from __future__ import annotations

import random

from ai.evaluator import (
    DISTANCE_WEIGHT,
    EXPECTED_RISK_WEIGHT,
    EXPECTED_WIN_RISK_WEIGHT,
    MATERIAL_WEIGHT,
    evaluate,
)
from ai.greedy_ai import GreedyAI
from ai.match import ai_version_signature, build_ai
from core.game_state import GameState
from core.types import Player, Position


# --- evaluator 权重参数化 -----------------------------------------------------


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


def test_evaluate_accepts_risk_weight_kwargs() -> None:
    state = GameState.from_layout(
        red={3: Position(2, 2)},
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(3, 4),
            4: Position(3, 3),
            5: Position(4, 0),
            6: Position(0, 4),
        },
        current_player=Player.RED,
    )

    without_risk = evaluate(state, Player.RED)
    with_risk = evaluate(
        state,
        Player.RED,
        expected_risk_weight=EXPECTED_RISK_WEIGHT,
        expected_win_risk_weight=EXPECTED_WIN_RISK_WEIGHT,
    )

    assert with_risk < without_risk


# --- GreedyAI 字段 ------------------------------------------------------------


def test_greedy_ai_default_weights_match_module_constants() -> None:
    ai = GreedyAI()

    assert ai.distance_weight == DISTANCE_WEIGHT
    assert ai.material_weight == MATERIAL_WEIGHT
    assert ai.expected_risk_weight == 0.0
    assert ai.expected_win_risk_weight == 0.0


def test_greedy_ai_accepts_custom_weights() -> None:
    ai = GreedyAI(distance_weight=2.0, material_weight=5.0)

    assert ai.distance_weight == 2.0
    assert ai.material_weight == 5.0


def test_greedy_ai_forwards_weights_to_evaluate(monkeypatch) -> None:
    """choose_move 必须把自己持有的权重透传给 evaluate。"""
    captured: list[dict] = []

    def fake_evaluate(state, perspective, **kwargs):  # noqa: ARG001
        captured.append(kwargs)
        return 0.0

    monkeypatch.setattr("ai.greedy_ai.evaluate", fake_evaluate)

    ai = GreedyAI(rng=random.Random(0), distance_weight=2.0)
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    ai.choose_move(state, dice=1)

    assert captured, "evaluate 没有被调用"
    for kw in captured:
        assert kw.get("distance_weight") == 2.0
        assert kw.get("material_weight") == MATERIAL_WEIGHT


# --- ai_version_signature -----------------------------------------------------


def test_ai_version_signature_for_greedy_default_includes_all_weights() -> None:
    ai = build_ai("greedy", seed=1)

    sig = ai_version_signature(ai)

    assert sig["name"] == "greedy"
    assert sig["distance_weight"] == DISTANCE_WEIGHT
    assert sig["material_weight"] == MATERIAL_WEIGHT


def test_ai_version_signature_for_greedy_risk_includes_risk_weights() -> None:
    ai = build_ai("greedy_risk", seed=1)

    sig = ai_version_signature(ai)

    assert sig["name"] == "greedy_risk"
    assert sig["expected_risk_weight"] == EXPECTED_RISK_WEIGHT
    assert sig["expected_win_risk_weight"] == EXPECTED_WIN_RISK_WEIGHT


def test_build_ai_random_rejects_evaluator_kwargs() -> None:
    """random AI 不应吞 evaluator 权重参数。"""
    import pytest

    with pytest.raises(TypeError, match="random"):
        build_ai("random", seed=1, distance_weight=1.0)
