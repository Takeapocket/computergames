"""Single-worker AI recommendations. This module never calls Tk."""
from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, SimpleQueue
from threading import Condition, Thread
from typing import Any, Literal

from core.game_state import GameState
from core.move import Move
from gui.formatting import format_move_label

RecommendationSource = Literal["rollout", "greedy_risk", "rules", "none"]
RecommendationKey = tuple[int, str]


def format_rollout_diagnostic(diagnostic: object) -> str:
    move = getattr(diagnostic, "move")
    visits = int(getattr(diagnostic, "visits"))
    score_value = getattr(diagnostic, "score", None)
    score = float(getattr(diagnostic, "winrate") if score_value is None else score_value)
    winrate = float(getattr(diagnostic, "winrate", score))
    wins = float(getattr(diagnostic, "wins", winrate * visits))
    draws = float(getattr(diagnostic, "draws", getattr(diagnostic, "cutoffs", 0.0)))
    losses = float(getattr(diagnostic, "losses", max(0.0, visits - wins - draws)))
    avg = float(getattr(diagnostic, "avg", 2 * score - 1))
    confidence = ", 置信=低" if getattr(diagnostic, "low_confidence", False) else ""
    return (
        f"{format_move_label(move, distinguish_self_capture=True)}\n"
        f"visits={visits}, score={score:.2f}, winrate={winrate:.2f}, "
        f"wins={wins:.0f}, losses={losses:.0f}, draws={draws:.0f}, avg={avg:.2f}"
        f"{confidence}"
    )


def diagnostic_lines(recommender: Any) -> tuple[str, ...]:
    """Format diagnostics while the worker still owns this decision's AI state."""
    lines: list[str] = []
    try:
        if getattr(recommender, "last_low_confidence", False):
            margin = getattr(recommender, "last_score_margin", None)
            lines.append(
                "低置信：建议人工核对候选列表（候选差距过小）"
                if margin is None
                else f"低置信：建议人工核对候选列表，候选差距={float(margin):.2f}"
            )
        if getattr(recommender, "last_timed_out", False):
            lines.append(
                "采样：超时，已使用 greedy_risk 回退"
                if getattr(recommender, "last_used_fallback", False)
                else "采样：超时，使用已完成样本"
            )
        stats = getattr(recommender, "last_root_stats", None)
        if stats is None:
            stats = getattr(recommender, "last_diagnostics", [])
        if stats:
            lines.append("rollout 候选：")
            lines.extend(format_rollout_diagnostic(item) for item in stats)
    except Exception:  # Diagnostics from an AI extension must not invalidate a legal move.
        lines.append("候选诊断不可用。")
    return tuple(lines)


@dataclass(frozen=True)
class RecommendationRequest:
    generation: int
    key: RecommendationKey
    dice: int
    state: GameState
    recommender: Any
    fallback: Any


@dataclass(frozen=True)
class RecommendationResult:
    generation: int
    key: RecommendationKey
    move: Move | None
    source: RecommendationSource
    diagnostics: tuple[str, ...] = ()


def calculate_recommendation(request: RecommendationRequest) -> RecommendationResult:
    """Use separate state copies so a failed AI cannot poison the fallback."""
    legal = request.state.legal_moves(request.state.current_player, request.dice)
    choices: tuple[tuple[RecommendationSource, Any], ...] = (
        ("rollout", request.recommender), ("greedy_risk", request.fallback),
    )
    for source, ai in choices:
        try:
            proposed = ai.choose_move(request.state.clone(include_history=False), request.dice)
        except Exception:  # AI failure must not disable the operator's recommendation.
            proposed = None
        if isinstance(proposed, Move):
            canonical = next((move for move in legal if move == proposed), None)
            if canonical is not None:
                return RecommendationResult(
                    request.generation, request.key, canonical.copy(), source,
                    diagnostic_lines(ai) if source == "rollout" else (),
                )
    return RecommendationResult(
        request.generation, request.key, legal[0].copy() if legal else None,
        "rules" if legal else "none",
    )


class RecommendationWorker:
    """At most one running request and one pending request, with latest-wins queueing."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._pending: RecommendationRequest | None = None
        self._closed = False
        self._thread: Thread | None = None
        self._results: SimpleQueue[RecommendationResult] = SimpleQueue()

    def submit(self, request: RecommendationRequest) -> None:
        with self._condition:
            if self._closed:
                return
            self._pending = request
            if self._thread is None or not self._thread.is_alive():
                self._thread = Thread(target=self._run, name="chess-recommendation", daemon=True)
                self._thread.start()
            self._condition.notify()

    def invalidate(self) -> None:
        with self._condition:
            self._pending = None

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
            self._condition.notify()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def drain(self) -> list[RecommendationResult]:
        results = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except Empty:
                return results

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._pending is not None)
                if self._closed:
                    return
                request = self._pending
                self._pending = None
            assert request is not None
            try:
                result = calculate_recommendation(request)
            except Exception:  # Keep future decisions alive even if an extension fails outside choose_move.
                try:
                    legal = request.state.legal_moves(request.state.current_player, request.dice)
                except Exception:
                    legal = []
                result = RecommendationResult(
                    request.generation, request.key,
                    legal[0].copy() if legal else None,
                    "rules" if legal else "none",
                )
            with self._condition:
                if self._closed:
                    return
                self._results.put(result)
