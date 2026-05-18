from __future__ import annotations

import random
import time
from collections import Counter
from typing import Any, Iterable

from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from ai.rollout_ai import RolloutAI
from ai.tactical import find_winning_moves, opponent_winning_dice_set
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from core.types import chebyshev_distance


def move_identity(move: Move) -> tuple[int, int, int, int, int]:
    return (
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def is_self_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player


def is_enemy_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player.opponent


def move_wins_immediately(state: GameState, move: Move, dice: int) -> bool:
    state.apply_move(move, dice=dice)
    try:
        return state.get_winner() is move.player
    finally:
        state.undo_move()


def opponent_winning_dice_after_move(state: GameState, move: Move, dice: int) -> set[int]:
    state.apply_move(move, dice=dice)
    try:
        return opponent_winning_dice_set(state, opponent=state.current_player)
    finally:
        state.undo_move()


def own_alive_after_move(state: GameState, move: Move, dice: int) -> int:
    state.apply_move(move, dice=dice)
    try:
        return sum(1 for piece in state.pieces[move.player].values() if piece.alive)
    finally:
        state.undo_move()


class SelfCaptureGuardAI:
    def __init__(
        self,
        *,
        base=None,
        rng: random.Random | None = None,
        name: str = "rollout_self_capture_guard",
        enemy_capture_margin: float = 0.08,
        non_self_low_material_margin: float = 0.12,
        prefer_enemy_capture_margin: float = 0.00,
        low_material_threshold: int = 3,
        max_score_gap_for_override: float = 0.12,
        require_safe_alternative: bool = True,
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        if base is None:
            base = RolloutAI(
                rng=random.Random(self._rng.randrange(2**31)),
                **RELEASE_DEFAULT_ROLLOUT_KWARGS,
            )
        self.base = base
        self.enemy_capture_margin = float(enemy_capture_margin)
        self.non_self_low_material_margin = float(non_self_low_material_margin)
        self.prefer_enemy_capture_margin = float(prefer_enemy_capture_margin)
        self.low_material_threshold = int(low_material_threshold)
        self.max_score_gap_for_override = float(max_score_gap_for_override)
        self.require_safe_alternative = bool(require_safe_alternative)
        self.fire_counts: Counter[str] = Counter()
        self.last_root_stats: list[Any] = []
        self.last_diagnostics: list[Any] = []
        self.last_score_margin: float | None = None
        self.last_low_confidence = False
        self.last_timed_out = False
        self.last_used_fallback = False

    @property
    def max_step_time_ms(self) -> float | None:
        return getattr(self.base, "max_step_time_ms", None)

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        started = time.perf_counter()
        self._reset_diagnostics()
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        direct_wins = find_winning_moves(state, dice, state.current_player)
        if direct_wins:
            return self._best_move(direct_wins, {})

        base_move = self.base.choose_move(state, dice)
        self._sync_from_base()
        score_map = self._score_map(self.last_root_stats)

        if base_move not in legal:
            self.fire_counts["fallback_illegal_base"] += 1
            self.last_used_fallback = True
            return self._fallback_legal_move(state, dice, legal, score_map)

        def deadline_exhausted() -> bool:
            if self._deadline_exhausted(started):
                self.fire_counts["kept_base_after_deadline"] += 1
                self.last_timed_out = True
                return True
            return False

        if deadline_exhausted():
            return base_move

        if move_wins_immediately(state, base_move, dice):
            if is_self_capture(base_move):
                self.fire_counts["kept_self_direct_win"] += 1
            return base_move
        if deadline_exhausted():
            return base_move

        base_score = self._move_score(base_move, score_map, default=1.0)
        enemy_moves = [move for move in legal if move != base_move and is_enemy_capture(move)]
        non_self_moves = [move for move in legal if move != base_move and not is_self_capture(move)]
        if deadline_exhausted():
            return base_move
        safe_enemy_moves = self._safe_moves(state, dice, enemy_moves)
        if deadline_exhausted():
            return base_move
        safe_non_self_moves = self._safe_moves(state, dice, non_self_moves)
        if deadline_exhausted():
            return base_move

        if is_self_capture(base_move):
            best_enemy = self._best_or_none(safe_enemy_moves, score_map)
            if best_enemy is not None:
                best_enemy_score = self._move_score(best_enemy, score_map)
                if self._within_margin(best_enemy_score, base_score, self.enemy_capture_margin):
                    self.fire_counts["override_self_to_enemy_capture"] += 1
                    return best_enemy

            if deadline_exhausted():
                return base_move
            own_after = own_alive_after_move(state, base_move, dice)
            if deadline_exhausted():
                return base_move
            if own_after <= self.low_material_threshold:
                best_non_self = self._best_or_none(safe_non_self_moves, score_map)
                if best_non_self is not None:
                    best_non_self_score = self._move_score(best_non_self, score_map)
                    if self._within_margin(
                        best_non_self_score,
                        base_score,
                        self.non_self_low_material_margin,
                    ):
                        self.fire_counts["override_self_to_non_self_low_material"] += 1
                        return best_non_self

            self.fire_counts[self._kept_self_reason(enemy_moves, non_self_moves, safe_enemy_moves, safe_non_self_moves)] += 1
            return base_move

        if not is_enemy_capture(base_move) and self.prefer_enemy_capture_margin > 0.0:
            best_enemy = self._best_or_none(safe_enemy_moves, score_map)
            if best_enemy is not None:
                best_enemy_score = self._move_score(best_enemy, score_map)
                if self._within_margin(best_enemy_score, base_score, self.prefer_enemy_capture_margin):
                    self.fire_counts["override_to_enemy_capture_soft"] += 1
                    return best_enemy

        return base_move

    def _reset_diagnostics(self) -> None:
        self.last_root_stats = []
        self.last_diagnostics = []
        self.last_score_margin = None
        self.last_low_confidence = False
        self.last_timed_out = False
        self.last_used_fallback = False

    def _sync_from_base(self) -> None:
        self.last_root_stats = list(getattr(self.base, "last_root_stats", []))
        self.last_diagnostics = list(getattr(self.base, "last_diagnostics", []))
        self.last_score_margin = getattr(self.base, "last_score_margin", None)
        self.last_low_confidence = bool(getattr(self.base, "last_low_confidence", False))
        self.last_timed_out = bool(getattr(self.base, "last_timed_out", False))
        self.last_used_fallback = bool(getattr(self.base, "last_used_fallback", False))

    @staticmethod
    def _score_map(root_stats: Iterable[Any]) -> dict[tuple[int, int, int, int, int], tuple[float, int]]:
        scores: dict[tuple[int, int, int, int, int], tuple[float, int]] = {}
        for item in root_stats:
            move = getattr(item, "move", None)
            if move is None:
                continue
            scores[move_identity(move)] = (
                float(getattr(item, "score", 0.0)),
                int(getattr(item, "visits", 0)),
            )
        return scores

    @staticmethod
    def _move_score(
        move: Move,
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
        *,
        default: float = 0.0,
    ) -> float:
        entry = score_map.get(move_identity(move))
        return default if entry is None else entry[0]

    @staticmethod
    def _move_visits(
        move: Move,
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
    ) -> int:
        entry = score_map.get(move_identity(move))
        return 0 if entry is None else entry[1]

    def _safe_moves(self, state: GameState, dice: int, moves: list[Move]) -> list[Move]:
        if not self.require_safe_alternative:
            return list(moves)
        return [
            move
            for move in moves
            if not opponent_winning_dice_after_move(state, move, dice)
        ]

    def _fallback_legal_move(
        self,
        state: GameState,
        dice: int,
        legal: list[Move],
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
    ) -> Move:
        safe = self._safe_moves(state, dice, legal)
        return self._best_move(safe or legal, score_map)

    def _best_or_none(
        self,
        moves: list[Move],
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
    ) -> Move | None:
        if not moves:
            return None
        return self._best_move(moves, score_map)

    def _best_move(
        self,
        moves: list[Move],
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
    ) -> Move:
        return sorted(moves, key=lambda move: self._sort_key(move, score_map))[0]

    def _sort_key(
        self,
        move: Move,
        score_map: dict[tuple[int, int, int, int, int], tuple[float, int]],
    ) -> tuple[float, bool, int, int, tuple[int, int, int, int, int]]:
        captured_distance = 99
        if move.captured_piece is not None:
            captured_distance = chebyshev_distance(
                move.captured_piece.position,
                target_corner(move.captured_piece.player),
            )
        return (
            -self._move_score(move, score_map),
            not is_enemy_capture(move),
            captured_distance,
            -self._move_visits(move, score_map),
            move_identity(move),
        )

    def _within_margin(self, candidate_score: float, base_score: float, margin: float) -> bool:
        effective_margin = min(float(margin), self.max_score_gap_for_override)
        return candidate_score >= base_score - effective_margin

    def _deadline_exhausted(self, started: float) -> bool:
        limit = self.max_step_time_ms
        if limit is None:
            return False
        try:
            return (time.perf_counter() - started) * 1000.0 >= float(limit)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _kept_self_reason(
        enemy_moves: list[Move],
        non_self_moves: list[Move],
        safe_enemy_moves: list[Move],
        safe_non_self_moves: list[Move],
    ) -> str:
        has_raw_alt = bool(enemy_moves or non_self_moves)
        has_safe_alt = bool(safe_enemy_moves or safe_non_self_moves)
        if has_raw_alt and not has_safe_alt:
            return "kept_self_unsafe_alt"
        if has_safe_alt:
            return "kept_self_score_gap"
        return "kept_self_no_alt"
