from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from core.types import Player
from record.game_record import GameRecord


AUTO_SAVE_PATH = Path(__file__).resolve().parents[1] / "replays" / "auto_save.json"
AUTO_SAVE_METADATA_KEY = "auto_save"


class TimerSnapshotLike(Protocol):
    current_player: Player
    remaining_seconds: Mapping[Player, float]
    paused: bool


def auto_save(
    record: GameRecord,
    timer_snapshot: TimerSnapshotLike,
    *,
    path: str | Path = AUTO_SAVE_PATH,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = record.to_dict()
    metadata = dict(payload.get("metadata", {}))
    metadata[AUTO_SAVE_METADATA_KEY] = _timer_metadata(timer_snapshot)
    payload["metadata"] = metadata

    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def has_auto_save(*, path: str | Path = AUTO_SAVE_PATH) -> bool:
    target = Path(path)
    if not target.is_file():
        return False
    try:
        return bool(target.read_text(encoding="utf-8").strip())
    except OSError:
        return False


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
