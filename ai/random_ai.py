from __future__ import annotations

import random

from core.game_state import GameState
from core.move import Move


def choose_random_move(
    state: GameState,
    dice: int,
    rng: random.Random | None = None,
) -> Move | None:
    moves = state.legal_moves(state.current_player, dice)
    if not moves:
        return None
    chooser = rng or random
    return chooser.choice(moves)


class RandomAI:
    """随机 AI：在合法走法中均匀随机抽签。"""

    def __init__(self, *, rng: random.Random | None = None, name: str = "random") -> None:
        self._rng = rng or random.Random()
        self.name = name

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        return choose_random_move(state, dice, rng=self._rng)
