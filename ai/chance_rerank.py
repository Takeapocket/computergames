from __future__ import annotations

import random
import time
from collections import Counter
from typing import Protocol

from ai.zweistein_dp import zweistein_dp_win_prob
from core.game_state import GameState
from core.move import Move
from core.types import Player


class _BaseAI(Protocol):
    name: str
    last_root_stats: list

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...


def _move_key(move: Move) -> tuple[int, int, int, int, int]:
    return (
        move.piece_id,
        move.from_pos.row,
        move.from_pos.col,
        move.to_pos.row,
        move.to_pos.col,
    )


def exact_opp1_zdp_value(
    state: GameState,
    dice: int,
    root_move: Move,
    perspective: Player,
) -> float:
    perspective = Player.from_value(perspective)
    sim = GameState.deserialize(state.serialize(include_history=False))
    sim.apply_move(root_move, dice=dice)

    winner = sim.get_winner()
    if winner is perspective:
        return 1.0
    if winner is perspective.opponent:
        return 0.0

    opponent = perspective.opponent
    total = 0.0
    for opp_dice in range(1, 7):
        opp_moves = sim.legal_moves(opponent, opp_dice)
        if not opp_moves:
            total += 1.0
            continue

        best_for_opponent = 1.0
        for opp_move in opp_moves:
            sim.apply_move(opp_move, dice=opp_dice)
            try:
                best_for_opponent = min(
                    best_for_opponent,
                    zweistein_dp_win_prob(sim, perspective),
                )
            finally:
                sim.undo_move()
        total += best_for_opponent

    return total / 6.0


class ExactOpponentDiceRerankAI:
    def __init__(
        self,
        *,
        base: _BaseAI | None = None,
        top_k: int = 3,
        exact_mix: float = 0.35,
        min_time_remaining_ms: float = 20.0,
        max_step_time_ms: float = 750.0,
        rng: random.Random | None = None,
        name: str = "rollout_exact_opp1_zdp",
    ) -> None:
        if base is None:
            from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
            from ai.rollout_ai import RolloutAI

            base = RolloutAI(
                rng=rng or random.Random(),
                **RELEASE_DEFAULT_ROLLOUT_KWARGS,
            )
        self.base = base
        self.top_k = max(1, int(top_k))
        self.exact_mix = max(0.0, min(1.0, float(exact_mix)))
        self.min_time_remaining_ms = max(0.0, float(min_time_remaining_ms))
        self.max_step_time_ms = float(max_step_time_ms)
        self._rng = rng or random.Random()
        self.name = name
        self.fire_counts: Counter[str] = Counter()

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        self.fire_counts = Counter()
        start = time.perf_counter()
        outer_deadline = start + self.max_step_time_ms / 1000.0
        perspective = state.current_player

        base_move = self.base.choose_move(state, dice)
        if base_move is None:
            self.fire_counts["passthrough_base_none"] += 1
            return None

        if self._time_remaining_ms(outer_deadline) <= self.min_time_remaining_ms:
            self.fire_counts["passthrough_no_time"] += 1
            return base_move

        legal = state.legal_moves(perspective, dice)
        stats = [
            stats
            for stats in getattr(self.base, "last_root_stats", [])
            if getattr(stats, "move", None) in legal
        ]
        if not stats:
            self.fire_counts["passthrough_no_stats"] += 1
            return base_move

        base_stats = next((stats_item for stats_item in stats if stats_item.move == base_move), None)
        if base_stats is None:
            self.fire_counts["passthrough_no_stats"] += 1
            return base_move

        top_stats = sorted(
            stats,
            key=lambda stats_item: (
                -stats_item.score,
                -stats_item.visits,
                _move_key(stats_item.move),
            ),
        )[: self.top_k]
        if not top_stats:
            self.fire_counts["passthrough_no_stats"] += 1
            return base_move

        self.fire_counts["considered"] += 1
        scored: list[tuple[float, float, int, tuple[int, int, int, int, int], Move]] = []
        for rank, stats_item in enumerate(top_stats):
            if self._time_remaining_ms(outer_deadline) <= self.min_time_remaining_ms:
                break
            exact_value = exact_opp1_zdp_value(state, dice, stats_item.move, perspective)
            mixed = (1.0 - self.exact_mix) * stats_item.score + self.exact_mix * exact_value
            scored.append((mixed, stats_item.score, stats_item.visits, _move_key(stats_item.move), stats_item.move))

        if not scored:
            self.fire_counts["passthrough_no_time"] += 1
            return base_move

        best_mixed, _, _, _, best_move = max(
            scored,
            key=lambda item: (item[0], item[1], item[2], tuple(-part for part in item[3])),
        )
        base_mixed = (1.0 - self.exact_mix) * base_stats.score + self.exact_mix * exact_opp1_zdp_value(
            state,
            dice,
            base_move,
            perspective,
        )
        if best_move != base_move and best_mixed > base_mixed:
            self.fire_counts["applied"] += 1
            return best_move

        self.fire_counts["passthrough_no_change"] += 1
        return base_move

    @staticmethod
    def _time_remaining_ms(deadline: float) -> float:
        return (deadline - time.perf_counter()) * 1000.0
