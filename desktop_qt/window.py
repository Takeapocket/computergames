"""Qt desktop UI using shared rules, match flow, clocks, and records."""
from __future__ import annotations

import logging
from pathlib import Path
from random import SystemRandom
from time import monotonic
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ai.match import build_ai
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from core.move import Move
from core.game_state import GameState
from core.rules import RULES_VERSION
from core.types import Player, Position
from desktop_qt.board import BoardWidget, move_label
from desktop_qt.dialogs import NewMatchDialog, OpeningDialog
from desktop_qt.paths import resolve_data_dir
from desktop_qt.session import GameSession
from desktop_qt.theme import BLUE, RED, STYLESHEET
from gui.recommendation_worker import RecommendationRequest, RecommendationResult, RecommendationWorker


class PrototypeWindow(QMainWindow):
    def __init__(
        self, session: GameSession | None = None, data_dir: Path | None = None, *,
        recommender: Any = None, fallback: Any = None, worker: Any = None,
    ) -> None:
        super().__init__()
        self.session = session if session is not None else GameSession()
        self.data_dir = resolve_data_dir(data_dir)
        self.record_path: Path | None = None
        # Construct the same explicit P14 configuration as the original GUI.
        self._recommender = recommender if recommender is not None else build_ai(
            "rollout", seed=0, **dict(RELEASE_DEFAULT_ROLLOUT_KWARGS))
        self._fallback = fallback if fallback is not None else build_ai("greedy_risk", seed=0)
        self._worker = worker if worker is not None else RecommendationWorker()
        self._generation = 0
        self._pending_key: tuple[int, str] | None = None
        self._recommendation: RecommendationResult | None = None
        self._display_revision = self.session.revision
        self._closed = False
        self._last_checkpoint = monotonic()
        self._recovery_offered = False
        self._recovery_acknowledged = False
        self._opening_preset_id = "balanced_v1"
        self._random = SystemRandom()
        self.setWindowTitle("Einstein · 爱恩斯坦棋 — 桌面对弈版")
        self.resize(1200, 960)
        self.setMinimumSize(760, 440)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(60)
        self._poll_timer.timeout.connect(self._poll_recommendation)
        self._poll_timer.start()
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(150)
        self._clock_timer.timeout.connect(self._refresh_clock)
        if self._has_match_flow:
            self._clock_timer.start()
        for sequence, callback in (("Ctrl+S", self._save_dialog), ("Ctrl+O", self._open_dialog),
                                   ("Ctrl+N", self.new_game), ("Ctrl+Z", self.undo)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
        self.refresh_view()

    @property
    def recommended_move(self) -> Move | None:
        result = self._recommendation
        if not self._can_play or result is None or result.key != self._current_key() or result.generation != self._generation:
            return None
        return result.move.copy() if result.move is not None else None

    @property
    def recommendation_pending(self) -> bool:
        return self._pending_key is not None and self._pending_key == self._current_key()

    @staticmethod
    def _label(text: str, name: str = "", *, wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setWordWrap(wrap)
        return label

    @staticmethod
    def _button(text: str, callback: Any, name: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        return frame, layout

    @property
    def _has_match_flow(self) -> bool:
        return hasattr(self.session, "phase")

    @property
    def _can_play(self) -> bool:
        if self._has_match_flow:
            return self.session.can_play
        return not self.session.continuation_error and not self.session.record.result and self.session.state.get_winner() is None

    def _build_match_toolbar(self, outer: QVBoxLayout) -> None:
        self.match_panel, layout = self._card()
        self.match_panel.setVisible(self._has_match_flow)
        layout.setContentsMargins(18, 12, 18, 12)
        heading = QHBoxLayout()
        self.match_label = self._label("", "sectionTitle", wrap=True)
        heading.addWidget(self.match_label, 1)
        self.setup_button = self._button("设置开局", self.configure_opening, "primary")
        self.next_game_button = self._button("下一盘", self.next_game, "primary")
        self.pause_button = self._button("暂停计时", self.toggle_pause)
        self.match_save_button = self._button("导出整轮", self._save_match_dialog)
        self.recovery_button = self._button("恢复自动保存", self.restore_recovery)
        for button in (self.setup_button, self.next_game_button, self.pause_button, self.match_save_button, self.recovery_button):
            heading.addWidget(button)
        layout.addLayout(heading)
        clocks = QHBoxLayout()
        self.red_clock_label = self._label("", "sectionTitle")
        self.red_clock_label.setStyleSheet(f"color: {RED};")
        self.blue_clock_label = self._label("", "sectionTitle")
        self.blue_clock_label.setStyleSheet(f"color: {BLUE};")
        self.step_clock_label = self._label("", "muted")
        for label in (self.red_clock_label, self.blue_clock_label, self.step_clock_label):
            clocks.addWidget(label)
        clocks.addStretch(1)
        self.timeout_button = self._button("裁判确认超时判负", self.confirm_timeout)
        clocks.addWidget(self.timeout_button)
        layout.addLayout(clocks)
        self.flow_hint = self._label("", "muted", wrap=True)
        layout.addWidget(self.flow_hint)
        save_row = QHBoxLayout()
        self.save_error_label = self._label("", "status", wrap=True)
        self.save_error_label.setStyleSheet("color: #B4483F;")
        self.save_error_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        save_row.addWidget(self.save_error_label, 1)
        self.retry_save_button = self._button("重试自动保存", self.retry_save)
        save_row.addWidget(self.retry_save_button)
        layout.addLayout(save_row)
        outer.addWidget(self.match_panel)

    @staticmethod
    def _clock_text(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _refresh_clock(self) -> None:
        if not self._has_match_flow or self._closed:
            return
        previous = self.session.revision
        previous_error = self.session.save_error
        self.session.check_timeout()
        if monotonic() - self._last_checkpoint >= 2.0:
            self._last_checkpoint = monotonic()
            if self.session.phase == "playing":
                self.session.checkpoint()
        snapshot = self.session.timer.snapshot()
        self.red_clock_label.setText(f"红方  {self._clock_text(snapshot.remaining_seconds[Player.RED])}")
        self.blue_clock_label.setText(f"蓝方  {self._clock_text(snapshot.remaining_seconds[Player.BLUE])}")
        self.step_clock_label.setText(f"本步 {snapshot.current_step_seconds:.1f} 秒" + (" · 已暂停" if snapshot.paused else ""))
        self.pause_button.setText("继续计时" if snapshot.paused else "暂停计时")
        self.timeout_button.setEnabled(bool(snapshot.timeout_players) and self.session.phase == "playing" and not self.session.continuation_error)
        if snapshot.timeout_players and self.session.phase == "playing":
            names = "、".join("红方" if player is Player.RED else "蓝方" for player in snapshot.timeout_players)
            self.flow_hint.setText(f"{names}时间已到 · 等待裁判确认；默认不自动判负。")
        if previous != self.session.revision or previous_error != self.session.save_error:
            self.refresh_view()

    def _refresh_match_flow(self) -> None:
        if not self._has_match_flow:
            return
        session = self.session
        match = session.match
        phase = session.phase
        if match is None:
            self.match_label.setText("单盘对局")
        else:
            side = "红方" if match.our_side is Player.RED else "蓝方"
            game_index = len(match.games) if phase == "finished" and match.games else match.current_game_index
            first = match.first_mover_color(max(1, game_index))
            first_text = "红方" if first is Player.RED else "蓝方"
            self.match_label.setText(f"七盘制 · 第 {game_index} / {match.total_games} 盘 · 我方 {match.games_won_us} : {match.games_won_them} 对方")
            self.match_label.setToolTip(f"我方：{side} / {match.our_role}方；本盘{first_text}先手")
        self.setup_button.setVisible(phase == "setup")
        self.setup_button.setEnabled(not session.continuation_error and not session.pending_finalize)
        self.next_game_button.setVisible(phase == "finished" and match is not None and not match.is_finished())
        self.next_game_button.setEnabled(session.can_next_game)
        self.pause_button.setEnabled(phase == "playing" and not session.continuation_error)
        self.match_save_button.setVisible(match is not None)
        self.recovery_button.setEnabled(session.has_recovery)
        self.retry_save_button.setVisible(bool(session.save_error))
        saved_text = "自动保存已开启" if session.has_started else "确认开局后开启自动保存"
        self.save_error_label.setText(str(session.save_error) if session.save_error else saved_text)
        self.save_error_label.setStyleSheet(f"color: {'#B4483F' if session.save_error else '#0F766E'};")
        self.save_error_label.setToolTip(f"数据目录：{self.data_dir}\n自动恢复：{self.data_dir / 'recovery'}")
        hints = {"setup": "请设置双方实际开局，确认后才开始计时。",
                 "playing": "暂停只停止计时，仍可录入走法；比赛现场以裁判要求为准。",
                 "finished": "本盘已结束。" + ("整轮已结束，可导出整轮棋谱。" if match and match.is_finished() else "核对结果后进入下一盘。" if match else "可保存棋谱或新建对局。")}
        detail = f"我方{side} / {match.our_role}方 · 本盘{first_text}先手。 " if match is not None else ""
        self.flow_hint.setText(session.continuation_error or detail + hints[phase])
        self._refresh_clock()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        # Keep controls reachable on short screens and at large display scaling.
        # The content keeps its layout minimum; the window itself may be smaller.
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidget(root)
        self.setCentralWidget(self.content_scroll)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 20, 28, 16)
        outer.setSpacing(16)
        header = QHBoxLayout()
        header.setSpacing(14)
        mark = self._label("E", "brandMark")
        mark.setFixedSize(46, 46)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(self._label("Einstein", "brand"))
        brand.addWidget(self._label("爱恩斯坦棋 · 离线对弈工作台", "brandChinese"))
        header.addLayout(brand)
        header.addStretch()
        header.addWidget(self._label("桌面对弈版", "badge"))
        header.addSpacing(6)
        self.new_button = self._button("新建对局", self.new_game)
        self.open_button = self._button("打开棋谱", self._open_dialog)
        self.save_button = self._button("保存棋谱", self._save_dialog)
        for button in (self.new_button, self.open_button, self.save_button):
            header.addWidget(button)
        outer.addLayout(header)
        self._build_match_toolbar(outer)

        body = QHBoxLayout()
        body.setSpacing(20)
        board_card, board_layout = self._card()
        board_heading = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(self._label("PLAY BOARD", "eyebrow"))
        names.addWidget(self._label("对局棋盘", "sectionTitle"))
        board_heading.addLayout(names)
        board_heading.addStretch()
        self.step_label = self._label("第 1 手", "muted")
        board_heading.addWidget(self.step_label)
        board_layout.addLayout(board_heading)
        self.board = BoardWidget()
        self.board.square_clicked.connect(self._board_clicked)
        board_layout.addWidget(self.board, 1)
        board_footer = QHBoxLayout()
        self.material_label = self._label("", "muted")
        board_footer.addWidget(self.material_label)
        board_footer.addStretch()
        self.undo_button = self._button("↶  悔棋", self.undo, "quiet")
        board_footer.addWidget(self.undo_button)
        board_layout.addLayout(board_footer)
        board_layout.addWidget(self._label("先选择骰子，再点棋子与落点；也可从右侧执行走法。", "muted"))
        body.addWidget(board_card, 1)

        sidebar = QVBoxLayout()
        sidebar.setSpacing(14)
        turn_card, turn_layout = self._card()
        turn_card.setFixedWidth(334)
        turn_layout.addWidget(self._label("YOUR TURN", "eyebrow"))
        self.turn_label = self._label("", "turn")
        turn_layout.addWidget(self.turn_label)
        self.turn_hint = self._label("请选择当前骰子点数", "muted", wrap=True)
        turn_layout.addWidget(self.turn_hint)
        dice_row = QHBoxLayout()
        dice_row.setSpacing(7)
        self.dice_buttons: list[QPushButton] = []
        for value in range(1, 7):
            button = self._button(str(value), lambda checked=False, d=value: self.set_dice(d), "dice")
            button.setCheckable(True)
            button.setAccessibleName(f"骰子 {value}")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            dice_row.addWidget(button)
            self.dice_buttons.append(button)
        turn_layout.addLayout(dice_row)
        self.roll_button = self._button("随机掷骰", self.roll_dice, "quiet")
        turn_layout.addWidget(self.roll_button, 0, Qt.AlignmentFlag.AlignRight)
        turn_layout.addWidget(self._label("合法走法", "muted"))
        self.move_combo = QComboBox()
        self.move_combo.setMinimumContentsLength(15)
        self.move_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.move_combo.currentIndexChanged.connect(self._select_move)
        turn_layout.addWidget(self.move_combo)
        self.execute_button = self._button("执行所选走法", self.execute_selected_move)
        turn_layout.addWidget(self.execute_button)
        sidebar.addWidget(turn_card)

        ai_card, ai_layout = self._card()
        ai_card.setFixedWidth(334)
        ai_heading = QHBoxLayout()
        ai_heading.addWidget(self._label("AI 建议", "sectionTitle"))
        ai_heading.addStretch()
        ai_heading.addWidget(self._label("P14", "badge"))
        ai_layout.addLayout(ai_heading)
        ai_layout.addWidget(self._label("Rollout · 当前默认配置", "muted"))
        self.recommendation_label = self._label("等待骰子", "recommendation", wrap=True)
        self.recommendation_label.setMinimumHeight(30)
        ai_layout.addWidget(self.recommendation_label)
        self.recommendation_hint = self._label("先录入骰子，再请求推荐。", "muted", wrap=True)
        self.recommendation_hint.setMinimumHeight(34)
        ai_layout.addWidget(self.recommendation_hint)
        ai_actions = QHBoxLayout()
        ai_actions.setSpacing(8)
        self.recommend_button = self._button("请求推荐", self.request_recommendation, "primary")
        self.apply_button = self._button("应用推荐", self.apply_recommendation)
        ai_actions.addWidget(self.recommend_button)
        ai_actions.addWidget(self.apply_button)
        ai_layout.addLayout(ai_actions)
        sidebar.addWidget(ai_card)
        sidebar.addStretch(1)
        sidebar.addWidget(self._label("规则与 P14 默认配置保持一致\n先确认开局，再开始计时和行棋。", "muted", wrap=True))
        body.addLayout(sidebar)
        outer.addLayout(body, 1)

        history_card, history_layout = self._card()
        history_layout.setContentsMargins(22, 13, 22, 10)
        history_layout.setSpacing(4)
        history_heading = QHBoxLayout()
        history_heading.addWidget(self._label("行棋记录", "sectionTitle"))
        history_heading.addStretch()
        self.record_label = self._label("未保存 · 0 手", "muted")
        history_heading.addWidget(self.record_label)
        history_layout.addLayout(history_heading)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["手数", "行棋方", "骰子", "走法"])
        self.history_table.verticalHeader().hide()
        self.history_table.verticalHeader().setDefaultSectionSize(27)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_table.setShowGrid(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.setFixedHeight(78)
        self.empty_history = self._label("尚无行棋记录。完成第一步后，棋谱会显示在这里。", "muted")
        history_layout.addWidget(self.empty_history)
        history_layout.addWidget(self.history_table)
        outer.addWidget(history_card)
        status_row = QHBoxLayout()
        self.status_label = self._label("就绪 · 默认布局 balanced_v1", "status")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status_row.addWidget(self.status_label, 1)
        rule_label = self._label("离线运行  /  规则 v2", "status")
        rule_label.setToolTip(RULES_VERSION)
        status_row.addWidget(rule_label)
        outer.addLayout(status_row)

    def _current_key(self) -> tuple[int, str]:
        phase = f"{self.session.phase}:{self.session.timer.is_paused}" if self._has_match_flow else ""
        return self.session.revision, f"{self.session.dice}:{phase}"

    def _invalidate_recommendation(self) -> None:
        self._generation += 1
        self._pending_key = None
        self._recommendation = None
        self._worker.invalidate()

    def refresh_view(self) -> None:
        if self.session.revision != self._display_revision:
            self._invalidate_recommendation()
            self._display_revision = self.session.revision
        state = self.session.state
        winner = state.get_winner()
        blocked = self.session.continuation_error
        ended = winner is not None or bool(self.session.record.result)
        active = self._can_play
        player = state.current_player
        side = "红方" if player is Player.RED else "蓝方"
        color = RED if player is Player.RED else BLUE
        turn_text = f"{side}行棋" if winner is None else f"{'红方' if winner is Player.RED else '蓝方'}获胜"
        if self._has_match_flow and self.session.phase == "setup":
            turn_text = "等待开局确认"
        elif self._has_match_flow and self.session.timer.is_paused and not ended:
            turn_text = "计时已暂停"
        self.turn_label.setText("本盘已结束" if self.session.record.result else turn_text)
        self.turn_label.setStyleSheet(f"color: {'#0F766E' if ended else color};")
        moves = self.session.legal_moves() if active and self.session.dice is not None else []
        piece_ids = sorted({move.piece_id for move in moves})
        hint = "请选择当前骰子点数" if self.session.dice is None else "可走棋子：" + "、".join(str(value) for value in piece_ids)
        if self._has_match_flow and not active and not ended:
            hint = "请先设置并确认双方开局。" if self.session.phase == "setup" else "点击继续计时后可以行棋。"
        self.turn_hint.setText(blocked or ("本盘已结束，可保存棋谱或新建对局。" if ended else hint))
        for value, button in enumerate(self.dice_buttons, 1):
            button.setChecked(self.session.dice == value)
            button.setEnabled(active)
        self.roll_button.setEnabled(active)
        selected = self.move_combo.currentData()
        self.move_combo.blockSignals(True)
        self.move_combo.clear()
        for move in moves:
            self.move_combo.addItem(move_label(move), move)
        if selected in moves:
            self.move_combo.setCurrentIndex(moves.index(selected))
        if not moves:
            self.move_combo.addItem("等待有效骰子" if active else "无法继续行棋", None)
        self.move_combo.blockSignals(False)
        self.move_combo.setEnabled(bool(moves))
        self.execute_button.setEnabled(bool(moves))
        self.undo_button.setEnabled(self.session.can_undo if self._has_match_flow else bool(self.session.record.steps) and not blocked)
        self.recommend_button.setEnabled(bool(moves) and not self.recommendation_pending)
        self.apply_button.setEnabled(self.recommended_move is not None and bool(moves))
        self.board.state = state
        self.board.legal_moves = moves
        self.board.selected_move = self.move_combo.currentData()
        self.board.recommendation = self.recommended_move
        self.board.last_move = self.session.record.steps[-1].move if self.session.record.steps else None
        self.board.setEnabled(active)
        self.board.update()
        self.step_label.setText("本盘结束" if ended else f"第 {len(self.session.record.steps) + 1} 手")
        red_count = sum(piece.alive for piece in state.pieces[Player.RED].values())
        blue_count = sum(piece.alive for piece in state.pieces[Player.BLUE].values())
        self.material_label.setText(f"● 红方 {red_count} 子    ● 蓝方 {blue_count} 子    ·    绿色标记为合法落点")
        self._refresh_recommendation_text()
        self._refresh_history()
        self._refresh_match_flow()

    def _refresh_history(self) -> None:
        steps = self.session.record.steps
        self.empty_history.setVisible(not steps)
        self.history_table.setVisible(bool(steps))
        self.history_table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            values = (str(step.turn), "红方" if step.player is Player.RED else "蓝方", str(step.dice), move_label(step.move))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col < 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row, col, item)
        if steps:
            self.history_table.scrollToBottom()
        name = self.record_path.name if self.record_path else "未保存"
        dirty = " · 有未保存更改" if self.session.dirty else ""
        self.record_label.setText(f"{name} · {len(steps)} 手{dirty}")
        self.record_label.setToolTip(str(self.record_path) if self.record_path else "新建棋谱")

    def _refresh_recommendation_text(self) -> None:
        if self.recommendation_pending:
            self.recommendation_label.setText("正在计算…")
            self.recommendation_hint.setText("后台计算中，仍可手动行棋。更改局面后，本次结果自动作废。")
        elif self.recommended_move is not None:
            self.recommendation_label.setText(move_label(self.recommended_move))
            source = self._recommendation.source
            messages = {"rollout": "P14 推荐已就绪，请核对后应用。", "greedy_risk": "P14 未返回有效走法，已使用 greedy_risk 回退。",
                        "rules": "AI 未返回有效走法，已选择第一条合法步。"}
            self.recommendation_hint.setText(messages.get(source, "没有可用推荐。"))
        else:
            self.recommendation_label.setText("等待骰子" if self.session.dice is None else "尚未请求推荐")
            if not self._can_play:
                self.recommendation_label.setText("推荐不可用")
                self.recommendation_hint.setText("请先确认开局；已结束或旧规则棋谱不能请求推荐。")
            else:
                self.recommendation_hint.setText("先录入骰子，再请求推荐。" if self.session.dice is None else "推荐由当前 P14 参数计算，不自动执行。")
        diagnostics = "\n\n".join(self._recommendation.diagnostics) if self._recommendation else ""
        self.recommendation_hint.setToolTip(diagnostics)

    def _select_move(self, index: int) -> None:
        self.board.selected_move = self.move_combo.itemData(index)
        self.board.update()

    def _board_clicked(self, row: int, col: int) -> None:
        position = Position(row, col)
        moves = self.board.legal_moves
        selected = self.move_combo.currentData()
        # A highlighted destination takes precedence, including legal self-captures.
        destination = next((move for move in moves if selected is not None
                            and move.from_pos == selected.from_pos and move.to_pos == position), None)
        if destination is not None:
            self._execute_move(destination)
            return
        origin = next((move for move in moves if move.from_pos == position), None)
        if origin is not None:
            self.move_combo.setCurrentIndex(moves.index(origin))

    def set_dice(self, value: int) -> None:
        try:
            self.session.set_dice(value)
        except (ValueError, TypeError) as exc:
            self._show_error("骰子无效", exc)
            return
        self.refresh_view()
        self._status(f"骰子 {value} · 请选走法或请求 P14 推荐")

    def roll_dice(self) -> None:
        self.set_dice(self._random.randint(1, 6))

    def execute_selected_move(self) -> None:
        move = self.move_combo.currentData()
        if move is not None:
            self._execute_move(move)

    def _execute_move(self, move: Move) -> None:
        try:
            self.session.apply_move(move)
        except (ValueError, TypeError) as exc:
            self._show_error("无法执行走法", exc)
            self.refresh_view()
            return
        self.refresh_view()
        self._status(f"已执行：{move_label(move)}" + (" · 自动保存状态见上方" if self._has_match_flow else " · 棋谱尚未保存"))

    def undo(self) -> None:
        if not self.undo_button.isEnabled():
            return
        try:
            self.session.undo()
        except ValueError as exc:
            self._show_error("无法悔棋", exc)
            return
        self.refresh_view()
        self._status("已撤销上一手 · 旧推荐已作废")

    def request_recommendation(self) -> None:
        self.refresh_view()
        if not self.board.legal_moves or self.recommendation_pending:
            return
        self._invalidate_recommendation()
        self._pending_key = self._current_key()
        request = RecommendationRequest(self._generation, self._pending_key, self.session.dice,
            self.session.state.clone(include_history=False), self._recommender, self._fallback)
        self._worker.submit(request)
        self.refresh_view()
        self._status("P14 后台计算中")

    def _poll_recommendation(self) -> None:
        if self._closed:
            return
        for result in self._worker.drain():
            if (result.generation != self._generation or result.key != self._pending_key
                    or result.key != self._current_key()):
                continue
            self._pending_key = None
            self._recommendation = result
            self.refresh_view()
            self._status("推荐已就绪" if result.move is not None else "没有可用推荐，请检查当前局面")

    def apply_recommendation(self) -> None:
        move = self.recommended_move
        if move is not None:
            self._execute_move(move)

    def new_game(self) -> None:
        if not self._confirm_discard():
            return
        if self._has_match_flow:
            dialog = NewMatchDialog(self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            options = dialog.options()
            mode = options.pop("mode")
            if mode == "single":
                options.pop("our_role")
            try:
                (self.session.start_match if mode == "match" else self.session.start_single)(**options)
            except (ValueError, OSError) as exc:
                self._show_error("无法新建对局", exc)
                return
            self._recovery_acknowledged = True
            self.record_path = None
            self.refresh_view()
            self.configure_opening()
            return
        self.session.new_game()
        self.record_path = None
        self.refresh_view()
        self._status("已新建单盘对局 · 默认布局 balanced_v1 · 红方先行")

    def configure_opening(self) -> None:
        if not self._has_match_flow or self.session.phase != "setup" or self.session.continuation_error:
            return
        if not self.session.has_started and self.session.has_recovery and not self._recovery_acknowledged:
            if not self._confirm_discard():
                return
        match = self.session.match
        first = match.first_mover_color(match.current_game_index) if match else Player.RED
        retained = None
        if match is not None and match.last_game_winner == "us" and match.games:
            previous = GameState.deserialize(match.games[-1].initial_state)
            retained = {piece_id: piece.position for piece_id, piece in previous.pieces[match.our_side].items() if piece.alive}
        dialog = OpeningDialog(self.data_dir / "layouts", self, first_player=first,
            fixed_first=match is not None, our_side=match.our_side if match else None,
            retained_our_layout=retained, preset_id=self._opening_preset_id)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.session.confirm_opening(*dialog.layouts(), current_player=dialog.first_combo.currentData(), layout_id=dialog.layout_id)
        except (ValueError, OSError) as exc:
            self._show_error("开局未确认", exc)
            return
        self._recovery_acknowledged = True
        self._opening_preset_id = dialog.selected_preset_id
        self.refresh_view()
        self._status("开局已确认 · 已开始计时")

    def next_game(self) -> None:
        if not self._has_match_flow or not self.session.can_next_game:
            return
        try:
            self.session.next_game()
        except (ValueError, OSError) as exc:
            self._show_error("无法进入下一盘", exc)
            return
        self.record_path = None
        self.refresh_view()
        self.configure_opening()

    def toggle_pause(self) -> None:
        if not self._has_match_flow or self.session.phase != "playing":
            return
        self._invalidate_recommendation()
        self.session.toggle_pause()
        self.refresh_view()
        self._status("计时已暂停 · 可以继续录入走法" if self.session.timer.is_paused else "计时已继续")

    def confirm_timeout(self) -> None:
        if not self._has_match_flow or self.session.phase != "playing":
            return
        players = self.session.timer.snapshot().timeout_players
        if not players:
            return
        player = players[0]
        if len(players) > 1:
            selected, accepted = QInputDialog.getItem(self, "选择裁判判负方",
                "双方时间均为零，请选择裁判判定超时负的一方：", ["红方", "蓝方"], 0, False)
            if not accepted:
                return
            player = Player.RED if selected == "红方" else Player.BLUE
        side = "红方" if player is Player.RED else "蓝方"
        answer = QMessageBox.warning(self, "裁判确认超时判负", f"{side}剩余时间为零。确认裁判已判定{side}超时负？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.session.forfeit_timeout(player)
        except ValueError as exc:
            self._show_error("无法判定超时", exc)
            return
        self.refresh_view()
        self._status(f"已记录{side}超时负")

    def retry_save(self) -> None:
        if not self._has_match_flow:
            return
        saved = self.session.retry_save()
        self.refresh_view()
        self._status("自动保存已完成" if saved else "自动保存仍失败，请检查数据目录权限或剩余空间")

    def offer_recovery(self) -> None:
        if self._recovery_offered or not self._has_match_flow or not self.session.has_recovery:
            return
        self._recovery_offered = True
        answer = QMessageBox.question(self, "发现上次自动保存",
            "恢复上次的棋盘、比分与计时？\n取消会保留恢复文件，可稍后点击“恢复自动保存”。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes)
        if answer == QMessageBox.StandardButton.Yes:
            self.restore_recovery(confirm=False)

    def restore_recovery(self, *, confirm: bool = True) -> bool:
        if not self._has_match_flow or not self.session.has_recovery:
            return False
        if confirm and self.session.has_started and not self._confirm_discard():
            return False
        try:
            restored = self.session.restore_recovery()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._show_error("恢复失败，原文件已保留", exc)
            self.refresh_view()
            return False
        if not restored:
            self._status("没有可恢复的记录；原文件保持不变")
            return False
        self._recovery_acknowledged = True
        self.record_path = None
        self._invalidate_recommendation()
        self.refresh_view()
        self._status("已恢复上次对局" + (" · 计时暂停，点击继续计时" if self.session.timer.is_paused else " · 计时已继续"))
        return True

    def _save_match_dialog(self) -> bool:
        if not self._has_match_flow or self.session.match is None:
            return False
        default = self.data_dir / "records" / f"整轮_{self.session.match.match_id}.json"
        path, _ = QFileDialog.getSaveFileName(self, "导出已结算整轮（进行中本盘请另存棋谱）", str(default), "JSON 棋谱 (*.json)")
        if not path:
            return False
        try:
            self.session.save_match(path)
        except (OSError, ValueError) as exc:
            self._show_error("整轮棋谱导出失败", exc)
            return False
        self._status(f"已导出整轮完成盘：{path} · 进行中本盘使用“保存棋谱”另存")
        return True

    def save_record(self, path: str | Path) -> bool:
        try:
            self.session.save(path)
        except (OSError, ValueError) as exc:
            self._show_error("棋谱保存失败", exc)
            return False
        self.record_path = Path(path)
        self.refresh_view()
        self._status(f"棋谱已保存：{self.record_path}")
        return True

    def load_record(self, path: str | Path) -> bool:
        if not self._confirm_discard():
            return False
        try:
            self.session.load(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._show_error("棋谱打开失败", exc)
            return False
        self._recovery_acknowledged = True
        self.record_path = None if self._has_match_flow and self.session.match is not None else Path(path)
        self.refresh_view()
        self._status(f"棋谱已打开：{Path(path)}" + (" · 只读棋谱" if self.session.continuation_error else ""))
        return True

    def _save_dialog(self) -> bool:
        default = self.record_path or self.data_dir / "records" / "爱恩斯坦棋谱.json"
        try:
            default.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_error("无法访问保存目录", exc)
            return False
        path, _ = QFileDialog.getSaveFileName(self, "保存本盘棋谱（含当前计时）", str(default), "JSON 棋谱 (*.json)")
        return self.save_record(path) if path else False

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "打开单盘、整轮或自动保存棋谱", str(self.data_dir / "records"), "JSON 棋谱 (*.json)")
        if path:
            self.load_record(path)

    def _confirm_discard(self, *, replacing: bool = True) -> bool:
        flow = self._has_match_flow
        unresolved = flow and replacing and not self._recovery_acknowledged and self.session.has_recovery and not self.session.has_started
        if unresolved:
            answer = QMessageBox.warning(self, "保留的自动恢复文件",
                "尚未恢复上次对局。继续新建或导入后，将使用新对局更新自动恢复文件。\n可取消后先点击“恢复自动保存”。是否继续？",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            return answer == QMessageBox.StandardButton.Discard
        has_match = flow and self.session.match is not None and replacing
        if not self.session.dirty and not has_match:
            return True
        detail = "是否先保存当前棋谱？"
        if has_match:
            detail = "当前有七盘制对局。保存将分别另存本盘和已结算整轮；放弃将替换当前对局。"
        answer = QMessageBox.warning(self, "保存当前对局", detail,
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Save:
            return self._save_dialog() and (not has_match or self._save_match_dialog())
        return answer == QMessageBox.StandardButton.Discard

    def _status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

    def _show_error(self, title: str, error: Exception) -> None:
        logging.getLogger(__name__).warning("%s: %s", title, error)
        self._status(f"{title}：{error}")
        QMessageBox.critical(self, title, str(error))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard(replacing=False):
            event.ignore()
            return
        if self._has_match_flow and self.session.has_started and (
                self.session.pending_finalize or self.session.save_error or not self.session.continuation_error):
            if not self.session.retry_save():
                self.refresh_view()
                answer = QMessageBox.warning(self, "关闭前自动保存失败",
                    "整轮比分或当前计时、棋谱未能自动保存。另存本盘不能代替整轮保存。仍要关闭吗？旧恢复文件将保留。",
                    QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel)
                if answer != QMessageBox.StandardButton.Discard:
                    event.ignore()
                    return
        self._closed = True
        self._poll_timer.stop()
        self._clock_timer.stop()
        self._worker.close()
        event.accept()
