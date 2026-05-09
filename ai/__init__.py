from __future__ import annotations

from typing import Protocol

from core.game_state import GameState
from core.move import Move

from ai.greedy_ai import GreedyAI
from ai.random_ai import RandomAI, choose_random_move


class AIPlayer(Protocol):
    """所有 AI 必须满足的协议：有可读的 ``name``，按 ``(state, dice)`` 给出走法。"""

    name: str

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...


__all__ = [
    "AIPlayer",
    "GreedyAI",
    "RandomAI",
    "choose_random_move",
]
