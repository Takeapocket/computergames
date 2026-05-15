from __future__ import annotations

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


def zweistein_lite_score(state: GameState, perspective: Player) -> float:
    """Return a compact zero-sum evaluation from ``perspective``.

    This is intentionally a project-local approximation: terminal score,
    progress, material, expected mobility, capture exposure and direct target
    win exposure. It avoids changing the legacy ``evaluate()`` contract.
    """
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    opponent = perspective.opponent
    return float(
        PROGRESS_WEIGHT * (_distance_total(state, opponent) - _distance_total(state, perspective))
        + MATERIAL_WEIGHT * (_alive_count(state, perspective) - _alive_count(state, opponent))
        + MOBILITY_WEIGHT * (_expected_mobility(state, perspective) - _expected_mobility(state, opponent))
        + CAPTURE_RISK_WEIGHT
        * (
            distance_weighted_capture_risk(state, opponent)
            - distance_weighted_capture_risk(state, perspective)
        )
        + TARGET_WIN_RISK_WEIGHT
        * (
            expected_target_win_risk(state, opponent)
            - expected_target_win_risk(state, perspective)
        )
    )


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
