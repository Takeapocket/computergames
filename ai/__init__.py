from __future__ import annotations

from typing import Protocol

from core.game_state import GameState
from core.move import Move

from ai.expectimax_ai import ExpectimaxAI
from ai.expectimax_v2 import ExpectimaxV2
from ai.greedy_ai import GreedyAI
from ai.chance_rerank import ExactOpponentDiceRerankAI
from ai.mcts import MCTSAI
from ai.random_ai import RandomAI, choose_random_move
from ai.rollout_ai import RolloutAI
from ai.tactical import TacticalAI
from ai.zweistein_ai import ZweisteinGreedyAI


class AIPlayer(Protocol):
    """所有 AI 必须满足的协议：有可读的 ``name``，按 ``(state, dice)`` 给出走法。"""

    name: str

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...


__all__ = [
    "AIPlayer",
    "ExpectimaxAI",
    "ExpectimaxV2",
    "ExactOpponentDiceRerankAI",
    "GreedyAI",
    "MCTSAI",
    "RandomAI",
    "RolloutAI",
    "TacticalAI",
    "ZweisteinGreedyAI",
    "choose_random_move",
]
