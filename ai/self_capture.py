"""Self-capture mobility heuristic (默认关闭).

为 evaluator 提供"吃本方子换取机动性"的可测特征。默认 SELF_CAPTURE_WEIGHT=0.0，
仅当候选实验显式开启时生效。本函数不修改输入 state。
"""
from __future__ import annotations

from core.game_state import GameState
from core.types import Player


def self_capture_mobility_gain(state: GameState, perspective: Player) -> float:
    """估算 ``perspective`` 通过合法自残获得的平均机动性增益（非负）。

    对 dice=1..6：
      - 收集 perspective 自残（``captured_piece.player == perspective``）走法；
      - 在 state 的副本上 apply_move（强制 current_player=perspective），算 mobility 增量；
      - 取该 dice 下增量最大值；
      - 全 6 个 dice 平均。

    GameState.apply_move() 要求 ``move.player == state.current_player``。当 evaluate() 在
    对手回合调用时，state.current_player ≠ perspective。因此本函数必须在副本上设置
    current_player=perspective，才能合法 apply。原 state 完全不变。
    """
    perspective = Player.from_value(perspective)
    baseline = _average_legal_moves(state, perspective)
    total = 0.0

    for dice in range(1, 7):
        best_delta = 0.0
        for move in state.legal_moves(perspective, dice):
            if move.captured_piece is None or move.captured_piece.player is not perspective:
                continue
            sim = GameState.deserialize(state.serialize(include_history=False))
            sim.current_player = perspective
            sim.apply_move(move, dice=dice)
            delta = _average_legal_moves(sim, perspective) - baseline
            if delta > best_delta:
                best_delta = delta
        total += best_delta

    return total / 6.0


def _average_legal_moves(state: GameState, player: Player) -> float:
    return sum(len(state.legal_moves(player, dice)) for dice in range(1, 7)) / 6.0
