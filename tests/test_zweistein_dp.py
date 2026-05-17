import pytest

from ai.match import default_starting_state
from ai.zweistein_dp import (
    CDF_VAL,
    PDF_VAL,
    TABLE_HORIZON,
    TABLE_STATES,
    decode_distance_index,
    distance_vector_for,
    encode_distance_vector,
    zweistein_dp_score,
    zweistein_dp_win_prob,
)
from core.game_state import GameState
from core.types import Player, Position


def test_distance_vector_encoding_roundtrips() -> None:
    samples = [
        (0, 0, 0, 0, 0, 0),
        (4, 4, 4, 4, 4, 4),
        (0, 1, 2, 3, 4, 0),
        (4, 3, 2, 1, 0, 4),
    ]

    for vector in samples:
        assert decode_distance_index(encode_distance_vector(vector)) == vector


@pytest.mark.parametrize(
    "vector",
    [
        (0, 1, 2, 3, 4),
        (0, 1, 2, 3, 4, 5),
        (-1, 1, 2, 3, 4, 0),
    ],
)
def test_distance_vector_encoding_rejects_invalid_vectors(vector) -> None:
    with pytest.raises(ValueError):
        encode_distance_vector(vector)


def test_dp_tables_have_expected_size_and_probability_shape() -> None:
    assert len(PDF_VAL) == TABLE_STATES == 5**6
    assert len(CDF_VAL) == TABLE_STATES
    assert all(len(row) == TABLE_HORIZON for row in PDF_VAL)
    assert all(len(row) == TABLE_HORIZON for row in CDF_VAL)

    for index in (
        encode_distance_vector((4, 4, 4, 4, 4, 4)),
        encode_distance_vector((1, 4, 4, 4, 4, 4)),
        encode_distance_vector((2, 2, 2, 2, 2, 2)),
    ):
        cdf_row = CDF_VAL[index]
        pdf_row = PDF_VAL[index]
        assert all(value >= 0.0 for value in pdf_row)
        assert all(0.0 <= value <= 1.0 for value in cdf_row)
        assert all(a <= b for a, b in zip(cdf_row, cdf_row[1:]))
        assert sum(pdf_row) <= 1.0 + 1e-12


def test_vector_with_zero_distance_is_already_winning_in_table() -> None:
    index = encode_distance_vector((0, 4, 4, 4, 4, 4))

    assert CDF_VAL[index] == tuple(1.0 for _ in range(TABLE_HORIZON))
    assert PDF_VAL[index][0] == 1.0
    assert all(value == 0.0 for value in PDF_VAL[index][1:])


def test_distance_vector_for_uses_target_distance_and_dead_piece_distance() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(4, 3)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )
    state.pieces[Player.RED][2].alive = False

    assert distance_vector_for(state, Player.RED) == (4, 4, 4, 4, 4, 4)
    assert distance_vector_for(state, Player.BLUE) == (4, 4, 4, 4, 4, 4)


def test_closer_distance_vector_has_no_lower_cumulative_probability() -> None:
    close = encode_distance_vector((1, 4, 4, 4, 4, 4))
    far = encode_distance_vector((4, 4, 4, 4, 4, 4))

    assert CDF_VAL[close][0] > CDF_VAL[far][0]


def test_zweistein_dp_terminal_probabilities_are_exact() -> None:
    red_wins = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 4)},
        current_player=Player.BLUE,
    )

    assert zweistein_dp_win_prob(red_wins, Player.RED) == 1.0
    assert zweistein_dp_win_prob(red_wins, Player.BLUE) == 0.0


def test_zweistein_dp_score_matches_probability_scale() -> None:
    state = default_starting_state()
    prob = zweistein_dp_win_prob(state, Player.RED)

    assert 0.0 <= prob <= 1.0
    assert zweistein_dp_score(state, Player.RED) == pytest.approx(2.0 * prob - 1.0)


def test_zweistein_dp_red_blue_mirror_probabilities_are_complementary() -> None:
    red_to_move = GameState.from_layout(
        red={1: Position(1, 1), 2: Position(0, 1)},
        blue={1: Position(3, 3), 2: Position(4, 3)},
        current_player=Player.RED,
    )
    blue_to_move_mirror = GameState.from_layout(
        red={1: Position(1, 1), 2: Position(0, 1)},
        blue={1: Position(3, 3), 2: Position(4, 3)},
        current_player=Player.BLUE,
    )

    assert zweistein_dp_win_prob(red_to_move, Player.RED) == pytest.approx(
        zweistein_dp_win_prob(blue_to_move_mirror, Player.BLUE)
    )
