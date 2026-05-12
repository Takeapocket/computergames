from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Literal

from ai.opening_layouts import (
    BLUE_ZONE,
    DEFAULT_LAYOUT_DIR,
    PRESETS,
    RED_ZONE,
    Layout,
    layout_to_metadata,
    list_saved_layouts,
    load_layout,
    mirror_layout,
    save_layout,
    validate_layout,
)
from core.game_state import GameState
from core.types import Player, Position


EditTarget = Literal["self", "opponent"]


@dataclass(frozen=True)
class OpeningSelection:
    our_side: Player
    red_layout: Layout
    blue_layout: Layout
    red_layout_source: str
    blue_layout_source: str

    def metadata(self) -> dict[str, object]:
        return {
            "our_side": self.our_side.value,
            "red_layout": layout_to_metadata(self.red_layout),
            "blue_layout": layout_to_metadata(self.blue_layout),
            "red_layout_source": self.red_layout_source,
            "blue_layout_source": self.blue_layout_source,
        }


class OpeningPanel(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_confirm: Callable[[OpeningSelection], None],
        on_layout_change: Callable[[], None] | None = None,
        layout_directory: str | Path = DEFAULT_LAYOUT_DIR,
    ) -> None:
        super().__init__(master)
        self._on_confirm = on_confirm
        self._on_layout_change = on_layout_change
        self._layout_directory = Path(layout_directory)
        self._red_layout: Layout = {}
        self._blue_layout: Layout = {}
        self._red_layout_source = "manual_entry"
        self._blue_layout_source = "manual_entry"
        self._saved_layout_ids: set[str] = set()
        self._notifications_enabled = False

        self.our_side_var = tk.StringVar(value=Player.RED.value)
        self.layout_var = tk.StringVar(value="balanced_v1")
        self.edit_target_var = tk.StringVar(value="opponent")
        self.selected_piece_var = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="")

        self._build_widgets()
        self.refresh_saved_layouts()
        self.reset(notify=False)
        self._notifications_enabled = True

    @property
    def our_side(self) -> Player:
        return Player.from_value(self.our_side_var.get())

    @property
    def red_layout_source(self) -> str:
        return self._red_layout_source

    @property
    def blue_layout_source(self) -> str:
        return self._blue_layout_source

    def get_layouts(self) -> tuple[Layout, Layout]:
        return dict(self._red_layout), dict(self._blue_layout)

    def preview_state(self) -> GameState:
        return GameState.from_layout(red=self._red_layout, blue=self._blue_layout, current_player=Player.RED)

    def current_edit_zone(self) -> frozenset[Position]:
        return RED_ZONE if self.current_edit_side() is Player.RED else BLUE_ZONE

    def current_edit_side(self) -> Player:
        if self.edit_target_var.get() == "self":
            return self.our_side
        return self.our_side.opponent

    def set_our_side(self, player: Player) -> None:
        self.our_side_var.set(Player.from_value(player).value)
        self._red_layout = {}
        self._blue_layout = {}
        self._red_layout_source = "manual_entry"
        self._blue_layout_source = "manual_entry"
        self.select_layout(self.layout_var.get())

    def select_layout(self, layout_id: str) -> None:
        self.layout_var.set(layout_id)
        if layout_id in PRESETS:
            preset = PRESETS[layout_id]
            if self.our_side is Player.RED:
                self._red_layout = dict(preset.red)
                self._red_layout_source = f"preset:{layout_id}"
            else:
                self._blue_layout = dict(preset.blue)
                self._blue_layout_source = f"preset:{layout_id}"
            self.status_var.set(f"已选择布局：{preset.name}")
            self._notify_layout_change()
            return

        try:
            saved = load_layout(layout_id, directory=self._layout_directory)
        except ValueError as exc:
            self.status_var.set(f"加载布局失败：{exc}")
            return

        if self.our_side is Player.RED:
            self._red_layout = dict(saved.red)
            self._red_layout_source = f"custom:{layout_id}"
        else:
            self._blue_layout = dict(saved.blue)
            self._blue_layout_source = f"custom:{layout_id}"
        self.status_var.set(f"已加载布局：{saved.name}")
        self._notify_layout_change()

    def set_edit_target(self, target: EditTarget) -> None:
        if target not in ("self", "opponent"):
            raise ValueError("edit target must be 'self' or 'opponent'")
        self.edit_target_var.set(target)
        self._notify_layout_change()

    def set_selected_piece(self, piece_id: int) -> None:
        if not 1 <= int(piece_id) <= 6:
            raise ValueError("piece id must be between 1 and 6")
        self.selected_piece_var.set(int(piece_id))
        self._update_piece_buttons()

    def handle_board_click(self, position: Position) -> bool:
        side = self.current_edit_side()
        zone = RED_ZONE if side is Player.RED else BLUE_ZONE
        if position not in zone:
            self.status_var.set("只能在当前编辑方的出发区内摆放棋子。")
            return False

        layout = self._layout_for_side(side)
        occupant = _piece_at(layout, position)
        if occupant is not None:
            del layout[occupant]
            self._mark_manual_source(side)
            self.status_var.set(f"已移除{_player_label(side)} {occupant}。")
            self._notify_layout_change()
            return True

        piece_id = int(self.selected_piece_var.get())
        layout[piece_id] = position
        self._mark_manual_source(side)
        self.status_var.set(f"已摆放{_player_label(side)} {piece_id}。")
        self._notify_layout_change()
        return True

    def confirm(self) -> None:
        errors = validate_layout(self._red_layout, self._blue_layout)
        if errors:
            self.status_var.set(errors[0])
            return
        self._on_confirm(
            OpeningSelection(
                our_side=self.our_side,
                red_layout=dict(self._red_layout),
                blue_layout=dict(self._blue_layout),
                red_layout_source=self._red_layout_source,
                blue_layout_source=self._blue_layout_source,
            )
        )

    def save_current_layout(self, layout_id: str, name: str) -> bool:
        try:
            red_layout, blue_layout = self._custom_layout_pair_for_save()
            save_layout(layout_id, red_layout, blue_layout, name, directory=self._layout_directory)
        except (OSError, ValueError) as exc:
            self.status_var.set(f"保存布局失败：{exc}")
            return False
        self.refresh_saved_layouts()
        self.status_var.set(f"布局已保存：{name}")
        return True

    def refresh_saved_layouts(self) -> None:
        self._saved_layout_ids = {layout.id for layout in list_saved_layouts(directory=self._layout_directory)}
        self._rebuild_layout_menu()

    def reset(self, *, notify: bool = True) -> None:
        was_enabled = self._notifications_enabled
        if not notify:
            self._notifications_enabled = False
        try:
            self.our_side_var.set(Player.RED.value)
            self.layout_var.set("balanced_v1")
            self.edit_target_var.set("opponent")
            self.selected_piece_var.set(1)
            self._red_layout = {}
            self._blue_layout = {}
            self._red_layout_source = "manual_entry"
            self._blue_layout_source = "manual_entry"
            self.select_layout("balanced_v1")
            self.status_var.set("请选择我方布局，并录入对方开局。")
            self._update_piece_buttons()
        finally:
            self._notifications_enabled = was_enabled
        if notify:
            self._notify_layout_change()

    def reset_for_match_game(
        self,
        *,
        our_side: Player,
        keep_our_layout: bool,
    ) -> None:
        """R-2 比赛模式专用：每盘开始时调用，固定我方颜色并按 sticky 规则准备布局。

        - keep_our_layout=True（上盘我方胜）：保留我方布局；清空对方布局
        - keep_our_layout=False（第 1 盘或上盘我方负）：重置我方布局为当前下拉预设；清空对方布局
        """
        new_side = Player.from_value(our_side)
        was_enabled = self._notifications_enabled
        self._notifications_enabled = False
        try:
            self.our_side_var.set(new_side.value)
            self.edit_target_var.set("opponent")
            self.selected_piece_var.set(1)
            if keep_our_layout and self._layout_for_side(new_side):
                # 沿用我方布局，清空对方
                opponent_layout = self._layout_for_side(new_side.opponent)
                opponent_layout.clear()
                if new_side is Player.RED:
                    self._blue_layout_source = "manual_entry"
                else:
                    self._red_layout_source = "manual_entry"
                self.status_var.set("已沿用我方上盘布局，请录入对方本盘开局。")
            else:
                # 重置我方布局为预设，清空对方
                self._red_layout = {}
                self._blue_layout = {}
                self._red_layout_source = "manual_entry"
                self._blue_layout_source = "manual_entry"
                # select_layout 会按当前 our_side 加载预设到我方那一侧
                self.select_layout(self.layout_var.get())
                self.status_var.set("请确认我方布局，并录入对方本盘开局。")
            self._update_piece_buttons()
        finally:
            self._notifications_enabled = was_enabled
        self._notify_layout_change()

    def set_side_controls_enabled(self, enabled: bool) -> None:
        """R-2 比赛模式专用：禁用/启用红/蓝颜色 radio。

        比赛模式下颜色一轮内固定，必须真正禁用 widget 防止误点。"""
        state = tk.NORMAL if enabled else tk.DISABLED
        try:
            self._red_side_radio.configure(state=state)
            self._blue_side_radio.configure(state=state)
        except tk.TclError:
            pass

    @property
    def side_controls_enabled(self) -> bool:
        try:
            return str(self._red_side_radio.cget("state")) == tk.NORMAL
        except tk.TclError:
            return True

    def _build_widgets(self) -> None:
        title = tk.Label(self, text="开局录入", font=("Segoe UI", 14, "bold"))
        title.pack(anchor=tk.W, pady=(0, 8))

        side_box = tk.LabelFrame(self, text="我方颜色", padx=8, pady=6)
        side_box.pack(fill=tk.X, pady=(0, 8))
        self._red_side_radio = tk.Radiobutton(
            side_box,
            text="红方",
            value=Player.RED.value,
            variable=self.our_side_var,
            command=lambda: self.set_our_side(Player.RED),
        )
        self._red_side_radio.pack(side=tk.LEFT)
        self._blue_side_radio = tk.Radiobutton(
            side_box,
            text="蓝方",
            value=Player.BLUE.value,
            variable=self.our_side_var,
            command=lambda: self.set_our_side(Player.BLUE),
        )
        self._blue_side_radio.pack(side=tk.LEFT)

        layout_box = tk.LabelFrame(self, text="我方布局", padx=8, pady=6)
        layout_box.pack(fill=tk.X, pady=(0, 8))
        self._layout_menu = tk.OptionMenu(layout_box, self.layout_var, "balanced_v1")
        self._layout_menu.pack(fill=tk.X)

        edit_box = tk.LabelFrame(self, text="编辑目标", padx=8, pady=6)
        edit_box.pack(fill=tk.X, pady=(0, 8))
        tk.Radiobutton(
            edit_box,
            text="我方",
            value="self",
            variable=self.edit_target_var,
            command=lambda: self.set_edit_target("self"),
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            edit_box,
            text="对方",
            value="opponent",
            variable=self.edit_target_var,
            command=lambda: self.set_edit_target("opponent"),
        ).pack(side=tk.LEFT)

        piece_box = tk.LabelFrame(self, text="棋子编号", padx=8, pady=6)
        piece_box.pack(fill=tk.X, pady=(0, 8))
        self._piece_buttons: dict[int, tk.Button] = {}
        for piece_id in range(1, 7):
            button = tk.Button(
                piece_box,
                text=str(piece_id),
                width=3,
                command=lambda value=piece_id: self.set_selected_piece(value),
            )
            button.pack(side=tk.LEFT, padx=2)
            self._piece_buttons[piece_id] = button

        action_row = tk.Frame(self)
        action_row.pack(fill=tk.X, pady=(0, 8))
        tk.Button(action_row, text="编辑自定义", command=lambda: self.set_edit_target("self")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(action_row, text="保存布局", command=self._save_layout_from_dialog).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(self, text="确认并开始", command=self.confirm).pack(fill=tk.X, pady=(0, 8))
        tk.Label(self, textvariable=self.status_var, anchor=tk.W, justify=tk.LEFT, wraplength=260).pack(fill=tk.X)

    def _rebuild_layout_menu(self) -> None:
        menu = self._layout_menu["menu"]
        menu.delete(0, "end")
        for layout_id in [*PRESETS, *sorted(self._saved_layout_ids)]:
            menu.add_command(label=layout_id, command=lambda value=layout_id: self.select_layout(value))

    def _save_layout_from_dialog(self) -> None:
        layout_id = simpledialog.askstring("保存布局", "布局 ID（字母、数字、下划线或连字符）：", parent=self)
        if not layout_id:
            return
        name = simpledialog.askstring("保存布局", "布局名称：", parent=self) or layout_id
        if not self.save_current_layout(layout_id, name):
            messagebox.showerror("保存布局失败", self.status_var.get(), parent=self)

    def _layout_for_side(self, side: Player) -> Layout:
        return self._red_layout if side is Player.RED else self._blue_layout

    def _custom_layout_pair_for_save(self) -> tuple[Layout, Layout]:
        if self.our_side is Player.RED:
            return dict(self._red_layout), mirror_layout(self._red_layout)
        return mirror_layout(self._blue_layout), dict(self._blue_layout)

    def _mark_manual_source(self, side: Player) -> None:
        if side is Player.RED:
            self._red_layout_source = "manual_entry"
        else:
            self._blue_layout_source = "manual_entry"

    def _notify_layout_change(self) -> None:
        if self._notifications_enabled and self._on_layout_change is not None:
            self._on_layout_change()

    def _update_piece_buttons(self) -> None:
        selected = int(self.selected_piece_var.get())
        for piece_id, button in self._piece_buttons.items():
            relief = tk.SUNKEN if piece_id == selected else tk.RAISED
            button.configure(relief=relief)


def _piece_at(layout: Layout, position: Position) -> int | None:
    for piece_id, piece_position in layout.items():
        if piece_position == position:
            return piece_id
    return None


def _player_label(player: Player) -> str:
    return "红方" if Player.from_value(player) is Player.RED else "蓝方"
