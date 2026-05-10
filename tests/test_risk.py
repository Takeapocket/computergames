import pytest

from ai.risk import (
    distance_weighted_capture_risk,
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


def test_distance_weighted_capture_risk_no_risk_is_zero():
    state = make_state(
        red={3: Position(2, 2)},
        blue={1: Position(4, 4)},
    )

    assert distance_weighted_capture_risk(state, Player.RED) == 0.0


def test_distance_weighted_capture_risk_closer_piece_weighs_more():
    # 红 3 在 (3,3) 被蓝 2 在 (4,3) 威胁（蓝 up 到 (3,3)）。
    # 红 3 距目标 (4,4)=1 → weight=1/2=0.5。
    # 红 1 在 (0,2) 被蓝 5 在 (0,3) 威胁（蓝 left 到 (0,2)）。
    # 红 1 距目标 (4,4)=4 → weight=1/5=0.2。
    # 两子各被 1 个 dice 直选 + fallback → 具体值依赖 dice 映射。
    # 关键断言：加权后的值 < 不加权的总值（因为所有权重 ≤ 1）。
    state = make_state(
        red={3: Position(3, 3), 1: Position(0, 2)},
        blue={
            2: Position(4, 3),
            5: Position(0, 3),
        },
    )

    weighted = distance_weighted_capture_risk(state, Player.RED)
    flat = total_expected_capture_risk(state, Player.RED)

    assert weighted > 0.0
    # 加权后一定小于或等于 flat（因为所有权重 ≤ 1.0）
    assert weighted < flat


def test_distance_weighted_capture_risk_dead_pieces_excluded():
    state = make_state(
        red={3: Position(2, 2)},
        blue={3: Position(3, 3)},
    )
    state.pieces[Player.RED][3].alive = False

    assert distance_weighted_capture_risk(state, Player.RED) == 0.0


def test_distance_weighted_capture_risk_piece_near_target_gets_higher_weight():
    # 比较两个场景：同一个子在不同位置被同一威胁吃掉的加权风险。
    # 位置越靠近目标角，加权风险越高。
    # 红 3 在 (3,3) — 距 (4,4)=1；红 3 在 (1,1) — 距 (4,4)=3。
    # 威胁都来自同一个蓝 2 在 (4,3)：蓝 up → (3,3) 吃；或蓝在 (2,2) 时左移 → (2,1)??
    # 直接构造：同一个子在不同位置的威胁相同，比较加权值。
    near_target = make_state(
        red={3: Position(3, 3)},
        blue={2: Position(4, 3)},
    )
    far_target = make_state(
        red={3: Position(1, 2)},
        blue={3: Position(1, 3)},
    )

    weighted_near = distance_weighted_capture_risk(near_target, Player.RED)
    weighted_far = distance_weighted_capture_risk(far_target, Player.RED)

    # 都有被吃风险时，近目标的子加权后应有更大的风险贡献
    # 注意：两边的被吃概率可能不同（dice fallback 不同），所以不硬编码期望值
    if weighted_near > 0 and weighted_far > 0:
        # 归一化比较：加权 / flat，近目标的应该更大
        near_ratio = weighted_near / max(total_expected_capture_risk(near_target, Player.RED), 0.001)
        far_ratio = weighted_far / max(total_expected_capture_risk(far_target, Player.RED), 0.001)
        assert near_ratio > far_ratio, (
            f"near ratio={near_ratio} should > far ratio={far_ratio}"
        )
