from __future__ import annotations

import math
import time
import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.types import Player
from gui.app import player_label
from gui.time_limit import validate_nonnegative_seconds, validate_total_seconds


from gui.timing import DEFAULT_TOTAL_SECONDS, MatchTimer, TimerSnapshot, format_seconds


class TimerPanel(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_toggle_pause: Callable[[], None],
        on_confirm_timeout_forfeit: Callable[[Player], None] | None = None,
    ) -> None:
        super().__init__(master, padx=16, pady=12)
        self._on_confirm_timeout_forfeit = on_confirm_timeout_forfeit
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

        timeout_button_row = tk.Frame(self)
        timeout_button_row.pack(fill=tk.X, pady=(6, 0))
        self.red_timeout_button = tk.Button(
            timeout_button_row,
            text="裁判判红方超时负",
            command=lambda: self._confirm_timeout_forfeit(Player.RED),
            state=tk.DISABLED,
        )
        self.red_timeout_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.blue_timeout_button = tk.Button(
            timeout_button_row,
            text="裁判判蓝方超时负",
            command=lambda: self._confirm_timeout_forfeit(Player.BLUE),
            state=tk.DISABLED,
        )
        self.blue_timeout_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

    def set_snapshot(
        self,
        snapshot: TimerSnapshot,
        *,
        auto_timeout_enabled: bool = True,
        timeout_adjudication_enabled: bool = False,
    ) -> None:
        self.red_remaining_var.set(f"红方剩余：{format_seconds(snapshot.remaining_seconds[Player.RED])}")
        self.blue_remaining_var.set(f"蓝方剩余：{format_seconds(snapshot.remaining_seconds[Player.BLUE])}")
        self.step_time_var.set(f"本步用时：{format_seconds(snapshot.current_step_seconds)}")

        if snapshot.timeout_players:
            timeout_text = "、".join(player_label(player) for player in snapshot.timeout_players)
            if auto_timeout_enabled:
                self.timer_status_var.set(f"超时：{timeout_text}")
            else:
                self.timer_status_var.set(f"超时提示：{timeout_text}（等裁判）")
        elif snapshot.paused:
            self.timer_status_var.set("计时暂停")
        else:
            suffix = "" if auto_timeout_enabled else "（仅提示）"
            self.timer_status_var.set(f"计时中：{player_label(snapshot.current_player)}{suffix}")

        self.pause_button.configure(text="恢复计时" if snapshot.paused else "暂停计时")
        enabled_players = set()
        if (
            timeout_adjudication_enabled
            and not auto_timeout_enabled
            and self._on_confirm_timeout_forfeit is not None
        ):
            enabled_players = set(snapshot.timeout_players)
        self.red_timeout_button.configure(
            state=tk.NORMAL if Player.RED in enabled_players else tk.DISABLED
        )
        self.blue_timeout_button.configure(
            state=tk.NORMAL if Player.BLUE in enabled_players else tk.DISABLED
        )

    def _confirm_timeout_forfeit(self, player: Player) -> None:
        if self._on_confirm_timeout_forfeit is None:
            return
        self._on_confirm_timeout_forfeit(player)
