from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Literal

from ai.match import build_ai
from core.move import Move
from core.types import Player, Position
from gui.app import create_default_state, format_move_label, player_label
from gui.board_widget import BoardWidget
from gui.control_panel import ControlPanel
from gui.match_mode import MatchModePanel
from gui.timer_panel import DEFAULT_TOTAL_SECONDS, MatchTimer, TimerPanel
from record.auto_save import AUTO_SAVE_PATH, auto_save, clear_auto_save, has_auto_save, load_auto_save
from record.game_record import GameRecord


DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[1] / "records"


class MainWindow(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        total_seconds: float = DEFAULT_TOTAL_SECONDS,
        auto_save_path: str | Path | None = None,
    ) -> None:
        super().__init__(master, padx=16, pady=16)
        self._build_menu(master)
        self._total_seconds = float(total_seconds)
        self._auto_save_path = Path(auto_save_path) if auto_save_path is not None else AUTO_SAVE_PATH
        self.state = create_default_state()
        self.record = GameRecord.from_state(self.state)
        self.timer = MatchTimer(total_seconds=self._total_seconds, current_player=self.state.current_player)
        self._timer_after_id: str | None = None
        self.current_dice = 6
        self.selected_move_index: int | None = None
        self.selected_position: Position | None = None
        self.status_message = "请输入骰子并选择合法走法。"
        self._record_dirty = False
        self._awaiting_dice = True
        self._mode: Literal["debug", "match"] = "debug"
        self._our_side: Player | None = None

        self.board = BoardWidget(self, self._handle_square_click)
        self.board.pack(side=tk.LEFT, padx=(0, 16), pady=0)

        side_panel = tk.Frame(self)
        side_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.timer_panel = TimerPanel(side_panel, on_toggle_pause=self._toggle_timer_pause)
        self.timer_panel.pack(fill=tk.X, pady=(0, 8))

        self.match_mode_panel = MatchModePanel(side_panel)
        self.match_mode_panel.pack(fill=tk.X, pady=(0, 8))

        self.controls = ControlPanel(
            side_panel,
            on_dice_change=self._handle_dice_change,
            on_move_select=self._handle_move_select,
            on_apply=self._apply_selected_move,
            on_undo=self._undo_move,
            on_reset=self._reset_game,
            on_save=self._save_record,
            on_load=self._load_record,
        )
        self.controls.pack(fill=tk.BOTH, expand=True)

        self._restore_auto_save_if_available()
        self._refresh()
        self._schedule_timer_refresh()

    def _handle_dice_change(self, value: str) -> None:
        try:
            dice = int(value)
        except ValueError:
            self.status_message = "骰子必须是 1-6 的整数。"
            self._refresh()
            return

        if not 1 <= dice <= 6:
            self.status_message = "骰子必须是 1-6 的整数。"
            self._refresh()
            return

        self.current_dice = dice
        self._awaiting_dice = False
        self._clear_selection()
        self.status_message = "骰子已更新，请选择合法走法。"
        self._refresh()

    def _handle_move_select(self, index: int) -> None:
        moves = self._current_moves()
        if not 0 <= index < len(moves):
            return

        self.selected_move_index = index
        self.selected_position = moves[index].from_pos
        self.status_message = f"已选择：{format_move_label(moves[index])}"
        self._refresh()

    def _handle_square_click(self, position: Position) -> None:
        if self.state.get_winner() is not None:
            self.status_message = "对局已结束；可以悔棋或重置。"
            self._refresh()
            return

        if self.selected_position is None:
            self._select_piece_at(position)
            self._refresh()
            return

        if self._select_destination(position):
            self._refresh()
            return

        self._select_piece_at(position)
        self._refresh()

    def _apply_selected_move(self) -> None:
        moves = self._current_moves()
        if self.selected_move_index is None or not 0 <= self.selected_move_index < len(moves):
            self.status_message = "请先选择一条合法走法。"
            self._refresh()
            return

        move = self.state.apply_move(moves[self.selected_move_index], dice=self.current_dice)
        step_seconds, remaining_seconds = self.timer.finish_turn(self.state.current_player)
        self.record.append(
            dice=self.current_dice,
            move=move,
            state_after=self.state,
            step_seconds=step_seconds,
            remaining_seconds=remaining_seconds,
            source=self._move_source(move.player),
        )
        self._record_dirty = True
        self._awaiting_dice = True
        self._clear_selection()

        winner = self.state.get_winner()
        if winner is not None:
            self.timer.pause()
            self.status_message = f"已执行：{format_move_label(move)}。{player_label(winner)}获胜。"
        else:
            self.status_message = f"已执行：{format_move_label(move)}。请录入下一轮骰子。"
        self._auto_save_current_game()
        self._refresh()

    def _undo_move(self) -> None:
        undone = self.state.undo_move()
        self._clear_selection()
        if undone is None:
            self.status_message = "当前没有可悔棋的走法。"
        else:
            self.record.undo_last()
            self.timer.set_active_player(self.state.current_player)
            self._record_dirty = True
            self._awaiting_dice = True
            self.status_message = f"已悔棋：{format_move_label(undone)}。计时不回退。"
            self._auto_save_current_game()
        self._refresh()

    def _reset_game(self) -> None:
        self.state = create_default_state()
        self.record = GameRecord.from_state(self.state)
        self.timer.reset(current_player=self.state.current_player)
        self.current_dice = 6
        self._clear_selection()
        self._record_dirty = False
        self._awaiting_dice = True
        self.status_message = "棋局已重置为临时三角布局。"
        self._clear_auto_save()
        self._refresh()

    def _auto_save_current_game(self) -> None:
        try:
            auto_save(self.record, self.timer.snapshot(), path=self._auto_save_path)
        except OSError as exc:
            self.status_message = f"自动保存失败：{exc}"

    def _clear_auto_save(self) -> None:
        try:
            clear_auto_save(path=self._auto_save_path)
        except OSError as exc:
            self.status_message = f"自动保存清理失败：{exc}"

    def _restore_auto_save_if_available(self) -> None:
        if not has_auto_save(path=self._auto_save_path):
            return

        should_restore = messagebox.askyesno(
            "恢复未完成对局",
            "检测到上次未完成的自动保存对局，是否恢复？",
            parent=self,
        )
        if not should_restore:
            self._clear_auto_save()
            return

        try:
            loaded_record, timer_metadata = load_auto_save(path=self._auto_save_path)
            loaded_state = loaded_record.restore_state()
            timer_current_player = Player.from_value(timer_metadata["timer_current_player"])
            timer_remaining = self._remaining_seconds_from_auto_save_metadata(timer_metadata)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("恢复自动保存失败", str(exc), parent=self)
            self._clear_auto_save()
            return

        self.record = loaded_record
        self.state = loaded_state
        self.timer.reset(
            current_player=timer_current_player,
            remaining_seconds=timer_remaining,
        )
        if bool(timer_metadata["timer_paused"]):
            self.timer.pause()
        self.current_dice = 6
        self._clear_selection()
        self._record_dirty = True
        self._awaiting_dice = True
        self.status_message = "已恢复上次未完成对局，请录入下一轮骰子。"

    def _remaining_seconds_from_auto_save_metadata(
        self,
        timer_metadata: dict[str, object],
    ) -> dict[Player, float]:
        remaining = timer_metadata["timer_remaining"]
        if not isinstance(remaining, dict):
            raise ValueError("invalid auto-save metadata")
        return {
            Player.RED: float(remaining[Player.RED.value]),
            Player.BLUE: float(remaining[Player.BLUE.value]),
        }

    def _save_record(self) -> None:
        DEFAULT_RECORD_DIR.mkdir(exist_ok=True)
        path = filedialog.asksaveasfilename(
            parent=self,
            title="保存棋谱",
            initialdir=str(DEFAULT_RECORD_DIR),
            defaultextension=".json",
            filetypes=(("JSON 棋谱", "*.json"), ("所有文件", "*.*")),
        )
        if not path:
            return

        try:
            self.record.save(path)
        except OSError as exc:
            messagebox.showerror("保存棋谱失败", str(exc), parent=self)
            return

        self._record_dirty = False
        self.status_message = f"棋谱已保存：{path}"
        self._refresh()

    def _load_record(self) -> None:
        DEFAULT_RECORD_DIR.mkdir(exist_ok=True)
        path = filedialog.askopenfilename(
            parent=self,
            title="加载棋谱",
            initialdir=str(DEFAULT_RECORD_DIR),
            filetypes=(("JSON 棋谱", "*.json"), ("所有文件", "*.*")),
        )
        if not path:
            return

        try:
            loaded_record = GameRecord.load(path)
            loaded_state = loaded_record.restore_state()
        except (OSError, ValueError) as exc:
            messagebox.showerror("加载棋谱失败", str(exc), parent=self)
            return

        self.record = loaded_record
        self.state = loaded_state
        self.timer.reset(
            current_player=self.state.current_player,
            remaining_seconds=self._remaining_seconds_from_record(self.record),
        )
        self.current_dice = 6
        self._clear_selection()
        self._record_dirty = False
        self._awaiting_dice = True
        self.status_message = "棋谱已加载，请录入下一轮骰子。"
        self._refresh()

    def _toggle_timer_pause(self) -> None:
        if self.timer.is_paused:
            self.timer.resume()
            self.status_message = "计时已恢复。"
        else:
            self.timer.pause()
            self.status_message = "计时已暂停。"
        self._refresh()

    def _select_piece_at(self, position: Position) -> None:
        piece = self.state.piece_at(position)
        selected_ids = self._selected_piece_ids()
        if piece is None or piece.player is not self.state.current_player:
            self.status_message = "请先点击当前行动方的可走棋子。"
            return

        if piece.piece_id not in selected_ids:
            self.status_message = f"{player_label(piece.player)} {piece.piece_id} 不符合当前骰子。"
            return

        piece_moves = [move for move in self._current_moves() if move.from_pos == position]
        if not piece_moves:
            self.status_message = f"{player_label(piece.player)} {piece.piece_id} 当前无合法走法。"
            return

        self.selected_position = position
        self.selected_move_index = None
        self.status_message = f"已选择 {player_label(piece.player)} {piece.piece_id}，请点击目标格或选择走法列表。"

    def _select_destination(self, position: Position) -> bool:
        for index, move in enumerate(self._current_moves()):
            if move.from_pos == self.selected_position and move.to_pos == position:
                self.selected_move_index = index
                self.status_message = f"已选择：{format_move_label(move)}"
                return True

        self.status_message = "目标格不是当前棋子的合法走法。"
        return False

    def _refresh(self) -> None:
        moves = self._current_moves()
        selected_ids = self._selected_piece_ids()
        move_labels = [format_move_label(move) for move in moves]
        legal_destinations = self._legal_destinations_for_selection(moves)
        winner = self.state.get_winner()

        self.match_mode_panel.set_current_player(player_label(self.state.current_player))
        self.match_mode_panel.set_phase(self._compute_phase_label(winner))
        self.match_mode_panel.set_selected_pieces(selected_ids)
        self.match_mode_panel.set_recommendation(self._recommendation_text(winner))
        self.match_mode_panel.set_record_dirty(self._record_dirty)
        self.match_mode_panel.set_can_undo(bool(self.state.history))

        self.controls.set_dice(self.current_dice)
        self.controls.set_moves(move_labels, self.selected_move_index)
        self.controls.set_winner(player_label(winner) if winner is not None else "未结束")
        self.controls.set_status(self.status_message)
        self.controls.set_can_apply(winner is None and self.selected_move_index is not None)
        self.controls.set_can_undo(bool(self.state.history))
        self.timer_panel.set_snapshot(self.timer.snapshot())
        self.board.set_state(
            self.state,
            selected=self.selected_position,
            legal_destinations=legal_destinations,
        )

    def _current_moves(self) -> list[Move]:
        if self.state.get_winner() is not None:
            return []
        return self.state.legal_moves(self.state.current_player, self.current_dice)

    def _selected_piece_ids(self) -> list[int]:
        if self.state.get_winner() is not None:
            return []
        return self.state.legal_piece_ids(self.state.current_player, self.current_dice)

    def _legal_destinations_for_selection(self, moves: list[Move]) -> list[Position]:
        if self.selected_position is None:
            return []
        return [move.to_pos for move in moves if move.from_pos == self.selected_position]

    def _clear_selection(self) -> None:
        self.selected_move_index = None
        self.selected_position = None

    def _compute_phase_label(self, winner: Player | None) -> str:
        if winner is not None:
            return "对局已结束"
        if self._mode == "match" and self._our_side is not None and self.state.current_player is not self._our_side:
            if self._awaiting_dice:
                return "等待对方录入：请输入对方骰子"
            return "等待对方录入：请点选对方走法"
        if self._awaiting_dice:
            return "请录入骰子"
        return "请选择走法"

    def _recommendation_text(self, winner: Player | None) -> str:
        if winner is not None:
            return "对局已结束"
        if self._awaiting_dice:
            return "等待骰子"

        ai = build_ai("greedy_risk", seed=0)
        move = ai.choose_move(self.state, self.current_dice)
        if move is None:
            return "当前骰子无合法走法"
        return f"greedy_risk：{format_move_label(move)}"

    def _move_source(self, mover: Player) -> Literal["self", "opponent", "unknown"]:
        if self._mode != "match" or self._our_side is None:
            return "unknown"
        return "self" if mover is self._our_side else "opponent"

    def _set_mode(self, mode: Literal["debug", "match"], *, our_side: Player | None = None) -> None:
        if mode == "match" and our_side is None:
            raise ValueError("match mode requires our_side")
        self._mode = mode
        self._our_side = our_side if mode == "match" else None
        self._refresh()

    def _build_menu(self, master: tk.Misc) -> None:
        if not isinstance(master, (tk.Tk, tk.Toplevel)):
            return
        menubar = tk.Menu(master)
        master.config(menu=menubar)

        mode_menu = tk.Menu(menubar, tearoff=0)
        mode_menu.add_command(label="调试模式", command=lambda: self._set_mode("debug"))
        mode_menu.add_command(label="比赛模式", command=self._enter_match_mode)
        menubar.add_cascade(label="模式", menu=mode_menu)

    def _enter_match_mode(self) -> None:
        chosen = self._show_pick_side_dialog()
        if chosen is None:
            return
        self._set_mode("match", our_side=chosen)

    def _show_pick_side_dialog(self) -> Player | None:
        dialog = tk.Toplevel(self)
        dialog.title("选择我方颜色")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result: dict[str, Player | None] = {"side": None}

        tk.Label(dialog, text="你方使用：", padx=20, pady=10).pack()
        button_row = tk.Frame(dialog)
        button_row.pack(padx=20, pady=(0, 16))

        def choose(player: Player) -> None:
            result["side"] = player
            dialog.destroy()

        tk.Button(button_row, text="红方", width=10, command=lambda: choose(Player.RED)).pack(side=tk.LEFT, padx=4)
        tk.Button(button_row, text="蓝方", width=10, command=lambda: choose(Player.BLUE)).pack(side=tk.LEFT, padx=4)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        return result["side"]

    def _remaining_seconds_from_record(self, record: GameRecord) -> dict[Player, float] | None:
        if not record.steps:
            return None

        remaining_seconds = record.steps[-1].remaining_seconds
        if Player.RED not in remaining_seconds or Player.BLUE not in remaining_seconds:
            return None
        return remaining_seconds

    def _schedule_timer_refresh(self) -> None:
        self._timer_after_id = self.after(500, self._refresh_timer)

    def _refresh_timer(self) -> None:
        if not self.winfo_exists():
            return
        self.timer_panel.set_snapshot(self.timer.snapshot())
        self._schedule_timer_refresh()

    def destroy(self) -> None:
        if self._timer_after_id is not None:
            try:
                self.after_cancel(self._timer_after_id)
            except tk.TclError:
                pass
            self._timer_after_id = None
        super().destroy()
