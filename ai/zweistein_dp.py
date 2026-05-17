from __future__ import annotations

from functools import lru_cache

from core.game_state import GameState
from core.rules import target_corner
from core.types import MAX_PIECE_ID, MIN_PIECE_ID, Player, chebyshev_distance


MAX_DISTANCE = 4
DISTANCE_VECTOR_SIZE = MAX_PIECE_ID - MIN_PIECE_ID + 1
TABLE_STATES = (MAX_DISTANCE + 1) ** DISTANCE_VECTOR_SIZE
TABLE_HORIZON = 20

DistanceVector = tuple[int, int, int, int, int, int]


def encode_distance_vector(distances: tuple[int, ...]) -> int:
    if len(distances) != DISTANCE_VECTOR_SIZE:
        raise ValueError("distance vector must contain 6 entries")
    index = 0
    multiplier = 1
    for distance in distances:
        if not 0 <= int(distance) <= MAX_DISTANCE:
            raise ValueError("distance values must be between 0 and 4")
        index += int(distance) * multiplier
        multiplier *= MAX_DISTANCE + 1
    return index


def decode_distance_index(index: int) -> DistanceVector:
    if not 0 <= int(index) < TABLE_STATES:
        raise ValueError(f"distance index must be between 0 and {TABLE_STATES - 1}")
    values: list[int] = []
    remaining = int(index)
    for _ in range(DISTANCE_VECTOR_SIZE):
        values.append(remaining % (MAX_DISTANCE + 1))
        remaining //= MAX_DISTANCE + 1
    return tuple(values)  # type: ignore[return-value]


def distance_vector_for(state: GameState, player: Player) -> DistanceVector:
    player = Player.from_value(player)
    target = target_corner(player)
    distances: list[int] = []
    for piece_id in range(MIN_PIECE_ID, MAX_PIECE_ID + 1):
        piece = state.pieces[player].get(piece_id)
        if piece is None or not piece.alive:
            distances.append(MAX_DISTANCE)
        else:
            distances.append(chebyshev_distance(piece.position, target))
    return tuple(distances)  # type: ignore[return-value]


@lru_cache(maxsize=None)
def _cdf_probability(index: int, turns: int) -> float:
    vector = decode_distance_index(index)
    if min(vector) == 0:
        return 1.0
    if turns <= 0:
        return 0.0

    total = 0.0
    for piece_index in range(DISTANCE_VECTOR_SIZE):
        next_vector = list(vector)
        next_vector[piece_index] = max(0, next_vector[piece_index] - 1)
        total += _cdf_probability(encode_distance_vector(tuple(next_vector)), turns - 1)
    return total / DISTANCE_VECTOR_SIZE


def _build_tables() -> tuple[tuple[tuple[float, ...], ...], tuple[tuple[float, ...], ...]]:
    pdf_rows: list[tuple[float, ...]] = []
    cdf_rows: list[tuple[float, ...]] = []
    for index in range(TABLE_STATES):
        cdf = tuple(_cdf_probability(index, turns) for turns in range(1, TABLE_HORIZON + 1))
        previous = 0.0
        pdf_values: list[float] = []
        for value in cdf:
            pdf_values.append(max(0.0, value - previous))
            previous = value
        pdf_rows.append(tuple(pdf_values))
        cdf_rows.append(cdf)
    return tuple(pdf_rows), tuple(cdf_rows)


PDF_VAL, CDF_VAL = _build_tables()


def _cdf_after_turns(cdf_row: tuple[float, ...], turns: int) -> float:
    if turns <= 0:
        return 0.0
    if turns >= TABLE_HORIZON:
        return cdf_row[-1]
    return cdf_row[turns - 1]


def zweistein_dp_win_prob(state: GameState, perspective: Player) -> float:
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return 1.0
    if winner is perspective.opponent:
        return 0.0

    own_index = encode_distance_vector(distance_vector_for(state, perspective))
    opp_index = encode_distance_vector(distance_vector_for(state, perspective.opponent))
    own_pdf = PDF_VAL[own_index]
    own_cdf = CDF_VAL[own_index]
    opp_cdf = CDF_VAL[opp_index]

    perspective_to_move = state.current_player is perspective
    resolved_win_prob = 0.0
    for turn_index, own_first_at_turn in enumerate(own_pdf):
        opponent_turns_before = turn_index if perspective_to_move else turn_index + 1
        opponent_already_won = _cdf_after_turns(opp_cdf, opponent_turns_before)
        resolved_win_prob += own_first_at_turn * (1.0 - opponent_already_won)

    unresolved_prob = (1.0 - own_cdf[-1]) * (1.0 - opp_cdf[-1])
    return max(0.0, min(1.0, resolved_win_prob + 0.5 * unresolved_prob))


def zweistein_dp_score(state: GameState, perspective: Player) -> float:
    return 2.0 * zweistein_dp_win_prob(state, perspective) - 1.0
