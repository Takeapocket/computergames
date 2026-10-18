from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from core.game_state import GameState
from core.move import Move
from core.rules import RULES_VERSION
from core.types import Player
from core.validation import require_finite_number, require_int


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
        object.__setattr__(self, "step_seconds", _normalize_step_seconds(self.step_seconds))
        object.__setattr__(self, "remaining_seconds", _normalize_remaining_seconds(self.remaining_seconds))
        require_int(self.turn, "turn")
        require_int(self.dice, "dice")
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
            "state_after": deepcopy(self.state_after),
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
                turn=data["turn"],
                player=Player.from_value(data["player"]),
                dice=data["dice"],
                move=Move.from_dict(data["move"]),
                state_after=deepcopy(dict(data["state_after"])),
                step_seconds=data.get("step_seconds", 0.0),
                remaining_seconds=data.get("remaining_seconds", {}),
                source=data.get("source", "unknown"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid move record data: {exc}") from exc


@dataclass
class GameRecord:
    initial_state: dict[str, Any]
    steps: list[MoveRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: GameState) -> "GameRecord":
        return cls(initial_state=state.serialize(), metadata={"rules_version": RULES_VERSION})


    def validate_continuation_rules(self) -> None:
        """Reject appending current-rule moves to explicitly different rules."""
        if "rules_version" in self.metadata and self.metadata["rules_version"] != RULES_VERSION:
            raise ValueError(
                f"record rules_version {self.metadata['rules_version']!r} differs from "
                f"current rules {RULES_VERSION!r}; start a new game record to continue"
            )

    def append(
        self,
        *,
        dice: int,
        move: Move,
        state_after: GameState,
        step_seconds: float = 0.0,
        remaining_seconds: (
            Mapping[Player, float] | Mapping[str, float] | Mapping[Player | str, float] | None
        ) = None,
        source: MoveSource = "unknown",
    ) -> MoveRecord:
        self.validate_continuation_rules()
        step = MoveRecord(
            turn=len(self.steps) + 1,
            player=move.player,
            dice=dice,
            move=move.copy(),
            state_after=state_after.serialize(include_history=False),
            step_seconds=step_seconds,
            remaining_seconds=_normalize_remaining_seconds({} if remaining_seconds is None else remaining_seconds),
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
            "initial_state": deepcopy(self.initial_state),
            "steps": [step.to_dict() for step in self.steps],
            "metadata": deepcopy(self.metadata),
            "result": deepcopy(self.result),
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
                initial_state=deepcopy(dict(data["initial_state"])),
                steps=[MoveRecord.from_dict(step_data) for step_data in steps_data],
                metadata=deepcopy(metadata),
                result=deepcopy(result),
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
                canonical_move = state.apply_move(step.move, dice=step.dice)
                if canonical_move != step.move:
                    raise ValueError("step move capture metadata does not match replayed move")
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
    remaining_seconds: Mapping[Player, float] | Mapping[str, float] | Mapping[Player | str, float],
) -> dict[Player, float]:
    if not isinstance(remaining_seconds, Mapping):
        raise ValueError("remaining_seconds must be a mapping")
    return {
        Player.from_value(player): require_finite_number(seconds, "remaining_seconds", minimum=0.0)
        for player, seconds in remaining_seconds.items()
    }


def _normalize_step_seconds(step_seconds: float) -> float:
    return require_finite_number(step_seconds, "step_seconds", minimum=0.0)
