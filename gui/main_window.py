from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Literal

from ai.match import build_ai
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from gui.app import create_default_state, format_move_label, player_label
from gui.board_widget import BoardWidget
from gui.control_panel import ControlPanel
from gui.match_mode import MatchModePanel
from gui.opening_panel import OpeningPanel, OpeningSelection
from gui.timer_panel import DEFAULT_TOTAL_SECONDS, MatchTimer, TimerPanel
from record.auto_save import (
    AUTO_SAVE_MATCH_PATH,
    AUTO_SAVE_PATH,
    auto_save,
    auto_save_match,
    clear_auto_save,
    clear_auto_save_match,
    has_auto_save,
    has_auto_save_match,
    load_auto_save,
    load_auto_save_match,
)
from record.game_record import GameRecord
from record.match_record import MatchRecord, MatchRole


DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[1] / "records"
DEFAULT_RECOMMENDER_KIND = "rollout"
DEFAULT_RECOMMENDER_KWARGS = {
    "rollouts_per_move": 16,
    "max_rollout_turns": 80,
    "max_step_time_ms": 500.0,
    "epsilon": 0.15,
}


class MainWindow(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        total_seconds: float = DEFAULT_TOTAL_SECONDS,
        auto_save_path: str | Path | None = None,
        auto_save_match_path: str | Path | None = None,
    ) -> None:
        super().__init__(master, padx=16, pady=16)
        self._build_menu(master)
        self._total_seconds = float(total_seconds)
        self._auto_save_path = Path(auto_save_path) if auto_save_path is not None else AUTO_SAVE_PATH
        self._auto_save_match_path = (
            Path(auto_save_match_path) if auto_save_match_path is not None else AUTO_SAVE_MATCH_PATH
        )
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
        self._phase: Literal["setup", "playing"] = "setup"
        self._mode: Literal["debug", "match"] = "debug"
        self._our_side: Player | None = None
        self._match: MatchRecord | None = None
        self._match_finished_notified = False
        # R-2 review Critical #5：AI 在 __init__ 一次构造、复用，避免每次 _refresh 都新建。
        self._recommender = build_ai(DEFAULT_RECOMMENDER_KIND, seed=0, **DEFAULT_RECOMMENDER_KWARGS)
        self._recommendation_cache_key: tuple[int, str] | None = None
        self._recommendation_cache_move: Move | None = None

        self.board = BoardWidget(self, self._handle_square_click)
        self.board.pack(side=tk.LEFT, padx=(0, 16), pady=0)

        side_panel = tk.Frame(self)
        side_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.timer_panel = TimerPanel(side_panel, on_toggle_pause=self._toggle_timer_pause)
        self.timer_panel.pack(fill=tk.X, pady=(0, 8))

        self.match_mode_panel = MatchModePanel(side_panel)
        self.match_mode_panel.pack(fill=tk.X, pady=(0, 8))

        self.opening_panel = OpeningPanel(
            side_panel,
            on_confirm=self._start_game_from_opening,
            on_layout_change=self._refresh_setup_board,
        )
        self.opening_panel.pack(fill=tk.BOTH, expand=True)

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

        restored = self._restore_auto_save_if_available()
        if not restored:
            self._phase = "setup"
            self._show_setup_phase()
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
        if winner is not None and self._match is not None and not self._match.is_finished():
            reason = self._determine_winner_reason(winner)
            self._finalize_match_game(winner, reason=reason)
            return
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
        self._phase = "setup"
        self._mode = "debug"
        self._our_side = None
        self._match = None
        self._match_finished_notified = False
        self.opening_panel.reset()
        self.opening_panel.set_side_controls_enabled(True)
        self.status_message = "棋局已重置，请重新录入开局。"
        self._clear_auto_save()
        clear_auto_save_match(path=self._auto_save_match_path)
        self._show_setup_phase()
        self._refresh()

    def _start_game_from_opening(self, selection: OpeningSelection) -> None:
        if self._match is not None:
            initial_player = self._match.first_mover_color(self._match.current_game_index)
        else:
            initial_player = Player.RED

        self.state = GameState.from_layout(
            red=selection.red_layout,
            blue=selection.blue_layout,
            current_player=initial_player,
        )
        self.record = GameRecord.from_state(self.state)
        record_meta = dict(selection.metadata())
        if self._match is not None:
            record_meta.update(
                {
                    "match_id": self._match.match_id,
                    "game_index": self._match.current_game_index,
                    "our_role": self._match.our_role,
                    "first_mover_color": initial_player.value,
                }
            )
        self.record.metadata.update(record_meta)
        self.timer.reset(current_player=initial_player)
        self.current_dice = 6
        self._clear_selection()
        self._record_dirty = False
        self._awaiting_dice = True
        self._phase = "playing"
        if self._match is not None:
            self._match.start_playing()
            auto_save_match(self._match, path=self._auto_save_match_path)
        else:
            # 没有 MatchRecord：legacy 单盘 match 模式（沿用 R-1 行为）
            self._mode = "match"
            self._our_side = selection.our_side
        self.status_message = "开局已确认，请录入第一轮骰子。"
        self._show_playing_phase()
        self._refresh()

    def _show_setup_phase(self) -> None:
        self.timer_panel.pack_forget()
        self.match_mode_panel.pack_forget()
        self.controls.pack_forget()
        if not self.opening_panel.winfo_manager():
            self.opening_panel.pack(fill=tk.BOTH, expand=True)

    def _show_playing_phase(self) -> None:
        self.opening_panel.pack_forget()
        if not self.timer_panel.winfo_manager():
            self.timer_panel.pack(fill=tk.X, pady=(0, 8))
        if not self.match_mode_panel.winfo_manager():
            self.match_mode_panel.pack(fill=tk.X, pady=(0, 8))
        if not self.controls.winfo_manager():
            self.controls.pack(fill=tk.BOTH, expand=True)

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

    def _restore_auto_save_if_available(self) -> bool:
        has_game = has_auto_save(path=self._auto_save_path)
        has_match = has_auto_save_match(path=self._auto_save_match_path)
        if not has_game and not has_match:
            return False

        should_restore = messagebox.askyesno(
            "恢复未完成对局",
            "检测到上次未完成的自动保存对局，是否恢复？",
            parent=self,
        )
        if not should_restore:
            self._clear_auto_save()
            clear_auto_save_match(path=self._auto_save_match_path)
            return False

        if has_match:
            return self._restore_match_auto_save(has_game=has_game)
        return self._restore_single_game_auto_save()

    def _restore_match_auto_save(self, *, has_game: bool) -> bool:
        try:
            match = load_auto_save_match(path=self._auto_save_match_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("恢复 match auto-save 失败", str(exc), parent=self)
            clear_auto_save_match(path=self._auto_save_match_path)
            self._clear_auto_save()
            return False

        self._match = match
        self._mode = "match"
        self._our_side = match.our_side
        self.opening_panel.set_side_controls_enabled(False)

        if match.phase == "finished":
            # R-2 review Important #12：先弹窗告知比分，待用户确认后再清盘。
            messagebox.showinfo(
                "上轮已结束",
                (
                    f"上一轮已结束。最终比分：我方 {match.games_won_us} — 对方 {match.games_won_them}。\n"
                    f"点击确定后将清理 auto-save，请通过'重置棋局'开始新一轮。"
                ),
                parent=self,
            )
            self._exit_match_mode()
            return False

        if match.phase == "playing" and has_game:
            try:
                loaded_record, timer_metadata = load_auto_save(path=self._auto_save_path)
                loaded_state = loaded_record.restore_state()
                timer_current_player = Player.from_value(timer_metadata["timer_current_player"])
                timer_remaining = self._remaining_seconds_from_auto_save_metadata(timer_metadata)
            except (OSError, ValueError, KeyError) as exc:
                messagebox.showerror("恢复单盘 auto-save 失败", str(exc), parent=self)
                self._clear_auto_save()
                # 退到 setup 阶段，让用户重新录入当前盘
                self._start_new_game_in_match()
                return True
            # R-2 review Important #13：若单盘恢复后发现该局已结束（finalize 后未及时清盘
            # 中间崩溃），不要继续以"未结束"状态展示，提示并丢弃单盘 auto-save。
            if loaded_state.get_winner() is not None:
                messagebox.showinfo(
                    "本盘已结束",
                    "检测到上次本盘已分出胜负但未清理自动保存。将清理后等待下一盘开局。",
                    parent=self,
                )
                self._clear_auto_save()
                self._start_new_game_in_match()
                return True
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
            self._phase = "playing"
            self._show_playing_phase()
            self.status_message = (
                f"已恢复第 {match.current_game_index} 盘（比分 "
                f"{match.games_won_us}:{match.games_won_them}）。"
            )
            return True

        # match.phase == "setup" 或 playing 但无单盘 auto-save
        if match.phase == "playing" and not has_game:
            # R-2 review Important #15：盘内进度缺失，不要静默丢失整轮记录。
            should_continue = messagebox.askyesno(
                "本盘进度缺失",
                (
                    f"检测到整轮记录处于第 {match.current_game_index} 盘进行中，"
                    f"但本盘的对局自动保存缺失。\n"
                    f"点'是'按当前盘开局重新录入（保留已完成盘数和比分），"
                    f"点'否'放弃整轮恢复。"
                ),
                parent=self,
            )
            if not should_continue:
                self._exit_match_mode()
                return False
        self.status_message = (
            f"已恢复整轮记录（比分 {match.games_won_us}:{match.games_won_them}），"
            f"请录入第 {match.current_game_index} 盘开局。"
        )
        if has_game:
            # R-1/R-2/R-3 二审 #3：到这里说明 match.phase == "setup"（或 playing+用户接受继续）
            # 仍同时残留单盘 auto-save，多半是 finalize 后崩在 _clear_auto_save 之前。
            # 残留的单盘记录已被整轮 games[] 收录，与即将开始的新一盘无关——丢弃，避免反复弹"是否恢复"。
            self._clear_auto_save()
        self._start_new_game_in_match()
        return True

    def _restore_single_game_auto_save(self) -> bool:
        try:
            loaded_record, timer_metadata = load_auto_save(path=self._auto_save_path)
            loaded_state = loaded_record.restore_state()
            timer_current_player = Player.from_value(timer_metadata["timer_current_player"])
            timer_remaining = self._remaining_seconds_from_auto_save_metadata(timer_metadata)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("恢复自动保存失败", str(exc), parent=self)
            self._clear_auto_save()
            return False

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
        self._phase = "playing"
        self._show_playing_phase()
        self._restore_mode_from_record_metadata()
        self.status_message = "已恢复上次未完成对局，请录入下一轮骰子。"
        return True

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
        # R-2 review Important #17：比赛进行中加载棋谱会产生混合状态，必须先确认并清掉 match。
        if self._match is not None and not self._match.is_finished():
            confirm = messagebox.askyesno(
                "比赛进行中",
                "当前正在比赛模式，加载棋谱将终止本轮比赛并丢弃整轮记录。是否继续？",
                parent=self,
            )
            if not confirm:
                return
            self._exit_match_mode()

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
        self._phase = "playing"
        self._restore_mode_from_record_metadata()
        self._show_playing_phase()
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

    def _refresh_setup_board(self) -> None:
        if not hasattr(self, "opening_panel"):
            return
        self.board.set_edit_mode(
            True,
            zone_cells=self.opening_panel.current_edit_zone(),
            on_cell_click=self.opening_panel.handle_board_click,
        )
        self.board.set_state(self.opening_panel.preview_state())

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
        if self._match is not None:
            first_mover_label = (
                "我方"
                if self._match.first_mover(self._match.current_game_index) == "us"
                else "对方"
            )
            self.match_mode_panel.set_match_status(
                game_index=self._match.current_game_index,
                total_games=self._match.total_games,
                games_won_us=self._match.games_won_us,
                games_won_them=self._match.games_won_them,
                first_mover_label=first_mover_label,
                our_role=self._match.our_role,
            )
        else:
            self.match_mode_panel.hide_match_status()

        self.controls.set_dice(self.current_dice)
        self.controls.set_moves(move_labels, self.selected_move_index)
        self.controls.set_winner(player_label(winner) if winner is not None else "未结束")
        self.controls.set_status(self.status_message)
        self.controls.set_can_apply(winner is None and self.selected_move_index is not None)
        self.controls.set_can_undo(bool(self.state.history))
        self.timer_panel.set_snapshot(self.timer.snapshot())
        if self._phase == "setup":
            self._refresh_setup_board()
        else:
            preview_move: Move | None = None
            if (
                self.selected_move_index is not None
                and 0 <= self.selected_move_index < len(moves)
            ):
                preview_move = moves[self.selected_move_index]
            self.board.set_edit_mode(False)
            self.board.set_state(
                self.state,
                selected=self.selected_position,
                legal_destinations=legal_destinations,
                preview_move=preview_move,
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

        move = self._recommended_move()
        if move is None:
            return "当前骰子无合法走法"
        return f"{DEFAULT_RECOMMENDER_KIND}：{format_move_label(move)}"

    def _recommended_move(self) -> Move | None:
        key = self._recommendation_key()
        if self._recommendation_cache_key != key:
            self._recommendation_cache_key = key
            self._recommendation_cache_move = self._recommender.choose_move(self.state, self.current_dice)
        return self._recommendation_cache_move

    def _recommendation_key(self) -> tuple[int, str]:
        return (
            self.current_dice,
            repr(self.state.serialize(include_history=False)),
        )

    def _move_source(self, mover: Player) -> Literal["self", "opponent", "unknown"]:
        if self._mode != "match" or self._our_side is None:
            return "unknown"
        return "self" if mover is self._our_side else "opponent"

    def _restore_mode_from_record_metadata(self) -> None:
        our_side = self.record.metadata.get("our_side")
        if isinstance(our_side, str):
            try:
                self._mode = "match"
                self._our_side = Player.from_value(our_side)
                return
            except ValueError:
                pass
        self._mode = "debug"
        self._our_side = None

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
        if self._match is not None and not self._match.is_finished():
            confirm = messagebox.askyesno(
                "正在比赛模式",
                "当前已处于比赛模式，是否结束当前轮次并重新开始？",
                parent=self,
            )
            if not confirm:
                return
        chosen = self._show_match_setup_dialog()
        if chosen is None:
            return
        our_side, our_role = chosen
        # R-2 review Important #18：进入新一轮前清掉可能残留的旧 auto-save（单盘 + 整轮）。
        self._clear_auto_save()
        clear_auto_save_match(path=self._auto_save_match_path)
        self._match = MatchRecord(our_side=our_side, our_role=our_role)
        self._mode = "match"
        self._our_side = our_side
        self.opening_panel.set_side_controls_enabled(False)
        self._record_dirty = False
        self._match_finished_notified = False
        self._start_new_game_in_match()
        auto_save_match(self._match, path=self._auto_save_match_path)

    def _exit_match_mode(self) -> None:
        """R-2 review Important #12/#17：集中清理 match 状态。

        清掉 self._match / self._our_side / 两个 auto-save 文件，回到 debug 模式。
        在 finished 弹窗确认后、_load_record 终止比赛、`_restore_match_auto_save` 用户放弃恢复
        等场景统一调用。
        """
        self._match = None
        self._mode = "debug"
        self._our_side = None
        self._match_finished_notified = False
        clear_auto_save_match(path=self._auto_save_match_path)
        self._clear_auto_save()
        self.opening_panel.set_side_controls_enabled(True)

    def _show_match_setup_dialog(self) -> tuple[Player, MatchRole] | None:
        dialog = tk.Toplevel(self)
        dialog.title("进入比赛模式")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        side_var = tk.StringVar(value=Player.RED.value)
        role_var = tk.StringVar(value="甲")
        result: dict[str, object] = {"chosen": None}

        tk.Label(dialog, text="我方颜色：", padx=20, anchor="w").pack(fill=tk.X, pady=(16, 4))
        side_row = tk.Frame(dialog)
        side_row.pack(fill=tk.X, padx=20)
        tk.Radiobutton(side_row, text="红方", value=Player.RED.value, variable=side_var).pack(side=tk.LEFT)
        tk.Radiobutton(side_row, text="蓝方", value=Player.BLUE.value, variable=side_var).pack(side=tk.LEFT)

        tk.Label(dialog, text="我方角色：", padx=20, anchor="w").pack(fill=tk.X, pady=(12, 4))
        role_row = tk.Frame(dialog)
        role_row.pack(fill=tk.X, padx=20)
        tk.Radiobutton(role_row, text="甲方（1/4/5 盘先手）", value="甲", variable=role_var).pack(anchor="w")
        tk.Radiobutton(role_row, text="乙方（2/3/6/7 盘先手）", value="乙", variable=role_var).pack(anchor="w")

        button_row = tk.Frame(dialog)
        button_row.pack(padx=20, pady=(16, 16))

        def confirm() -> None:
            result["chosen"] = (Player.from_value(side_var.get()), role_var.get())
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        tk.Button(button_row, text="确认", width=10, command=confirm).pack(side=tk.LEFT, padx=4)
        tk.Button(button_row, text="取消", width=10, command=cancel).pack(side=tk.LEFT, padx=4)

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        chosen = result["chosen"]
        if chosen is None:
            return None
        return chosen  # type: ignore[return-value]

    # 旧 API 保留：仅返回颜色，给 _set_mode("match", our_side=...) 这条 legacy 路径使用
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

    def _start_new_game_in_match(self) -> None:
        if self._match is None:
            return
        keep = self._match.last_game_winner == "us"
        self.opening_panel.reset_for_match_game(
            our_side=self._match.our_side,
            keep_our_layout=keep,
        )
        self.opening_panel.set_side_controls_enabled(False)
        self.timer.pause()
        self.current_dice = 6
        self._clear_selection()
        self._awaiting_dice = True
        self._phase = "setup"
        self._match.phase = "setup"
        score = f"{self._match.games_won_us}:{self._match.games_won_them}"
        first_mover = "我方" if self._match.first_mover(self._match.current_game_index) == "us" else "对方"
        self.status_message = (
            f"本轮第 {self._match.current_game_index} 盘 / 比分 {score}，"
            f"本盘 {first_mover} 先手，请录入本盘开局后开始。"
        )
        self._show_setup_phase()
        auto_save_match(self._match, path=self._auto_save_match_path)
        self._refresh()

    def _finalize_match_game(self, winner: Player, *, reason: str) -> None:
        if self._match is None or self._match.is_finished():
            return
        outcome = "us" if winner is self._match.our_side else "them"
        self.record.result = {
            "winner": winner.value,
            "winner_side": outcome,
            "reason": reason,
            "game_index": self._match.current_game_index,
        }
        self._match.append_finished_game(self.record, outcome)
        # R-2 review Important #13：先持久化 match auto-save（包含已结束盘），再清单盘 auto-save。
        # 中间崩溃时 match 已是 setup 含本盘成绩；下次启动会看到 has_game=True 但 state 已结束，
        # _restore_match_auto_save 里有专门的守卫会清掉它。
        auto_save_match(self._match, path=self._auto_save_match_path)
        self._clear_auto_save()
        self._refresh()
        if self._match.is_finished():
            self._show_match_finished_dialog()
        else:
            self._show_round_finished_dialog()

    def _show_round_finished_dialog(self) -> None:
        if self._match is None:
            return
        last_winner = "我方" if self._match.last_game_winner == "us" else "对方"
        messagebox.showinfo(
            "本盘结束",
            (
                f"本盘 {last_winner} 胜。\n"
                f"比分：我方 {self._match.games_won_us} — 对方 {self._match.games_won_them}\n"
                f"下一盘第 {self._match.current_game_index} 盘，请确认开局后开始。"
            ),
            parent=self,
        )
        self._start_new_game_in_match()

    def _show_match_finished_dialog(self) -> None:
        if self._match is None or self._match_finished_notified:
            return
        self._match_finished_notified = True
        winner_label = "我方" if self._match.winner() == "us" else "对方"
        messagebox.showinfo(
            "本轮结束",
            (
                f"本轮结束！{winner_label} 胜出。\n"
                f"最终比分：我方 {self._match.games_won_us} — 对方 {self._match.games_won_them}\n"
                f"可保存棋谱后通过菜单退出比赛模式。"
            ),
            parent=self,
        )

    def _determine_winner_reason(self, winner: Player) -> str:
        from core.rules import target_corner as _target_corner

        opponent = winner.opponent
        if any(
            piece.alive and piece.position == _target_corner(winner)
            for piece in self.state.pieces[winner].values()
        ):
            return "target_corner"
        if not any(piece.alive for piece in self.state.pieces[opponent].values()):
            return "capture_all"
        return "unknown"

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
        snapshot = self.timer.snapshot()
        self.timer_panel.set_snapshot(snapshot)
        if (
            self._phase == "playing"
            and self.state.get_winner() is None
            and snapshot.timeout_players
            and self._match is not None
            and not self._match.is_finished()
        ):
            timed_out = snapshot.timeout_players[0]
            self._handle_timeout(timed_out)
            return
        self._schedule_timer_refresh()

    def _handle_timeout(self, timed_out: Player) -> None:
        winner = timed_out.opponent
        self.timer.pause()
        # R-2 review Important #16：state.get_winner() 仍为 None（core 不识超时），
        # GUI 用 status + match panel 文案显式标注超时判负，避免棋盘"未结束"误导。
        self.status_message = (
            f"{player_label(timed_out)} 超时判负，{player_label(winner)} 获胜。"
        )
        if self._match is not None and not self._match.is_finished():
            self.match_mode_panel.set_phase(
                f"超时判负：{player_label(winner)} 胜"
            )
            self._finalize_match_game(winner, reason="timeout")
            # R-1/R-2/R-3 二审 #1：finalize 整链路（含 round-finished 弹窗和 _start_new_game_in_match）
            # 都没有重排定时器刷新；不补这一行，本盘超时后 500ms 周期刷新永久死掉，
            # 下一盘计时面板不再自动更新，也无法再检测超时。
            self._schedule_timer_refresh()
        else:
            self._refresh()
            self._schedule_timer_refresh()

    def destroy(self) -> None:
        if self._timer_after_id is not None:
            try:
                self.after_cancel(self._timer_after_id)
            except tk.TclError:
                pass
            self._timer_after_id = None
        super().destroy()
