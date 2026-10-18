"""Shared monotonic match clock, independent of either GUI toolkit."""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.types import Player
from gui.time_limit import validate_nonnegative_seconds, validate_total_seconds

DEFAULT_TOTAL_SECONDS = 240.0


def format_seconds(seconds: float) -> str:
    total_seconds = math.ceil(max(0.0, seconds))
    minutes, remainder = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remainder:02d}"


@dataclass(frozen=True)
class TimerSnapshot:
    current_player: Player
    remaining_seconds: dict[Player, float]
    current_step_seconds: float
    paused: bool
    timeout_players: tuple[Player, ...]


class MatchTimer:
    def __init__(
        self,
        *,
        total_seconds: float = DEFAULT_TOTAL_SECONDS,
        current_player: Player = Player.RED,
        now: Callable[[], float] | None = None,
        remaining_seconds: Mapping[Player, float] | Mapping[str, float] | Mapping[Player | str, float] | None = None,
    ) -> None:
        self.total_seconds = validate_total_seconds(total_seconds)
        self._now = now or time.monotonic
        self._current_player = Player.from_value(current_player)
        self._remaining_seconds = self._normalize_remaining_seconds(remaining_seconds)
        self._turn_elapsed_seconds = 0.0
        self._running_since: float | None = self._now()

    def snapshot(self) -> TimerSnapshot:
        remaining_seconds = dict(self._remaining_seconds)
        current_elapsed = self._current_elapsed_seconds()
        current_remaining = remaining_seconds[self._current_player] - current_elapsed
        remaining_seconds[self._current_player] = max(0.0, current_remaining)
        timeout_players = tuple(
            player for player in (Player.RED, Player.BLUE) if remaining_seconds[player] <= 0.0
        )
        return TimerSnapshot(
            current_player=self._current_player,
            remaining_seconds=remaining_seconds,
            current_step_seconds=current_elapsed,
            paused=self.is_paused,
            timeout_players=timeout_players,
        )

    @property
    def is_paused(self) -> bool:
        return self._running_since is None

    def pause(self) -> None:
        if self._running_since is None:
            return
        self._turn_elapsed_seconds = self._current_elapsed_seconds()
        self._running_since = None

    def resume(self) -> None:
        if self._running_since is not None:
            return
        self._running_since = self._now()

    def finish_turn(self, next_player: Player) -> tuple[float, dict[Player, float]]:
        next_player = Player.from_value(next_player)
        step_seconds = self._current_elapsed_seconds()
        self._remaining_seconds[self._current_player] = max(
            0.0,
            self._remaining_seconds[self._current_player] - step_seconds,
        )
        remaining_seconds = dict(self._remaining_seconds)
        was_paused = self.is_paused
        self._current_player = next_player
        self._turn_elapsed_seconds = 0.0
        self._running_since = None if was_paused else self._now()
        return step_seconds, remaining_seconds

    def set_active_player(self, player: Player) -> None:
        player = Player.from_value(player)
        was_paused = self.is_paused
        elapsed = self._current_elapsed_seconds()
        self._remaining_seconds[self._current_player] = max(
            0.0,
            self._remaining_seconds[self._current_player] - elapsed,
        )
        self._current_player = player
        self._turn_elapsed_seconds = 0.0
        self._running_since = None if was_paused else self._now()

    def reset(
        self, *, current_player: Player = Player.RED,
        remaining_seconds: Mapping[Player, float] | Mapping[str, float] | Mapping[Player | str, float] | None = None,
    ) -> None:
        current = Player.from_value(current_player)
        remaining = self._normalize_remaining_seconds(remaining_seconds)
        now = self._now()
        self._current_player = current
        self._remaining_seconds = remaining
        self._turn_elapsed_seconds = 0.0
        self._running_since = now

    def _current_elapsed_seconds(self) -> float:
        if self._running_since is None:
            return self._turn_elapsed_seconds
        return self._turn_elapsed_seconds + max(0.0, self._now() - self._running_since)

    def _normalize_remaining_seconds(
        self,
        remaining_seconds: Mapping[Player, float] | Mapping[str, float] | Mapping[Player | str, float] | None,
    ) -> dict[Player, float]:
        normalized = {Player.RED: self.total_seconds, Player.BLUE: self.total_seconds}
        if remaining_seconds is None:
            return normalized
        for player, seconds in remaining_seconds.items():
            normalized[Player.from_value(player)] = validate_nonnegative_seconds(seconds)
        return normalized
