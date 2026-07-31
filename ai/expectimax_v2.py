from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Literal

from ai.evaluator import WIN_SCORE, evaluate
from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from core.types import Player, chebyshev_distance


EXPECTIMAX_V2_MIN_SCORE: float = -WIN_SCORE
EXPECTIMAX_V2_MAX_SCORE: float = WIN_SCORE
EXPECTIMAX_V2_EVALUATOR_VERSION: str = "current-risk0-v1"

ExpectimaxV2NodeType = Literal["chance", "turn"]
ExpectimaxV2ChancePruning = Literal["none", "star1", "star2", "star2_recursive"]
ExpectimaxV2PieceKey = tuple[str, int, bool, int, int]
ExpectimaxV2StateKey = tuple[str, tuple[ExpectimaxV2PieceKey, ...]]
ExpectimaxV2TranspositionKey = tuple[
    str,
    str,
    int,
    int | None,
    str,
    ExpectimaxV2StateKey,
]
ExpectimaxV2TranspositionTable = dict[ExpectimaxV2TranspositionKey, float]


@dataclass
class ExpectimaxV2SearchStats:
    nodes: int = 0
    tt_hits: int = 0
    tt_stores: int = 0
    chance_prunes: int = 0
    chance_probes: int = 0
    chance_probe_cutoffs: int = 0
    timed_out: bool = False
    completed_depth: int = 0


def expectimax_v2_score_in_bounds(score: float) -> bool:
    return EXPECTIMAX_V2_MIN_SCORE <= float(score) <= EXPECTIMAX_V2_MAX_SCORE


def expectimax_v2_require_score_in_bounds(score: float, *, context: str) -> float:
    value = float(score)
    if not expectimax_v2_score_in_bounds(value):
        raise ValueError(
            f"{context} score {value} outside ExpectimaxV2 bounds "
            f"[{EXPECTIMAX_V2_MIN_SCORE}, {EXPECTIMAX_V2_MAX_SCORE}]"
        )
    return value


def expectimax_v2_state_key(state: GameState) -> ExpectimaxV2StateKey:
    pieces: list[ExpectimaxV2PieceKey] = []
    for player in (Player.RED, Player.BLUE):
        for piece_id in sorted(state.pieces[player]):
            piece = state.pieces[player][piece_id]
            row = piece.position.row if piece.alive else -1
            col = piece.position.col if piece.alive else -1
            pieces.append((player.value, int(piece_id), bool(piece.alive), row, col))
    return (state.current_player.value, tuple(pieces))


def expectimax_v2_transposition_key(
    state: GameState,
    *,
    node_type: ExpectimaxV2NodeType,
    perspective: Player,
    depth: int,
    dice: int | None,
    evaluator_version: str = EXPECTIMAX_V2_EVALUATOR_VERSION,
) -> ExpectimaxV2TranspositionKey:
    if node_type not in ("chance", "turn"):
        raise ValueError("node_type must be 'chance' or 'turn'")
    normalized_dice = None if dice is None else int(dice)
    if normalized_dice is not None and not 1 <= normalized_dice <= 6:
        raise ValueError("dice must be between 1 and 6")
    return (
        node_type,
        Player.from_value(perspective).value,
        int(depth),
        normalized_dice,
        str(evaluator_version),
        expectimax_v2_state_key(state),
    )


def expectimax_v2_order_moves(state: GameState, moves: list[Move]) -> list[Move]:
    del state

    def _ordering_key(move: Move) -> tuple[bool, bool, int, int]:
        target = target_corner(move.player)
        before = chebyshev_distance(move.from_pos, target)
        after = chebyshev_distance(move.to_pos, target)
        captured = move.captured_piece
        enemy_capture = captured is not None and captured.player is move.player.opponent
        return (
            move.to_pos == target,
            enemy_capture,
            before - after,
            -after,
        )

    return sorted(moves, key=_ordering_key, reverse=True)


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
        use_transposition_table: bool = False,
        move_ordering: bool = False,
        iterative_deepening: bool = False,
        chance_pruning: ExpectimaxV2ChancePruning = "none",
    ) -> None:
        if chance_pruning not in ("none", "star1", "star2", "star2_recursive"):
            raise ValueError(
                "chance_pruning must be one of: "
                "'none', 'star1', 'star2', 'star2_recursive'"
            )
        self.depth = int(depth)
        self.time_limit_ms = float(time_limit_ms)
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = bool(randomize_ties)
        self.use_transposition_table = bool(use_transposition_table)
        self.move_ordering = bool(move_ordering)
        self.iterative_deepening = bool(iterative_deepening)
        self.chance_pruning = chance_pruning
        self.expected_risk_weight = 0.0
        self.expected_win_risk_weight = 0.0
        self.last_search_stats = ExpectimaxV2SearchStats()

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        self.last_search_stats = ExpectimaxV2SearchStats()
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        if self.depth <= 0:
            return GreedyAI(rng=self._rng, randomize_ties=self.randomize_ties).choose_move(state, dice)

        deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        perspective = state.current_player
        table: ExpectimaxV2TranspositionTable | None = (
            {} if self.use_transposition_table else None
        )

        if self.iterative_deepening:
            return self._choose_move_iterative(
                state,
                legal=legal,
                dice=dice,
                perspective=perspective,
                deadline=deadline,
                table=table,
            )

        best_moves, complete = self._search_root_at_depth(
            state,
            legal=legal,
            dice=dice,
            perspective=perspective,
            depth=self.depth,
            deadline=deadline,
            table=table,
        )
        if complete:
            self.last_search_stats.completed_depth = self.depth
        return self._fallback(legal, best_moves)

    def _choose_move_iterative(
        self,
        state: GameState,
        *,
        legal: list[Move],
        dice: int,
        perspective: Player,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> Move:
        best_completed_moves: list[Move] = []
        for depth in range(1, self.depth + 1):
            if time.perf_counter() >= deadline:
                self.last_search_stats.timed_out = True
                break
            best_moves, complete = self._search_root_at_depth(
                state,
                legal=legal,
                dice=dice,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
            if not complete:
                break
            best_completed_moves = best_moves
            self.last_search_stats.completed_depth = depth
        return self._fallback(legal, best_completed_moves)

    def _search_root_at_depth(
        self,
        state: GameState,
        *,
        legal: list[Move],
        dice: int,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[list[Move], bool]:
        best_score = float("-inf")
        best_moves: list[Move] = []
        complete = True
        search_moves = self._ordered_moves(state, legal)

        for move in search_moves:
            if time.perf_counter() >= deadline:
                self.last_search_stats.timed_out = True
                return self._moves_in_legal_order(legal, best_moves), False
            state.apply_move(move, dice=dice)
            try:
                cutoff_upper_bound = (
                    best_score
                    if self.chance_pruning
                    in ("star1", "star2", "star2_recursive")
                    and best_moves
                    else None
                )
                chance_kwargs = {
                    "perspective": perspective,
                    "depth": depth,
                    "deadline": deadline,
                    "table": table,
                }
                if cutoff_upper_bound is not None:
                    chance_kwargs["cutoff_upper_bound"] = cutoff_upper_bound
                score, child_complete = self._chance_value_with_status(state, **chance_kwargs)
                if not child_complete and self.last_search_stats.timed_out:
                    complete = False
            finally:
                state.undo_move()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self._moves_in_legal_order(legal, best_moves), complete

    def _chance_value(self, state: GameState, *, perspective, depth: int, deadline: float) -> float:
        value, _complete = self._chance_value_with_status(
            state,
            perspective=perspective,
            depth=depth,
            deadline=deadline,
            table=None,
            cutoff_upper_bound=None,
        )
        return value

    def _chance_value_with_status(
        self,
        state: GameState,
        *,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
        cutoff_upper_bound: float | None = None,
        cutoff_lower_bound: float | None = None,
    ) -> tuple[float, bool]:
        self.last_search_stats.nodes += 1
        if time.perf_counter() >= deadline:
            self.last_search_stats.timed_out = True
            return self._evaluate_leaf(state, perspective=perspective), False
        if depth <= 0 or state.get_winner() is not None:
            return self._evaluate_leaf(state, perspective=perspective), True

        key = expectimax_v2_transposition_key(
            state,
            node_type="chance",
            perspective=perspective,
            depth=depth,
            dice=None,
        )
        if table is not None and key in table:
            self.last_search_stats.tt_hits += 1
            return expectimax_v2_require_score_in_bounds(table[key], context="cached chance"), True

        if self.chance_pruning == "star2_recursive" or (
            self.chance_pruning == "star2" and depth == 1
        ):
            value, complete = self._chance_value_star2(
                state,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
                cutoff_upper_bound=cutoff_upper_bound,
                cutoff_lower_bound=cutoff_lower_bound,
            )
        elif self.chance_pruning in ("star1", "star2"):
            value, complete = self._chance_value_star1(
                state,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
                cutoff_upper_bound=cutoff_upper_bound,
                cutoff_lower_bound=cutoff_lower_bound,
            )
        else:
            value, complete = self._chance_value_exact(
                state,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
        if complete and table is not None:
            table[key] = value
            self.last_search_stats.tt_stores += 1
        return value, complete

    def _chance_value_exact(
        self,
        state: GameState,
        *,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[float, bool]:
        total = 0.0
        complete = True
        for dice in range(1, 7):
            value, child_complete = self._turn_value_with_status(
                state,
                dice=dice,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
            total += value
            complete = complete and child_complete
        value = total / 6.0
        value = expectimax_v2_require_score_in_bounds(value, context="chance")
        return value, complete

    def _chance_value_star1(
        self,
        state: GameState,
        *,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
        cutoff_upper_bound: float | None,
        cutoff_lower_bound: float | None,
    ) -> tuple[float, bool]:
        total = 0.0
        complete = True
        for index, dice in enumerate(range(1, 7), start=1):
            value, child_complete = self._turn_value_with_status(
                state,
                dice=dice,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
            total += value
            complete = complete and child_complete
            remaining = 6 - index
            if (
                cutoff_upper_bound is not None
                and remaining > 0
                and not self.last_search_stats.timed_out
            ):
                max_possible = (total + remaining * EXPECTIMAX_V2_MAX_SCORE) / 6.0
                if max_possible < cutoff_upper_bound:
                    self.last_search_stats.chance_prunes += remaining
                    return (
                        expectimax_v2_require_score_in_bounds(
                            max_possible,
                            context="chance-pruned-upper-bound",
                        ),
                        False,
                    )
            if (
                cutoff_lower_bound is not None
                and remaining > 0
                and not self.last_search_stats.timed_out
            ):
                min_possible = (total + remaining * EXPECTIMAX_V2_MIN_SCORE) / 6.0
                if min_possible > cutoff_lower_bound:
                    self.last_search_stats.chance_prunes += remaining
                    return (
                        expectimax_v2_require_score_in_bounds(
                            min_possible,
                            context="chance-pruned-lower-bound",
                        ),
                        False,
                    )
        value = total / 6.0
        value = expectimax_v2_require_score_in_bounds(value, context="chance")
        return value, complete


    def _chance_value_probe_exact(
        self,
        state: GameState,
        *,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[float, bool]:
        self.last_search_stats.nodes += 1
        if time.perf_counter() >= deadline:
            self.last_search_stats.timed_out = True
            return self._evaluate_leaf(state, perspective=perspective), False
        if depth <= 0 or state.get_winner() is not None:
            return self._evaluate_leaf(state, perspective=perspective), True

        key = expectimax_v2_transposition_key(
            state,
            node_type="chance",
            perspective=perspective,
            depth=depth,
            dice=None,
        )
        if table is not None and key in table:
            self.last_search_stats.tt_hits += 1
            return (
                expectimax_v2_require_score_in_bounds(
                    table[key],
                    context="cached exact probe chance",
                ),
                True,
            )

        total = 0.0
        for dice in range(1, 7):
            value, complete = self._turn_value_probe_exact(
                state,
                dice=dice,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
            if not complete:
                return value, False
            total += value
        value = expectimax_v2_require_score_in_bounds(
            total / 6.0,
            context="exact probe chance",
        )
        if table is not None:
            table[key] = value
            self.last_search_stats.tt_stores += 1
        return value, True

    def _turn_value_probe_exact(
        self,
        state: GameState,
        *,
        dice: int,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[float, bool]:
        self.last_search_stats.nodes += 1
        winner = state.get_winner()
        if winner is not None:
            value = WIN_SCORE if winner is perspective else -WIN_SCORE
            return expectimax_v2_require_score_in_bounds(value, context="terminal"), True

        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        key = expectimax_v2_transposition_key(
            state,
            node_type="turn",
            perspective=perspective,
            depth=depth,
            dice=dice,
        )
        if not legal:
            value = -WIN_SCORE if whose_turn is perspective else WIN_SCORE
            value = expectimax_v2_require_score_in_bounds(
                value,
                context="exact probe no-move",
            )
            if table is not None:
                table[key] = value
                self.last_search_stats.tt_stores += 1
            return value, True
        if time.perf_counter() >= deadline:
            self.last_search_stats.timed_out = True
            return self._evaluate_leaf(state, perspective=perspective), False
        if table is not None and key in table:
            self.last_search_stats.tt_hits += 1
            return (
                expectimax_v2_require_score_in_bounds(
                    table[key],
                    context="cached exact probe turn",
                ),
                True,
            )

        scores = []
        for move in self._ordered_moves(state, legal):
            if time.perf_counter() >= deadline:
                self.last_search_stats.timed_out = True
                return self._evaluate_leaf(state, perspective=perspective), False
            state.apply_move(move, dice=dice)
            try:
                value, complete = self._chance_value_probe_exact(
                    state,
                    perspective=perspective,
                    depth=depth - 1,
                    deadline=deadline,
                    table=table,
                )
            finally:
                state.undo_move()
            if not complete:
                return value, False
            scores.append(value)

        value = max(scores) if whose_turn is perspective else min(scores)
        value = expectimax_v2_require_score_in_bounds(value, context="exact probe turn")
        if table is not None:
            table[key] = value
            self.last_search_stats.tt_stores += 1
        return value, True

    def _probe_turn_bound(
        self,
        state: GameState,
        *,
        dice: int,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[float, bool]:
        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        if not legal:
            value = -WIN_SCORE if whose_turn is perspective else WIN_SCORE
            return (
                expectimax_v2_require_score_in_bounds(
                    value,
                    context="star2-probe-no-move",
                ),
                True,
            )
        if time.perf_counter() >= deadline:
            self.last_search_stats.timed_out = True
            return self._evaluate_leaf(state, perspective=perspective), False

        move = self._ordered_moves(state, legal)[0]
        state.apply_move(move, dice=dice)
        self.last_search_stats.chance_probes += 1
        try:
            return self._chance_value_probe_exact(
                state,
                perspective=perspective,
                depth=depth - 1,
                deadline=deadline,
                table=table,
            )
        finally:
            state.undo_move()

    def _chance_value_star2(
        self,
        state: GameState,
        *,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
        cutoff_upper_bound: float | None,
        cutoff_lower_bound: float | None,
    ) -> tuple[float, bool]:
        whose_turn = state.current_player
        upper_probe = (
            cutoff_upper_bound is not None
            and cutoff_lower_bound is None
            and whose_turn is not perspective
        )
        lower_probe = (
            cutoff_lower_bound is not None
            and cutoff_upper_bound is None
            and whose_turn is perspective
        )
        if not (upper_probe or lower_probe):
            return self._chance_value_star1(
                state,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
                cutoff_upper_bound=cutoff_upper_bound,
                cutoff_lower_bound=cutoff_lower_bound,
            )

        probe_total = 0.0
        for dice in range(1, 7):
            value, complete = self._probe_turn_bound(
                state,
                dice=dice,
                perspective=perspective,
                depth=depth,
                deadline=deadline,
                table=table,
            )
            if not complete:
                return value, False
            probe_total += value

        probe_bound = expectimax_v2_require_score_in_bounds(
            probe_total / 6.0,
            context="star2-probe-bound",
        )
        if upper_probe:
            assert cutoff_upper_bound is not None
            should_cut = probe_bound < cutoff_upper_bound
        else:
            assert lower_probe and cutoff_lower_bound is not None
            should_cut = probe_bound > cutoff_lower_bound
        if should_cut:
            self.last_search_stats.chance_probe_cutoffs += 1
            return probe_bound, False

        return self._chance_value_star1(
            state,
            perspective=perspective,
            depth=depth,
            deadline=deadline,
            table=table,
            cutoff_upper_bound=cutoff_upper_bound,
            cutoff_lower_bound=cutoff_lower_bound,
        )

    def _turn_value(self, state: GameState, *, dice: int, perspective, depth: int, deadline: float) -> float:
        value, _complete = self._turn_value_with_status(
            state,
            dice=dice,
            perspective=perspective,
            depth=depth,
            deadline=deadline,
            table=None,
        )
        return value

    def _turn_value_with_status(
        self,
        state: GameState,
        *,
        dice: int,
        perspective: Player,
        depth: int,
        deadline: float,
        table: ExpectimaxV2TranspositionTable | None,
    ) -> tuple[float, bool]:
        self.last_search_stats.nodes += 1
        winner = state.get_winner()
        if winner is not None:
            value = WIN_SCORE if winner is perspective else -WIN_SCORE
            return expectimax_v2_require_score_in_bounds(value, context="terminal"), True

        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        key = expectimax_v2_transposition_key(
            state,
            node_type="turn",
            perspective=perspective,
            depth=depth,
            dice=dice,
        )
        if not legal:
            value = -WIN_SCORE if whose_turn is perspective else WIN_SCORE
            value = expectimax_v2_require_score_in_bounds(value, context="no-move")
            if table is not None:
                table[key] = value
                self.last_search_stats.tt_stores += 1
            return value, True
        if time.perf_counter() >= deadline:
            self.last_search_stats.timed_out = True
            return self._evaluate_leaf(state, perspective=perspective), False
        if table is not None and key in table:
            self.last_search_stats.tt_hits += 1
            return expectimax_v2_require_score_in_bounds(table[key], context="cached turn"), True

        scores = []
        complete = True
        search_moves = self._ordered_moves(state, legal)
        for move in search_moves:
            if time.perf_counter() >= deadline:
                self.last_search_stats.timed_out = True
                complete = False
                break
            state.apply_move(move, dice=dice)
            try:
                chance_kwargs = {
                    "perspective": perspective,
                    "depth": depth - 1,
                    "deadline": deadline,
                    "table": table,
                }
                if self.chance_pruning in (
                    "star1",
                    "star2",
                    "star2_recursive",
                ) and scores:
                    if whose_turn is perspective:
                        chance_kwargs["cutoff_upper_bound"] = max(scores)
                    else:
                        chance_kwargs["cutoff_lower_bound"] = min(scores)
                value, child_complete = self._chance_value_with_status(
                    state,
                    **chance_kwargs,
                )
                scores.append(value)
                complete = complete and child_complete
            finally:
                state.undo_move()
        if not scores:
            return self._evaluate_leaf(state, perspective=perspective), False
        value = max(scores) if whose_turn is perspective else min(scores)
        value = expectimax_v2_require_score_in_bounds(value, context="turn")
        if complete and table is not None:
            table[key] = value
            self.last_search_stats.tt_stores += 1
        return value, complete

    def _evaluate_leaf(self, state: GameState, *, perspective: Player) -> float:
        value = evaluate(
            state,
            perspective=perspective,
            expected_risk_weight=0.0,
            expected_win_risk_weight=0.0,
        )
        return expectimax_v2_require_score_in_bounds(value, context="leaf")

    def _ordered_moves(self, state: GameState, moves: list[Move]) -> list[Move]:
        if not self.move_ordering:
            return moves
        return expectimax_v2_order_moves(state, moves)

    def _moves_in_legal_order(self, legal: list[Move], moves: list[Move]) -> list[Move]:
        if len(moves) <= 1:
            return moves
        return [move for move in legal if move in moves]

    def _fallback(self, legal: list[Move], best_moves: list[Move]) -> Move:
        choices = best_moves or legal
        return self._rng.choice(choices) if self.randomize_ties else choices[0]
