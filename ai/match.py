from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, get_args

from ai.opening_layouts import PRESETS
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from core.types import Player, Position

if TYPE_CHECKING:
    from ai import AIPlayer
    from record.game_record import GameRecord


TerminationReason = Literal[
    "winner_target_corner",
    "winner_capture_all",
    "draw_max_turns",
    "no_move",
    "illegal_move",
    "crash",
]
TERMINATION_REASONS: tuple[TerminationReason, ...] = get_args(TerminationReason)


STARTING_LAYOUT_ID = "default_no_stuck_corner_v1"
"""开局布局的稳定标识。阶段 7 引入候选开局库后，会从单一字符串升级为 dict 选择器。

含义：把标准三角形开局里 5/6 号棋子从 (1,1)/(2,0) 调到 (2,0)/(3,1)（蓝方对称），
让 1 号角子在初始局面就有合法走法，规避不可控的 dice=1 强制 forfeit。
"""

STANDARD_TRIANGLE_LAYOUT_ID = "standard_triangle_v1"
"""标准三角形开局：piece 5 在 (1,1) / piece 6 在 (2,0)（蓝方对称）。

仅用于 reproducer 复现 4.1 baseline (commit baea8bb 之前未保留的开局)。
production 默认用 ``default_no_stuck_corner_v1``。
"""


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


def standard_triangle_state() -> GameState:
    """4.1 baseline 的"标准三角形"开局：piece 5 在 (1,1) / piece 6 在 (2,0)。

    Red 1 在 (0,0)，三个走法方向 (1,0)/(0,1)/(1,1) 分别被 Red 4/2/5 占据 → 角子被围死。
    任何 dice=1 都会强制选 piece 1 但 legal_moves=[] → 当前方判负。
    用于复现 reports/bench_20260509_081311_greedy_vs_random.json (0.59 / 48 forfeit)。
    """
    return GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(0, 2),
            4: Position(1, 0),
            5: Position(1, 1),
            6: Position(2, 0),
        },
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(4, 2),
            4: Position(3, 4),
            5: Position(3, 3),
            6: Position(2, 4),
        },
        current_player=Player.RED,
    )


def _opening_preset_state(layout_id: str) -> GameState:
    preset = PRESETS[layout_id]
    return GameState.from_layout(
        red=preset.red,
        blue=preset.blue,
        current_player=Player.RED,
    )


LAYOUTS = {
    STARTING_LAYOUT_ID: default_starting_state,
    STANDARD_TRIANGLE_LAYOUT_ID: standard_triangle_state,
    **{
        layout_id: (lambda preset_id=layout_id: _opening_preset_state(preset_id))
        for layout_id in PRESETS
    },
}


def starting_state_for(layout_id: str) -> GameState:
    """按 ``layout_id`` 返回对应开局；未知 id 抛 ValueError 列出可用 id。"""
    factory = LAYOUTS.get(layout_id)
    if factory is None:
        raise ValueError(
            f"unknown starting layout {layout_id!r}; expected one of {sorted(LAYOUTS)}"
        )
    return factory()


@dataclass
class MatchResult:
    """一局对战的最终结果，所有字段都用于 reports。"""

    winner: Player | None  # None = 达到 max_turns 上限，记为平局
    turns: int
    illegal_moves: int
    crashes: int
    record: "GameRecord | None"
    step_times_ms: list[float] = field(default_factory=list)
    termination_reason: TerminationReason | Literal[""] = ""

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


def _classify_winner_reason(state: GameState, winner: Player) -> TerminationReason:
    """给定 ``state`` 已判定 ``winner``，分类原因。

    - winner_target_corner: ``winner`` 任一活子位置等于自己 target_corner
    - winner_capture_all: 否则（即对方全死）
    """
    target = target_corner(winner)
    if any(piece.alive and piece.position == target for piece in state.pieces[winner].values()):
        return "winner_target_corner"
    return "winner_capture_all"


def play_one_game(
    *,
    red_ai: "AIPlayer",
    blue_ai: "AIPlayer",
    dice_rng: random.Random,
    max_turns: int = 200,
    starting_state: GameState | None = None,
) -> MatchResult:
    """跑一局 AI vs AI，返回 ``MatchResult``。

    异常处理约定：
    - AI ``choose_move`` 抛异常：crash 计 1，当前方判负，立即结束。
    - AI 返回 ``None`` 或返回的走法不在 legal_moves 中：分别计 no-move 与 illegal_moves；当前方判负。
    - 达到 ``max_turns``：winner=None（draw）。

    ``starting_state`` 默认为 ``default_starting_state()``；测试可注入任意起始局面。
    """
    from record.game_record import GameRecord

    state = starting_state if starting_state is not None else default_starting_state()
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
                termination_reason=_classify_winner_reason(state, winner),
            )

        if len(record.steps) >= max_turns:
            return MatchResult(
                winner=None,
                turns=len(record.steps),
                illegal_moves=illegal_moves,
                crashes=crashes,
                record=record,
                step_times_ms=step_times_ms,
                termination_reason="draw_max_turns",
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
                termination_reason="crash",
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
                termination_reason="no_move",
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
                termination_reason="illegal_move",
            )

        record.append(dice=dice, move=applied, state_after=state, source="self")


def build_ai(kind: str, *, seed: int | None = None, **ai_kwargs: Any) -> "AIPlayer":
    """按 kind 字符串构造带种子的 AI。

    额外的 keyword 参数会按 AI 类型透传。``random`` 不接受任何 evaluator 类参数；
    传入会抛 TypeError。
    """
    rng = random.Random(seed)
    if kind == "random":
        if ai_kwargs:
            raise TypeError(f"random AI does not accept kwargs: {sorted(ai_kwargs)}")
        from ai.random_ai import RandomAI
        return RandomAI(rng=rng, name="random")
    if kind == "greedy":
        from ai.greedy_ai import GreedyAI
        return GreedyAI(rng=rng, name="greedy", **ai_kwargs)
    if kind == "greedy_risk":
        from ai.evaluator import EXPECTED_RISK_WEIGHT, EXPECTED_WIN_RISK_WEIGHT
        from ai.greedy_ai import GreedyAI

        expected_risk_weight = ai_kwargs.pop("expected_risk_weight", EXPECTED_RISK_WEIGHT)
        expected_win_risk_weight = ai_kwargs.pop("expected_win_risk_weight", EXPECTED_WIN_RISK_WEIGHT)
        return GreedyAI(
            rng=rng,
            name="greedy_risk",
            expected_risk_weight=expected_risk_weight,
            expected_win_risk_weight=expected_win_risk_weight,
            **ai_kwargs,
        )
    if kind == "expectimax":
        from ai.evaluator import EXPECTED_RISK_WEIGHT, EXPECTED_WIN_RISK_WEIGHT
        from ai.expectimax_ai import ExpectimaxAI

        depth = int(ai_kwargs.pop("depth", 1))
        expected_risk_weight = ai_kwargs.pop("expected_risk_weight", EXPECTED_RISK_WEIGHT)
        expected_win_risk_weight = ai_kwargs.pop("expected_win_risk_weight", EXPECTED_WIN_RISK_WEIGHT)
        return ExpectimaxAI(
            rng=rng,
            name="expectimax",
            depth=depth,
            expected_risk_weight=expected_risk_weight,
            expected_win_risk_weight=expected_win_risk_weight,
            **ai_kwargs,
        )
    if kind == "rollout":
        from ai.rollout_ai import RolloutAI
        return RolloutAI(rng=rng, **ai_kwargs)
    if kind == "expectimax_v2":
        from ai.expectimax_v2 import ExpectimaxV2
        return ExpectimaxV2(rng=rng, **ai_kwargs)
    raise ValueError(f"unknown AI: {kind!r}")


def ai_version_signature(ai: "AIPlayer") -> dict[str, Any]:
    """提取 AI 的可复现性签名，用于 bench/replay metadata。

    包含 ``name`` 以及 evaluator 类权重属性若实例上存在。这样 baseline、
    production 与 4.2 risk candidate 在 metadata 里有显式区分。
    """
    sig: dict[str, Any] = {"name": ai.name}
    for attr in (
        "depth",
        "time_limit_ms",
        "randomize_ties",
        "distance_weight",
        "material_weight",
        "expected_risk_weight",
        "expected_win_risk_weight",
        "self_capture_weight",
        "rollouts_per_move",
        "max_rollout_turns",
        "max_step_time_ms",
        "epsilon",
    ):
        if hasattr(ai, attr):
            sig[attr] = getattr(ai, attr)
    return sig
