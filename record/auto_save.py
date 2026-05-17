from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from core.types import Player
from record.game_record import GameRecord
from record.match_record import MatchRecord


AUTO_SAVE_PATH = Path(__file__).resolve().parents[1] / "replays" / "auto_save.json"
AUTO_SAVE_MATCH_PATH = Path(__file__).resolve().parents[1] / "replays" / "auto_save_match.json"
AUTO_SAVE_METADATA_KEY = "auto_save"


class TimerSnapshotLike(Protocol):
    current_player: Player
    remaining_seconds: Mapping[Player, float]
    paused: bool


def _atomic_write_text(target: Path, text: str, *, encoding: str = "utf-8") -> None:
    """R-2 review Critical #3：原子写。同目录写临时文件 + os.replace，避免中途崩溃损坏现有文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp-",
        suffix=target.suffix or ".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _is_valid_json_file(target: Path) -> bool:
    """R-2 review Important #11：has_auto_save* 不能只看非空，还要保证能解析为 JSON 对象。"""
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.strip():
        return False
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


def _is_invalid_json_file(path: Path) -> bool:
    return path.is_file() and not _is_valid_json_file(path)


def is_invalid_auto_save_file(*, path: str | Path = AUTO_SAVE_PATH) -> bool:
    return _is_invalid_json_file(Path(path))


def is_invalid_match_auto_save_file(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> bool:
    return _is_invalid_json_file(Path(path))


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
    return _is_valid_json_file(target)


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
    return _is_valid_json_file(target)


def load_auto_save_match(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> MatchRecord:
    return MatchRecord.load(path)


def clear_auto_save_match(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> None:
    Path(path).unlink(missing_ok=True)
