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
