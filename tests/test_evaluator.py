from ai.evaluator import (
    DISTANCE_WEIGHT,
    EXPECTED_RISK_WEIGHT,
    EXPECTED_WIN_RISK_WEIGHT,
    MATERIAL_WEIGHT,
    WIN_SCORE,
    chebyshev_distance,
    evaluate,
)
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_chebyshev_distance_diagonal_counts_as_one_per_step():
    assert chebyshev_distance(Position(0, 0), Position(0, 0)) == 0
    assert chebyshev_distance(Position(0, 0), Position(2, 2)) == 2
    assert chebyshev_distance(Position(1, 3), Position(4, 4)) == 3
    assert chebyshev_distance(Position(4, 4), Position(0, 0)) == 4


def test_evaluate_red_at_target_corner_wins():
    state = make_state(red={1: Position(4, 4)}, blue={1: Position(0, 0)})

    assert evaluate(state, Player.RED) == WIN_SCORE
    assert evaluate(state, Player.BLUE) == -WIN_SCORE


def test_evaluate_blue_at_target_corner_wins():
    # 蓝到达 (0,0) 是蓝方目标角；红在别处，不重叠。
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 0)})

    assert evaluate(state, Player.BLUE) == WIN_SCORE
    assert evaluate(state, Player.RED) == -WIN_SCORE


def test_evaluate_red_all_blue_dead_wins_by_capture():
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    state.pieces[Player.BLUE][1].alive = False

    assert evaluate(state, Player.RED) == WIN_SCORE
    assert evaluate(state, Player.BLUE) == -WIN_SCORE


def test_evaluate_prefers_state_where_own_piece_is_closer_to_target():
    farther = make_state(red={1: Position(0, 0)}, blue={1: Position(0, 4)})
    closer = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})

    assert evaluate(closer, Player.RED) > evaluate(farther, Player.RED)


def test_evaluate_prefers_state_where_opponent_is_farther_from_their_target():
    # 红视角：蓝距离自己目标(0,0)越远越好
    blue_close = make_state(red={1: Position(0, 0)}, blue={1: Position(1, 1)})
    blue_far = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})

    assert evaluate(blue_far, Player.RED) > evaluate(blue_close, Player.RED)


def test_evaluate_prefers_more_material():
    one_red_dead = make_state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(4, 4)},
    )
    one_red_dead.pieces[Player.RED][2].alive = False

    both_red_alive = make_state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(4, 4)},
    )

    assert evaluate(both_red_alive, Player.RED) > evaluate(one_red_dead, Player.RED)


def test_evaluate_is_zero_sum_for_non_terminal_state():
    state = make_state(
        red={1: Position(1, 0), 2: Position(2, 1)},
        blue={1: Position(3, 4), 2: Position(2, 3)},
    )

    red_score = evaluate(state, Player.RED)
    blue_score = evaluate(state, Player.BLUE)

    assert red_score == -blue_score


def test_evaluate_weights_are_finite_and_positive():
    assert WIN_SCORE > 0
    assert DISTANCE_WEIGHT > 0
    assert MATERIAL_WEIGHT > 0
    # 单子被吃比一个距离单位的代价大得多
    assert MATERIAL_WEIGHT > DISTANCE_WEIGHT


from ai.evaluator import STUCK_PIECE_PENALTY, count_stuck_pieces


def test_count_stuck_pieces_zero_when_all_have_moves():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})

    assert count_stuck_pieces(state, Player.RED) == 0


def test_count_stuck_pieces_detects_corner_piece_surrounded_by_own():
    # Red 1 在 (0,0)，被自家 2/3/4 完全围死
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )

    assert count_stuck_pieces(state, Player.RED) == 1


def test_count_stuck_pieces_dead_pieces_not_counted():
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )
    state.pieces[Player.RED][1].alive = False

    assert count_stuck_pieces(state, Player.RED) == 0


def test_evaluate_penalizes_state_with_own_stuck_piece():
    # 同样的红方棋子数量与距离，唯一区别是 piece 1 是否被围死
    stuck = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )
    free = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(2, 2),  # 4 移到 (2,2)，松开 (1,1)，piece 1 不再被围
        },
        blue={1: Position(4, 4)},
    )

    assert evaluate(free, Player.RED) > evaluate(stuck, Player.RED)


def test_evaluate_zero_sum_still_holds_with_stuck_penalty():
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4), 2: Position(3, 4), 3: Position(4, 3)},
    )

    assert evaluate(state, Player.RED) == -evaluate(state, Player.BLUE)


def test_evaluate_with_risk_weights_is_not_zero_sum_by_design():
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

    red_score = evaluate(state, Player.RED, expected_risk_weight=EXPECTED_RISK_WEIGHT)
    blue_score = evaluate(state, Player.BLUE, expected_risk_weight=EXPECTED_RISK_WEIGHT)

    assert red_score != -blue_score


def test_stuck_penalty_constant_is_finite_and_positive():
    assert STUCK_PIECE_PENALTY > 0
    # 应该比一个材料单位的代价大，否则 AI 不会优先解放角子
    assert STUCK_PIECE_PENALTY > 10


def test_expected_risk_weight_constant_is_finite_and_positive():
    assert EXPECTED_RISK_WEIGHT > 0
    assert EXPECTED_RISK_WEIGHT < MATERIAL_WEIGHT


def test_evaluate_penalizes_expected_capture_risk_when_enabled():
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

    without_risk = evaluate(state, Player.RED, expected_risk_weight=0.0)
    with_risk = evaluate(state, Player.RED, expected_risk_weight=EXPECTED_RISK_WEIGHT)

    assert with_risk < without_risk


def test_evaluate_penalizes_expected_target_win_risk_when_enabled():
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

    without_risk = evaluate(state, Player.RED, expected_win_risk_weight=0.0)
    with_risk = evaluate(state, Player.RED, expected_win_risk_weight=EXPECTED_WIN_RISK_WEIGHT)

    assert EXPECTED_WIN_RISK_WEIGHT > EXPECTED_RISK_WEIGHT
    assert with_risk < without_risk
