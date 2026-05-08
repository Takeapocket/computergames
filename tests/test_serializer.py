import json

from core.game_state import GameState
from core.types import Player, Position
from record.serializer import deserialize_game_state, serialize_game_state, to_json


def test_game_state_serialize_deserialize_round_trip():
    state = GameState.from_layout(
        red={1: Position(0, 0), 6: Position(2, 2)},
        blue={2: Position(4, 4)},
        current_player=Player.BLUE,
    )
    move = state.legal_moves_for_piece(Player.BLUE, 2)[0]
    state.apply_move(move, dice=2)

    restored = GameState.deserialize(state.serialize())

    assert restored.serialize() == state.serialize()


def test_serializer_outputs_json_friendly_dict_and_restores_state():
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )

    data = serialize_game_state(state)
    json.dumps(data)
    restored = deserialize_game_state(data)

    assert restored.serialize() == state.serialize()


def test_to_json_outputs_parseable_state_json():
    state = GameState.from_layout(red={1: Position(0, 0)})

    payload = to_json(state)

    assert json.loads(payload) == state.serialize()


def test_deserialize_rejects_piece_player_mismatch():
    state = GameState.from_layout(red={1: Position(0, 0)})
    data = state.serialize()
    data["pieces"]["red"]["1"]["player"] = "blue"

    try:
        GameState.deserialize(data)
    except ValueError as exc:
        assert "piece metadata" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_deserialize_rejects_piece_id_mismatch():
    state = GameState.from_layout(red={1: Position(0, 0)})
    data = state.serialize()
    data["pieces"]["red"]["1"]["piece_id"] = 6

    try:
        GameState.deserialize(data)
    except ValueError as exc:
        assert "piece metadata" in str(exc)
    else:
        raise AssertionError("expected ValueError")
