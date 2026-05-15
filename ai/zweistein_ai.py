from __future__ import annotations

import random

from ai.zweistein import zweistein_lite_score
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
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = randomize_ties

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
                score = zweistein_lite_score(state, perspective)
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
