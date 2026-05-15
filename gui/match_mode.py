from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence


class MatchModePanel(tk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padx=16, pady=8, borderwidth=1, relief="solid")

        self.current_player_var = tk.StringVar(value="当前行动方：-")
        self.phase_var = tk.StringVar(value="当前阶段：请录入骰子")
        self.selected_pieces_var = tk.StringVar(value="可走棋子：-")
        self.recommendation_var = tk.StringVar(value="推荐走法：未启用 AI")
        self.record_status_var = tk.StringVar(value="棋谱状态：✓ 已保存")
        self.can_undo_var = tk.StringVar(value="悔棋：不可用")

        # R-2 比赛模式专用字段
        self.round_status_var = tk.StringVar(value="")
        self.score_var = tk.StringVar(value="")
        self.first_mover_var = tk.StringVar(value="")
        self.role_var = tk.StringVar(value="")

        tk.Label(self, textvariable=self.current_player_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.phase_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.selected_pieces_var, anchor="w").pack(fill=tk.X)
        tk.Label(
            self,
            textvariable=self.recommendation_var,
            anchor="w",
            justify=tk.LEFT,
            wraplength=320,
        ).pack(fill=tk.X)
        tk.Label(self, textvariable=self.record_status_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.can_undo_var, anchor="w").pack(fill=tk.X)

        self._match_separator = tk.Frame(self, height=1, bg="#999999")
        self._round_label = tk.Label(self, textvariable=self.round_status_var, anchor="w")
        self._score_label = tk.Label(self, textvariable=self.score_var, anchor="w")
        self._first_mover_label = tk.Label(self, textvariable=self.first_mover_var, anchor="w")
        self._role_label = tk.Label(self, textvariable=self.role_var, anchor="w")
        self._match_widgets: tuple[tk.Widget, ...] = (
            self._match_separator,
            self._round_label,
            self._score_label,
            self._first_mover_label,
            self._role_label,
        )
        self._match_visible = False

    def set_current_player(self, value: str) -> None:
        self.current_player_var.set(f"当前行动方：{value}")

    def set_phase(self, phase_label: str) -> None:
        self.phase_var.set(f"当前阶段：{phase_label}")

    def set_selected_pieces(self, piece_ids: Sequence[int]) -> None:
        value = "、".join(str(pid) for pid in piece_ids) if piece_ids else "-"
        self.selected_pieces_var.set(f"可走棋子：{value}")

    def set_recommendation(self, text: str) -> None:
        self.recommendation_var.set(f"推荐走法：{text}")

    def set_record_dirty(self, dirty: bool) -> None:
        self.record_status_var.set("棋谱状态：● 未保存" if dirty else "棋谱状态：✓ 已保存")

    def set_can_undo(self, enabled: bool) -> None:
        self.can_undo_var.set("悔棋：可用" if enabled else "悔棋：不可用")

    def set_match_status(
        self,
        *,
        game_index: int,
        total_games: int,
        games_won_us: int,
        games_won_them: int,
        first_mover_label: str,
        our_role: str,
    ) -> None:
        """R-2 比赛模式专用：刷新盘数、比分、本盘先手、我方身份。会自动显示这 4 行。"""
        self.round_status_var.set(f"本轮：第 {game_index} 盘 / 共 {total_games} 盘")
        self.score_var.set(f"比分：我方 {games_won_us} — 对方 {games_won_them}")
        self.first_mover_var.set(f"本盘先手：{first_mover_label}")
        self.role_var.set(f"我方身份：{our_role}方")
        if not self._match_visible:
            self._match_separator.pack(fill=tk.X, pady=(6, 4))
            self._round_label.pack(fill=tk.X)
            self._score_label.pack(fill=tk.X)
            self._first_mover_label.pack(fill=tk.X)
            self._role_label.pack(fill=tk.X)
            self._match_visible = True

    def hide_match_status(self) -> None:
        """调试模式或退出比赛模式时调用，隐藏 R-2 比赛字段。"""
        if self._match_visible:
            for widget in self._match_widgets:
                widget.pack_forget()
            self._match_visible = False
        self.round_status_var.set("")
        self.score_var.set("")
        self.first_mover_var.set("")
        self.role_var.set("")

    @property
    def is_match_status_visible(self) -> bool:
        return self._match_visible
