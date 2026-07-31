from __future__ import annotations

import random

from ai.zweistein import (
    CAPTURE_RISK_WEIGHT,
    MATERIAL_WEIGHT,
    MOBILITY_WEIGHT,
    PROGRESS_WEIGHT,
    TARGET_WIN_RISK_WEIGHT,
    validate_zweistein_weights,
    zweistein_lite_score,
)
from core.game_state import GameState
from core.move import Move


class ZweisteinGreedyAI:
    """One-ply greedy AI backed by the Zweistein-lite evaluator."""

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        name: str = "greedy_zweistein",
        randomize_ties: bool = True,
        progress_weight: float = PROGRESS_WEIGHT,
        material_weight: float = MATERIAL_WEIGHT,
        mobility_weight: float = MOBILITY_WEIGHT,
        capture_risk_weight: float = CAPTURE_RISK_WEIGHT,
        target_win_risk_weight: float = TARGET_WIN_RISK_WEIGHT,
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = randomize_ties
        (
            self.progress_weight,
            self.material_weight,
            self.mobility_weight,
            self.capture_risk_weight,
            self.target_win_risk_weight,
        ) = validate_zweistein_weights(
            progress_weight=progress_weight,
            material_weight=material_weight,
            mobility_weight=mobility_weight,
            capture_risk_weight=capture_risk_weight,
            target_win_risk_weight=target_win_risk_weight,
        )

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal_moves = state.legal_moves(state.current_player, dice)
        if not legal_moves:
            return None

        perspective = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal_moves:
            applied = state.apply_move(move, dice=dice)
            try:
                score = zweistein_lite_score(
                    state,
                    perspective,
                    progress_weight=self.progress_weight,
                    material_weight=self.material_weight,
                    mobility_weight=self.mobility_weight,
                    capture_risk_weight=self.capture_risk_weight,
                    target_win_risk_weight=self.target_win_risk_weight,
                )
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        if self.randomize_ties:
            return self._rng.choice(best_moves)
        return best_moves[0]
