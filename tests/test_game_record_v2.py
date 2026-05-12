"""GameRecord schema v2: 顶层 metadata/result + step.state_after 不再嵌 history。

review #1 + #2 + Minor #2：replay 顶层缺乏 metadata（seed/AI 名/winner/termination_reason
等），单步 state_after 内嵌完整累计 history 导致长局 O(n^2) 膨胀。
"""

from __future__ import annotations

import pytest

from core.game_state import GameState
from core.types import Player, Position
from record.game_record import GameRecord


def _record_with_one_move() -> tuple[GameRecord, GameState]:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)
    move = state.apply_move(state.legal_moves(Player.RED, 1)[0], dice=1)
    record.append(dice=1, move=move, state_after=state)
    return record, state


def test_append_writes_state_after_without_history_field() -> None:
    record, state = _record_with_one_move()

    step_state_after = record.steps[-1].state_after

    assert "history" not in step_state_after
    # 确认其他字段仍齐全
    assert "current_player" in step_state_after
    assert "pieces" in step_state_after


def test_record_has_top_level_metadata_and_result_dicts_default_empty() -> None:
    record, _ = _record_with_one_move()

    assert record.metadata == {}
    assert record.result == {}


def test_metadata_and_result_round_trip_through_to_from_dict() -> None:
    record, _ = _record_with_one_move()
    record.metadata = {
        "seed": 2026,
        "git_revision": "abc1234",
        "ai_versions": {"red": {"name": "greedy", "distance_weight": 1.0}},
    }
    record.result = {
        "winner": "red",
        "termination_reason": "winner_target_corner",
        "turns": 1,
    }

    restored = GameRecord.from_dict(record.to_dict())

    assert restored.metadata == record.metadata
    assert restored.result == record.result


def test_to_dict_contains_metadata_and_result_at_top_level() -> None:
    record, _ = _record_with_one_move()
    record.metadata = {"seed": 7}
    record.result = {"winner": "red"}

    payload = record.to_dict()

    assert payload["metadata"] == {"seed": 7}
    assert payload["result"] == {"winner": "red"}


def test_from_dict_tolerates_legacy_record_without_metadata_or_result() -> None:
    """v1 replay JSON 没有 metadata/result 顶层字段 → load 不应崩溃。"""
    record, _ = _record_with_one_move()
    raw = record.to_dict()
    raw.pop("metadata", None)
    raw.pop("result", None)

    restored = GameRecord.from_dict(raw)

    assert restored.metadata == {}
    assert restored.result == {}


def test_from_dict_rejects_falsy_non_dict_metadata_and_result() -> None:
    record, _ = _record_with_one_move()
    raw = record.to_dict()

    raw["metadata"] = []
    with pytest.raises(ValueError, match="metadata"):
        GameRecord.from_dict(raw)

    raw["metadata"] = {}
    raw["result"] = ""
    with pytest.raises(ValueError, match="result"):
        GameRecord.from_dict(raw)


def test_state_after_in_serialized_step_does_not_grow_with_history_length() -> None:
    """走 5 步后，最后一步 state_after 的 JSON 长度不应该是第一步的 5 倍。

    O(n^2) 膨胀的根因是每个 state_after 都嵌完整累计 history。
    """
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    record = GameRecord.from_state(state)

    step_payload_lengths = []
    for _ in range(5):
        legal = state.legal_moves(state.current_player, 1)
        if not legal:
            break
        applied = state.apply_move(legal[0], dice=1)
        record.append(dice=1, move=applied, state_after=state)
        step_payload_lengths.append(len(str(record.steps[-1].state_after)))

    # 每步 state_after 不含累计 history，所以长度近似常数（仅 piece position 微变）
    longest = max(step_payload_lengths)
    shortest = min(step_payload_lengths)
    assert longest - shortest < 50, (
        f"state_after sizes vary too much (min={shortest}, max={longest}); "
        "history 可能仍被嵌入。"
    )
