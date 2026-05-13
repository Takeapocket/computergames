from __future__ import annotations

import random
import time

from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move
from core.types import Player


class RolloutAI:
    """Bounded flat rollout candidate. It never mutates the input state."""

    def __init__(
        self,
        *,
        rollouts_per_move: int = 16,
        max_rollout_turns: int = 80,
        max_step_time_ms: float = 500.0,
        epsilon: float = 0.15,
        rng: random.Random | None = None,
        name: str = "rollout",
    ) -> None:
        self.rollouts_per_move = int(rollouts_per_move)
        self.max_rollout_turns = int(max_rollout_turns)
        self.max_step_time_ms = float(max_step_time_ms)
        self.epsilon = float(epsilon)
        self._rng = rng or random.Random()
        self.name = name
        self.fallback_count = 0

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        deadline = time.perf_counter() + self.max_step_time_ms / 1000.0
        perspective = state.current_player
        fallback = GreedyAI(rng=random.Random(self._rng.randrange(2**31)), name="rollout_fallback")
        best_move = fallback.choose_move(state, dice) or self._rng.choice(legal)
        best_score = float("-inf")
        scored_any = False

        for move in legal:
            if time.perf_counter() >= deadline:
                self.fallback_count += 1
                return best_move
            wins = 0.0
            completed = 0
            for _ in range(self.rollouts_per_move):
                if time.perf_counter() >= deadline:
                    self.fallback_count += 1
                    return best_move
                sim = GameState.deserialize(state.serialize())
                sim.apply_move(move, dice=dice)
                winner = self._playout(sim, deadline=deadline)
                if winner is perspective:
                    wins += 1.0
                elif winner is None:
                    wins += 0.5
                completed += 1
            if completed:
                score = wins / completed
                scored_any = True
                if score > best_score:
                    best_score = score
                    best_move = move

        if not scored_any:
            self.fallback_count += 1
        return best_move

    def _playout(self, state: GameState, *, deadline: float) -> Player | None:
        policy = GreedyAI(rng=random.Random(self._rng.randrange(2**31)), name="rollout_policy")
        for _ in range(self.max_rollout_turns):
            winner = state.get_winner()
            if winner is not None:
                return winner
            if time.perf_counter() >= deadline:
                return None
            dice = self._rng.randint(1, 6)
            legal = state.legal_moves(state.current_player, dice)
            if not legal:
                return state.current_player.opponent
            if self._rng.random() < self.epsilon:
                move = self._rng.choice(legal)
            else:
                move = policy.choose_move(state, dice) or self._rng.choice(legal)
            state.apply_move(move, dice=dice)
        return state.get_winner()
