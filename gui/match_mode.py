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

        tk.Label(self, textvariable=self.current_player_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.phase_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.selected_pieces_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.recommendation_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.record_status_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.can_undo_var, anchor="w").pack(fill=tk.X)

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
