from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from core.game_state import GameState
from core.move import Move
from core.types import Player


MoveSource = Literal["self", "opponent", "unknown"]


def _atomic_write_text(target: Path, text: str, *, encoding: str = "utf-8") -> None:
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


@dataclass(frozen=True)
class MoveRecord:
    turn: int
    player: Player
    dice: int
    move: Move
    state_after: dict[str, Any]
    step_seconds: float = 0.0
    remaining_seconds: dict[Player, float] = field(default_factory=dict)
    source: MoveSource = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "player", Player.from_value(self.player))
        object.__setattr__(self, "step_seconds", max(0.0, float(self.step_seconds)))
        object.__setattr__(self, "remaining_seconds", _normalize_remaining_seconds(self.remaining_seconds))
        if self.turn < 1:
            raise ValueError("turn must be positive")
        if not 1 <= self.dice <= 6:
            raise ValueError("dice must be between 1 and 6")
        if self.source not in ("self", "opponent", "unknown"):
            raise ValueError(f"invalid source: {self.source!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "player": self.player.value,
            "dice": self.dice,
            "move": self.move.to_dict(),
            "state_after": self.state_after,
            "step_seconds": self.step_seconds,
            "remaining_seconds": {
                player.value: seconds for player, seconds in self.remaining_seconds.items()
            },
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoveRecord":
        try:
            return cls(
                turn=int(data["turn"]),
                player=Player.from_value(data["player"]),
                dice=int(data["dice"]),
                move=Move.from_dict(data["move"]),
                state_after=dict(data["state_after"]),
                step_seconds=float(data.get("step_seconds", 0.0)),
                remaining_seconds=_normalize_remaining_seconds(data.get("remaining_seconds", {})),
                source=data.get("source", "unknown"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid move record data") from exc


@dataclass
class GameRecord:
    initial_state: dict[str, Any]
    steps: list[MoveRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: GameState) -> "GameRecord":
        return cls(initial_state=state.serialize())

    def append(
        self,
        *,
        dice: int,
        move: Move,
        state_after: GameState,
        step_seconds: float = 0.0,
        remaining_seconds: Mapping[Player | str, float] | None = None,
        source: MoveSource = "unknown",
    ) -> MoveRecord:
        step = MoveRecord(
            turn=len(self.steps) + 1,
            player=move.player,
            dice=dice,
            move=move,
            state_after=state_after.serialize(include_history=False),
            step_seconds=step_seconds,
            remaining_seconds=_normalize_remaining_seconds(remaining_seconds or {}),
            source=source,
        )
        self.steps.append(step)
        return step

    def undo_last(self) -> MoveRecord | None:
        if not self.steps:
            return None
        return self.steps.pop()

    def restore_state(self) -> GameState:
        state = GameState.deserialize(self.initial_state)
        for step in self.steps:
            state.apply_move(step.move, dice=step.dice)
        return state

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_state": self.initial_state,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameRecord":
        try:
            steps_data = data["steps"]
            if not isinstance(steps_data, list):
                raise ValueError("record steps must be a list")

            metadata = data.get("metadata", {})
            result = data.get("result", {})
            if metadata is None:
                metadata = {}
            if result is None:
                result = {}
            if not isinstance(metadata, dict):
                raise ValueError("record metadata must be a dict")
            if not isinstance(result, dict):
                raise ValueError("record result must be a dict")

            record = cls(
                initial_state=dict(data["initial_state"]),
                steps=[MoveRecord.from_dict(step_data) for step_data in steps_data],
                metadata=dict(metadata),
                result=dict(result),
            )
            state = GameState.deserialize(record.initial_state)
            for expected_turn, step in enumerate(record.steps, start=1):
                if step.turn != expected_turn:
                    raise ValueError(
                        f"step turn must be continuous: expected {expected_turn}, got {step.turn}"
                    )
                if step.player is not step.move.player:
                    raise ValueError(
                        f"step player {step.player.value!r} differs from move player "
                        f"{step.move.player.value!r}"
                    )
                state.apply_move(step.move, dice=step.dice)
                expected_state_after = GameState.deserialize(step.state_after).serialize(
                    include_history=False
                )
                actual_state_after = state.serialize(include_history=False)
                if actual_state_after != expected_state_after:
                    raise ValueError("step state_after does not match replayed state")
            return record
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid game record data: {exc}") from exc

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, payload: str) -> "GameRecord":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid game record json") from exc
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        _atomic_write_text(Path(path), self.to_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "GameRecord":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def _normalize_remaining_seconds(
    remaining_seconds: Mapping[Player | str, float],
) -> dict[Player, float]:
    return {
        Player.from_value(player): max(0.0, float(seconds))
        for player, seconds in remaining_seconds.items()
    }
