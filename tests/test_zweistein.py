from __future__ import annotations

import math
import sys

import pytest

from ai.evaluator import WIN_SCORE
from ai.zweistein import zweistein_lite_score
from ai.zweistein_ai import ZweisteinGreedyAI
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


def test_zweistein_default_score_matches_pre_parameterization_characterization():
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 2)},
        blue={1: Position(1, 1)},
    )

    assert state.get_winner() is None
    assert zweistein_lite_score(state, Player.RED) == pytest.approx(
        -546.0,
        rel=0.0,
        abs=1e-12,
    )


def test_zweistein_default_ai_choice_matches_pre_parameterization_characterization():
    state = make_state(
        red={1: Position(1, 1)},
        blue={1: Position(4, 0)},
    )

    move = ZweisteinGreedyAI(randomize_ties=False).choose_move(state, dice=1)

    assert move is not None
    assert move.piece_id == 1
    assert move.from_pos == Position(1, 1)
    assert move.to_pos == Position(2, 2)
    assert not move.is_capture


def test_zweistein_rejects_non_finite_custom_weights():
    state = make_state(
        red={1: Position(1, 1)},
        blue={1: Position(4, 0)},
    )
    weight_names = (
        "progress_weight",
        "material_weight",
        "mobility_weight",
        "capture_risk_weight",
        "target_win_risk_weight",
    )

    for weight_name in weight_names:
        for invalid_weight in (math.nan, math.inf, -math.inf):
            with pytest.raises(ValueError, match=rf"{weight_name}.*finite"):
                zweistein_lite_score(
                    state,
                    Player.RED,
                    **{weight_name: invalid_weight},
                )
            with pytest.raises(ValueError, match=rf"{weight_name}.*finite"):
                ZweisteinGreedyAI(**{weight_name: invalid_weight})


def test_zweistein_rejects_non_finite_score_from_extreme_finite_weight():
    state = make_state(
        red={1: Position(2, 2)},
        blue={1: Position(4, 0)},
    )

    with pytest.raises(ValueError, match=r"Zweistein score.*finite"):
        zweistein_lite_score(
            state,
            Player.RED,
            progress_weight=sys.float_info.max,
            material_weight=0.0,
            mobility_weight=0.0,
            capture_risk_weight=0.0,
            target_win_risk_weight=0.0,
        )


def test_zweistein_ai_surfaces_non_finite_score_as_value_error():
    state = make_state(
        red={1: Position(1, 1)},
        blue={1: Position(4, 4)},
    )
    original = state.serialize()
    ai = ZweisteinGreedyAI(
        randomize_ties=False,
        progress_weight=sys.float_info.max,
        material_weight=0.0,
        mobility_weight=0.0,
        capture_risk_weight=0.0,
        target_win_risk_weight=0.0,
    )

    with pytest.raises(ValueError, match=r"Zweistein score.*finite"):
        ai.choose_move(state, dice=1)

    assert state.serialize() == original


def test_zweistein_custom_material_only_weight_is_hand_computable():
    state = make_state(
        red={1: Position(1, 1), 2: Position(2, 1)},
        blue={1: Position(3, 3)},
    )

    score = zweistein_lite_score(
        state,
        Player.RED,
        progress_weight=0.0,
        material_weight=7.0,
        mobility_weight=0.0,
        capture_risk_weight=0.0,
        target_win_risk_weight=0.0,
    )

    assert score == 7.0


def test_zweistein_greedy_custom_weights_change_self_capture_choice():
    progress_state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3)},
        blue={1: Position(4, 0)},
    )
    material_state = progress_state.clone(include_history=False)
    progress_ai = ZweisteinGreedyAI(
        randomize_ties=False,
        progress_weight=1000.0,
        material_weight=0.0,
        mobility_weight=0.0,
        capture_risk_weight=0.0,
        target_win_risk_weight=0.0,
    )
    material_ai = ZweisteinGreedyAI(
        randomize_ties=False,
        progress_weight=0.0,
        material_weight=1000.0,
        mobility_weight=0.0,
        capture_risk_weight=0.0,
        target_win_risk_weight=0.0,
    )

    progress_move = progress_ai.choose_move(progress_state, dice=1)
    material_move = material_ai.choose_move(material_state, dice=1)

    assert progress_move is not None and progress_move.is_capture
    assert progress_move.captured_piece is not None
    assert progress_move.captured_piece.player is Player.RED
    assert material_move is not None and not material_move.is_capture
