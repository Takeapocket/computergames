from __future__ import annotations

import tkinter as tk

from core.move import Move
from core.types import Player, Position
from gui.app import create_default_state, format_move_label, player_label
from gui.board_widget import BoardWidget
from gui.control_panel import ControlPanel


class MainWindow(tk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padx=16, pady=16)
        self.state = create_default_state()
        self.current_dice = 6
        self.selected_move_index: int | None = None
        self.selected_position: Position | None = None
        self.status_message = "请输入骰子并选择合法走法。"

        self.board = BoardWidget(self, self._handle_square_click)
        self.board.pack(side=tk.LEFT, padx=(0, 16), pady=0)

        self.controls = ControlPanel(
            self,
            on_dice_change=self._handle_dice_change,
            on_move_select=self._handle_move_select,
            on_apply=self._apply_selected_move,
            on_undo=self._undo_move,
            on_reset=self._reset_game,
        )
        self.controls.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._refresh()

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
        self._clear_selection()

        winner = self.state.get_winner()
        if winner is not None:
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
            self.status_message = f"已悔棋：{format_move_label(undone)}"
        self._refresh()

    def _reset_game(self) -> None:
        self.state = create_default_state()
        self.current_dice = 6
        self._clear_selection()
        self.status_message = "棋局已重置为临时三角布局。"
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
