from __future__ import annotations

import random
import time

from ai.evaluator import WIN_SCORE, evaluate
from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move


class ExpectimaxV2:
    """Experimental expectimax candidate with leaf risk disabled by default.

    ``depth`` counts opponent-response plies after the root move. ``depth=0``
    falls back to GreedyAI; ``depth=1`` evaluates the expected opponent reply.
    """

    def __init__(
        self,
        *,
        depth: int = 1,
        time_limit_ms: float = 500.0,
        rng: random.Random | None = None,
        name: str = "expectimax_v2",
        randomize_ties: bool = True,
    ) -> None:
        self.depth = int(depth)
        self.time_limit_ms = float(time_limit_ms)
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = bool(randomize_ties)
        self.expected_risk_weight = 0.0
        self.expected_win_risk_weight = 0.0

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        if self.depth <= 0:
            return GreedyAI(rng=self._rng, randomize_ties=self.randomize_ties).choose_move(state, dice)

        deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        perspective = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal:
            if time.perf_counter() >= deadline:
                return self._fallback(legal, best_moves)
            state.apply_move(move, dice=dice)
            try:
                score = self._chance_value(state, perspective=perspective, depth=self.depth, deadline=deadline)
            finally:
                state.undo_move()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self._fallback(legal, best_moves)

    def _chance_value(self, state: GameState, *, perspective, depth: int, deadline: float) -> float:
        if time.perf_counter() >= deadline or depth <= 0 or state.get_winner() is not None:
            return evaluate(
                state,
                perspective=perspective,
                expected_risk_weight=0.0,
                expected_win_risk_weight=0.0,
            )
        total = 0.0
        for dice in range(1, 7):
            total += self._turn_value(state, dice=dice, perspective=perspective, depth=depth, deadline=deadline)
        return total / 6.0

    def _turn_value(self, state: GameState, *, dice: int, perspective, depth: int, deadline: float) -> float:
        winner = state.get_winner()
        if winner is not None:
            return WIN_SCORE if winner is perspective else -WIN_SCORE
        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        if not legal:
            return -WIN_SCORE if whose_turn is perspective else WIN_SCORE
        scores = []
        for move in legal:
            if time.perf_counter() >= deadline:
                break
            state.apply_move(move, dice=dice)
            try:
                scores.append(self._chance_value(state, perspective=perspective, depth=depth - 1, deadline=deadline))
            finally:
                state.undo_move()
        if not scores:
            return evaluate(state, perspective=perspective, expected_risk_weight=0.0, expected_win_risk_weight=0.0)
        return max(scores) if whose_turn is perspective else min(scores)

    def _fallback(self, legal: list[Move], best_moves: list[Move]) -> Move:
        choices = best_moves or legal
        return self._rng.choice(choices) if self.randomize_ties else choices[0]
