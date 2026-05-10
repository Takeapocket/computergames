from __future__ import annotations

import random

from ai.evaluator import (
    DISTANCE_WEIGHT,
    MATERIAL_WEIGHT,
    STUCK_PIECE_PENALTY,
    evaluate,
)
from core.game_state import GameState
from core.move import Move


class GreedyAI:
    """贪心 AI：对每个合法走法跑一步前瞻 + 评估，挑分数最高，多并列用 RNG 抽签。

    evaluator 的三个权重 (distance_weight / material_weight / stuck_penalty)
    可通过构造参数注入。reproducer 用 ``stuck_penalty=0`` 复现 4.1 baseline。
    """

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        name: str = "greedy",
        distance_weight: float = DISTANCE_WEIGHT,
        material_weight: float = MATERIAL_WEIGHT,
        stuck_penalty: float = STUCK_PIECE_PENALTY,
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        self.distance_weight = distance_weight
        self.material_weight = material_weight
        self.stuck_penalty = stuck_penalty

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
                score = evaluate(
                    state,
                    perspective=mover,
                    distance_weight=self.distance_weight,
                    material_weight=self.material_weight,
                    stuck_penalty=self.stuck_penalty,
                )
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        return self._rng.choice(best_moves)
