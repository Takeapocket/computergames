from __future__ import annotations

import pytest

from ai.evaluator import WIN_SCORE
from ai.zweistein import zweistein_lite_score
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


def mirror_state(state: GameState) -> GameState:
    red = {
        piece_id: Position(4 - piece.position.row, 4 - piece.position.col)
        for piece_id, piece in state.pieces[Player.BLUE].items()
        if piece.alive
    }
    blue = {
        piece_id: Position(4 - piece.position.row, 4 - piece.position.col)
        for piece_id, piece in state.pieces[Player.RED].items()
        if piece.alive
    }
    return GameState.from_layout(
        red=red,
        blue=blue,
        current_player=state.current_player.opponent,
    )


def test_zweistein_terminal_scores_match_win_score():
    state = make_state(red={1: Position(4, 4)}, blue={1: Position(0, 0)})

    assert zweistein_lite_score(state, Player.RED) == WIN_SCORE
    assert zweistein_lite_score(state, Player.BLUE) == -WIN_SCORE


def test_zweistein_prefers_piece_closer_to_target():
    far = make_state(red={1: Position(0, 0)}, blue={1: Position(0, 4)})
    close = make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4)})

    assert zweistein_lite_score(close, Player.RED) > zweistein_lite_score(far, Player.RED)


def test_zweistein_prefers_more_material():
    down_piece = make_state(
        red={1: Position(1, 1)},
        blue={1: Position(3, 3), 2: Position(4, 2)},
    )
    even_material = make_state(
        red={1: Position(1, 1), 2: Position(2, 1)},
        blue={1: Position(3, 3), 2: Position(4, 2)},
    )

    assert zweistein_lite_score(even_material, Player.RED) > zweistein_lite_score(down_piece, Player.RED)


def test_zweistein_prefers_more_mobile_shape():
    blocked = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4), 2: Position(4, 3), 3: Position(3, 4), 4: Position(3, 3)},
    )
    mobile = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 2),
            3: Position(2, 0),
            4: Position(2, 2),
        },
        blue={1: Position(4, 4), 2: Position(4, 3), 3: Position(3, 4), 4: Position(3, 3)},
    )

    assert zweistein_lite_score(mobile, Player.RED) > zweistein_lite_score(blocked, Player.RED)


def test_zweistein_red_blue_mirror_is_opposite():
    state = make_state(
        red={1: Position(1, 0), 2: Position(2, 1)},
        blue={1: Position(3, 4), 2: Position(2, 3)},
    )
    mirrored = mirror_state(state)

    assert zweistein_lite_score(state, Player.RED) == pytest.approx(
        -zweistein_lite_score(mirrored, Player.BLUE)
    )


def test_zweistein_sparse_states_do_not_crash():
    empty = make_state()
    single = make_state(red={1: Position(2, 2)})

    assert isinstance(zweistein_lite_score(empty, Player.RED), float)
    assert isinstance(zweistein_lite_score(single, Player.RED), float)
