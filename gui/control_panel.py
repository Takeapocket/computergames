from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence


class ControlPanel(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_dice_change: Callable[[str], None],
        on_move_select: Callable[[int], None],
        on_apply: Callable[[], None],
        on_undo: Callable[[], None],
        on_reset: Callable[[], None],
        on_save: Callable[[], None],
        on_load: Callable[[], None],
    ) -> None:
        super().__init__(master, padx=16, pady=12)
        self._on_dice_change = on_dice_change
        self._on_move_select = on_move_select

        self.current_player_var = tk.StringVar(value="当前行动方：-")
        self.dice_var = tk.StringVar(value="6")
        self.selected_pieces_var = tk.StringVar(value="可走棋子：-")
        self.winner_var = tk.StringVar(value="胜负：未结束")
        self.status_var = tk.StringVar(value="请输入骰子并选择合法走法。")

        tk.Label(self, textvariable=self.current_player_var, anchor="w").pack(fill=tk.X, pady=(0, 8))

        dice_row = tk.Frame(self)
        dice_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(dice_row, text="骰子：").pack(side=tk.LEFT)
        self.dice_spinbox = tk.Spinbox(
            dice_row,
            from_=1,
            to=6,
            width=5,
            textvariable=self.dice_var,
            command=self._emit_dice_change,
        )
        self.dice_spinbox.pack(side=tk.LEFT)
        self.dice_spinbox.bind("<Return>", self._emit_dice_change)
        self.dice_spinbox.bind("<FocusOut>", self._emit_dice_change)

        tk.Label(self, textvariable=self.selected_pieces_var, anchor="w").pack(fill=tk.X, pady=(0, 8))
        tk.Label(self, text="合法走法：", anchor="w").pack(fill=tk.X)

        self.move_listbox = tk.Listbox(self, height=12, exportselection=False)
        self.move_listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self.move_listbox.bind("<<ListboxSelect>>", self._emit_move_select)

        self.apply_button = tk.Button(self, text="执行走法", command=on_apply)
        self.apply_button.pack(fill=tk.X, pady=(0, 6))

        button_row = tk.Frame(self)
        button_row.pack(fill=tk.X, pady=(0, 8))
        tk.Button(button_row, text="悔棋", command=on_undo).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(button_row, text="重置", command=on_reset).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        record_row = tk.Frame(self)
        record_row.pack(fill=tk.X, pady=(0, 8))
        tk.Button(record_row, text="保存棋谱", command=on_save).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(record_row, text="加载棋谱", command=on_load).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        tk.Label(self, textvariable=self.winner_var, anchor="w").pack(fill=tk.X, pady=(0, 8))
        tk.Label(self, textvariable=self.status_var, anchor="w", wraplength=300, justify=tk.LEFT).pack(fill=tk.X)

    def set_current_player(self, value: str) -> None:
        self.current_player_var.set(f"当前行动方：{value}")

    def set_dice(self, dice: int) -> None:
        self.dice_var.set(str(dice))

    def set_selected_pieces(self, piece_ids: Sequence[int]) -> None:
        value = "、".join(str(piece_id) for piece_id in piece_ids) if piece_ids else "-"
        self.selected_pieces_var.set(f"可走棋子：{value}")

    def set_moves(self, labels: Sequence[str], selected_index: int | None) -> None:
        self.move_listbox.delete(0, tk.END)
        for label in labels:
            self.move_listbox.insert(tk.END, label)
        if selected_index is not None and 0 <= selected_index < len(labels):
            self.move_listbox.selection_set(selected_index)
            self.move_listbox.see(selected_index)

    def set_winner(self, value: str) -> None:
        self.winner_var.set(f"胜负：{value}")

    def set_status(self, value: str) -> None:
        self.status_var.set(value)

    def set_can_apply(self, enabled: bool) -> None:
        self.apply_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def _emit_dice_change(self, event: tk.Event | None = None) -> None:
        self._on_dice_change(self.dice_var.get())

    def _emit_move_select(self, event: tk.Event) -> None:
        selection = self.move_listbox.curselection()
        if selection:
            self._on_move_select(int(selection[0]))
