"""Tactical-patch wrapper AI: two hard rules (direct win / one-step neutralize)
layered on top of any base AI that follows the AIPlayer protocol.

无战术规则触发时，对 base AI 完全透明：base 看到同一个 state/dice，且只被调一次。
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid circular import with ai/__init__.py
    from ai import AIPlayer
    from core.game_state import GameState
    from core.move import Move
    from core.types import Player


def pick_max_material(moves, rng: random.Random):
    """从 moves 里优先选「吃对手子」的走法；多个则 rng.choice；
    若无任何吃对手子的走法则在全部 moves 上 rng.choice。

    设计文档 §5.2：tie-break 顺序最大吃子 → rng 抽签。
    自己吃自己（罕见但 core 允许）不计入「吃子」。
    """
    if not moves:
        raise ValueError("pick_max_material called with empty moves list")
    perspective_capturing = [
        m for m in moves
        if m.captured_piece is not None and m.captured_piece.player is not m.player
    ]
    pool = perspective_capturing if perspective_capturing else list(moves)
    return rng.choice(pool)


# Forward declarations — populated in later tasks.
def find_winning_moves(state, dice: int, perspective):
    """返回 apply 后让 perspective 立即获胜的 legal_moves 子集。

    依赖 ``state.get_winner()`` 同时覆盖「到角胜」和「吃光胜」两种 core 胜利条件。
    用 apply_move/undo_move 配对，包在 try/finally 内以保证异常路径不污染 state。
    """
    winning = []
    for move in state.legal_moves(perspective, dice):
        state.apply_move(move, dice)
        try:
            if state.get_winner() is perspective:
                winning.append(move)
        finally:
            state.undo_move()
    return winning


def opponent_winning_dice_set(state, *, opponent) -> set[int]:
    """``opponent`` 下一回合能用哪些骰子值一步获胜，返回 set[int]。

    显式收 ``opponent`` 而非用 ``state.current_player``：本函数会被前后两种 state
    状态下调用（行动前 current_player==perspective，行动后 current_player==opponent）。

    一步获胜判定依赖 ``state.get_winner()``，同时覆盖「到角胜」和「吃光胜」。
    用反序列化副本模拟，绝不触碰原 state。
    """
    from core.game_state import GameState

    winning_dice: set[int] = set()
    snapshot = state.serialize()
    for d in range(1, 7):
        sim = GameState.deserialize(snapshot)
        sim.current_player = opponent
        for move in sim.legal_moves(opponent, d):
            sim.apply_move(move, dice=d)
            if sim.get_winner() is opponent:
                winning_dice.add(d)
                sim.undo_move()
                break
            sim.undo_move()
    return winning_dice


def find_neutralizing_moves(state, dice, perspective):  # noqa: D401
    """返回 apply 后完全消除对手一步胜威胁的 legal_moves 子集。"""
    neutralizing = []
    for move in state.legal_moves(perspective, dice):
        state.apply_move(move, dice=dice)
        try:
            post_threat = opponent_winning_dice_set(
                state, opponent=perspective.opponent
            )
            if not post_threat:
                neutralizing.append(move)
        finally:
            state.undo_move()
    return neutralizing


class TacticalAI:
    name: str

    def __init__(self, *, base, rng=None, name=None):
        self.base = base
        self.rng = rng if rng is not None else random.Random()
        if name is not None:
            self.name = name
        else:
            base_name = getattr(base, "name", "base")
            self.name = f"{base_name}_tactical"

    def choose_move(self, state, dice):
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        perspective = state.current_player
        winning = find_winning_moves(state, dice, perspective)
        if winning:
            return pick_max_material(winning, self.rng)

        pre_move_threat = opponent_winning_dice_set(
            state, opponent=perspective.opponent
        )
        if pre_move_threat:
            neutralizing = find_neutralizing_moves(state, dice, perspective)
            if neutralizing:
                return self._delegate_to_base_filtered(state, dice, neutralizing)

        return self.base.choose_move(state, dice)

    def _delegate_to_base_filtered(self, state, dice, allowed):
        base_choice = self.base.choose_move(state, dice)
        allowed_pairs = {(move.from_pos, move.to_pos) for move in allowed}
        if (
            base_choice is not None
            and (base_choice.from_pos, base_choice.to_pos) in allowed_pairs
        ):
            return base_choice

        return self.rng.choice(allowed)
