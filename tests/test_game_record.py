import json

import pytest

from core.game_state import GameState
from core.types import Player, Position
from record.game_record import GameRecord


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


def test_from_state_stores_initial_state_snapshot():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)

    state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    assert record.initial_state == make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)}).serialize()
    assert record.steps == []


def test_append_records_normal_move_with_state_after_snapshot():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    step = record.append(dice=1, move=move, state_after=state)

    assert step.turn == 1
    assert step.player is Player.RED
    assert step.dice == 1
    assert step.move == move
    assert step.state_after == state.serialize()
    assert step.step_seconds == 0.0
    assert step.remaining_seconds == {}


def test_append_records_step_time_and_remaining_seconds():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    step = record.append(
        dice=1,
        move=move,
        state_after=state,
        step_seconds=3.25,
        remaining_seconds={Player.RED: 236.75, Player.BLUE: 240.0},
    )

    assert step.step_seconds == 3.25
    assert step.remaining_seconds == {Player.RED: 236.75, Player.BLUE: 240.0}
    assert step.to_dict()["remaining_seconds"] == {"red": 236.75, "blue": 240.0}


def test_append_records_capture_move():
    state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    record = GameRecord.from_state(state)
    capture = next(move for move in state.legal_moves(Player.RED, 1) if move.to_pos == Position(3, 3))
    applied = state.apply_move(capture, dice=1)

    step = record.append(dice=1, move=applied, state_after=state)

    assert step.move.is_capture is True
    assert step.move.captured_piece is not None
    assert step.move.captured_piece.player is Player.BLUE
    assert step.move.captured_piece.piece_id == 2


def test_undo_last_removes_latest_step_and_returns_it():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    step = record.append(dice=1, move=move, state_after=state)

    undone = record.undo_last()

    assert undone == step
    assert record.steps == []
    assert record.undo_last() is None


def test_restore_state_returns_initial_state_when_record_has_no_steps():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)

    restored = record.restore_state()

    assert restored.serialize() == state.serialize()


def test_restore_state_returns_last_state_after_when_record_has_steps():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)

    restored = record.restore_state()

    assert restored.serialize() == state.serialize()


def test_json_round_trip_preserves_record_data():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)

    restored = GameRecord.from_json(record.to_json(indent=2))

    assert restored.to_dict() == record.to_dict()
    assert json.loads(record.to_json()) == record.to_dict()


def test_json_round_trip_preserves_timing_data():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(
        dice=1,
        move=move,
        state_after=state,
        step_seconds=7.5,
        remaining_seconds={Player.RED: 232.5, Player.BLUE: 240.0},
    )

    restored = GameRecord.from_json(record.to_json())

    assert restored.steps[0].step_seconds == 7.5
    assert restored.steps[0].remaining_seconds == {Player.RED: 232.5, Player.BLUE: 240.0}


def test_from_dict_accepts_legacy_steps_without_timing_fields():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)
    data = record.to_dict()
    data["steps"][0].pop("step_seconds")
    data["steps"][0].pop("remaining_seconds")

    restored = GameRecord.from_dict(data)

    assert restored.steps[0].step_seconds == 0.0
    assert restored.steps[0].remaining_seconds == {}


def test_save_and_load_preserve_record_data(tmp_path):
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)
    path = tmp_path / "game_record.json"

    record.save(path)
    restored = GameRecord.load(path)

    assert restored.to_dict() == record.to_dict()


def test_from_dict_rejects_invalid_record_data():
    with pytest.raises(ValueError, match="record"):
        GameRecord.from_dict({"initial_state": {}, "steps": "invalid"})


def test_append_records_source_self():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    step = record.append(dice=1, move=move, state_after=state, source="self")

    assert step.source == "self"


def test_append_records_source_opponent():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    step = record.append(dice=1, move=move, state_after=state, source="opponent")

    assert step.source == "opponent"


def test_append_default_source_is_unknown():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)

    step = record.append(dice=1, move=move, state_after=state)

    assert step.source == "unknown"


def test_json_round_trip_preserves_source():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state, source="self")

    restored = GameRecord.from_json(record.to_json())

    assert restored.steps[-1].source == "self"


def test_from_dict_legacy_record_without_source_defaults_to_unknown():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)

    raw = record.to_dict()
    for step in raw["steps"]:
        step.pop("source", None)

    restored = GameRecord.from_dict(raw)

    assert restored.steps[-1].source == "unknown"


def test_from_json_rejects_malformed_json():
    with pytest.raises(ValueError, match="json"):
        GameRecord.from_json("{not valid json")


def test_from_dict_rejects_missing_initial_state():
    with pytest.raises(ValueError, match="record"):
        GameRecord.from_dict({"steps": []})


def test_from_dict_rejects_corrupt_intermediate_step():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)
    raw = record.to_dict()
    raw["steps"][0]["dice"] = 99

    with pytest.raises(ValueError, match="record"):
        GameRecord.from_dict(raw)


def test_from_dict_rejects_corrupt_intermediate_state_after():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    record = GameRecord.from_state(state)
    move_one = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move_one, state_after=state)
    move_two = state.apply_move(state.legal_moves(Player.BLUE, 1)[0], dice=1)
    record.append(dice=1, move=move_two, state_after=state)
    raw = record.to_dict()
    # 损坏第一步（中间步）的 state_after，让最后一步看起来仍合法。
    raw["steps"][0]["state_after"] = {"current_player": "red", "pieces": "garbage"}

    with pytest.raises(ValueError, match="record"):
        GameRecord.from_dict(raw)
