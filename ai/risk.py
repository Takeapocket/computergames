from __future__ import annotations

from core.game_state import GameState
from core.rules import target_corner
from core.types import Player, chebyshev_distance


DICE_PROBABILITY = 1.0 / 6.0


def expected_capture_risk(state: GameState, player: Player) -> dict[int, float]:
    """估计 ``player`` 每枚活子在对方下一轮被吃掉的骰子概率。

    风险枚举必须经过 ``GameState.legal_moves``，这样骰子点数对应棋子死亡时的最近编号选择
    规则只维护在 core 里，不在 AI 层复制。
    """
    player = Player.from_value(player)
    risk = {
        piece_id: 0.0
        for piece_id, piece in state.pieces[player].items()
        if piece.alive
    }

    for dice in range(1, 7):
        threatened_piece_ids: set[int] = set()
        for move in state.legal_moves(player.opponent, dice):
            captured = move.captured_piece
            if captured is not None and captured.player is player and captured.alive:
                threatened_piece_ids.add(captured.piece_id)

        for piece_id in threatened_piece_ids:
            risk[piece_id] += DICE_PROBABILITY

    return {piece_id: value for piece_id, value in risk.items() if value > 0.0}


def total_expected_capture_risk(state: GameState, player: Player) -> float:
    return sum(expected_capture_risk(state, player).values())


def distance_weighted_capture_risk(state: GameState, player: Player) -> float:
    """与 ``total_expected_capture_risk`` 相同，但每枚子的被吃概率按其到目标角的
    chebyshev 距离加权——离目标越近的子暴露被吃时惩罚越重。远离目标角的棋子暴露
    风险相对较轻，避免 AI 为保护无关棋子而过度保守。
    """
    player = Player.from_value(player)
    own_target = target_corner(player)
    risk_map = expected_capture_risk(state, player)
    weighted = 0.0
    for piece_id, risk_prob in risk_map.items():
        piece = state.pieces[player][piece_id]
        distance = chebyshev_distance(piece.position, own_target)
        weight = 1.0 / (distance + 1)
        weighted += risk_prob * weight
    return weighted


def expected_target_win_risk(state: GameState, player: Player) -> float:
    """估计对手下一轮直接走到目标角获胜的骰子概率。"""
    player = Player.from_value(player)
    opponent = player.opponent
    opponent_target = target_corner(opponent)
    risk = 0.0

    for dice in range(1, 7):
        if any(move.to_pos == opponent_target for move in state.legal_moves(opponent, dice)):
            risk += DICE_PROBABILITY

    return risk
