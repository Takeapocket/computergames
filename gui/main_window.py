from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from core.move import Move
from core.types import Player, Position
from gui.app import create_default_state, format_move_label, player_label
from gui.board_widget import BoardWidget
from gui.control_panel import ControlPanel
from gui.timer_panel import MatchTimer, TimerPanel
from record.game_record import GameRecord


DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[1] / "records"


class MainWindow(tk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padx=16, pady=16)
        self.state = create_default_state()
        self.record = GameRecord.from_state(self.state)
        self.timer = MatchTimer(current_player=self.state.current_player)
        self._timer_after_id: str | None = None
        self.current_dice = 6
        self.selected_move_index: int | None = None
        self.selected_position: Position | None = None
        self.status_message = "请输入骰子并选择合法走法。"

        self.board = BoardWidget(self, self._handle_square_click)
        self.board.pack(side=tk.LEFT, padx=(0, 16), pady=0)

        side_panel = tk.Frame(self)
        side_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.timer_panel = TimerPanel(side_panel, on_toggle_pause=self._toggle_timer_pause)
        self.timer_panel.pack(fill=tk.X, pady=(0, 8))

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
        )
        self._clear_selection()

        winner = self.state.get_winner()
        if winner is not None:
            self.timer.pause()
            self.status_message = f"已执行：{format_move_label(move)}。{player_label(winner)}获胜。"
        else:
            self.status_message = f"已执行：{format_move_label(move)}。请录入下一轮骰子。"
        self._refresh()

    def _undo_move(self) -> None:
        undone = self.state.undo_move()
        self._clear_selection()
        if undone is None:
            self.status_message = "当前没有可悔棋的走法。"
        else:
            self.record.undo_last()
            self.timer.set_active_player(self.state.current_player)
            self.status_message = f"已悔棋：{format_move_label(undone)}。计时不回退。"
        self._refresh()

    def _reset_game(self) -> None:
        self.state = create_default_state()
        self.record = GameRecord.from_state(self.state)
        self.timer.reset(current_player=self.state.current_player)
        self.current_dice = 6
        self._clear_selection()
        self.status_message = "棋局已重置为临时三角布局。"
        self._refresh()

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

        self.controls.set_current_player(player_label(self.state.current_player))
        self.controls.set_dice(self.current_dice)
        self.controls.set_selected_pieces(selected_ids)
        self.controls.set_moves(move_labels, self.selected_move_index)
        self.controls.set_winner(player_label(winner) if winner is not None else "未结束")
        self.controls.set_status(self.status_message)
        self.controls.set_can_apply(winner is None and self.selected_move_index is not None)
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
        self.timer_panel.set_snapshot(self.timer.snapshot())
        self._schedule_timer_refresh()
