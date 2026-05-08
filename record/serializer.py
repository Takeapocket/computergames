from __future__ import annotations

import json
from typing import Any

from core.game_state import GameState


def serialize_game_state(state: GameState) -> dict[str, Any]:
    return state.serialize()


def deserialize_game_state(data: dict[str, Any]) -> GameState:
    return GameState.deserialize(data)


def to_json(state: GameState, *, indent: int | None = None) -> str:
    return json.dumps(state.serialize(), ensure_ascii=False, indent=indent)


def from_json(payload: str) -> GameState:
    return GameState.deserialize(json.loads(payload))
