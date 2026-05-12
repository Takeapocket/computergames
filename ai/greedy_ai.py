from __future__ import annotations

import random

from ai.evaluator import (
    DISTANCE_WEIGHT,
    MATERIAL_WEIGHT,
    SELF_CAPTURE_WEIGHT,
    evaluate,
)
from core.game_state import GameState
from core.move import Move


class GreedyAI:
    """贪心 AI：对每个合法走法跑一步前瞻 + 评估，挑分数最高，多并列用 RNG 抽签。

    evaluator 权重可通过构造参数注入；4.2 candidate 用 ``expected_risk_weight=EXPECTED_RISK_WEIGHT``
    开启风险惩罚。
    """

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        name: str = "greedy",
        distance_weight: float = DISTANCE_WEIGHT,
        material_weight: float = MATERIAL_WEIGHT,
        expected_risk_weight: float = 0.0,
        expected_win_risk_weight: float = 0.0,
        self_capture_weight: float = SELF_CAPTURE_WEIGHT,
        randomize_ties: bool = True,
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        self.distance_weight = distance_weight
        self.material_weight = material_weight
        self.expected_risk_weight = expected_risk_weight
        self.expected_win_risk_weight = expected_win_risk_weight
        self.self_capture_weight = self_capture_weight
        self.randomize_ties = randomize_ties

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
                    expected_risk_weight=self.expected_risk_weight,
                    expected_win_risk_weight=self.expected_win_risk_weight,
                    self_capture_weight=self.self_capture_weight,
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
