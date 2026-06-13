from __future__ import annotations

from ai.match import default_starting_state
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from record.game_record import GameRecord


def _record_with_dice(dice_values: list[int], *, source: str = "opponent") -> GameRecord:
    state = default_starting_state()
    record = GameRecord.from_state(state)
    for dice in dice_values:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            break
        applied = state.apply_move(legal[0], dice=dice)
        record.append(dice=dice, move=applied, state_after=state, source=source)
    return record


def test_count_dice_by_source_groups_steps_without_claiming_dice_source():
    from scripts.dice_forensics import count_dice_by_source

    record = _record_with_dice([1, 2, 2], source="opponent")

    grouped = count_dice_by_source([record])

    assert grouped == {"opponent": {1: 1, 2: 2, 3: 0, 4: 0, 5: 0, 6: 0}}


def test_chi_square_uniform_returns_statistic_and_sample_size():
    from scripts.dice_forensics import chi_square_uniform

    result = chi_square_uniform({1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2})

    assert result["n"] == 12
    assert result["chi_square"] == 0.0
    assert result["p_value"] == 1.0
    assert result["cramers_v"] == 0.0
    assert result["df"] == 5


def test_threat_coincidence_summary_counts_opponent_threat_piece_capture_dice():
    from scripts.dice_forensics import threat_coincidence_summary

    state = GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(2, 0),
            4: Position(1, 1),
            5: Position(3, 1),
            6: Position(0, 2),
        },
        blue={
            1: Position(1, 0),
            2: Position(3, 3),
            3: Position(4, 2),
            4: Position(2, 4),
            5: Position(2, 3),
            6: Position(3, 2),
        },
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)
    move = Move(Player.RED, 1, Position(0, 0), Position(1, 0))
    state.apply_move(move, dice=1)
    record.append(dice=1, move=move, state_after=state, source="opponent")

    summary = threat_coincidence_summary([record])

    assert summary["opponent_target_threat_steps"] == 1
    assert summary["dice_capture_opportunity_steps"] == 1
    assert summary["chosen_capture_steps"] == 1
    assert summary["actual_dice_hit_rate"] == 1.0
    assert summary["expected_dice_hit_probability"] == 1 / 6


def test_threat_coincidence_summary_does_not_count_mover_target_hit_as_dice_capture():
    from scripts.dice_forensics import threat_coincidence_summary

    state = GameState.from_layout(
        red={
            1: Position(3, 4),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
            5: Position(2, 0),
            6: Position(0, 2),
        },
        blue={
            1: Position(4, 3),
            2: Position(3, 3),
            3: Position(4, 2),
            4: Position(2, 4),
            5: Position(2, 3),
            6: Position(3, 2),
        },
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)
    move = Move(Player.RED, 1, Position(3, 4), Position(4, 4))
    state.apply_move(move, dice=1)
    record.append(dice=1, move=move, state_after=state, source="self")

    summary = threat_coincidence_summary([record])

    assert summary["opponent_target_threat_steps"] == 0
    assert summary["dice_capture_opportunity_steps"] == 0
    assert summary["chosen_capture_steps"] == 0
