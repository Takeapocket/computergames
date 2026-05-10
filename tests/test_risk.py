import pytest

from ai.risk import (
    expected_capture_risk,
    expected_target_win_risk,
    total_expected_capture_risk,
)
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_expected_capture_risk_counts_dice_probability_once_per_dice():
    state = make_state(
        red={3: Position(2, 2)},
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(3, 4),
            4: Position(3, 3),
            5: Position(4, 0),
            6: Position(0, 4),
        },
    )

    risk = expected_capture_risk(state, Player.RED)

    assert risk == {3: pytest.approx(1 / 6)}
    assert total_expected_capture_risk(state, Player.RED) == pytest.approx(1 / 6)


def test_expected_capture_risk_reuses_core_dice_fallback_selection():
    state = make_state(
        red={4: Position(2, 2)},
        blue={
            3: Position(3, 3),
            5: Position(0, 4),
        },
    )

    risk = expected_capture_risk(state, Player.RED)

    assert risk == {4: pytest.approx(4 / 6)}


def test_expected_capture_risk_ignores_dead_target_pieces():
    state = make_state(
        red={3: Position(2, 2)},
        blue={4: Position(3, 3)},
    )
    state.pieces[Player.RED][3].alive = False

    assert expected_capture_risk(state, Player.RED) == {}
    assert total_expected_capture_risk(state, Player.RED) == 0.0


def test_expected_target_win_risk_counts_opponent_next_turn_goal_probability():
    state = make_state(
        red={1: Position(2, 2)},
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(3, 4),
            4: Position(1, 1),
            5: Position(4, 0),
            6: Position(0, 4),
        },
    )

    assert expected_target_win_risk(state, Player.RED) == pytest.approx(1 / 6)
