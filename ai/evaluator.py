from __future__ import annotations

from core.game_state import GameState
from core.rules import generate_legal_moves_for_piece, target_corner
from core.types import Player, Position


WIN_SCORE: float = 1_000_000.0
DISTANCE_WEIGHT: float = 1.0
MATERIAL_WEIGHT: float = 10.0
STUCK_PIECE_PENALTY: float = 100.0


def chebyshev_distance(a: Position, b: Position) -> int:
    """Chebyshev / Chess-king distance：因为本游戏走法包含对角线，单步等于 1。"""
    return max(abs(a.row - b.row), abs(a.col - b.col))


def count_stuck_pieces(state: GameState, player: Player) -> int:
    """统计 ``player`` 一方"alive 但当前没有任何合法走法"的棋子数。

    用于 evaluator 的 stuck_penalty：被自家围死的棋子在 dice 强制选中时会触发 forfeit，
    属于潜在的"自杀风险"，需要在评估时折现。
    """
    player = Player.from_value(player)
    return sum(
        1
        for piece in state.pieces[player].values()
        if piece.alive and not generate_legal_moves_for_piece(piece, state.piece_at)
    )


def evaluate(state: GameState, perspective: Player) -> float:
    """从 ``perspective`` 视角对 ``state`` 打分。

    终局直接返回 ±WIN_SCORE。否则线性组合：
    - 距离差：对方距其目标角越远越好；自己距己方目标角越近越好。
    - 子力差：自己存活子越多越好。
    - stuck 差：自己被围死的子越少越好（避免 dice 强制选中触发 forfeit）。
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
    own_stuck = count_stuck_pieces(state, perspective)
    opp_stuck = count_stuck_pieces(state, perspective.opponent)

    return (
        DISTANCE_WEIGHT * (opp_distance_total - own_distance_total)
        + MATERIAL_WEIGHT * (own_alive - opp_alive)
        + STUCK_PIECE_PENALTY * (opp_stuck - own_stuck)
    )
