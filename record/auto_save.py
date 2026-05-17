from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from core.types import Player
from record.game_record import GameRecord, _atomic_write_text
from record.match_record import MatchRecord


AUTO_SAVE_PATH = Path(__file__).resolve().parents[1] / "replays" / "auto_save.json"
AUTO_SAVE_MATCH_PATH = Path(__file__).resolve().parents[1] / "replays" / "auto_save_match.json"
AUTO_SAVE_METADATA_KEY = "auto_save"


class TimerSnapshotLike(Protocol):
    current_player: Player
    remaining_seconds: Mapping[Player, float]
    paused: bool


def _load_json_payload(target: Path) -> Any:
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read auto-save file: {exc}") from exc
    if not text.strip():
        raise ValueError("auto-save file is empty")
    return json.loads(text)


def _validate_auto_save_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("auto-save payload must be a JSON object")
    record = GameRecord.from_dict(payload)
    timer_metadata = record.metadata.get(AUTO_SAVE_METADATA_KEY)
    if not isinstance(timer_metadata, dict):
        raise ValueError("invalid auto-save metadata")
    _validate_timer_metadata(timer_metadata)


def _validate_standard_match_auto_save(match: MatchRecord) -> None:
    if match.total_games != 7 or match.target_wins != 4:
        raise ValueError("standard 7-game match requires total_games=7 and target_wins=4")


def _validate_match_auto_save_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("match auto-save payload must be a JSON object")
    _validate_standard_match_auto_save(MatchRecord.from_dict(payload))


def _is_valid_json_file(target: Path, validator: Callable[[Any], None]) -> bool:
    """R-2/P6 恢复入口：JSON 语法和对应 auto-save schema 都必须有效。"""
    try:
        validator(_load_json_payload(target))
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return True


def _is_invalid_json_file(path: Path, validator: Callable[[Any], None]) -> bool:
    return path.is_file() and not _is_valid_json_file(path, validator)


def is_invalid_auto_save_file(*, path: str | Path = AUTO_SAVE_PATH) -> bool:
    return _is_invalid_json_file(Path(path), _validate_auto_save_payload)


def is_invalid_match_auto_save_file(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> bool:
    return _is_invalid_json_file(Path(path), _validate_match_auto_save_payload)


def auto_save(
    record: GameRecord,
    timer_snapshot: TimerSnapshotLike,
    *,
    path: str | Path = AUTO_SAVE_PATH,
) -> None:
    target = Path(path)
    payload = record.to_dict()
    metadata = dict(payload.get("metadata", {}))
    metadata[AUTO_SAVE_METADATA_KEY] = _timer_metadata(timer_snapshot)
    payload["metadata"] = metadata
    _atomic_write_text(
        target,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def has_auto_save(*, path: str | Path = AUTO_SAVE_PATH) -> bool:
    target = Path(path)
    if not target.is_file():
        return False
    return _is_valid_json_file(target, _validate_auto_save_payload)


def load_auto_save(*, path: str | Path = AUTO_SAVE_PATH) -> tuple[GameRecord, dict[str, Any]]:
    record = GameRecord.load(path)
    timer_metadata = record.metadata.get(AUTO_SAVE_METADATA_KEY)
    if not isinstance(timer_metadata, dict):
        raise ValueError("invalid auto-save metadata")
    _validate_timer_metadata(timer_metadata)
    return record, timer_metadata


def clear_auto_save(*, path: str | Path = AUTO_SAVE_PATH) -> None:
    Path(path).unlink(missing_ok=True)


def _timer_metadata(snapshot: TimerSnapshotLike) -> dict[str, Any]:
    return {
        "timer_current_player": Player.from_value(snapshot.current_player).value,
        "timer_remaining": {
            Player.from_value(player).value: max(0.0, float(seconds))
            for player, seconds in snapshot.remaining_seconds.items()
        },
        "timer_paused": bool(snapshot.paused),
    }


def _validate_timer_metadata(metadata: dict[str, Any]) -> None:
    try:
        Player.from_value(metadata["timer_current_player"])
        remaining = metadata["timer_remaining"]
        if not isinstance(remaining, dict):
            raise ValueError
        for player in (Player.RED, Player.BLUE):
            float(remaining[player.value])
        bool(metadata["timer_paused"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid auto-save metadata") from exc


def auto_save_match(
    match: MatchRecord,
    *,
    path: str | Path = AUTO_SAVE_MATCH_PATH,
) -> None:
    """R-2 多盘 auto-save：完整保存 MatchRecord，包括 games[]/phase/scores。原子写入。"""
    _atomic_write_text(Path(path), match.to_json(indent=2) + "\n")


def has_auto_save_match(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> bool:
    target = Path(path)
    if not target.is_file():
        return False
    return _is_valid_json_file(target, _validate_match_auto_save_payload)


def load_auto_save_match(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> MatchRecord:
    match = MatchRecord.load(path)
    _validate_standard_match_auto_save(match)
    return match


def clear_auto_save_match(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> None:
    Path(path).unlink(missing_ok=True)
