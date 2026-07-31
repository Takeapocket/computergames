from __future__ import annotations

import math

from ai.evaluator import WIN_SCORE
from ai.risk import distance_weighted_capture_risk, expected_target_win_risk
from core.game_state import GameState
from core.rules import target_corner
from core.types import Player, chebyshev_distance


PROGRESS_WEIGHT = 12.0
MATERIAL_WEIGHT = 90.0
MOBILITY_WEIGHT = 6.0
CAPTURE_RISK_WEIGHT = 120.0
TARGET_WIN_RISK_WEIGHT = 600.0


def validate_zweistein_weights(
    *,
    progress_weight: float,
    material_weight: float,
    mobility_weight: float,
    capture_risk_weight: float,
    target_win_risk_weight: float,
) -> tuple[float, float, float, float, float]:
    validated: list[float] = []
    for name, value in (
        ("progress_weight", progress_weight),
        ("material_weight", material_weight),
        ("mobility_weight", mobility_weight),
        ("capture_risk_weight", capture_risk_weight),
        ("target_win_risk_weight", target_win_risk_weight),
    ):
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"{name} must be finite")
        validated.append(numeric_value)
    return tuple(validated)


def zweistein_lite_score(
    state: GameState,
    perspective: Player,
    *,
    progress_weight: float = PROGRESS_WEIGHT,
    material_weight: float = MATERIAL_WEIGHT,
    mobility_weight: float = MOBILITY_WEIGHT,
    capture_risk_weight: float = CAPTURE_RISK_WEIGHT,
    target_win_risk_weight: float = TARGET_WIN_RISK_WEIGHT,
) -> float:
    """Return a compact zero-sum evaluation from ``perspective``.

    This is intentionally a project-local approximation: terminal score,
    progress, material, expected mobility, capture exposure and direct target
    win exposure. It avoids changing the legacy ``evaluate()`` contract.
    """
    (
        progress_weight,
        material_weight,
        mobility_weight,
        capture_risk_weight,
        target_win_risk_weight,
    ) = validate_zweistein_weights(
        progress_weight=progress_weight,
        material_weight=material_weight,
        mobility_weight=mobility_weight,
        capture_risk_weight=capture_risk_weight,
        target_win_risk_weight=target_win_risk_weight,
    )
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    opponent = perspective.opponent
    score = float(
        progress_weight * (_distance_total(state, opponent) - _distance_total(state, perspective))
        + material_weight * (_alive_count(state, perspective) - _alive_count(state, opponent))
        + mobility_weight * (_expected_mobility(state, perspective) - _expected_mobility(state, opponent))
        + capture_risk_weight
        * (
            distance_weighted_capture_risk(state, opponent)
            - distance_weighted_capture_risk(state, perspective)
        )
        + target_win_risk_weight
        * (
            expected_target_win_risk(state, opponent)
            - expected_target_win_risk(state, perspective)
        )
    )
    if not math.isfinite(score):
        raise ValueError(
            "Zweistein score must be finite; reduce custom weight magnitudes"
        )
    return score


def _alive_count(state: GameState, player: Player) -> int:
    return sum(1 for piece in state.pieces[player].values() if piece.alive)


def _distance_total(state: GameState, player: Player) -> int:
    target = target_corner(player)
    return sum(
        chebyshev_distance(piece.position, target)
        for piece in state.pieces[player].values()
        if piece.alive
    )


def _expected_mobility(state: GameState, player: Player) -> float:
    return sum(len(state.legal_moves(player, dice)) for dice in range(1, 7)) / 6.0
