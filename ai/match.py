from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.game_state import GameState
from core.move import Move
from core.types import Player, Position

if TYPE_CHECKING:
    from ai import AIPlayer
    from record.game_record import GameRecord


def default_starting_state() -> GameState:
    """返回 5x5 默认开局：近三角形布局，确保每枚棋子初始都有至少一个合法走法。

    与标准三角形（角子被自家围死）相比，这里把 5/6 号棋子从 (1,1)/(2,0) 调到 (2,0)/(3,1)
    （蓝方对称），让 1 号棋子在 (0,0) 时能向 (1,1) 移动。规避了"dice 强制选中已被围死的
    角子→无合法走法→当前方负"这个不可控的 1/6 forfeit 上限。

    阶段 7 引入候选开局库后，这个布局会被多个候选阵型替代。
    """
    return GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(0, 2),
            4: Position(1, 0),
            5: Position(2, 0),
            6: Position(3, 1),
        },
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(4, 2),
            4: Position(3, 4),
            5: Position(2, 4),
            6: Position(1, 3),
        },
        current_player=Player.RED,
    )


@dataclass
class MatchResult:
    """一局对战的最终结果，所有字段都用于 reports。"""

    winner: Player | None  # None = 达到 max_turns 上限，记为平局
    turns: int
    illegal_moves: int
    crashes: int
    record: "GameRecord | None"
    step_times_ms: list[float] = field(default_factory=list)

    @property
    def avg_step_time_ms(self) -> float:
        if not self.step_times_ms:
            return 0.0
        return sum(self.step_times_ms) / len(self.step_times_ms)

    @property
    def max_step_time_ms(self) -> float:
        if not self.step_times_ms:
            return 0.0
        return max(self.step_times_ms)


def play_one_game(
    *,
    red_ai: "AIPlayer",
    blue_ai: "AIPlayer",
    dice_rng: random.Random,
    max_turns: int = 200,
) -> MatchResult:
    """跑一局 AI vs AI，返回 ``MatchResult``。

    异常处理约定：
    - AI ``choose_move`` 抛异常：crash 计 1，当前方判负，立即结束。
    - AI 返回 ``None`` 或返回的走法不在 legal_moves 中：分别计 no-move 与 illegal_moves；当前方判负。
    - 达到 ``max_turns``：winner=None（draw）。
    """
    from record.game_record import GameRecord

    state = default_starting_state()
    record = GameRecord.from_state(state)
    illegal_moves = 0
    crashes = 0
    step_times_ms: list[float] = []

    while True:
        winner = state.get_winner()
        if winner is not None:
            return MatchResult(
                winner=winner,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
            )

        if len(record.steps) >= max_turns:
            return MatchResult(
                winner=None,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
            )

        active = state.current_player
        ai = red_ai if active is Player.RED else blue_ai
        dice = dice_rng.randint(1, 6)

        start = time.perf_counter()
        try:
            move = ai.choose_move(state, dice)
        except Exception:  # noqa: BLE001 — harness 必须吞下任意异常
            crashes += 1
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            step_times_ms.append(elapsed_ms)
            return MatchResult(
                winner=active.opponent,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        step_times_ms.append(elapsed_ms)

        if move is None:
            return MatchResult(
                winner=active.opponent,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
            )

        try:
            applied = state.apply_move(move, dice=dice)
        except ValueError:
            illegal_moves += 1
            return MatchResult(
                winner=active.opponent,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
            )

        record.append(dice=dice, move=applied, state_after=state, source="self")


def build_ai(kind: str, *, seed: int | None = None) -> "AIPlayer":
    """按 kind 字符串构造带种子的 AI。"""
    rng = random.Random(seed)
    if kind == "random":
        from ai.random_ai import RandomAI
        return RandomAI(rng=rng, name="random")
    if kind == "greedy":
        from ai.greedy_ai import GreedyAI
        return GreedyAI(rng=rng, name="greedy")
    raise ValueError(f"unknown AI: {kind!r}")
