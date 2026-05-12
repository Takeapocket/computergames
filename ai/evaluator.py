from __future__ import annotations

from ai.risk import distance_weighted_capture_risk, expected_target_win_risk
from ai.self_capture import self_capture_mobility_gain
from core.game_state import GameState
from core.rules import target_corner
from core.types import Player, Position, chebyshev_distance


WIN_SCORE: float = 1_000_000.0
DISTANCE_WEIGHT: float = 1.0
MATERIAL_WEIGHT: float = 10.0
EXPECTED_RISK_WEIGHT: float = 3.0
EXPECTED_WIN_RISK_WEIGHT: float = 500.0
SELF_CAPTURE_WEIGHT: float = 0.0


def evaluate(
    state: GameState,
    perspective: Player,
    *,
    distance_weight: float = DISTANCE_WEIGHT,
    material_weight: float = MATERIAL_WEIGHT,
    expected_risk_weight: float = 0.0,
    expected_win_risk_weight: float = 0.0,
    self_capture_weight: float = SELF_CAPTURE_WEIGHT,
) -> float:
    """从 ``perspective`` 视角对 ``state`` 打分。

    终局直接返回 ±WIN_SCORE。否则线性组合：
    - 距离差：对方距其目标角越远越好；自己距己方目标角越近越好。
    - 子力差：自己存活子越多越好。
    - 风险项：仅惩罚 ``perspective`` 自身的下一轮被吃/被冲线风险。
    - self-capture 机动性增益：默认 0；候选实验可通过非零权重开启。

    注意：当 ``expected_risk_weight`` 或 ``expected_win_risk_weight`` 非零时，本函数不保证
    ``evaluate(state, RED) == -evaluate(state, BLUE)``。当前用途是 GreedyAI 对同一视角下候选
    走法排序；后续 Minimax/MCTS/Expectimax 若依赖零和评估，需要改为显式计算双方风险差。
    """
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    own_pieces = state.pieces[perspective]
    opp_pieces = state.pieces[perspective.opponent]
    own_target = target_corner(perspective)
    opp_target = target_corner(perspective.opponent)

    own_distance_total = sum(
        chebyshev_distance(p.position, own_target) for p in own_pieces.values() if p.alive
    )
    opp_distance_total = sum(
        chebyshev_distance(p.position, opp_target) for p in opp_pieces.values() if p.alive
    )
    own_alive = sum(1 for p in own_pieces.values() if p.alive)
    opp_alive = sum(1 for p in opp_pieces.values() if p.alive)
    own_expected_risk = distance_weighted_capture_risk(state, perspective)
    own_expected_win_risk = expected_target_win_risk(state, perspective)
    own_self_capture_gain = (
        self_capture_mobility_gain(state, perspective) if self_capture_weight else 0.0
    )

    return (
        distance_weight * (opp_distance_total - own_distance_total)
        + material_weight * (own_alive - opp_alive)
        - expected_risk_weight * own_expected_risk
        - expected_win_risk_weight * own_expected_win_risk
        + self_capture_weight * own_self_capture_gain
    )
