from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.types import Player
from gui.app import player_label


DEFAULT_TOTAL_SECONDS = 240.0


def format_seconds(seconds: float) -> str:
    total_seconds = int(max(0.0, seconds))
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
        remaining_seconds: Mapping[Player | str, float] | None = None,
    ) -> None:
        self.total_seconds = float(total_seconds)
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
        step_seconds = self._current_elapsed_seconds()
        self._remaining_seconds[self._current_player] = max(
            0.0,
            self._remaining_seconds[self._current_player] - step_seconds,
        )
        remaining_seconds = dict(self._remaining_seconds)
        was_paused = self.is_paused
        self._current_player = Player.from_value(next_player)
        self._turn_elapsed_seconds = 0.0
        self._running_since = None if was_paused else self._now()
        return step_seconds, remaining_seconds

    def set_active_player(self, player: Player) -> None:
        was_paused = self.is_paused
        elapsed = self._current_elapsed_seconds()
        self._remaining_seconds[self._current_player] = max(
            0.0,
            self._remaining_seconds[self._current_player] - elapsed,
        )
        self._current_player = Player.from_value(player)
        self._turn_elapsed_seconds = 0.0
        self._running_since = None if was_paused else self._now()

    def reset(
        self,
        *,
        current_player: Player = Player.RED,
        remaining_seconds: Mapping[Player | str, float] | None = None,
    ) -> None:
        self._current_player = Player.from_value(current_player)
        self._remaining_seconds = self._normalize_remaining_seconds(remaining_seconds)
        self._turn_elapsed_seconds = 0.0
        self._running_since = self._now()

    def _current_elapsed_seconds(self) -> float:
        if self._running_since is None:
            return self._turn_elapsed_seconds
        return self._turn_elapsed_seconds + max(0.0, self._now() - self._running_since)

    def _normalize_remaining_seconds(
        self,
        remaining_seconds: Mapping[Player | str, float] | None,
    ) -> dict[Player, float]:
        normalized = {
            Player.RED: self.total_seconds,
            Player.BLUE: self.total_seconds,
        }
        if remaining_seconds is None:
            return normalized

        for player, seconds in remaining_seconds.items():
            normalized[Player.from_value(player)] = max(0.0, float(seconds))
        return normalized


class TimerPanel(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_toggle_pause: Callable[[], None],
    ) -> None:
        super().__init__(master, padx=16, pady=12)
        self.red_remaining_var = tk.StringVar(value="红方剩余：04:00")
        self.blue_remaining_var = tk.StringVar(value="蓝方剩余：04:00")
        self.step_time_var = tk.StringVar(value="本步用时：00:00")
        self.timer_status_var = tk.StringVar(value="计时中")

        tk.Label(self, textvariable=self.red_remaining_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.blue_remaining_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.step_time_var, anchor="w").pack(fill=tk.X, pady=(4, 0))
        tk.Label(self, textvariable=self.timer_status_var, anchor="w").pack(fill=tk.X, pady=(4, 6))

        self.pause_button = tk.Button(self, text="暂停计时", command=on_toggle_pause)
        self.pause_button.pack(fill=tk.X)

    def set_snapshot(self, snapshot: TimerSnapshot) -> None:
        self.red_remaining_var.set(f"红方剩余：{format_seconds(snapshot.remaining_seconds[Player.RED])}")
        self.blue_remaining_var.set(f"蓝方剩余：{format_seconds(snapshot.remaining_seconds[Player.BLUE])}")
        self.step_time_var.set(f"本步用时：{format_seconds(snapshot.current_step_seconds)}")

        if snapshot.timeout_players:
            timeout_text = "、".join(player_label(player) for player in snapshot.timeout_players)
            self.timer_status_var.set(f"超时：{timeout_text}")
        elif snapshot.paused:
            self.timer_status_var.set("计时暂停")
        else:
            self.timer_status_var.set(f"计时中：{player_label(snapshot.current_player)}")

        self.pause_button.configure(text="恢复计时" if snapshot.paused else "暂停计时")
