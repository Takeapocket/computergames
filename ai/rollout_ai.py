from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace

from ai.evaluator import EXPECTED_RISK_WEIGHT, EXPECTED_WIN_RISK_WEIGHT, evaluate
from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move
from core.types import Player


@dataclass(frozen=True)
class RootMoveStats:
    move: Move
    visits: int
    wins: float
    losses: float
    draws: float
    cutoffs: float
    score: float
    winrate: float
    avg: float
    low_confidence: bool = False


@dataclass(frozen=True)
class RolloutMoveDiagnostic:
    move: Move
    visits: int
    wins: float
    losses: float
    cutoffs: float
    score: float
    winrate: float
    avg: float
    low_confidence: bool = False

    @property
    def draws(self) -> float:
        return self.cutoffs


@dataclass
class _RolloutMoveScore:
    move: Move
    wins: float = 0.0
    losses: float = 0.0
    draws: float = 0.0
    cutoffs: float = 0.0
    visits: int = 0

    @property
    def score(self) -> float:
        if self.visits <= 0:
            return float("-inf")
        return (self.wins + 0.5 * self.draws) / self.visits

    @property
    def winrate(self) -> float:
        if self.visits <= 0:
            return float("-inf")
        return self.wins / self.visits

    def record_win(self) -> None:
        self.wins += 1.0
        self.visits += 1

    def record_loss(self) -> None:
        self.losses += 1.0
        self.visits += 1

    def record_cutoff(self, outcome: float) -> None:
        self.cutoffs += 1.0
        if outcome == 0.5:
            self.draws += 1.0
        else:
            self.wins += outcome
            self.losses += 1.0 - outcome
        self.visits += 1

    def to_root_stats(self) -> RootMoveStats:
        winrate = self.winrate
        return RootMoveStats(
            move=self.move,
            visits=self.visits,
            wins=self.wins,
            losses=self.losses,
            draws=self.draws,
            cutoffs=self.cutoffs,
            score=self.score,
            winrate=winrate,
            avg=2 * self.score - 1,
        )


class RolloutAI:
    """有时间上限的平面 rollout AI，输入局面只读。"""

    def __init__(
        self,
        *,
        rollouts_per_move: int = 16,
        max_rollout_turns: int = 80,
        max_step_time_ms: float = 500.0,
        epsilon: float = 0.15,
        close_sample_margin: float = 0.08,
        close_sample_rollouts_per_move: int | None = None,
        low_confidence_margin: float = 0.08,
        playout_policy: str = "greedy",
        cutoff_eval: str = "draw",
        rng: random.Random | None = None,
        name: str = "rollout",
    ) -> None:
        if playout_policy not in {"greedy", "greedy_risk"}:
            raise ValueError(f"unknown playout_policy: {playout_policy!r}")
        if cutoff_eval not in {"draw", "current"}:
            raise ValueError(f"unknown cutoff_eval: {cutoff_eval!r}")
        self.rollouts_per_move = int(rollouts_per_move)
        self.max_rollout_turns = int(max_rollout_turns)
        self.max_step_time_ms = float(max_step_time_ms)
        self.epsilon = float(epsilon)
        self.close_sample_margin = float(close_sample_margin)
        close_rollouts = (
            self.rollouts_per_move
            if close_sample_rollouts_per_move is None
            else int(close_sample_rollouts_per_move)
        )
        self.close_sample_rollouts_per_move = max(self.rollouts_per_move, close_rollouts)
        self.low_confidence_margin = float(low_confidence_margin)
        self.playout_policy = playout_policy
        self.cutoff_eval = cutoff_eval
        self._rng = rng or random.Random()
        self.name = name
        self.fallback_count = 0
        self.last_root_stats: list[RootMoveStats] = []
        self.last_diagnostics: list[RolloutMoveDiagnostic] = []
        self.last_score_margin: float | None = None
        self.last_low_confidence = False
        self.last_timed_out = False
        self.last_used_fallback = False
        self._playout_hit_deadline = False

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        self.last_root_stats = []
        self.last_diagnostics = []
        self.last_score_margin = None
        self.last_low_confidence = False
        self.last_timed_out = False
        self.last_used_fallback = False
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        deadline = time.perf_counter() + self.max_step_time_ms / 1000.0
        perspective = state.current_player
        fallback = GreedyAI(
            rng=random.Random(self._rng.randrange(2**31)),
            name="rollout_fallback",
            expected_risk_weight=EXPECTED_RISK_WEIGHT,
            expected_win_risk_weight=EXPECTED_WIN_RISK_WEIGHT,
        )
        fallback_move = fallback.choose_move(state, dice) or self._rng.choice(legal)
        scores = [_RolloutMoveScore(move=move) for move in legal]

        for score in scores:
            timed_out = self._sample_move_score(
                score,
                state=state,
                dice=dice,
                perspective=perspective,
                deadline=deadline,
                target_visits=self.rollouts_per_move,
            )
            if timed_out:
                self.fallback_count += 1
                self.last_timed_out = True
                self.last_used_fallback = True
                self._record_diagnostics(scores)
                return fallback_move

        best_move = self._best_score(scores).move
        close_scores = self._close_scores(scores)
        if close_scores:
            for score in close_scores:
                timed_out = self._sample_move_score(
                    score,
                    state=state,
                    dice=dice,
                    perspective=perspective,
                    deadline=deadline,
                    target_visits=self.close_sample_rollouts_per_move,
                )
                if timed_out:
                    self.fallback_count += 1
                    self.last_timed_out = True
                    self._record_diagnostics(scores)
                    self._record_confidence(scores)
                    return self._best_score(scores).move
            best_move = self._best_score(scores).move

        self._record_diagnostics(scores)
        self._record_confidence(scores)
        return best_move

    def _sample_move_score(
        self,
        score: _RolloutMoveScore,
        *,
        state: GameState,
        dice: int,
        perspective: Player,
        deadline: float,
        target_visits: int,
    ) -> bool:
        while score.visits < target_visits:
            if time.perf_counter() >= deadline:
                return True
            sim = GameState.deserialize(state.serialize())
            sim.apply_move(score.move, dice=dice)
            self._playout_hit_deadline = False
            winner = self._playout(sim, deadline=deadline)
            if self._playout_hit_deadline:
                return True
            if winner is perspective:
                score.record_win()
            elif winner is perspective.opponent:
                score.record_loss()
            elif winner is None:
                score.record_cutoff(self._cutoff_score(sim, perspective))
        return False

    def _best_score(self, scores: list[_RolloutMoveScore]) -> _RolloutMoveScore:
        return max(scores, key=lambda score: score.score)

    def _ranked_scores(self, scores: list[_RolloutMoveScore]) -> list[_RolloutMoveScore]:
        return sorted(scores, key=lambda score: score.score, reverse=True)

    def _close_scores(self, scores: list[_RolloutMoveScore]) -> list[_RolloutMoveScore]:
        if self.close_sample_rollouts_per_move <= self.rollouts_per_move:
            return []
        ranked = self._ranked_scores(scores)
        if len(ranked) < 2:
            return []
        if ranked[0].score - ranked[1].score >= self.close_sample_margin:
            return []
        best_score = ranked[0].score
        return [
            score
            for score in scores
            if best_score - score.score <= self.close_sample_margin
        ]

    def _record_diagnostics(self, scores: list[_RolloutMoveScore]) -> None:
        self.last_root_stats = [
            score.to_root_stats()
            for score in scores
            if score.visits > 0
        ]
        self._sync_legacy_diagnostics()

    def _sync_legacy_diagnostics(self) -> None:
        self.last_diagnostics = [
            RolloutMoveDiagnostic(
                move=stats.move,
                visits=stats.visits,
                wins=stats.wins,
                losses=stats.losses,
                cutoffs=stats.draws,
                score=stats.score,
                winrate=stats.winrate,
                avg=stats.avg,
                low_confidence=stats.low_confidence,
            )
            for stats in self.last_root_stats
        ]

    def _record_confidence(self, scores: list[_RolloutMoveScore]) -> None:
        ranked = self._ranked_scores([score for score in scores if score.visits > 0])
        if len(ranked) < 2:
            self.last_score_margin = None
            self.last_low_confidence = False
            return
        margin = ranked[0].score - ranked[1].score
        self.last_score_margin = margin
        self.last_low_confidence = margin < self.low_confidence_margin
        if not self.last_low_confidence:
            return
        best_score = ranked[0].score
        self.last_root_stats = [
            replace(stats, low_confidence=best_score - stats.score < self.low_confidence_margin)
            for stats in self.last_root_stats
        ]
        self._sync_legacy_diagnostics()

    def _cutoff_score(self, state: GameState, perspective: Player) -> float:
        if self.cutoff_eval == "draw":
            return 0.5
        value = evaluate(state, perspective)
        if value > 0:
            return 1.0
        if value < 0:
            return 0.0
        return 0.5

    def _playout(self, state: GameState, *, deadline: float) -> Player | None:
        policy_kwargs = {
            "rng": random.Random(self._rng.randrange(2**31)),
            "name": "rollout_policy",
        }
        if self.playout_policy == "greedy_risk":
            policy_kwargs["expected_risk_weight"] = EXPECTED_RISK_WEIGHT
            policy_kwargs["expected_win_risk_weight"] = EXPECTED_WIN_RISK_WEIGHT
        policy = GreedyAI(**policy_kwargs)
        for _ in range(self.max_rollout_turns):
            winner = state.get_winner()
            if winner is not None:
                return winner
            if time.perf_counter() >= deadline:
                self._playout_hit_deadline = True
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
