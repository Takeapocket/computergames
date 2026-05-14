"""Tactical AI wrapper unit tests."""
from __future__ import annotations

import random

import pytest

from ai.greedy_ai import GreedyAI
from ai.tactical import (
    TacticalAI,
    find_neutralizing_moves,
    find_winning_moves,
    opponent_winning_dice_set,
    pick_max_material,
)
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


def _state(red=None, blue=None, current_player=Player.RED) -> GameState:
    return GameState.from_layout(
        red=red or {}, blue=blue or {}, current_player=current_player
    )


def _move(player, piece_id, frm, to, captured=None) -> Move:
    return Move(
        player=player,
        piece_id=piece_id,
        from_pos=frm,
        to_pos=to,
        is_capture=captured is not None,
        captured_piece=captured,
    )


# -------- pick_max_material --------

def test_pick_max_material_returns_only_move():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    moves = state.legal_moves(Player.RED, 1)
    assert moves, "fixture should produce at least one legal move"
    rng = random.Random(0)

    chosen = pick_max_material([moves[0]], rng)

    assert chosen == moves[0]


def test_pick_max_material_prefers_capture_of_opponent():
    state = _state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(0, 1)},
    )
    legal = state.legal_moves(Player.RED, 1)
    capturing = [m for m in legal if m.captured_piece is not None and m.captured_piece.player is Player.BLUE]
    non_capturing = [m for m in legal if m.captured_piece is None]
    assert capturing and non_capturing, "fixture must contain both kinds"
    rng = random.Random(0)

    chosen = pick_max_material(capturing + non_capturing, rng)

    assert chosen in capturing


def test_pick_max_material_falls_back_to_rng_when_no_captures():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    legal = state.legal_moves(Player.RED, 1)
    moves = [m for m in legal if m.captured_piece is None]
    assert len(moves) >= 2 or moves, "need at least one non-capture"
    rng_a = random.Random(42)
    rng_b = random.Random(42)

    a = pick_max_material(moves, rng_a)
    b = pick_max_material(moves, rng_b)

    assert a == b  # deterministic given same rng seed


def test_pick_max_material_ignores_self_captures():
    """Self-captures (capturing own piece) must not count as 'material'."""
    fake_self_piece_move = _move(
        Player.RED, 1, Position(0, 0), Position(1, 1),
        captured=type("P", (), {"player": Player.RED})(),
    )
    fake_opp_capture = _move(
        Player.RED, 2, Position(2, 2), Position(3, 3),
        captured=type("P", (), {"player": Player.BLUE})(),
    )
    rng = random.Random(0)

    chosen = pick_max_material([fake_self_piece_move, fake_opp_capture], rng)

    assert chosen is fake_opp_capture


# -------- find_winning_moves --------

def test_find_winning_moves_detects_target_corner_win():
    """RED piece one step from (4,4); dice=1 should reach target_corner and win."""
    state = _state(
        red={6: Position(3, 4)},
        blue={1: Position(0, 4)},
    )

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning, "should find at least one winning move"
    assert all(m.to_pos == Position(4, 4) for m in winning)


def test_find_winning_moves_detects_capture_all_win():
    """RED has piece adjacent to BLUE's last surviving piece; capture wins by elimination."""
    state = _state(
        red={1: Position(2, 2)},
        blue={1: Position(2, 3)},  # blue has only one piece
    )

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning
    captured_targets = [m.captured_piece for m in winning if m.captured_piece]
    assert any(c and c.player is Player.BLUE for c in captured_targets)


def test_find_winning_moves_returns_empty_when_no_win():
    state = _state(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},  # blue already at target — opponent already won? skip if so
    )
    if state.get_winner() is not None:
        pytest.skip("layout produces immediate winner")

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning == []


def test_find_winning_moves_does_not_mutate_state():
    state = _state(
        red={6: Position(3, 4)},
        blue={1: Position(0, 4)},
    )
    before = state.serialize()

    find_winning_moves(state, dice=1, perspective=Player.RED)

    assert state.serialize() == before
