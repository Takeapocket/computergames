import random

import pytest

from ai.endgame_solver import (
    ExactEndgameAI,
    ExactEndgameSolver,
    endgame_progress_measure,
    is_exact_endgame_eligible,
)
from ai.match import default_starting_state, play_one_game
from core.game_state import GameState
from core.types import Player, Position


def _make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


@pytest.mark.parametrize(
    ("state", "dice"),
    [
        (
            _make_state(
                red={1: Position(2, 2)},
                blue={1: Position(0, 4)},
                current_player=Player.RED,
            ),
            1,
        ),
        (
            _make_state(
                red={1: Position(4, 0)},
                blue={1: Position(2, 2)},
                current_player=Player.BLUE,
            ),
            1,
        ),
        (
            _make_state(
                red={1: Position(2, 2), 2: Position(3, 2)},
                blue={1: Position(0, 4)},
                current_player=Player.RED,
            ),
            1,
        ),
        (
            _make_state(
                red={1: Position(2, 2)},
                blue={1: Position(3, 3), 6: Position(0, 4)},
                current_player=Player.RED,
            ),
            1,
        ),
    ],
)
def test_endgame_progress_strictly_decreases_for_every_legal_move(state, dice):
    before_state = state.serialize()
    before_progress = endgame_progress_measure(state)
    legal = state.legal_moves(state.current_player, dice)

    assert legal
    for move in legal:
        state.apply_move(move, dice=dice)
        try:
            assert endgame_progress_measure(state) < before_progress
        finally:
            state.undo_move()
    assert state.serialize() == before_state


def test_exact_endgame_eligibility_accepts_piece_or_distance_gate():
    piece_gate = _make_state(
        red={1: Position(0, 0), 6: Position(0, 1)},
        blue={1: Position(4, 4)},
    )
    distance_gate = _make_state(
        red={1: Position(4, 3), 2: Position(3, 4)},
        blue={1: Position(0, 1), 2: Position(1, 0)},
    )

    assert endgame_progress_measure(piece_gate) > 6
    assert is_exact_endgame_eligible(piece_gate)
    assert endgame_progress_measure(distance_gate) <= 6
    assert is_exact_endgame_eligible(distance_gate)
    assert not is_exact_endgame_eligible(default_starting_state())


def test_exact_endgame_hand_computed_dice_oracle_is_one_half():
    state = _make_state(
        red={1: Position(4, 3), 6: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    before = state.serialize()
    solver = ExactEndgameSolver()

    red_probability = solver.solve_win_probability(state, perspective=Player.RED)
    blue_probability = solver.solve_win_probability(state, perspective=Player.BLUE)

    assert red_probability == 0.5
    assert blue_probability == 0.5
    assert red_probability + blue_probability == 1.0
    assert state.serialize() == before


def test_exact_endgame_hand_computed_dice_oracle_is_one_third():
    state = _make_state(
        red={1: Position(4, 3), 4: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    solver = ExactEndgameSolver()

    red_probability = solver.solve_win_probability(state, perspective=Player.RED)
    blue_probability = solver.solve_win_probability(state, perspective=Player.BLUE)

    assert red_probability == pytest.approx(1.0 / 3.0)
    assert blue_probability == pytest.approx(2.0 / 3.0)
    assert red_probability + blue_probability == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("state", "expected_red_probability"),
    [
        (
            _make_state(
                red={1: Position(3, 3)},
                blue={1: Position(0, 1)},
                current_player=Player.RED,
            ),
            1.0,
        ),
        (
            _make_state(
                red={1: Position(4, 3)},
                blue={1: Position(1, 1)},
                current_player=Player.BLUE,
            ),
            0.0,
        ),
    ],
)
def test_exact_endgame_known_dice_turn_uses_red_max_and_blue_min(
    state,
    expected_red_probability,
):
    solver = ExactEndgameSolver()
    legal = state.legal_moves(state.current_player, 1)
    solver._begin_search()

    red_probability = solver._turn_red_probability(state, dice=1)

    assert len(legal) == 3
    assert red_probability == expected_red_probability


def test_exact_endgame_terminal_values_bypass_nonterminal_gate():
    state = _make_state(
        red={1: Position(4, 4), 2: Position(0, 0)},
        blue={1: Position(4, 0), 2: Position(4, 1), 3: Position(4, 2)},
        current_player=Player.BLUE,
    )
    solver = ExactEndgameSolver(max_total_pieces=1, max_total_distance=1)

    assert not (
        sum(1 for pieces in state.pieces.values() for piece in pieces.values() if piece.alive)
        <= solver.max_total_pieces
    )
    assert solver.solve_win_probability(state, perspective=Player.RED) == 1.0
    assert solver.solve_win_probability(state, perspective=Player.BLUE) == 0.0


def test_exact_endgame_rejects_ineligible_nonterminal_state():
    solver = ExactEndgameSolver()

    with pytest.raises(ValueError, match="outside exact endgame gate"):
        solver.solve_win_probability(default_starting_state(), perspective=Player.RED)


def test_exact_endgame_tt_matches_uncached_value_and_reduces_nodes():
    state = _make_state(
        red={1: Position(4, 3), 6: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    before = state.serialize()
    cached = ExactEndgameSolver(use_transposition_table=True)
    uncached = ExactEndgameSolver(use_transposition_table=False)

    cached_value = cached.solve_win_probability(state, perspective=Player.RED)
    uncached_value = uncached.solve_win_probability(state, perspective=Player.RED)

    assert cached_value == uncached_value == 0.5
    assert cached.last_search_stats.tt_hits > 0
    assert cached.last_search_stats.tt_stores == cached.last_table_size > 0
    assert cached.last_search_stats.nodes < uncached.last_search_stats.nodes
    assert uncached.last_search_stats.tt_hits == 0
    assert uncached.last_search_stats.tt_stores == 0
    assert uncached.last_table_size == 0
    assert state.serialize() == before


def test_exact_endgame_repeated_solve_is_deterministic_and_resets_stats():
    state = _make_state(
        red={1: Position(4, 3), 6: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    solver = ExactEndgameSolver()

    first_value = solver.solve_win_probability(state, perspective=Player.RED)
    first_stats = solver.last_search_stats
    first_table_size = solver.last_table_size
    second_value = solver.solve_win_probability(state, perspective=Player.RED)

    assert second_value == first_value == 0.5
    assert solver.last_search_stats == first_stats
    assert solver.last_table_size == first_table_size


def test_exact_endgame_restores_existing_history():
    state = _make_state(
        red={1: Position(4, 3), 6: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]
    state.apply_move(move, dice=6)
    before = state.serialize()
    solver = ExactEndgameSolver()

    probability = solver.solve_win_probability(state, perspective=Player.RED)

    assert probability == 0.0
    assert state.serialize() == before
    assert len(state.history) == 1


def test_exact_endgame_restores_state_when_recursive_child_raises(monkeypatch):
    state = _make_state(
        red={1: Position(3, 3)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    before = state.serialize()
    solver = ExactEndgameSolver()
    solver._begin_search()

    def raise_from_child(_state):
        raise RuntimeError("scripted recursive failure")

    monkeypatch.setattr(solver, "_chance_red_probability", raise_from_child)

    with pytest.raises(RuntimeError, match="scripted recursive failure"):
        solver._turn_red_probability(state, dice=1)

    assert state.serialize() == before


def test_exact_endgame_ai_selects_direct_win_and_restores_state():
    state = _make_state(
        red={1: Position(3, 3)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    before = state.serialize()
    ai = ExactEndgameAI(randomize_ties=False)

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.to_pos == Position(4, 4)
    assert state.serialize() == before


def test_exact_endgame_ai_uses_first_legal_move_for_deterministic_ties():
    state = _make_state(
        red={1: Position(0, 3)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(Player.RED, 1)
    ai = ExactEndgameAI(randomize_ties=False)

    move = ai.choose_move(state, dice=1)

    assert len(legal) > 1
    assert move == legal[0]
    assert [probability for _move, probability in ai.last_root_probabilities] == [
        0.0
    ] * len(legal)


def test_exact_endgame_ai_random_ties_are_seed_reproducible():
    state_a = _make_state(
        red={1: Position(0, 3)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    state_b = state_a.clone(include_history=False)
    ai_a = ExactEndgameAI(rng=random.Random(9), randomize_ties=True)
    ai_b = ExactEndgameAI(rng=random.Random(9), randomize_ties=True)

    move_a = ai_a.choose_move(state_a, dice=1)
    move_b = ai_b.choose_move(state_b, dice=1)

    assert move_a == move_b
    assert move_a in state_a.legal_moves(Player.RED, 1)


def test_exact_endgame_ai_rejects_ineligible_nonterminal_before_search():
    state = default_starting_state()
    before = state.serialize()
    ai = ExactEndgameAI()

    with pytest.raises(ValueError, match="outside exact endgame gate"):
        ai.choose_move(state, dice=1)

    assert ai.last_search_stats.nodes == 0
    assert state.serialize() == before


def test_exact_endgame_ai_runs_small_match_without_illegal_or_crash():
    state = _make_state(
        red={1: Position(4, 3), 6: Position(4, 0)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    red_ai = ExactEndgameAI(rng=random.Random(1), randomize_ties=False)
    blue_ai = ExactEndgameAI(rng=random.Random(2), randomize_ties=False)

    result = play_one_game(
        red_ai=red_ai,
        blue_ai=blue_ai,
        dice_rng=random.Random(3),
        max_turns=10,
        starting_state=state,
    )

    assert result.winner is not None
    assert result.illegal_moves == 0
    assert result.crashes == 0
    assert result.turns <= 2
