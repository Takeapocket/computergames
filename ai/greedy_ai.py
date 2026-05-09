from __future__ import annotations

import random

from ai.evaluator import evaluate
from core.game_state import GameState
from core.move import Move


class GreedyAI:
    """贪心 AI：对每个合法走法跑一步前瞻 + 评估，挑分数最高，多并列用 RNG 抽签。"""

    def __init__(self, *, rng: random.Random | None = None, name: str = "greedy") -> None:
        self._rng = rng or random.Random()
        self.name = name

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal_moves = state.legal_moves(state.current_player, dice)
        if not legal_moves:
            return None

        mover = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal_moves:
            applied = state.apply_move(move, dice=dice)
            try:
                score = evaluate(state, perspective=mover)
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        return self._rng.choice(best_moves)
