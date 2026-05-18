from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Literal

from ai.match import build_ai
from core.dice import roll_die
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from gui.app import create_default_state, format_move_label, player_label
from gui.board_widget import BoardWidget
from gui.control_panel import ControlPanel
from gui.match_mode import MatchModePanel
from gui.opening_panel import OpeningPanel, OpeningSelection
from gui.time_limit import validate_nonnegative_seconds, validate_total_seconds
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
    is_invalid_auto_save_file,
    is_invalid_match_auto_save_file,
    load_auto_save,
    load_auto_save_match,
)
from record.game_record import GameRecord
from record.match_record import MatchRecord, MatchRole


DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[1] / "records"
DEFAULT_RECOMMENDER_KIND = "rollout"
DEFAULT_RECOMMENDER_KWARGS = {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0,
}


def _format_rollout_diagnostic(diagnostic: object) -> str:
    move = getattr(diagnostic, "move")
    visits = int(getattr(diagnostic, "visits"))
    score = float(getattr(diagnostic, "score", getattr(diagnostic, "winrate")))
    winrate = float(getattr(diagnostic, "winrate", score))
    wins = float(getattr(diagnostic, "wins", winrate * visits))
    draws = float(getattr(diagnostic, "draws", getattr(diagnostic, "cutoffs", 0.0)))
    losses = float(getattr(diagnostic, "losses", max(0.0, visits - wins - draws)))
    avg = float(getattr(diagnostic, "avg", 2 * score - 1))
    confidence = ", 置信=低" if getattr(diagnostic, "low_confidence", False) else ""
    return (
        f"{format_move_label(move, distinguish_self_capture=True)}\n"
        f"visits={visits}, score={score:.2f}, winrate={winrate:.2f}, "
        f"wins={wins:.0f}, losses={losses:.0f}, draws={draws:.0f}, avg={avg:.2f}"
        f"{confidence}"
    )


class MainWindow(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        total_seconds: float = DEFAULT_TOTAL_SECONDS,
        auto_timeout_enabled: bool = False,
        auto_save_path: str | Path | None = None,
        auto_save_match_path: str | Path | None = None,
    ) -> None:
        validated_total_seconds = validate_total_seconds(total_seconds)
        super().__init__(master, padx=16, pady=16)
        self._build_menu(master)
        self._total_seconds = validated_total_seconds
        self._auto_timeout_enabled = bool(auto_timeout_enabled)
        self._timeout_notice_players: tuple[Player, ...] = ()
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
        self._fallback_recommender = build_ai("greedy_risk", seed=0)
        self._recommendation_cache_key: tuple[int, str] | None = None
        self._recommendation_cache_move: Move | None = None
        self._recommendation_cache_source: Literal["rollout", "greedy_risk", "rules", "none"] = "none"

        self.board = BoardWidget(self, self._handle_square_click)
        self.board.pack(side=tk.LEFT, padx=(0, 16), pady=0)

        side_panel = tk.Frame(self)
        side_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.timer_panel = TimerPanel(
            side_panel,
            on_toggle_pause=self._toggle_timer_pause,
            on_confirm_timeout_forfeit=self._confirm_timeout_forfeit,
        )
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
            on_roll_dice=self._roll_dice_from_gui,
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
        if self._match_is_finished():
            self.status_message = "本轮已结束，不能继续录入骰子。"
            self._clear_selection()
            self._refresh()
            return
        if self._phase != "playing":
            self.status_message = "请先确认开局后再录入骰子。"
            self._clear_selection()
            self._refresh()
            return
        if self.state.get_winner() is not None:
            self.status_message = "对局已结束，不能继续录入骰子。"
            self._clear_selection()
            self._refresh()
            return

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

    def _roll_dice_from_gui(self) -> None:
        if self._match_is_finished():
            self.status_message = "本轮已结束，不能掷骰。"
            self._clear_selection()
            self._refresh()
            return
        if self._phase != "playing":
            self.status_message = "请先确认开局，再掷骰。"
            self._clear_selection()
            self._refresh()
            return
        if self.state.get_winner() is not None:
            self.status_message = "对局已结束，不能掷骰。"
            self._clear_selection()
            self._refresh()
            return
        if not self._awaiting_dice:
            self.status_message = "本轮骰子已录入；如需改错，请手动修改骰子框。"
            self._refresh()
            return

        dice = roll_die()
        self.current_dice = dice
        self._awaiting_dice = False
        self._clear_selection()
        self.status_message = f"程序掷骰：{dice}。请双方确认后选择合法走法。"
        self._refresh()

    def _handle_move_select(self, index: int) -> None:
        if not self._can_select_moves():
            self.status_message = self._blocked_move_message()
            self._clear_selection()
            self._refresh()
            return

        moves = self._current_moves()
        if not 0 <= index < len(moves):
            return

        self.selected_move_index = index
        self.selected_position = moves[index].from_pos
        self.status_message = f"已选择：{format_move_label(moves[index], distinguish_self_capture=True)}"
        self._refresh()

    def _handle_square_click(self, position: Position) -> None:
        if self.state.get_winner() is not None:
            self.status_message = "对局已结束；可以悔棋或重置。"
            self._refresh()
            return
        if not self._can_select_moves():
            self.status_message = self._blocked_move_message()
            self._clear_selection()
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
        if not self._can_select_moves():
            self.status_message = self._blocked_move_message()
            self._clear_selection()
            self._refresh()
            return

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
            self.status_message = (
                f"已执行：{format_move_label(move, distinguish_self_capture=True)}。"
                f"{player_label(winner)}获胜。"
            )
        else:
            self.status_message = (
                f"已执行：{format_move_label(move, distinguish_self_capture=True)}。"
                "请录入下一轮骰子。"
            )
        self._auto_save_current_game()
        if winner is not None and self._match is not None and not self._match.is_finished():
            reason = self._determine_winner_reason(winner)
            self._finalize_match_game(winner, reason=reason)
            return
        self._refresh()

    def _undo_move(self) -> None:
        if not self._can_undo_move():
            if self._match_is_finished():
                self.status_message = "本轮已结束，不能悔棋。"
            elif self._phase != "playing":
                self.status_message = "当前不在对局中，不能悔棋。"
            else:
                self.status_message = "当前没有可悔棋的走法。"
            self._clear_selection()
            self._refresh()
            return

        undone = self.state.undo_move()
        self._clear_selection()
        if undone is None:
            self.status_message = "当前没有可悔棋的走法。"
        else:
            self.record.undo_last()
            self.timer.set_active_player(self.state.current_player)
            self._record_dirty = True
            self._awaiting_dice = True
            self.status_message = (
                f"已悔棋：{format_move_label(undone, distinguish_self_capture=True)}。"
                "计时不回退。"
            )
            self._auto_save_current_game()
        self._refresh()

    def _reset_game(self) -> None:
        if not self._confirm_reset_game():
            return

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
        self._auto_timeout_enabled = False
        self._timeout_notice_players = ()
        self.opening_panel.reset()
        self.opening_panel.set_side_controls_enabled(True)
        self.status_message = "棋局已重置，请重新录入开局。"
        self._clear_auto_save()
        self._clear_match_auto_save()
        self._show_setup_phase()
        self._refresh()

    def _confirm_reset_game(self) -> bool:
        active_match = self._match is not None and not self._match.is_finished()
        if not active_match and not self._record_dirty:
            return True

        if active_match:
            message = (
                "当前正在比赛模式。重置棋局将放弃本轮比赛和当前记录，"
                "并清理本轮自动保存。是否继续？"
            )
        else:
            message = "当前记录尚未保存。重置棋局将放弃当前记录。是否继续？"
        return messagebox.askyesno("确认重置棋局", message, parent=self)

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
        record_meta.update(
            {
                "time_limit_seconds": self._total_seconds,
                "auto_timeout_enabled": self._auto_timeout_enabled,
            }
        )
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
        self._timeout_notice_players = ()
        self._record_dirty = False
        self._awaiting_dice = True
        self._phase = "playing"
        if self._match is not None:
            self._match.start_playing()
            self._auto_save_current_match()
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
            self.record.metadata["time_limit_seconds"] = self._total_seconds
            self.record.metadata["auto_timeout_enabled"] = self._auto_timeout_enabled
            auto_save(self.record, self.timer.snapshot(), path=self._auto_save_path)
        except OSError as exc:
            self.status_message = f"自动保存失败：{exc}"

    def _clear_auto_save(self) -> None:
        try:
            clear_auto_save(path=self._auto_save_path)
        except OSError as exc:
            self.status_message = f"自动保存清理失败：{exc}"

    def _auto_save_current_match(self) -> None:
        if self._match is None:
            return
        try:
            auto_save_match(self._match, path=self._auto_save_match_path)
        except OSError as exc:
            self.status_message = f"整轮自动保存失败：{exc}"

    def _clear_match_auto_save(self) -> None:
        try:
            clear_auto_save_match(path=self._auto_save_match_path)
        except OSError as exc:
            self.status_message = f"整轮自动保存清理失败：{exc}"

    def _clear_invalid_auto_save_files(self) -> None:
        if is_invalid_auto_save_file(path=self._auto_save_path):
            self._clear_auto_save()
        if is_invalid_match_auto_save_file(path=self._auto_save_match_path):
            self._clear_match_auto_save()

    def _restore_auto_save_if_available(self) -> bool:
        self._clear_invalid_auto_save_files()
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
            self._clear_match_auto_save()
            return False

        if has_match:
            return self._restore_match_auto_save(has_game=has_game)
        return self._restore_single_game_auto_save()

    def _restore_match_auto_save(self, *, has_game: bool) -> bool:
        try:
            match = load_auto_save_match(path=self._auto_save_match_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("恢复 match auto-save 失败", str(exc), parent=self)
            self._clear_match_auto_save()
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
            self._restore_timer_options_from_record(loaded_record)
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
        self._restore_timer_options_from_record(loaded_record)
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
            Player.RED: validate_nonnegative_seconds(remaining[Player.RED.value]),
            Player.BLUE: validate_nonnegative_seconds(remaining[Player.BLUE.value]),
        }

    def _restore_timer_options_from_record(self, record: GameRecord) -> None:
        time_limit = record.metadata.get("time_limit_seconds")
        if time_limit is not None:
            try:
                self._total_seconds = validate_total_seconds(time_limit)
            except ValueError:
                pass
            else:
                self.timer.total_seconds = self._total_seconds

        auto_timeout_enabled = record.metadata.get("auto_timeout_enabled")
        if isinstance(auto_timeout_enabled, bool):
            self._auto_timeout_enabled = auto_timeout_enabled
        else:
            self._auto_timeout_enabled = False
        self._timeout_notice_players = ()

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
            remaining_seconds = self._remaining_seconds_from_record(loaded_record)
        except (OSError, ValueError) as exc:
            messagebox.showerror("加载棋谱失败", str(exc), parent=self)
            return

        # R-2 review Important #17：比赛进行中加载棋谱会产生混合状态；先确认文件有效，
        # 再让操作员确认退出 match，避免取消/损坏文件清掉当前整轮上下文。
        if self._match is not None and not self._match.is_finished():
            confirm = messagebox.askyesno(
                "比赛进行中",
                "当前正在比赛模式，加载棋谱将终止本轮比赛并丢弃整轮记录。是否继续？",
                parent=self,
            )
            if not confirm:
                return
            self._exit_match_mode()

        self.record = loaded_record
        self.state = loaded_state
        self._restore_timer_options_from_record(self.record)
        self.timer.reset(
            current_player=self.state.current_player,
            remaining_seconds=remaining_seconds,
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
                self.status_message = f"已选择：{format_move_label(move, distinguish_self_capture=True)}"
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
        legal_destinations = self._legal_destinations_for_selection(moves)
        winner = self.state.get_winner()
        can_enter_dice = self._can_enter_dice(winner)
        can_select_moves = self._can_select_moves(winner)
        recommended_move: Move | None = None
        is_opponent_turn = (
            self._mode == "match"
            and self._our_side is not None
            and self.state.current_player is not self._our_side
        )
        if can_select_moves and not is_opponent_turn:
            recommended_move = self._recommended_move()
        move_labels = []
        for move in moves:
            label = format_move_label(move, distinguish_self_capture=True)
            if recommended_move is not None and move == recommended_move:
                label = f"[AI推荐] {label}"
            move_labels.append(label)
        selected_move_valid = (
            self.selected_move_index is not None
            and 0 <= self.selected_move_index < len(moves)
        )
        can_apply = can_select_moves and selected_move_valid

        self.match_mode_panel.set_current_player(player_label(self.state.current_player))
        self.match_mode_panel.set_phase(self._compute_phase_label(winner))
        self.match_mode_panel.set_selected_pieces(selected_ids)
        self.match_mode_panel.set_recommendation(self._recommendation_text(winner))
        self.match_mode_panel.set_record_dirty(self._record_dirty)
        self.match_mode_panel.set_can_undo(self._can_undo_move(winner))
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
        self.controls.set_can_apply(can_apply)
        self.controls.set_can_undo(self._can_undo_move(winner))
        self.controls.set_dice_enabled(can_enter_dice)
        self.controls.set_can_roll_dice(can_enter_dice and self._awaiting_dice)
        self.controls.set_move_selection_enabled(can_select_moves)
        snapshot = self.timer.snapshot()
        self.timer_panel.set_snapshot(
            snapshot,
            auto_timeout_enabled=self._auto_timeout_enabled,
            timeout_adjudication_enabled=self._can_confirm_timeout_forfeit(snapshot),
        )
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
        if not self._can_select_moves():
            return []
        return self.state.legal_moves(self.state.current_player, self.current_dice)

    def _selected_piece_ids(self) -> list[int]:
        if not self._can_select_moves():
            return []
        return self.state.legal_piece_ids(self.state.current_player, self.current_dice)

    def _legal_destinations_for_selection(self, moves: list[Move]) -> list[Position]:
        if self.selected_position is None:
            return []
        return [move.to_pos for move in moves if move.from_pos == self.selected_position]

    def _clear_selection(self) -> None:
        self.selected_move_index = None
        self.selected_position = None

    def _match_is_finished(self) -> bool:
        return self._match is not None and self._match.is_finished()

    def _can_enter_dice(self, winner: Player | None = None) -> bool:
        if winner is None:
            winner = self.state.get_winner()
        return self._phase == "playing" and winner is None and not self._match_is_finished()

    def _can_select_moves(self, winner: Player | None = None) -> bool:
        return self._can_enter_dice(winner) and not self._awaiting_dice

    def _can_undo_move(self, winner: Player | None = None) -> bool:
        return self._phase == "playing" and not self._match_is_finished() and bool(self.state.history)

    def _blocked_move_message(self) -> str:
        if self._match_is_finished():
            return "本轮已结束，不能继续选择或执行走法。"
        if self._phase != "playing":
            return "请先确认开局后再选择或执行走法。"
        if self.state.get_winner() is not None:
            return "对局已结束，不能继续选择或执行走法。"
        if self._awaiting_dice:
            return "请先录入骰子后再选择或执行走法。"
        return "当前不能选择或执行走法。"

    def _compute_phase_label(self, winner: Player | None) -> str:
        if self._match_is_finished():
            return "本轮已结束"
        if winner is not None:
            return "对局已结束"
        if self._timeout_notice_players and not self._auto_timeout_enabled:
            timeout_text = "、".join(player_label(player) for player in self._timeout_notice_players)
            return f"超时提示：{timeout_text}（等裁判）"
        if self._mode == "match" and self._our_side is not None and self.state.current_player is not self._our_side:
            if self._awaiting_dice:
                return "等待对方录入：请输入对方骰子"
            return "等待对方录入：请点选对方走法"
        if self._awaiting_dice:
            return "请录入骰子"
        return "请选择走法"

    def _recommendation_text(self, winner: Player | None) -> str:
        match = getattr(self, "_match", None)
        if match is not None and match.is_finished():
            return "本轮已结束"
        if winner is not None:
            return "对局已结束"
        mode = getattr(self, "_mode", "debug")
        our_side = getattr(self, "_our_side", None)
        state = getattr(self, "state", None)
        if mode == "match" and our_side is not None and state is not None and state.current_player is not our_side:
            if getattr(self, "_awaiting_dice", True):
                return "等待对方骰子"
            return "等待对方走法"
        if getattr(self, "_awaiting_dice", True):
            return "等待骰子"

        move = self._recommended_move()
        if move is None:
            return "当前骰子无合法走法"

        source = getattr(self, "_recommendation_cache_source", "rollout")
        source_label = {
            "rollout": DEFAULT_RECOMMENDER_KIND,
            "greedy_risk": "greedy_risk 回退",
            "rules": "规则兜底",
            "none": DEFAULT_RECOMMENDER_KIND,
        }.get(source, DEFAULT_RECOMMENDER_KIND)
        lines = [f"{source_label}：{format_move_label(move, distinguish_self_capture=True)}"]
        if source == "rollout":
            if getattr(self._recommender, "last_low_confidence", False):
                margin = getattr(self._recommender, "last_score_margin", None)
                if margin is None:
                    lines.append("低置信：建议人工核对候选列表（候选差距过小）")
                else:
                    lines.append(f"低置信：建议人工核对候选列表，候选差距={float(margin):.2f}")
            if getattr(self._recommender, "last_timed_out", False):
                if getattr(self._recommender, "last_used_fallback", False):
                    lines.append("采样：超时，已使用 greedy_risk 回退")
                else:
                    lines.append("采样：超时，使用已完成样本")
            diagnostics = getattr(self._recommender, "last_root_stats", None)
            if diagnostics is None:
                diagnostics = getattr(self._recommender, "last_diagnostics", [])
            if diagnostics:
                lines.append("rollout 候选：")
                lines.extend(_format_rollout_diagnostic(diagnostic) for diagnostic in diagnostics)
        return "\n".join(lines)

    def _is_legal_recommendation(self, move: Move | None, legal_moves: list[Move]) -> bool:
        return move is not None and move in legal_moves

    def _choose_fallback_recommendation(
        self, legal_moves: list[Move]
    ) -> tuple[Move | None, Literal["greedy_risk", "rules", "none"]]:
        try:
            fallback_move = self._fallback_recommender.choose_move(self.state, self.current_dice)
        except Exception:  # noqa: BLE001 - GUI fallback must survive AI failures.
            fallback_move = None

        if self._is_legal_recommendation(fallback_move, legal_moves):
            return fallback_move, "greedy_risk"
        if legal_moves:
            return legal_moves[0], "rules"
        return None, "none"

    def _recommended_move(self) -> Move | None:
        key = self._recommendation_key()
        if self._recommendation_cache_key == key:
            return self._recommendation_cache_move

        self._recommendation_cache_key = key
        legal_moves = self.state.legal_moves(self.state.current_player, self.current_dice)
        if not legal_moves:
            self._recommendation_cache_move = None
            self._recommendation_cache_source = "none"
            return None

        try:
            rollout_move = self._recommender.choose_move(self.state, self.current_dice)
        except Exception:  # noqa: BLE001 - GUI must keep producing a safe recommendation.
            rollout_move = None

        if self._is_legal_recommendation(rollout_move, legal_moves):
            self._recommendation_cache_move = rollout_move
            self._recommendation_cache_source = "rollout"
            return rollout_move

        fallback_move, source = self._choose_fallback_recommendation(legal_moves)
        self._recommendation_cache_move = fallback_move
        self._recommendation_cache_source = source
        return fallback_move

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

    def _enter_debug_mode(self) -> None:
        active_match = self._match is not None and not self._match.is_finished()
        if active_match:
            confirm = messagebox.askyesno(
                "退出比赛模式",
                "切换到调试模式将放弃本轮比赛和当前记录，并清理本轮自动保存。是否继续？",
                parent=self,
            )
            if not confirm:
                return
            previous_status = self.status_message
            self._exit_match_mode()
            if self.status_message == previous_status:
                self.status_message = "已退出比赛模式，当前为调试模式。"
            self._refresh()
            return

        if self._match is not None:
            self._exit_match_mode()
            self.status_message = "已退出比赛模式，当前为调试模式。"
            self._refresh()
            return

        self._set_mode("debug")

    def _build_menu(self, master: tk.Misc) -> None:
        if not isinstance(master, (tk.Tk, tk.Toplevel)):
            return
        menubar = tk.Menu(master)
        master.config(menu=menubar)

        mode_menu = tk.Menu(menubar, tearoff=0)
        mode_menu.add_command(label="调试模式", command=self._enter_debug_mode)
        mode_menu.add_command(label="比赛模式", command=self._enter_match_mode)
        menubar.add_cascade(label="模式", menu=mode_menu)

    def _enter_match_mode(self) -> None:
        if self._match is not None and not self._match.is_finished():
            confirm = messagebox.askyesno(
                "正在比赛模式",
                "当前已处于比赛模式。重新开始将放弃本轮比赛和当前记录，是否继续？",
                parent=self,
            )
            if not confirm:
                return
        chosen = self._show_match_setup_dialog()
        if chosen is None:
            return
        if len(chosen) == 2:
            our_side, our_role = chosen
            auto_timeout_enabled = self._auto_timeout_enabled
            total_seconds = self._total_seconds
        else:
            our_side, our_role, auto_timeout_enabled, total_seconds = chosen
        self._configure_timer_options(
            total_seconds=total_seconds,
            auto_timeout_enabled=auto_timeout_enabled,
        )
        # R-2 review Important #18：进入新一轮前清掉可能残留的旧 auto-save（单盘 + 整轮）。
        self._clear_auto_save()
        self._clear_match_auto_save()
        self._match = MatchRecord(our_side=our_side, our_role=our_role)
        self._mode = "match"
        self._our_side = our_side
        self.opening_panel.set_side_controls_enabled(False)
        self._record_dirty = False
        self._match_finished_notified = False
        self._start_new_game_in_match()
        self._auto_save_current_match()

    def _configure_timer_options(
        self,
        *,
        total_seconds: float,
        auto_timeout_enabled: bool,
    ) -> None:
        self._total_seconds = validate_total_seconds(total_seconds)
        self._auto_timeout_enabled = bool(auto_timeout_enabled)
        self._timeout_notice_players = ()
        self.timer = MatchTimer(total_seconds=self._total_seconds, current_player=self.state.current_player)

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
        self._clear_match_auto_save()
        self._clear_auto_save()
        self.opening_panel.set_side_controls_enabled(True)

    def _show_match_setup_dialog(self) -> tuple[Player, MatchRole, bool, float] | None:
        dialog = tk.Toplevel(self)
        dialog.title("进入比赛模式")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        side_var = tk.StringVar(value=Player.RED.value)
        role_var = tk.StringVar(value="甲")
        total_seconds_var = tk.StringVar(value=f"{self._total_seconds:g}")
        auto_timeout_var = tk.BooleanVar(value=self._auto_timeout_enabled)
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

        tk.Label(dialog, text="单方时限（秒）：", padx=20, anchor="w").pack(fill=tk.X, pady=(12, 4))
        tk.Entry(dialog, textvariable=total_seconds_var).pack(fill=tk.X, padx=20)

        tk.Checkbutton(
            dialog,
            text="程序自动超时判负（默认关闭；裁判要求时再打开）",
            variable=auto_timeout_var,
            padx=20,
            anchor="w",
        ).pack(fill=tk.X, pady=(12, 0))

        button_row = tk.Frame(dialog)
        button_row.pack(padx=20, pady=(16, 16))

        def confirm() -> None:
            try:
                total_seconds = validate_total_seconds(total_seconds_var.get())
            except ValueError:
                messagebox.showerror("时限无效", "单方时限必须是正数秒。", parent=dialog)
                return
            result["chosen"] = (
                Player.from_value(side_var.get()),
                role_var.get(),
                bool(auto_timeout_var.get()),
                total_seconds,
            )
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
        self._timeout_notice_players = ()
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
        self._auto_save_current_match()
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
        self._auto_save_current_match()
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

    def _cancel_timer_refresh(self) -> None:
        if self._timer_after_id is None:
            return
        try:
            self.after_cancel(self._timer_after_id)
        except tk.TclError:
            pass
        self._timer_after_id = None

    def _refresh_timer(self) -> None:
        if not self.winfo_exists():
            return
        snapshot = self.timer.snapshot()
        self.timer_panel.set_snapshot(
            snapshot,
            auto_timeout_enabled=self._auto_timeout_enabled,
            timeout_adjudication_enabled=self._can_confirm_timeout_forfeit(snapshot),
        )
        if (
            self._phase == "playing"
            and self.state.get_winner() is None
            and snapshot.timeout_players
            and self._match is not None
            and not self._match.is_finished()
        ):
            timed_out = snapshot.timeout_players[0]
            if self._auto_timeout_enabled:
                self._handle_timeout(timed_out)
                return
            self._show_timeout_notice(snapshot.timeout_players)
        else:
            self._timeout_notice_players = ()
        self._schedule_timer_refresh()

    def _show_timeout_notice(self, timeout_players: tuple[Player, ...]) -> None:
        timeout_players = tuple(timeout_players)
        if timeout_players == self._timeout_notice_players:
            return
        self._timeout_notice_players = timeout_players
        timeout_text = "、".join(player_label(player) for player in timeout_players)
        self.status_message = (
            f"计时提示：{timeout_text} 已到 0。未自动判负，请以裁判判定为准。"
        )
        self._refresh()

    def _can_confirm_timeout_forfeit(self, snapshot: object) -> bool:
        timeout_players = getattr(snapshot, "timeout_players", ())
        return (
            not self._auto_timeout_enabled
            and self._phase == "playing"
            and self.state.get_winner() is None
            and bool(timeout_players)
            and self._match is not None
            and not self._match.is_finished()
        )

    def _confirm_timeout_forfeit(self, timed_out: Player) -> None:
        snapshot = self.timer.snapshot()
        if timed_out not in snapshot.timeout_players or not self._can_confirm_timeout_forfeit(snapshot):
            return
        winner = timed_out.opponent
        confirm = messagebox.askyesno(
            "确认超时判负",
            (
                f"确认裁判已判定{player_label(timed_out)}超时判负，"
                f"{player_label(winner)}获胜？"
            ),
            parent=self,
        )
        if not confirm:
            return
        self._cancel_timer_refresh()
        self._handle_timeout(timed_out)

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
        self._cancel_timer_refresh()
        super().destroy()
