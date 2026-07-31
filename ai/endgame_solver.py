from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal

from ai.expectimax_v2 import ExpectimaxV2StateKey, expectimax_v2_state_key
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from core.types import Player


DEFAULT_ENDGAME_MAX_TOTAL_PIECES = 3
DEFAULT_ENDGAME_MAX_TOTAL_DISTANCE = 6

ExactEndgameNodeType = Literal["chance", "turn"]
ExactEndgameTranspositionKey = tuple[
    ExactEndgameNodeType,
    int | None,
    ExpectimaxV2StateKey,
]
ExactEndgameTranspositionTable = dict[ExactEndgameTranspositionKey, float]


@dataclass
class ExactEndgameSearchStats:
    nodes: int = 0
    chance_nodes: int = 0
    turn_nodes: int = 0
    tt_hits: int = 0
    tt_stores: int = 0


def endgame_progress_measure(state: GameState) -> int:
    return sum(
        abs(piece.position.row - target_corner(player).row)
        + abs(piece.position.col - target_corner(player).col)
        for player, pieces in state.pieces.items()
        for piece in pieces.values()
        if piece.alive
    )


def _living_piece_count(state: GameState) -> int:
    return sum(
        1
        for pieces in state.pieces.values()
        for piece in pieces.values()
        if piece.alive
    )


def is_exact_endgame_eligible(
    state: GameState,
    *,
    max_total_pieces: int = DEFAULT_ENDGAME_MAX_TOTAL_PIECES,
    max_total_distance: int = DEFAULT_ENDGAME_MAX_TOTAL_DISTANCE,
) -> bool:
    max_pieces = int(max_total_pieces)
    max_distance = int(max_total_distance)
    if max_pieces < 0:
        raise ValueError("max_total_pieces must be non-negative")
    if max_distance < 0:
        raise ValueError("max_total_distance must be non-negative")
    if state.get_winner() is not None:
        return True
    return (
        _living_piece_count(state) <= max_pieces
        or endgame_progress_measure(state) <= max_distance
    )


def exact_endgame_transposition_key(
    state: GameState,
    *,
    node_type: ExactEndgameNodeType,
    dice: int | None,
) -> ExactEndgameTranspositionKey:
    if node_type not in ("chance", "turn"):
        raise ValueError("node_type must be 'chance' or 'turn'")
    normalized_dice = None if dice is None else int(dice)
    if node_type == "chance" and normalized_dice is not None:
        raise ValueError("chance keys must not include dice")
    if node_type == "turn" and (
        normalized_dice is None or not 1 <= normalized_dice <= 6
    ):
        raise ValueError("turn keys require dice between 1 and 6")
    return node_type, normalized_dice, expectimax_v2_state_key(state)


def _require_probability(value: float, *, context: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{context} probability outside [0, 1]: {probability!r}")
    return probability


class ExactEndgameSolver:
    def __init__(
        self,
        *,
        max_total_pieces: int = DEFAULT_ENDGAME_MAX_TOTAL_PIECES,
        max_total_distance: int = DEFAULT_ENDGAME_MAX_TOTAL_DISTANCE,
        use_transposition_table: bool = True,
    ) -> None:
        self.max_total_pieces = int(max_total_pieces)
        self.max_total_distance = int(max_total_distance)
        if self.max_total_pieces < 0:
            raise ValueError("max_total_pieces must be non-negative")
        if self.max_total_distance < 0:
            raise ValueError("max_total_distance must be non-negative")
        self.use_transposition_table = bool(use_transposition_table)
        self.last_search_stats = ExactEndgameSearchStats()
        self._table: ExactEndgameTranspositionTable | None = None

    @property
    def last_table_size(self) -> int:
        return 0 if self._table is None else len(self._table)

    def _begin_search(self) -> None:
        self.last_search_stats = ExactEndgameSearchStats()
        self._table = {} if self.use_transposition_table else None

    def _require_eligible(self, state: GameState) -> None:
        if state.get_winner() is not None:
            return
        if is_exact_endgame_eligible(
            state,
            max_total_pieces=self.max_total_pieces,
            max_total_distance=self.max_total_distance,
        ):
            return
        raise ValueError(
            "state is outside exact endgame gate: "
            f"alive={_living_piece_count(state)}, "
            f"progress={endgame_progress_measure(state)}, "
            f"max_total_pieces={self.max_total_pieces}, "
            f"max_total_distance={self.max_total_distance}"
        )

    def solve_win_probability(
        self,
        state: GameState,
        *,
        perspective: Player,
    ) -> float:
        perspective = Player.from_value(perspective)
        self._begin_search()

        winner = state.get_winner()
        if winner is not None:
            return 1.0 if winner is perspective else 0.0
        self._require_eligible(state)

        red_probability = self._chance_red_probability(state)
        if perspective is Player.RED:
            return red_probability
        return _require_probability(
            1.0 - red_probability,
            context="blue perspective",
        )

    def _red_probability_after_legal_move(
        self,
        state: GameState,
        *,
        move: Move,
        progress_before: int,
    ) -> float:
        state._apply_known_legal_move(move)
        try:
            progress_after = endgame_progress_measure(state)
            if progress_after >= progress_before:
                raise RuntimeError(
                    "exact endgame move did not strictly reduce progress: "
                    f"before={progress_before}, after={progress_after}, "
                    f"move={move!r}"
                )
            return self._chance_red_probability(state)
        finally:
            state.undo_move()

    def _chance_red_probability(self, state: GameState) -> float:
        self.last_search_stats.nodes += 1
        self.last_search_stats.chance_nodes += 1
        winner = state.get_winner()
        if winner is not None:
            return 1.0 if winner is Player.RED else 0.0

        key = exact_endgame_transposition_key(
            state,
            node_type="chance",
            dice=None,
        )
        if self._table is not None and key in self._table:
            self.last_search_stats.tt_hits += 1
            return _require_probability(
                self._table[key],
                context="cached endgame chance",
            )

        value = _require_probability(
            math.fsum(
                self._turn_red_probability(state, dice=dice)
                for dice in range(1, 7)
            )
            / 6.0,
            context="endgame chance",
        )
        if self._table is not None:
            self._table[key] = value
            self.last_search_stats.tt_stores += 1
        return value

    def _turn_red_probability(self, state: GameState, *, dice: int) -> float:
        self.last_search_stats.nodes += 1
        self.last_search_stats.turn_nodes += 1
        winner = state.get_winner()
        if winner is not None:
            return 1.0 if winner is Player.RED else 0.0

        key = exact_endgame_transposition_key(
            state,
            node_type="turn",
            dice=dice,
        )
        if self._table is not None and key in self._table:
            self.last_search_stats.tt_hits += 1
            return _require_probability(
                self._table[key],
                context="cached endgame turn",
            )

        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        if not legal:
            value = 0.0 if whose_turn is Player.RED else 1.0
        else:
            progress_before = endgame_progress_measure(state)
            values = [
                self._red_probability_after_legal_move(
                    state,
                    move=move,
                    progress_before=progress_before,
                )
                for move in legal
            ]
            value = max(values) if whose_turn is Player.RED else min(values)

        value = _require_probability(value, context="endgame turn")
        if self._table is not None:
            self._table[key] = value
            self.last_search_stats.tt_stores += 1
        return value


class ExactEndgameAI(ExactEndgameSolver):
    def __init__(
        self,
        *,
        max_total_pieces: int = DEFAULT_ENDGAME_MAX_TOTAL_PIECES,
        max_total_distance: int = DEFAULT_ENDGAME_MAX_TOTAL_DISTANCE,
        use_transposition_table: bool = True,
        rng: random.Random | None = None,
        name: str = "endgame_exact",
        randomize_ties: bool = False,
    ) -> None:
        super().__init__(
            max_total_pieces=max_total_pieces,
            max_total_distance=max_total_distance,
            use_transposition_table=use_transposition_table,
        )
        self._rng = rng or random.Random()
        self.name = str(name)
        self.randomize_ties = bool(randomize_ties)
        self.last_root_probabilities: list[tuple[Move, float]] = []

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        self._begin_search()
        self.last_root_probabilities = []
        if state.get_winner() is not None:
            return None
        self._require_eligible(state)

        whose_turn = state.current_player
        legal = state.legal_moves(whose_turn, dice)
        if not legal:
            return None

        progress_before = endgame_progress_measure(state)
        for move in legal:
            red_probability = self._red_probability_after_legal_move(
                state,
                move=move,
                progress_before=progress_before,
            )
            own_probability = (
                red_probability
                if whose_turn is Player.RED
                else _require_probability(
                    1.0 - red_probability,
                    context="blue root",
                )
            )
            self.last_root_probabilities.append((move, own_probability))

        best_probability = max(
            probability for _move, probability in self.last_root_probabilities
        )
        best_moves = [
            move
            for move, probability in self.last_root_probabilities
            if probability == best_probability
        ]
        if self.randomize_ties and len(best_moves) > 1:
            return self._rng.choice(best_moves)
        return best_moves[0]
