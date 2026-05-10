"""GameState.serialize(include_history=...) 控制 history 字段是否输出。

Replay step.state_after 已经被 step 序列覆盖了 history，重复嵌入会让单局 JSON
随步数 O(n^2) 膨胀（见 reports replay v1）。serialize 增加 include_history 开关，
让 GameRecord 在写 step 时跳过 history。默认行为保持兼容（GUI/撤销依赖完整 history）。
"""

from __future__ import annotations

from core.game_state import GameState
from core.types import Player, Position


def _state_with_history() -> GameState:
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(3, 3)},
        current_player=Player.RED,
    )
    move = state.legal_moves_for_piece(Player.RED, 1)[0]
    state.apply_move(move, dice=1)
    return state


def test_serialize_default_includes_history() -> None:
    state = _state_with_history()

    payload = state.serialize()

    assert "history" in payload
    assert len(payload["history"]) == 1


def test_serialize_with_include_history_false_omits_history() -> None:
    state = _state_with_history()

    payload = state.serialize(include_history=False)

    assert "history" not in payload
    assert "pieces" in payload
    assert "current_player" in payload


def test_deserialize_tolerates_missing_history_field() -> None:
    state = _state_with_history()
    payload = state.serialize(include_history=False)

    restored = GameState.deserialize(payload)

    assert restored.history == []
    assert restored.current_player is state.current_player
