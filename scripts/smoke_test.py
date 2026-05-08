from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.game_state import GameState
from core.types import Player, Position


def main() -> None:
    state = GameState.from_layout(
        red={
            1: Position(0, 0),
            3: Position(2, 2),
            6: Position(4, 0),
        },
        blue={
            2: Position(4, 4),
            4: Position(3, 3),
            5: Position(0, 4),
        },
        current_player=Player.RED,
    )
    before = state.serialize()
    dice = 3

    selected = state.legal_piece_ids(state.current_player, dice)
    moves = state.legal_moves(state.current_player, dice)

    print(f"dice: {dice}")
    print(f"selected pieces: {selected}")
    print("legal moves:")
    for index, move in enumerate(moves, start=1):
        capture = " capture" if move.is_capture else ""
        print(f"{index}. {move.player.value} {move.piece_id}: {move.from_pos} -> {move.to_pos}{capture}")

    if not moves:
        print("no legal moves")
        return

    applied = state.apply_move(moves[0], dice=dice)
    print(f"applied: {applied}")
    print(f"winner: {state.get_winner()}")

    state.undo_move()
    restored = state.serialize() == before
    print(f"undo restored: {restored}")
    assert restored


if __name__ == "__main__":
    main()
