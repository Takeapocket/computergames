"""不依赖 Qt 的单盘会话，规则与棋谱全部调用现有模块。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from ai.match import starting_state_for
from core.game_state import GameState
from core.move import Move
from core.validation import require_int
from record.game_record import GameRecord


class GameSession:
    """样机只负责单盘；不接管旧界面的计时与七盘制比赛流程。

    窗口通过这些方法修改会话，读取 state/record 时不得原地修改。
    revision 标记当前局面及骰子选择，用于使异步推荐失效。
    """

    def __init__(self) -> None:
        self.revision = 0
        self.dice: int | None = None
        self.dirty = False
        self.state: GameState
        self.record: GameRecord
        self.new_game()

    @property
    def continuation_error(self) -> str | None:
        """旧规则与已记录结局仍可查看和另存，但不能追加新走法。"""
        try:
            self.record.validate_continuation_rules()
        except ValueError as exc:
            return f"此棋谱只能查看：{exc}"
        if self.record.result:
            return "此棋谱已经记录对局结果，只能查看；请新建对局。"
        return None

    def _require_continuation(self) -> None:
        error = self.continuation_error
        if error is not None:
            raise ValueError(error)

    def new_game(self, layout_id: str = "balanced_v1") -> None:
        state = starting_state_for(layout_id)
        record = GameRecord.from_state(state)
        record.metadata.update({"layout_id": layout_id, "interface": "desktop_qt"})
        self.state, self.record = state, record
        self.dice = None
        self.dirty = False
        self.revision += 1

    def set_dice(self, value: int) -> None:
        value = require_int(value, "dice", minimum=1, maximum=6)
        self._require_continuation()
        if self.state.get_winner() is not None:
            raise ValueError("game is already finished")
        if value != self.dice:
            self.dice = value
            self.revision += 1

    def legal_moves(self) -> list[Move]:
        if (
            self.dice is None
            or self.continuation_error is not None
            or self.state.get_winner() is not None
        ):
            return []
        return [move.copy() for move in self.state.legal_moves(self.state.current_player, self.dice)]

    def apply_move(self, move: Move) -> None:
        self._require_continuation()
        if self.dice is None:
            raise ValueError("请先录入本步骰子。")
        if not isinstance(move, Move):
            raise ValueError("move must be a Move")
        # 先在独立副本上完成规则校验及棋谱记录，任一环节失败都不改变当前会话。
        state = self.state.clone()
        record = deepcopy(self.record)
        canonical = state.apply_move(move.copy(), dice=self.dice)
        record.append(dice=self.dice, move=canonical, state_after=state, source="unknown")
        self.state, self.record = state, record
        self.dice = None
        self.dirty = True
        self.revision += 1

    def undo(self) -> None:
        self._require_continuation()
        if not self.record.steps:
            raise ValueError("当前棋谱没有可撤回的走法。")
        state = self.state.clone()
        record = deepcopy(self.record)
        step = record.undo_last()
        move = state.undo_move()
        if step is None or move != step.move:
            raise ValueError("棋谱与局面历史不一致，无法撤回。")
        self.state, self.record = state, record
        self.dice = step.dice
        self.dirty = True
        self.revision += 1

    def save(self, path: str | Path) -> None:
        # GameRecord.save 使用同目录临时文件和原子替换；写入成功才清除脏标记。
        deepcopy(self.record).save(path)
        self.dirty = False

    def load(self, path: str | Path) -> None:
        record = GameRecord.load(path)
        state = record.restore_state()
        # 所有解析、逐步重放校验成功后才替换，损坏文件不会清掉当前对局。
        self.state, self.record = state, record
        self.dice = None
        self.dirty = False
        self.revision += 1
