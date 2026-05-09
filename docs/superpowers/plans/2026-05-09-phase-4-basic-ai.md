# 阶段 4.0 + 4.1 基础 AI 与最小对战 harness 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现阶段 4.0 最小对战 harness（AI vs AI 单局 + 批量 100 局/200 局 bench）和阶段 4.1 基础 GreedyAI + 启发式评估函数，并通过 quick_bench 数据验证 GreedyAI vs RandomAI 胜率 ≥ 95%。

**Architecture:**
- 在 `ai/` 下定义 `AIPlayer` Protocol（`name + choose_move(state, dice)`）。
- 把现有 `choose_random_move` 函数包装为 `RandomAI` 类（保留函数做向后兼容）。
- 新增 `ai/match.py`：`default_starting_state()`、`MatchResult`、`play_one_game()`、`build_ai()` 工厂——所有可被 pytest 直接调用，CLI 脚本只是薄封装。
- 阶段 4.1 新增 `ai/evaluator.py`（终局 + chebyshev 距离 + 存活子数差，纯函数）和 `ai/greedy_ai.py`（按"应用→评估→撤销"挑最高分走法，平分 RNG 抽签）。
- `scripts/run_match.py`：跑一局，输出 JSON + 保存 replay 到 `replays/`。
- `scripts/quick_bench.py`：跑 N 局，输出 stdout 摘要 + JSON 报告到 `reports/`。

**Tech Stack:** Python 3.11、`random`、`time.perf_counter`、`json`、`argparse`、pytest。

**关联阶段文档：** `PROJECT_PHASES.md` 阶段 4.0 / 4.1。

---

## 项目工程约束（来自 AGENTS.md）

- **不自动 commit / push**：本 plan 的 "Commit" 步骤标注为 **等用户确认时机**，executing-plans 不应自动跑 commit。完成若干相关 task 后请向用户报告并询问是否要 commit。
- 测试与脚本一律使用 `.venv/Scripts/python.exe`：`& ".venv/Scripts/python.exe" -m pytest`。
- 不能在没有验证输出的情况下声称"完成 / 通过 / 可用"。先跑测试或脚本，看到输出再下结论。
- 仅完成阶段 4.0 + 4.1，**不做** 4.2 (Expected Risk)、4.3 (Edge Safety)、4.4 (Piece Importance)、GUI 建议走法集成——这些等 4.1 出数据后单独规划。
- CLI 参数与 `PROJECT_PHASES.md` 推荐示例的命名差异：本计划使用 `--red <kind>` / `--blue <kind>` 替代 `--black / --white`，与代码内 `Player.RED / Player.BLUE` 对齐；JSON 报告字段同步使用 `red_win_rate / blue_win_rate / draw_rate`。Task 6 包含一处 `PROJECT_PHASES.md` 文档同步修正。

---

## 文件结构

**新建：**
- `ai/match.py` —— `AIPlayer`-兼容的对战 runner、`MatchResult`、默认起始局面、AI 工厂。
- `ai/evaluator.py` —— 评估函数与权重常量。
- `ai/greedy_ai.py` —— `GreedyAI` 类。
- `scripts/run_match.py` —— 单局 CLI。
- `scripts/quick_bench.py` —— 批量 bench CLI + JSON 报告写入。
- `tests/test_ai_match.py` —— 起始局面 / play_one_game / build_ai 测试。
- `tests/test_ai_basic.py` —— RandomAI / GreedyAI 行为测试。
- `tests/test_evaluator.py` —— evaluator 单元测试。

**修改：**
- `ai/__init__.py` —— 新增 `AIPlayer` Protocol 与 `RandomAI` 类导出，保留 `choose_random_move` 函数。
- `ai/random_ai.py` —— 在现有函数上新增 `RandomAI` 类。
- `PROJECT_PHASES.md` —— 把阶段 4.0 验收命令里的 `--black random --white random` 改为 `--red random --blue random`，字段示例同步更新（Task 6 末尾步骤）。

**目录假设（无需创建）：**
- `replays/`、`reports/`、`tests/` 已存在。

---

## Task 1：AIPlayer Protocol + RandomAI 类

**目标：** 在 `ai/` 下定义 AI 协议；把 `choose_random_move` 包装为 `RandomAI` 类，便于 harness 统一调用。`name` 字段后续进 reports。原函数保留，避免破坏未来可能的直接调用。

**Files:**
- Modify: `ai/__init__.py`
- Modify: `ai/random_ai.py`
- Test: `tests/test_ai_basic.py`（新建）

### Step 1: 写失败测试 —— RandomAI 类与 AIPlayer 协议

- [ ] 新建 `tests/test_ai_basic.py`，写入：

```python
import random

import pytest

from ai import AIPlayer, RandomAI
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_random_ai_satisfies_aiplayer_shape():
    # AIPlayer 是 typing.Protocol（无 @runtime_checkable），不能用 isinstance；
    # 这里用结构性检查保证字段齐全且可调用。
    ai = RandomAI(rng=random.Random(0))
    assert ai.name == "random"
    assert hasattr(ai, "choose_move")
    assert callable(ai.choose_move)
    # 同时确认 AIPlayer 这个名字被导出（仅作 import smoke）
    assert AIPlayer is not None


def test_random_ai_choose_move_returns_legal_move():
    ai = RandomAI(rng=random.Random(0))
    state = make_state(red={1: Position(2, 2)})

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.player is Player.RED
    legal = state.legal_moves(Player.RED, 1)
    assert move in legal


def test_random_ai_returns_none_when_no_legal_moves():
    ai = RandomAI(rng=random.Random(0))
    state = make_state(red={}, blue={1: Position(0, 0)}, current_player=Player.RED)

    assert ai.choose_move(state, dice=1) is None


def test_random_ai_is_deterministic_under_same_seed():
    state = make_state(red={1: Position(0, 0), 2: Position(1, 1), 3: Position(2, 2)})

    ai_a = RandomAI(rng=random.Random(2026))
    ai_b = RandomAI(rng=random.Random(2026))

    moves_a = [ai_a.choose_move(state, dice=d) for d in [1, 2, 3, 1, 2, 3]]
    moves_b = [ai_b.choose_move(state, dice=d) for d in [1, 2, 3, 1, 2, 3]]

    assert moves_a == moves_b


def test_random_ai_custom_name():
    ai = RandomAI(rng=random.Random(0), name="random_v2")
    assert ai.name == "random_v2"
```

> 注意：`isinstance(ai, AIPlayer)` 在 `Protocol` 不带 `@runtime_checkable` 时为 `False`，所以测试用 `hasattr` 校验接口形状，不强制 `runtime_checkable`，避免协议设计被测试反向绑死。

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_basic.py -v
```

预期：5 条测试全部 ImportError 或 AttributeError 失败（`RandomAI` 类与 `AIPlayer` 都还不存在）。

### Step 3: 在 `ai/random_ai.py` 增加 `RandomAI` 类

- [ ] 把 `ai/random_ai.py` 全文替换为：

```python
from __future__ import annotations

import random

from core.game_state import GameState
from core.move import Move


def choose_random_move(
    state: GameState,
    dice: int,
    rng: random.Random | None = None,
) -> Move | None:
    moves = state.legal_moves(state.current_player, dice)
    if not moves:
        return None
    chooser = rng or random
    return chooser.choice(moves)


class RandomAI:
    """随机 AI：在合法走法中均匀随机抽签。"""

    def __init__(self, *, rng: random.Random | None = None, name: str = "random") -> None:
        self._rng = rng or random.Random()
        self.name = name

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        return choose_random_move(state, dice, rng=self._rng)
```

### Step 4: 在 `ai/__init__.py` 暴露 Protocol 与 RandomAI

- [ ] 把 `ai/__init__.py` 全文替换为：

```python
from __future__ import annotations

from typing import Protocol

from core.game_state import GameState
from core.move import Move

from ai.random_ai import RandomAI, choose_random_move


class AIPlayer(Protocol):
    """所有 AI 必须满足的协议：有可读的 ``name``，按 ``(state, dice)`` 给出走法。"""

    name: str

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...


__all__ = [
    "AIPlayer",
    "RandomAI",
    "choose_random_move",
]
```

### Step 5: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_basic.py -v
```

预期：5 条测试全部通过。

### Step 6: 跑全量回归测试

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest -v
```

预期：之前所有测试仍然通过（`ai/__init__.py` 重写没破坏向后兼容）。

### Step 7: Commit（**等用户确认时机**）

```bash
git add ai/__init__.py ai/random_ai.py tests/test_ai_basic.py
git commit -m "feat(ai): add AIPlayer protocol and RandomAI class wrapper"
```

---

## Task 2：默认起始局面 + MatchResult 数据结构

**目标：** 在 `ai/match.py` 中提供唯一的 5x5 三角形开局（红左上、蓝右下，对称布局），以及描述一局结果的 `MatchResult`。这是 harness 的"棋盘 + 比分卡"。

**Files:**
- Create: `ai/match.py`
- Test: `tests/test_ai_match.py`（新建）

### Step 1: 写失败测试 —— 默认起始局面

- [ ] 新建 `tests/test_ai_match.py`，写入：

```python
import random

import pytest

from ai.match import MatchResult, default_starting_state
from core.types import Player, Position


def test_default_starting_state_has_six_pieces_per_side():
    state = default_starting_state()

    assert sum(1 for p in state.pieces[Player.RED].values() if p.alive) == 6
    assert sum(1 for p in state.pieces[Player.BLUE].values() if p.alive) == 6
    assert state.current_player is Player.RED


def test_default_starting_state_red_triangle_top_left():
    state = default_starting_state()

    expected_red_positions = {
        1: Position(0, 0),
        2: Position(0, 1),
        3: Position(0, 2),
        4: Position(1, 0),
        5: Position(1, 1),
        6: Position(2, 0),
    }
    for piece_id, position in expected_red_positions.items():
        assert state.pieces[Player.RED][piece_id].position == position


def test_default_starting_state_blue_triangle_bottom_right():
    state = default_starting_state()

    expected_blue_positions = {
        1: Position(4, 4),
        2: Position(4, 3),
        3: Position(4, 2),
        4: Position(3, 4),
        5: Position(3, 3),
        6: Position(2, 4),
    }
    for piece_id, position in expected_blue_positions.items():
        assert state.pieces[Player.BLUE][piece_id].position == position


def test_default_starting_state_is_independent_per_call():
    state_a = default_starting_state()
    state_b = default_starting_state()
    state_a.pieces[Player.RED][1].alive = False

    assert state_b.pieces[Player.RED][1].alive is True


def test_match_result_step_time_aggregates():
    record_placeholder = None  # 暂用 None；play_one_game 测试会传真的 GameRecord
    result = MatchResult(
        winner=Player.RED,
        turns=3,
        illegal_moves=0,
        crashes=0,
        record=record_placeholder,
        step_times_ms=[1.0, 3.0, 2.0],
    )

    assert result.avg_step_time_ms == pytest.approx(2.0)
    assert result.max_step_time_ms == pytest.approx(3.0)


def test_match_result_step_time_aggregates_empty():
    result = MatchResult(
        winner=None,
        turns=0,
        illegal_moves=0,
        crashes=0,
        record=None,
        step_times_ms=[],
    )

    assert result.avg_step_time_ms == 0.0
    assert result.max_step_time_ms == 0.0
```

> 关于 Task 2 测试中 `record_placeholder = None`：MatchResult 是数据容器，对 record 不做类型校验，None 可通过；Task 3 的 play_one_game 测试会传真的 `GameRecord`。

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py -v
```

预期：6 条测试全部 ImportError 失败（`ai/match.py` 不存在）。

### Step 3: 创建 `ai/match.py`，实现起始局面与 MatchResult

- [ ] 新建 `ai/match.py`：

```python
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
    """返回 5x5 标准三角形开局：红左上、蓝右下，对称布局。

    本阶段只提供一种固定开局，便于 harness 复现。阶段 7 会引入候选开局库。
    棋子编号按"由内向外、按行从左到右"读取，左下/右上为 6 号。
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
```

### Step 4: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py -v
```

预期：6 条测试全部通过。

### Step 5: Commit（**等用户确认时机**）

```bash
git add ai/match.py tests/test_ai_match.py
git commit -m "feat(ai): default starting layout and MatchResult dataclass"
```

---

## Task 3：play_one_game 单局对战循环

**目标：** 实现一局完整 AI vs AI 对战循环：每回合掷骰 → 当前 AI 出招 → 校验 / 应用 → 检查胜负或 max_turns。illegal/crash/no-move 一律按当前方负处理，并把对应计数填进 `MatchResult`。

**Files:**
- Modify: `ai/match.py`
- Test: `tests/test_ai_match.py`

### Step 1: 写失败测试 —— play_one_game 基本行为

- [ ] 在 `tests/test_ai_match.py` 末尾追加：

```python
from ai.match import play_one_game
from ai.random_ai import RandomAI


class _AlwaysCrashAI:
    name = "crash_bot"

    def choose_move(self, state, dice):
        raise RuntimeError("boom")


class _IllegalMoveAI:
    """总是给出非法 Move（捏造一个不在 legal_moves 里的目的地）。"""

    name = "illegal_bot"

    def choose_move(self, state, dice):
        from core.move import Move
        from core.types import Position

        # 强行造一个出界的走法，apply_move 会抛 ValueError
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        sample = legal[0]
        return Move(
            player=sample.player,
            piece_id=sample.piece_id,
            from_pos=sample.from_pos,
            to_pos=Position(99, 99),
            is_capture=False,
            captured_piece=None,
        )


class _NeverMoveAI:
    name = "never_bot"

    def choose_move(self, state, dice):
        return None


def test_play_one_game_random_vs_random_terminates_with_winner_or_draw():
    red_ai = RandomAI(rng=random.Random(2026))
    blue_ai = RandomAI(rng=random.Random(2027))
    dice_rng = random.Random(2028)

    result = play_one_game(red_ai=red_ai, blue_ai=blue_ai, dice_rng=dice_rng, max_turns=200)

    assert result.illegal_moves == 0
    assert result.crashes == 0
    assert 0 < result.turns <= 200
    assert result.record is not None
    assert len(result.record.steps) == result.turns


def test_play_one_game_is_deterministic_with_same_seeds():
    def run():
        return play_one_game(
            red_ai=RandomAI(rng=random.Random(2026)),
            blue_ai=RandomAI(rng=random.Random(2027)),
            dice_rng=random.Random(2028),
            max_turns=200,
        )

    a = run()
    b = run()

    assert a.winner == b.winner
    assert a.turns == b.turns
    assert [s.move.to_dict() for s in a.record.steps] == [s.move.to_dict() for s in b.record.steps]


def test_play_one_game_crash_is_counted_and_opponent_wins():
    result = play_one_game(
        red_ai=_AlwaysCrashAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    assert result.crashes == 1
    assert result.winner is Player.BLUE


def test_play_one_game_illegal_move_is_counted_and_opponent_wins():
    result = play_one_game(
        red_ai=_IllegalMoveAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    assert result.illegal_moves == 1
    assert result.winner is Player.BLUE


def test_play_one_game_no_legal_move_forfeits_to_opponent():
    result = play_one_game(
        red_ai=_NeverMoveAI(),
        blue_ai=RandomAI(rng=random.Random(0)),
        dice_rng=random.Random(0),
        max_turns=50,
    )

    # 没合法走法返回 None：当前方判负，不计 illegal/crash
    assert result.crashes == 0
    assert result.illegal_moves == 0
    assert result.winner is Player.BLUE


def test_play_one_game_step_times_recorded():
    result = play_one_game(
        red_ai=RandomAI(rng=random.Random(2026)),
        blue_ai=RandomAI(rng=random.Random(2027)),
        dice_rng=random.Random(2028),
        max_turns=50,
    )

    # 每个 turn 都有 step_time，包含最终那一步
    assert len(result.step_times_ms) == result.turns
    assert all(t >= 0.0 for t in result.step_times_ms)
```

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py -v
```

预期：6 条新测试 ImportError 失败（`play_one_game` 还不存在），原 6 条仍通过。

### Step 3: 在 `ai/match.py` 实现 `play_one_game`

- [ ] 在 `ai/match.py` 末尾追加：

```python
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
```

### Step 4: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py -v
```

预期：12 条测试全部通过。

### Step 5: 跑一次随机自对弈做 smoke

- [ ] 运行（验证 100 局 RandomAI 自对弈在可接受时间内完成、零 illegal / crash）：

```bash
& ".venv/Scripts/python.exe" -c "
import random, time
from ai.match import play_one_game
from ai.random_ai import RandomAI

start = time.perf_counter()
total_illegal = 0
total_crash = 0
winners = {'RED': 0, 'BLUE': 0, 'DRAW': 0}
for i in range(100):
    seed = 2026 * 100000 + i
    r = play_one_game(
        red_ai=RandomAI(rng=random.Random(seed + 1)),
        blue_ai=RandomAI(rng=random.Random(seed + 2)),
        dice_rng=random.Random(seed),
        max_turns=200,
    )
    total_illegal += r.illegal_moves
    total_crash += r.crashes
    key = r.winner.value.upper() if r.winner else 'DRAW'
    winners[key] = winners.get(key, 0) + 1
elapsed = time.perf_counter() - start
print(f'100 games in {elapsed:.2f}s, winners={winners}, illegal={total_illegal}, crashes={total_crash}')
"
```

预期：30 秒内完成，`illegal=0`、`crashes=0`，winners 各方都有数（红蓝大致接近，但允许 RandomAI 的明显先手优势）。

### Step 6: Commit（**等用户确认时机**）

```bash
git add ai/match.py tests/test_ai_match.py
git commit -m "feat(ai): play_one_game runner with crash/illegal/no-move handling"
```

---

## Task 4：build_ai 工厂

**目标：** 给 CLI / bench 一个统一入口，按字符串 kind 构造带种子的 AI。当前只支持 `random`，4.1 完成后会自动支持 `greedy`（改一行注册即可）。

**Files:**
- Modify: `ai/match.py`
- Test: `tests/test_ai_match.py`

### Step 1: 写失败测试

- [ ] 在 `tests/test_ai_match.py` 末尾追加：

```python
from ai.match import build_ai


def test_build_ai_random_returns_random_ai():
    ai = build_ai("random", seed=42)
    assert ai.name == "random"
    assert hasattr(ai, "choose_move")


def test_build_ai_random_seeded_is_deterministic():
    ai_a = build_ai("random", seed=42)
    ai_b = build_ai("random", seed=42)
    state = default_starting_state()

    moves_a = [ai_a.choose_move(state, dice=d) for d in [1, 2, 3, 4, 5, 6]]
    moves_b = [ai_b.choose_move(state, dice=d) for d in [1, 2, 3, 4, 5, 6]]

    assert moves_a == moves_b


def test_build_ai_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="unknown AI"):
        build_ai("does_not_exist", seed=0)
```

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py::test_build_ai_random_returns_random_ai tests/test_ai_match.py::test_build_ai_random_seeded_is_deterministic tests/test_ai_match.py::test_build_ai_unknown_kind_raises_value_error -v
```

预期：3 条测试 ImportError 失败。

### Step 3: 在 `ai/match.py` 实现 `build_ai`

- [ ] 在 `ai/match.py` 末尾追加：

```python
def build_ai(kind: str, *, seed: int | None = None) -> "AIPlayer":
    """按 kind 字符串构造带种子的 AI。后续 4.1 会在这里注册 ``greedy``。"""
    rng = random.Random(seed)
    if kind == "random":
        from ai.random_ai import RandomAI
        return RandomAI(rng=rng, name="random")
    raise ValueError(f"unknown AI: {kind!r}")
```

### Step 4: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_match.py -v
```

预期：15 条测试全部通过。

### Step 5: Commit（**等用户确认时机**）

```bash
git add ai/match.py tests/test_ai_match.py
git commit -m "feat(ai): build_ai factory by string kind"
```

---

## Task 5：scripts/run_match.py 单局 CLI

**目标：** 跑一局 AI vs AI，把结果以 JSON 打到 stdout，并把 GameRecord 存到 `replays/match_<timestamp>_<red>_vs_<blue>.json`。便于手工调试单局棋谱。

**Files:**
- Create: `scripts/run_match.py`

### Step 1: 实现 `scripts/run_match.py`

- [ ] 新建 `scripts/run_match.py`：

```python
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a single AI vs AI Einstein chess game and dump JSON + replay.")
    parser.add_argument("--red", required=True, help="Red AI kind (e.g. random / greedy)")
    parser.add_argument("--blue", required=True, help="Blue AI kind (e.g. random / greedy)")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed for dice and AI RNGs")
    parser.add_argument("--max-turns", type=int, default=200, help="Hard cap on total half-moves; reaching it = draw")
    parser.add_argument(
        "--replay-dir",
        default=str(ROOT / "replays"),
        help="Directory to write the replay JSON file",
    )
    parser.add_argument(
        "--no-save-replay",
        action="store_true",
        help="Skip writing the replay file (useful when calling from other scripts)",
    )
    args = parser.parse_args(argv)

    red_ai = build_ai(args.red, seed=args.seed * 3 + 1)
    blue_ai = build_ai(args.blue, seed=args.seed * 3 + 2)
    dice_rng = random.Random(args.seed * 3)

    result = play_one_game(
        red_ai=red_ai,
        blue_ai=blue_ai,
        dice_rng=dice_rng,
        max_turns=args.max_turns,
    )

    replay_path: str | None = None
    if not args.no_save_replay and result.record is not None:
        replay_dir = Path(args.replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        replay_path = str(replay_dir / f"match_{timestamp}_{args.red}_vs_{args.blue}_seed{args.seed}.json")
        result.record.save(replay_path)

    summary = {
        "red_ai": red_ai.name,
        "blue_ai": blue_ai.name,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "winner": result.winner.value if result.winner else None,
        "turns": result.turns,
        "illegal_moves": result.illegal_moves,
        "crashes": result.crashes,
        "avg_step_time_ms": round(result.avg_step_time_ms, 3),
        "max_step_time_ms": round(result.max_step_time_ms, 3),
        "replay_path": replay_path,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: 手动跑一局，验证 JSON 输出与 replay 文件生成

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" scripts/run_match.py --red random --blue random --seed 2026 --max-turns 200
```

预期：
- stdout 是合法 JSON，包含 `winner / turns / illegal_moves / crashes / replay_path` 字段。
- `illegal_moves == 0`、`crashes == 0`。
- `replays/` 下生成一个 `match_*_random_vs_random_seed2026.json`。

### Step 3: 验证 replay 可被 GameRecord.load 反序列化

- [ ] 运行（替换 `<path>` 为上一步生成的实际路径）：

```bash
& ".venv/Scripts/python.exe" -c "
import json, glob, os
from record.game_record import GameRecord
files = sorted(glob.glob('replays/match_*_random_vs_random_seed2026.json'), key=os.path.getmtime)
path = files[-1]
record = GameRecord.load(path)
print(f'loaded {path}: steps={len(record.steps)}, last_player={record.steps[-1].player.value if record.steps else None}')
"
```

预期：打印步数 > 0，无异常。

### Step 4: Commit（**等用户确认时机**）

```bash
git add scripts/run_match.py
git commit -m "feat(scripts): run_match.py single-game CLI with replay export"
```

---

## Task 6：scripts/quick_bench.py 批量 bench CLI + JSON 报告

**目标：** 跑 N 局，每局用确定性派生种子保证可复现；输出 stdout 摘要 + `reports/bench_<timestamp>.json` 报告，包含 PROJECT_PHASES.md 列出的全部字段。这是 4.0 验收的主入口。

**Files:**
- Create: `scripts/quick_bench.py`
- Modify: `PROJECT_PHASES.md`（同步 CLI 命名）

### Step 1: 实现 `scripts/quick_bench.py`

- [ ] 新建 `scripts/quick_bench.py`：

```python
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game
from core.types import Player


def _aggregate(results) -> dict:
    games = len(results)
    if games == 0:
        return {}

    winners = {Player.RED: 0, Player.BLUE: 0, None: 0}
    total_turns = 0
    total_illegal = 0
    total_crashes = 0
    all_step_times: list[float] = []

    for r in results:
        winners[r.winner] = winners.get(r.winner, 0) + 1
        total_turns += r.turns
        total_illegal += r.illegal_moves
        total_crashes += r.crashes
        all_step_times.extend(r.step_times_ms)

    avg_step = sum(all_step_times) / len(all_step_times) if all_step_times else 0.0
    max_step = max(all_step_times) if all_step_times else 0.0

    return {
        "games": games,
        "red_wins": winners[Player.RED],
        "blue_wins": winners[Player.BLUE],
        "draws": winners[None],
        "red_win_rate": winners[Player.RED] / games,
        "blue_win_rate": winners[Player.BLUE] / games,
        "draw_rate": winners[None] / games,
        "average_turns": total_turns / games,
        "illegal_moves": total_illegal,
        "crashes": total_crashes,
        "timeouts": 0,  # 阶段 4 还没引入单步时限
        "average_step_time_ms": avg_step,
        "max_step_time_ms": max_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run N AI vs AI games and emit a JSON benchmark report.")
    parser.add_argument("--red", required=True, help="Red AI kind")
    parser.add_argument("--blue", required=True, help="Blue AI kind")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed; per-game seed = master*100000 + i")
    parser.add_argument("--max-turns", type=int, default=200, help="Per-game half-move cap; reaching it = draw")
    parser.add_argument(
        "--report-dir",
        default=str(ROOT / "reports"),
        help="Directory to write the JSON report file",
    )
    parser.add_argument(
        "--no-save-report",
        action="store_true",
        help="Skip writing the report file (only print summary to stdout)",
    )
    args = parser.parse_args(argv)

    start = time.perf_counter()
    results = []
    for i in range(args.games):
        per_game_seed = args.seed * 100_000 + i
        red_ai = build_ai(args.red, seed=per_game_seed * 3 + 1)
        blue_ai = build_ai(args.blue, seed=per_game_seed * 3 + 2)
        dice_rng = random.Random(per_game_seed * 3)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=args.max_turns,
        )
        results.append(result)
    elapsed = time.perf_counter() - start

    summary = _aggregate(results)
    summary.update({
        "red_ai": args.red,
        "blue_ai": args.blue,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "wall_seconds": round(elapsed, 3),
    })

    report_path: str | None = None
    if not args.no_save_report:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = str(report_dir / f"bench_{timestamp}_{args.red}_vs_{args.blue}.json")
        Path(report_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["report_path"] = report_path

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: 手动跑 100 局 random vs random，验证耗时与零 illegal/crash

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" scripts/quick_bench.py --red random --blue random --games 100 --seed 2026 --max-turns 200
```

预期：
- stdout JSON 中 `illegal_moves == 0`、`crashes == 0`、`timeouts == 0`、`wall_seconds < 30`。
- `red_win_rate + blue_win_rate + draw_rate == 1.0`（浮点近似）。
- `reports/` 下生成一个 `bench_*_random_vs_random.json`。

### Step 3: 同步 PROJECT_PHASES.md 中阶段 4.0 推荐命令

- [ ] 编辑 `PROJECT_PHASES.md`，把阶段 4.0 验收标准里的：

```text
python scripts/quick_bench.py --black random --white random --games 100 --seed 2026
```

改为：

```text
python scripts/quick_bench.py --red random --blue random --games 100 --seed 2026
```

并把：

```text
black_win_rate / white_win_rate / draw_rate
```

改为：

```text
red_win_rate / blue_win_rate / draw_rate
```

> Step 3 仅修改 `PROJECT_PHASES.md` 这一处文档（阶段 4 章节）。阶段 5 的 tournament 命令暂不改，等到了阶段 5 再统一处理。

### Step 4: Commit（**等用户确认时机**）

```bash
git add scripts/quick_bench.py PROJECT_PHASES.md
git commit -m "feat(scripts): quick_bench.py batch CLI + sync PROJECT_PHASES wording"
```

---

## Task 7：阶段 4.0 验收 —— 100 局 random vs random

**目标：** 用 quick_bench 跑 PROJECT_PHASES.md 阶段 4.0 验收命令；确认通过后保留报告作为 baseline。

**Files:**
- 无新建/修改，只跑命令并在 reports/ 留档。

### Step 1: 跑验收命令

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" scripts/quick_bench.py --red random --blue random --games 100 --seed 2026 --max-turns 200
```

### Step 2: 检查输出，对照阶段 4.0 验收标准

- [ ] 验收检查清单：
  - `illegal_moves == 0`：✓/✗
  - `crashes == 0`：✓/✗
  - `timeouts == 0`：✓/✗
  - `wall_seconds < 30.0`：✓/✗
  - `report_path` 文件存在：✓/✗

如果任意一项失败，**不要**进入 Task 8，先排查根因（最常见：max_turns 太小导致 draw_rate 异常高；或者 RandomAI seed 派生有 bug）。

### Step 3: 把这次报告路径记到提交信息里

- [ ] Commit（**等用户确认时机**）：

```bash
git add reports/bench_*_random_vs_random.json
git commit -m "chore(reports): phase 4.0 baseline — random vs random 100 games"
```

---

## Task 8：基础评估函数 evaluator.py

**目标：** 实现纯函数 `evaluate(state, perspective) -> float`，包含三块：
1. 终局检查：胜方 = +WIN_SCORE，败方 = -WIN_SCORE。
2. 距离差：双方所有存活子到各自目标角的 chebyshev 距离之和的差。
3. 子力差：存活子数差。

不实现 4.2 的 Expected Risk、4.3 的 Edge Safety、4.4 的 Piece Importance —— 这些等 4.1 跑出 ≥95% 后单独规划。

**Files:**
- Create: `ai/evaluator.py`
- Test: `tests/test_evaluator.py`（新建）

### Step 1: 写失败测试 —— 终局 / 距离 / 子力

- [ ] 新建 `tests/test_evaluator.py`：

```python
from ai.evaluator import (
    DISTANCE_WEIGHT,
    MATERIAL_WEIGHT,
    WIN_SCORE,
    chebyshev_distance,
    evaluate,
)
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def test_chebyshev_distance_diagonal_counts_as_one_per_step():
    assert chebyshev_distance(Position(0, 0), Position(0, 0)) == 0
    assert chebyshev_distance(Position(0, 0), Position(2, 2)) == 2
    assert chebyshev_distance(Position(1, 3), Position(4, 4)) == 3
    assert chebyshev_distance(Position(4, 4), Position(0, 0)) == 4


def test_evaluate_red_at_target_corner_wins():
    state = make_state(red={1: Position(4, 4)}, blue={1: Position(0, 0)})

    assert evaluate(state, Player.RED) == WIN_SCORE
    assert evaluate(state, Player.BLUE) == -WIN_SCORE


def test_evaluate_blue_at_target_corner_wins():
    # 蓝到达 (0,0) 是蓝方目标角；红在别处，不重叠。
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 0)})

    assert evaluate(state, Player.BLUE) == WIN_SCORE
    assert evaluate(state, Player.RED) == -WIN_SCORE


def test_evaluate_red_all_blue_dead_wins_by_capture():
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(4, 4)})
    state.pieces[Player.BLUE][1].alive = False

    assert evaluate(state, Player.RED) == WIN_SCORE
    assert evaluate(state, Player.BLUE) == -WIN_SCORE


def test_evaluate_prefers_state_where_own_piece_is_closer_to_target():
    farther = make_state(red={1: Position(0, 0)}, blue={1: Position(0, 4)})
    closer = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})

    assert evaluate(closer, Player.RED) > evaluate(farther, Player.RED)


def test_evaluate_prefers_state_where_opponent_is_farther_from_their_target():
    # 红视角：蓝距离自己目标(0,0)越远越好
    blue_close = make_state(red={1: Position(0, 0)}, blue={1: Position(1, 1)})
    blue_far = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})

    assert evaluate(blue_far, Player.RED) > evaluate(blue_close, Player.RED)


def test_evaluate_prefers_more_material():
    one_red_dead = make_state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(4, 4)},
    )
    one_red_dead.pieces[Player.RED][2].alive = False

    both_red_alive = make_state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(4, 4)},
    )

    assert evaluate(both_red_alive, Player.RED) > evaluate(one_red_dead, Player.RED)


def test_evaluate_is_zero_sum_for_non_terminal_state():
    state = make_state(
        red={1: Position(1, 0), 2: Position(2, 1)},
        blue={1: Position(3, 4), 2: Position(2, 3)},
    )

    red_score = evaluate(state, Player.RED)
    blue_score = evaluate(state, Player.BLUE)

    assert red_score == -blue_score


def test_evaluate_weights_are_finite_and_positive():
    assert WIN_SCORE > 0
    assert DISTANCE_WEIGHT > 0
    assert MATERIAL_WEIGHT > 0
    # 单子被吃比一个距离单位的代价大得多
    assert MATERIAL_WEIGHT > DISTANCE_WEIGHT
```

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_evaluator.py -v
```

预期：9 条测试 ImportError 失败。

### Step 3: 实现 `ai/evaluator.py`

- [ ] 新建 `ai/evaluator.py`：

```python
from __future__ import annotations

from core.game_state import GameState
from core.rules import target_corner
from core.types import Player, Position


WIN_SCORE: float = 1_000_000.0
DISTANCE_WEIGHT: float = 1.0
MATERIAL_WEIGHT: float = 10.0


def chebyshev_distance(a: Position, b: Position) -> int:
    """Chebyshev / Chess-king distance：因为本游戏走法包含对角线，单步等于 1。"""
    return max(abs(a.row - b.row), abs(a.col - b.col))


def evaluate(state: GameState, perspective: Player) -> float:
    """从 ``perspective`` 视角对 ``state`` 打分。

    终局直接返回 ±WIN_SCORE。否则线性组合：
    - 距离差：对方距其目标角越远越好；自己距己方目标角越近越好。
    - 子力差：自己存活子越多越好。
    """
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    own_pieces = state.pieces[perspective]
    opp_pieces = state.pieces[perspective.opponent]
    own_target = target_corner(perspective)
    opp_target = target_corner(perspective.opponent)

    own_distance_total = sum(
        chebyshev_distance(p.position, own_target) for p in own_pieces.values() if p.alive
    )
    opp_distance_total = sum(
        chebyshev_distance(p.position, opp_target) for p in opp_pieces.values() if p.alive
    )
    own_alive = sum(1 for p in own_pieces.values() if p.alive)
    opp_alive = sum(1 for p in opp_pieces.values() if p.alive)

    return (
        DISTANCE_WEIGHT * (opp_distance_total - own_distance_total)
        + MATERIAL_WEIGHT * (own_alive - opp_alive)
    )
```

### Step 4: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_evaluator.py -v
```

预期：9 条测试全部通过。

### Step 5: Commit（**等用户确认时机**）

```bash
git add ai/evaluator.py tests/test_evaluator.py
git commit -m "feat(ai): basic evaluator with terminal+distance+material"
```

---

## Task 9：GreedyAI 实现 + 注册到工厂

**目标：** 实现 `GreedyAI`：枚举当前 `legal_moves` → 对每个 move 临时 apply → `evaluate(state, mover)` → undo → 取分数最高，平分用 RNG 抽签。注册到 `build_ai`。

**Files:**
- Create: `ai/greedy_ai.py`
- Modify: `ai/match.py`（在 build_ai 中注册 greedy）
- Modify: `ai/__init__.py`（导出 GreedyAI）
- Test: `tests/test_ai_basic.py`

### Step 1: 写失败测试 —— GreedyAI 行为

- [ ] 在 `tests/test_ai_basic.py` 末尾追加：

```python
from ai.greedy_ai import GreedyAI


def test_greedy_ai_is_protocol_compatible():
    ai = GreedyAI(rng=random.Random(0))
    assert ai.name == "greedy"
    assert hasattr(ai, "choose_move")


def test_greedy_ai_picks_winning_move_when_available():
    # 红 6 号在 (4,3)，dice=6 → 必走 6 号；(4,4) 是目标角并且空，应选这步胜
    state = make_state(
        red={6: Position(4, 3), 1: Position(0, 0)},
        blue={1: Position(0, 4)},
    )
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=6)

    assert move is not None
    assert move.to_pos == Position(4, 4)


def test_greedy_ai_picks_capture_when_capture_also_advances():
    # 红 1 号在 (3,3)，蓝 5 号在 (4,4)：吃掉蓝 5 号既到目标角也吃子，必选
    state = make_state(red={1: Position(3, 3)}, blue={5: Position(4, 4)})
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.to_pos == Position(4, 4)
    assert move.is_capture is True


def test_greedy_ai_prefers_advancing_toward_target():
    # 红 1 号在 (2,2)，dice=1，三个合法走法：
    #   (3,2) 距(4,4)=2、(2,3) 距(4,4)=2、(3,3) 距(4,4)=1
    # GreedyAI 应选 (3,3)
    state = make_state(red={1: Position(2, 2)}, blue={1: Position(0, 4)})
    ai = GreedyAI(rng=random.Random(0))

    move = ai.choose_move(state, dice=1)

    assert move is not None
    assert move.to_pos == Position(3, 3)


def test_greedy_ai_returns_none_when_no_legal_moves():
    state = make_state(red={}, blue={1: Position(4, 4)}, current_player=Player.RED)
    ai = GreedyAI(rng=random.Random(0))

    assert ai.choose_move(state, dice=1) is None


def test_greedy_ai_does_not_mutate_state():
    state = make_state(red={1: Position(2, 2), 2: Position(3, 1)}, blue={1: Position(0, 4)})
    before = state.serialize()
    ai = GreedyAI(rng=random.Random(0))

    ai.choose_move(state, dice=1)
    ai.choose_move(state, dice=2)

    assert state.serialize() == before


def test_greedy_ai_is_deterministic_under_same_seed():
    state = make_state(red={1: Position(0, 0), 2: Position(1, 1)}, blue={1: Position(4, 4)})

    a = GreedyAI(rng=random.Random(42))
    b = GreedyAI(rng=random.Random(42))

    assert a.choose_move(state, dice=1) == b.choose_move(state, dice=1)
    assert a.choose_move(state, dice=2) == b.choose_move(state, dice=2)


def test_build_ai_supports_greedy():
    from ai.match import build_ai

    ai = build_ai("greedy", seed=2026)

    assert ai.name == "greedy"
    assert hasattr(ai, "choose_move")
```

### Step 2: 跑测试，确认失败

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_basic.py -v
```

预期：8 条新测试 ImportError / build_ai-ValueError 失败。

### Step 3: 实现 `ai/greedy_ai.py`

- [ ] 新建 `ai/greedy_ai.py`：

```python
from __future__ import annotations

import random

from ai.evaluator import evaluate
from core.game_state import GameState
from core.move import Move


class GreedyAI:
    """贪心 AI：对每个合法走法跑一步前瞻 + 评估，挑分数最高，多并列用 RNG 抽签。"""

    def __init__(self, *, rng: random.Random | None = None, name: str = "greedy") -> None:
        self._rng = rng or random.Random()
        self.name = name

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal_moves = state.legal_moves(state.current_player, dice)
        if not legal_moves:
            return None

        mover = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal_moves:
            applied = state.apply_move(move, dice=dice)
            try:
                score = evaluate(state, perspective=mover)
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        return self._rng.choice(best_moves)
```

### Step 4: 在 `ai/match.py` 的 `build_ai` 注册 greedy

- [ ] 在 `ai/match.py` 中，找到：

```python
def build_ai(kind: str, *, seed: int | None = None) -> "AIPlayer":
    """按 kind 字符串构造带种子的 AI。后续 4.1 会在这里注册 ``greedy``。"""
    rng = random.Random(seed)
    if kind == "random":
        from ai.random_ai import RandomAI
        return RandomAI(rng=rng, name="random")
    raise ValueError(f"unknown AI: {kind!r}")
```

替换为：

```python
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
```

### Step 5: 在 `ai/__init__.py` 导出 GreedyAI

- [ ] 把 `ai/__init__.py` 的现有内容修改为：

```python
from __future__ import annotations

from typing import Protocol

from core.game_state import GameState
from core.move import Move

from ai.greedy_ai import GreedyAI
from ai.random_ai import RandomAI, choose_random_move


class AIPlayer(Protocol):
    """所有 AI 必须满足的协议：有可读的 ``name``，按 ``(state, dice)`` 给出走法。"""

    name: str

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...


__all__ = [
    "AIPlayer",
    "GreedyAI",
    "RandomAI",
    "choose_random_move",
]
```

### Step 6: 跑测试，确认通过

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_basic.py tests/test_ai_match.py tests/test_evaluator.py -v
```

预期：所有测试通过（test_ai_basic.py 13 条 + test_ai_match.py 15 条 + test_evaluator.py 9 条）。

### Step 7: 跑全量回归

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" -m pytest -v
```

预期：全部测试通过；阶段 1-3 的旧测试不受影响。

### Step 8: Commit（**等用户确认时机**）

```bash
git add ai/greedy_ai.py ai/match.py ai/__init__.py tests/test_ai_basic.py
git commit -m "feat(ai): GreedyAI with one-step lookahead and registry entry"
```

---

## Task 8.5：evaluator 加 stuck_penalty（计划外修订，决策来自 reports/4-1-failure-analysis.md）

**目标：** 在 evaluator 里增加 stuck 子惩罚——任何己方存活子若 `legal_moves_for_piece` 为空则记一份惩罚分。这是简化版的 expected forfeit risk，主要避免 GreedyAI 让自家角子长期被自家围死、被 dice 强制选中后 forfeit。

**Files:**
- Modify: `ai/evaluator.py`
- Test: `tests/test_evaluator.py`

### Step 1: 写失败测试

- [ ] 在 `tests/test_evaluator.py` 末尾追加：

```python
from ai.evaluator import STUCK_PIECE_PENALTY, count_stuck_pieces


def test_count_stuck_pieces_zero_when_all_have_moves():
    state = make_state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})

    assert count_stuck_pieces(state, Player.RED) == 0


def test_count_stuck_pieces_detects_corner_piece_surrounded_by_own():
    # Red 1 在 (0,0)，被自家 2/3/4 完全围死
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )

    assert count_stuck_pieces(state, Player.RED) == 1


def test_count_stuck_pieces_dead_pieces_not_counted():
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )
    state.pieces[Player.RED][1].alive = False

    assert count_stuck_pieces(state, Player.RED) == 0


def test_evaluate_penalizes_state_with_own_stuck_piece():
    # 同样的红方棋子数量与距离，唯一区别是 piece 1 是否被围死
    stuck = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4)},
    )
    free = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(2, 2),  # 4 移到 (2,2)，松开 (1,1)，piece 1 不再被围
        },
        blue={1: Position(4, 4)},
    )

    assert evaluate(free, Player.RED) > evaluate(stuck, Player.RED)


def test_evaluate_zero_sum_still_holds_with_stuck_penalty():
    state = make_state(
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
        },
        blue={1: Position(4, 4), 2: Position(3, 4), 3: Position(4, 3)},
    )

    assert evaluate(state, Player.RED) == -evaluate(state, Player.BLUE)


def test_stuck_penalty_constant_is_finite_and_positive():
    assert STUCK_PIECE_PENALTY > 0
    # 应该比一个材料单位的代价大，否则 AI 不会优先解放角子
    assert STUCK_PIECE_PENALTY > 10
```

### Step 2: 跑测试看失败

```bash
.venv/Scripts/python.exe -m pytest tests/test_evaluator.py -v
```

预期：6 条新测试 ImportError 失败。

### Step 3: 在 `ai/evaluator.py` 新增 STUCK_PIECE_PENALTY 与 count_stuck_pieces，并改 evaluate

把 `ai/evaluator.py` 全文替换为：

```python
from __future__ import annotations

from core.game_state import GameState
from core.rules import generate_legal_moves_for_piece, target_corner
from core.types import Player, Position


WIN_SCORE: float = 1_000_000.0
DISTANCE_WEIGHT: float = 1.0
MATERIAL_WEIGHT: float = 10.0
STUCK_PIECE_PENALTY: float = 100.0


def chebyshev_distance(a: Position, b: Position) -> int:
    return max(abs(a.row - b.row), abs(a.col - b.col))


def count_stuck_pieces(state: GameState, player: Player) -> int:
    """统计 ``player`` 一方"alive 但当前没有任何合法走法"的棋子数。"""
    player = Player.from_value(player)
    return sum(
        1
        for piece in state.pieces[player].values()
        if piece.alive and not generate_legal_moves_for_piece(piece, state.piece_at)
    )


def evaluate(state: GameState, perspective: Player) -> float:
    """从 ``perspective`` 视角对 ``state`` 打分。终局±WIN_SCORE，否则线性组合。"""
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    own_pieces = state.pieces[perspective]
    opp_pieces = state.pieces[perspective.opponent]
    own_target = target_corner(perspective)
    opp_target = target_corner(perspective.opponent)

    own_distance_total = sum(
        chebyshev_distance(p.position, own_target) for p in own_pieces.values() if p.alive
    )
    opp_distance_total = sum(
        chebyshev_distance(p.position, opp_target) for p in opp_pieces.values() if p.alive
    )
    own_alive = sum(1 for p in own_pieces.values() if p.alive)
    opp_alive = sum(1 for p in opp_pieces.values() if p.alive)
    own_stuck = count_stuck_pieces(state, perspective)
    opp_stuck = count_stuck_pieces(state, perspective.opponent)

    return (
        DISTANCE_WEIGHT * (opp_distance_total - own_distance_total)
        + MATERIAL_WEIGHT * (own_alive - opp_alive)
        + STUCK_PIECE_PENALTY * (opp_stuck - own_stuck)
    )
```

### Step 4: 跑测试确认通过

```bash
.venv/Scripts/python.exe -m pytest tests/test_evaluator.py tests/test_ai_basic.py tests/test_ai_match.py -v
```

预期：全部通过。如有失败，多半是 GreedyAI 的局面预期变了（评估函数变了）。需要单独检查。

---

## Task 9.5：default_starting_state 改为"无初始 stuck 子"布局

**目标：** 把红/蓝 5 号、6 号棋子调整位置，让 6 枚棋子初始时每枚都有至少一个合法走法。规避"角子被自家围死 + dice=1 强制选 → forfeit"的不可控初始 1/6 上限。

**新布局（红方对应蓝方对称）：**
- 红：1@(0,0), 2@(0,1), 3@(0,2), 4@(1,0), 5@(2,0), 6@(3,1)
- 蓝：1@(4,4), 2@(4,3), 3@(4,2), 4@(3,4), 5@(2,4), 6@(1,3)

**关键变化：** 旧 5@(1,1) → 新 5@(2,0)；旧 6@(2,0) → 新 6@(3,1)（对应蓝方对称）。这样 (0,0) 的红 1 号有了一个空邻居 (1,1)，不再被围死。所有 6 枚红子都至少 1 个合法走法。

**Files:**
- Modify: `ai/match.py`
- Test: `tests/test_ai_match.py`

### Step 1: 修改测试以反映新布局，并加"无初始 stuck"检验

- [ ] 把 `tests/test_ai_match.py` 中的 `test_default_starting_state_red_triangle_top_left` 与 `test_default_starting_state_blue_triangle_bottom_right` 改为新位置，并新增一条测试：

```python
def test_default_starting_state_red_layout():
    state = default_starting_state()

    expected_red_positions = {
        1: Position(0, 0),
        2: Position(0, 1),
        3: Position(0, 2),
        4: Position(1, 0),
        5: Position(2, 0),
        6: Position(3, 1),
    }
    for piece_id, position in expected_red_positions.items():
        assert state.pieces[Player.RED][piece_id].position == position


def test_default_starting_state_blue_layout():
    state = default_starting_state()

    expected_blue_positions = {
        1: Position(4, 4),
        2: Position(4, 3),
        3: Position(4, 2),
        4: Position(3, 4),
        5: Position(2, 4),
        6: Position(1, 3),
    }
    for piece_id, position in expected_blue_positions.items():
        assert state.pieces[Player.BLUE][piece_id].position == position


def test_default_starting_state_no_piece_is_initially_stuck():
    from core.rules import generate_legal_moves_for_piece

    state = default_starting_state()
    for player_pieces in state.pieces.values():
        for piece in player_pieces.values():
            if piece.alive:
                moves = generate_legal_moves_for_piece(piece, state.piece_at)
                assert moves, f"piece {piece.player.value}/{piece.piece_id} at {piece.position} should have at least one legal move"
```

### Step 2: 跑测试看失败

```bash
.venv/Scripts/python.exe -m pytest tests/test_ai_match.py -v
```

预期：旧的 `test_default_starting_state_red_triangle_top_left` / `blue_triangle_bottom_right` 仍按旧位置 fail；新加的两条测试也 fail（因为 default_starting_state 还没改）。

> 实际操作时记得**删除**旧的两条 `_red_triangle_top_left` 和 `_blue_triangle_bottom_right` 测试，避免新旧两套位置同时存在。

### Step 3: 修改 default_starting_state

替换 `ai/match.py:default_starting_state` 函数的字典字面量为新布局。

### Step 4: 跑测试确认通过

```bash
.venv/Scripts/python.exe -m pytest tests/test_ai_match.py tests/test_ai_basic.py tests/test_evaluator.py -v
```

预期：全部通过。

---

## Task 10：阶段 4.1 验收 —— GreedyAI vs RandomAI 200 局，胜率 ≥ 95%

**Files:**
- 无新建/修改，只跑命令并保留 reports。

### Step 1: 跑验收命令 —— 红方 GreedyAI、蓝方 RandomAI

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" scripts/quick_bench.py --red greedy --blue random --games 200 --seed 2026 --max-turns 200
```

### Step 2: 检查输出，对照阶段 4.1 验收标准

- [ ] 验收检查清单：
  - `red_win_rate >= 0.95`：✓/✗
  - `illegal_moves == 0`：✓/✗
  - `crashes == 0`：✓/✗
  - `timeouts == 0`：✓/✗
  - `wall_seconds < 60.0`（200 局应该比 100 局慢但不会爆炸）：✓/✗
  - `report_path` 文件已生成：✓/✗

如果 `red_win_rate < 0.95`：
- **不要**直接调权重就上。先把单局 replay 看一下：`scripts/run_match.py --red greedy --blue random --seed <某个失败局的 seed>`，找出 GreedyAI 失误模式。
- 在 `reports/` 里写一份 `4-1-failure-analysis.md`（≤ 200 字），列出失误模式与初步诊断。
- 之后再决定是改 evaluator 权重，还是补一个"避免送子"的小启发式（这部分严格说属于 4.2 范畴，可考虑跳到 4.2 规划）。

### Step 3: 反向 sanity —— 蓝方 GreedyAI、红方 RandomAI

- [ ] 运行：

```bash
& ".venv/Scripts/python.exe" scripts/quick_bench.py --red random --blue greedy --games 200 --seed 2026 --max-turns 200
```

预期：`blue_win_rate >= 0.95`。

> 这一步是为了确认 GreedyAI 不是"先手优势硬抗"，而是真的因为评估函数变强；如果只在红方位置打得过 RandomAI、换到蓝方位置就明显变弱，说明评估函数对蓝方目标角(0,0)的方向处理可能有 bug。

### Step 4: GreedyAI 自对弈 —— 100 局

- [ ] 运行（额外稳定性检查，不在 4.1 验收清单，但有用）：

```bash
& ".venv/Scripts/python.exe" scripts/quick_bench.py --red greedy --blue greedy --games 100 --seed 2026 --max-turns 200
```

预期：`illegal_moves == 0`、`crashes == 0`、`draw_rate < 0.5`（确认 GreedyAI 不会陷入死循环导致大量平局）。

### Step 5: 把验收报告路径与对应数据记到 commit 信息里

- [ ] Commit（**等用户确认时机**）：

```bash
git add reports/bench_*greedy*.json
git commit -m "chore(reports): phase 4.1 acceptance — greedy vs random ≥95% (red & blue)"
```

---

## Self-Review Checklist

完成所有 task 之后，开 plan 时再过一遍这份 checklist：

1. **Spec 覆盖：** 阶段 4.0 验收 4 项（harness 跑 100 局 random vs random、illegal=0、crashes=0、≤30s）→ Task 6/7 覆盖。阶段 4.1 验收第一项（GreedyAI vs RandomAI ≥ 95%、200 局、固定 seed、reports 留档）→ Task 8/9/10 覆盖。**故意未覆盖**：4.1 spec 中的"威胁阻止 / 阻止对方一步获胜 / 概率风险评估"——这些与 4.2 的 Expected Risk 设计强耦合，统一在下一份 plan 里处理；4.2/4.3/4.4 的进一步胜率门槛同理。

2. **Placeholder 扫描：** 无 TBD / TODO / "implement later"；所有 Step 都有具体代码或具体命令。

3. **类型一致性：**
   - `AIPlayer.choose_move(state, dice) -> Move | None`：在 RandomAI / GreedyAI / `_AlwaysCrashAI` 等所有实现中签名一致。
   - `play_one_game(*, red_ai, blue_ai, dice_rng, max_turns) -> MatchResult`：在 Task 3 / Task 5 / Task 6 调用一致。
   - `MatchResult` 字段（winner / turns / illegal_moves / crashes / record / step_times_ms）：在 Task 2/3 定义、Task 6 `_aggregate` 消费一致。
   - `build_ai(kind, *, seed)`：Task 4 / Task 9 / Task 5 / Task 6 调用一致。
   - JSON 字段（red_win_rate / blue_win_rate / draw_rate / illegal_moves / crashes / timeouts / average_turns / average_step_time_ms / max_step_time_ms）：Task 6 输出、Task 7/10 验收一致。

4. **跨 task 依赖明确：**
   - Task 1 → Task 2/3（Protocol 与 RandomAI 类是 play_one_game 测试基础）。
   - Task 2 → Task 3（MatchResult 是 play_one_game 返回值）。
   - Task 3 → Task 4（build_ai 输出要喂给 play_one_game）。
   - Task 4 → Task 5/6（CLI 通过 build_ai 构造 AI）。
   - Task 6 → Task 7（验收命令必须跑 quick_bench）。
   - Task 8 → Task 9（GreedyAI 依赖 evaluator）。
   - Task 9 → Task 10（验收 GreedyAI 的胜率）。

5. **可中断点：** Task 4 / Task 7 / Task 9 是天然 commit 边界，每个边界都对应一组完整能跑通的功能（Protocol、4.0 验收、4.1 验收）。

---

## 完成阶段 4.0 + 4.1 后的下一步

阶段 4.1 通过后向用户确认：

- 是否进入下一份 plan（4.2 Expected Risk + 4.3 Edge Safety + 4.4 Piece Importance）。建议每个里程碑出一份独立 plan，因为每一步都需要 4.1 的 baseline 数据来定权重门槛。
- 是否同时规划"GUI 建议走法"（PROJECT_PHASES.md 阶段 4 第 6/7 项）—— 这块独立于 4.2-4.4 的强度迭代，可以并行也可以延后。
- 是否需要把 quick_bench 的 markdown 报告（PROJECT_PHASES.md 阶段 5 的 `reports/latest.md`）顺手做了 —— 当前 plan 只输出 JSON，markdown 排版严格说属于阶段 5 的工程化。
