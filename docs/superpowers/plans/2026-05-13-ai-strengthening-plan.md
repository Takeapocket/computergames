# AI Strengthening Implementation Plan

> 历史执行计划（2026-05-13）。计划中 `greedy_risk` 作为默认 AI 的表述是执行前上下文；当前默认 AI 已升级为旧 flat `rollout`，adaptive rollout 只是显式实验候选。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data-driven AI strengthening pipeline that can improve beyond `greedy_risk` without breaking the stable offline competition GUI.

**Architecture:** Keep `core/` as the only rules authority. Add or adjust AI candidates under `ai/`, run them only through harness scripts under `scripts/`, write evidence to `reports/`, and promote defaults only after explicit gate checks. OpenSpiel and ewn-gym are references for search structure and diagnostics, not dependencies or rule sources.

**Tech Stack:** Python 3.11, pytest, existing `core.GameState`, existing `ai.match.play_one_game`, existing `scripts/quick_bench.py`, `scripts/tournament.py`, `scripts/search_openings.py`, `scripts/param_sweep.py`.

**Git policy:** This project forbids unrequested git commit/push/branch operations. This plan intentionally contains no commit steps. Commit only if the user explicitly asks.

**Resource safety note (2026-05-13 crash recovery):** Do not run the large local benchmark commands in Task 2 Step 6, Task 3 Step 6, Task 6 Step 1, or Task 7 Step 1 on this laptop without explicit approval. The existing 400+400 rollout gate took about 817 seconds, and the planned opening search, parameter sweep, and tournament commands can run thousands to tens of thousands of games. Prefer smoke commands and existing JSON evidence during cleanup; schedule large reruns separately with smaller batches or an overnight window.

---

## File Structure

Planned files and responsibilities:

| Path | Action | Responsibility |
|---|---|---|
| `scripts/ai_diagnostics.py` | Create | Baseline failure classification and pairwise diagnostic report generation. |
| `tests/test_ai_diagnostics.py` | Create | Unit tests for classification, stats aggregation, and report formatting. |
| `reports/ai_diagnostics.md` | Generate | Human-readable baseline failure report. |
| `scripts/search_openings.py` | Modify | Align report gate text and optional seed-pool validation with the new opening promotion gate. |
| `tests/test_search_openings.py` | Modify | Cover updated opening gate text and report metadata. |
| `reports/opening_search_v2.md` | Generate | Opening search evidence. |
| `scripts/param_sweep.py` | Modify | Align report gate text and candidate summary with the stricter AI promotion gate. |
| `tests/test_param_sweep.py` | Modify | Cover updated gate text and candidate metadata. |
| `reports/param_sweep_v2.md` | Generate | Parameter sweep evidence. |
| `ai/rollout_ai.py` | Create | Bounded flat rollout candidate with deadline fallback. |
| `tests/test_rollout_ai.py` | Create | Rollout determinism, no-mutation, fallback, and legal-move tests. |
| `ai/match.py` | Modify | Register `rollout` and later `expectimax_v2`; expose AI signatures for reports. |
| `scripts/quick_bench.py` | Modify if needed | Add explicit candidate args only when a candidate requires CLI-tunable parameters. |
| `ai/expectimax_v2.py` | Create after A0-A3 | Fixed-risk experimental expectimax candidate. |
| `tests/test_expectimax_v2.py` | Create after A0-A3 | Unit tests for V2 search behavior and timeout fallback. |
| `reports/rollout_viability.md` | Generate | Rollout experiment result and promotion status. |
| `reports/expectimax_v2_experiment.md` | Generate if A4 runs | Expectimax V2 experiment result and promotion status. |
| `reports/ai_promotion_decision.md` | Modify | Final candidate promotion decision. |
| `ai/opening_layouts.py` | Modify only after gate | Add tuned layout preset only if it passes opening gate. |
| `gui/main_window.py` | Modify only after gate | Change default recommender only if an AI candidate passes full promotion gate. |

---

## Task 0: Context Gate

**Files:**
- Read: `PROJECT_MEMORY.md`
- Read: `PROJECT_PHASES.md`
- Read: `docs/RULE_ASSUMPTIONS.md`
- Read: `docs/superpowers/specs/2026-05-13-ai-strengthening-design.md`

**Goal:** Ensure the implementer starts from current project facts and does not revive outdated AI assumptions.

- [ ] **Step 1: Verify the current stable baseline**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

Expected:

```text
pytest exits 0
smoke_test.py exits 0
s2_rehearsal.py exits 0 and prints Total: 8/8 scenarios passed
```

- [ ] **Step 2: Verify `greedy_risk` remains the default**

Run:

```powershell
rg -n "build_ai\\(\"greedy_risk\"|greedy_risk" "gui/main_window.py" "release/v1.0" "reports/ai_promotion_decision.md"
```

Expected:

```text
gui/main_window.py still constructs greedy_risk
release docs still identify greedy_risk as default unless a later promotion task changes it
```

- [ ] **Step 3: Confirm rule source**

Run:

```powershell
rg -n "吃本方|骰子|胜负|目标格" "docs/RULE_ASSUMPTIONS.md" "core" "ai"
```

Expected:

```text
Rules are defined in docs/RULE_ASSUMPTIONS.md and core/
AI files call core APIs and do not define separate movement rules
```

---

## Task 1: A0 Baseline Diagnostics

**Files:**
- Create: `scripts/ai_diagnostics.py`
- Create: `tests/test_ai_diagnostics.py`
- Generate: `reports/ai_diagnostics.md`

**Goal:** Classify why `greedy_risk` loses before changing any AI behavior.

- [ ] **Step 1: Write classification tests**

Create `tests/test_ai_diagnostics.py`:

```python
from scripts.ai_diagnostics import (
    FailureBucket,
    aggregate_buckets,
    format_bucket_table,
)


def test_aggregate_buckets_counts_known_reasons():
    rows = [
        {"winner": "blue", "termination_reason": "winner_target_corner", "loser": "red"},
        {"winner": "blue", "termination_reason": "winner_capture_all", "loser": "red"},
        {"winner": "red", "termination_reason": "winner_target_corner", "loser": "blue"},
    ]

    buckets = aggregate_buckets(rows, perspective="red")

    assert buckets[FailureBucket.LOST_BY_TARGET] == 1
    assert buckets[FailureBucket.LOST_BY_CAPTURE_ALL] == 1
    assert buckets[FailureBucket.WON_BY_TARGET] == 1


def test_format_bucket_table_contains_counts():
    table = format_bucket_table({
        FailureBucket.LOST_BY_TARGET: 2,
        FailureBucket.LOST_BY_CAPTURE_ALL: 1,
        FailureBucket.WON_BY_TARGET: 3,
    })

    assert "| bucket | count |" in table
    assert "| lost_by_target | 2 |" in table
    assert "| lost_by_capture_all | 1 |" in table
    assert "| won_by_target | 3 |" in table
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_diagnostics.py -v
```

Expected:

```text
FAIL because scripts.ai_diagnostics does not exist
```

- [ ] **Step 3: Implement diagnostic helpers**

Create `scripts/ai_diagnostics.py` with this structure:

```python
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game, starting_state_for
from core.types import Player


class FailureBucket(StrEnum):
    LOST_BY_TARGET = "lost_by_target"
    LOST_BY_CAPTURE_ALL = "lost_by_capture_all"
    WON_BY_TARGET = "won_by_target"
    WON_BY_CAPTURE_ALL = "won_by_capture_all"
    DRAW_OR_LIMIT = "draw_or_limit"
    ILLEGAL_OR_CRASH = "illegal_or_crash"


def aggregate_buckets(rows: Iterable[dict[str, object]], *, perspective: str) -> Counter[FailureBucket]:
    perspective_player = Player.from_value(perspective)
    buckets: Counter[FailureBucket] = Counter()
    for row in rows:
        winner_value = row.get("winner")
        reason = str(row.get("termination_reason", ""))
        if row.get("illegal_moves", 0) or row.get("crashes", 0):
            buckets[FailureBucket.ILLEGAL_OR_CRASH] += 1
        elif winner_value is None:
            buckets[FailureBucket.DRAW_OR_LIMIT] += 1
        else:
            winner = Player.from_value(str(winner_value))
            did_win = winner is perspective_player
            if reason == "winner_target_corner":
                buckets[FailureBucket.WON_BY_TARGET if did_win else FailureBucket.LOST_BY_TARGET] += 1
            elif reason == "winner_capture_all":
                buckets[FailureBucket.WON_BY_CAPTURE_ALL if did_win else FailureBucket.LOST_BY_CAPTURE_ALL] += 1
            else:
                buckets[FailureBucket.DRAW_OR_LIMIT] += 1
    return buckets


def format_bucket_table(buckets: Counter[FailureBucket] | dict[FailureBucket, int]) -> str:
    lines = ["| bucket | count |", "|---|---:|"]
    for bucket in FailureBucket:
        count = int(buckets.get(bucket, 0))
        if count:
            lines.append(f"| {bucket.value} | {count} |")
    return "\n".join(lines)
```

- [ ] **Step 4: Add a CLI runner to `scripts/ai_diagnostics.py`**

Append:

```python
def run_direction(
    *,
    red: str,
    blue: str,
    games: int,
    seed: int,
    starting_layout: str,
    perspective: Player,
) -> tuple[list[dict[str, object]], Counter[FailureBucket]]:
    rows: list[dict[str, object]] = []
    for i in range(games):
        per_game_seed = seed * 100_000 + i
        result = play_one_game(
            red_ai=build_ai(red, seed=per_game_seed * 3 + 1),
            blue_ai=build_ai(blue, seed=per_game_seed * 3 + 2),
            dice_rng=random.Random(per_game_seed * 3),
            starting_state=starting_state_for(starting_layout),
        )
        rows.append({
            "game_index": i + 1,
            "winner": result.winner.value if result.winner is not None else None,
            "termination_reason": result.termination_reason,
            "turns": result.turns,
            "illegal_moves": result.illegal_moves,
            "crashes": result.crashes,
            "loser": result.winner.opponent.value if result.winner is not None else None,
        })
    return rows, aggregate_buckets(rows, perspective=perspective.value)


def write_report(
    *,
    report_path: Path,
    red: str,
    blue: str,
    games: int,
    seed: int,
    starting_layout: str,
    rows: list[dict[str, object]],
    buckets: Counter[FailureBucket],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Diagnostics",
        "",
        f"- red: `{red}`",
        f"- blue: `{blue}`",
        f"- games: `{games}`",
        f"- seed: `{seed}`",
        f"- starting_layout: `{starting_layout}`",
        "",
        "## Failure Buckets",
        "",
        format_bucket_table(buckets),
        "",
        "## Sample Rows",
        "",
        "```json",
        json.dumps(rows[:20], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify AI match outcomes for baseline diagnostics.")
    parser.add_argument("--red", default="greedy_risk")
    parser.add_argument("--blue", default="greedy")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--starting-layout", default="balanced_v1")
    parser.add_argument("--perspective", choices=["red", "blue"], default="red")
    parser.add_argument("--output", default=str(ROOT / "reports" / "ai_diagnostics.md"))
    args = parser.parse_args(argv)

    rows, buckets = run_direction(
        red=args.red,
        blue=args.blue,
        games=args.games,
        seed=args.seed,
        starting_layout=args.starting_layout,
        perspective=Player.from_value(args.perspective),
    )
    write_report(
        report_path=Path(args.output),
        red=args.red,
        blue=args.blue,
        games=args.games,
        seed=args.seed,
        starting_layout=args.starting_layout,
        rows=rows,
        buckets=buckets,
    )
    print(json.dumps({"report_path": args.output, "buckets": {k.value: v for k, v in buckets.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and smoke diagnostics**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_diagnostics.py tests/test_ai_match.py -v
& ".venv/Scripts/python.exe" "scripts/ai_diagnostics.py" --red greedy_risk --blue greedy --games 20 --seed 2026 --perspective red --output reports/ai_diagnostics_smoke.md
```

Expected:

```text
tests pass
reports/ai_diagnostics_smoke.md exists
stdout JSON contains report_path and buckets
```

- [ ] **Step 6: Run baseline diagnostics**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/ai_diagnostics.py" --red greedy_risk --blue greedy --games 200 --seed 2026 --perspective red --output reports/ai_diagnostics.md
& ".venv/Scripts/python.exe" "scripts/ai_diagnostics.py" --red greedy --blue greedy_risk --games 200 --seed 2026 --perspective blue --output reports/ai_diagnostics_reverse.md
```

Expected:

```text
Both reports exist
Reports classify losses by target-corner and capture-all buckets
No default AI changes
```

---

## Task 2: A1 Opening Search V2 Gate Alignment

**Files:**
- Modify: `scripts/search_openings.py`
- Modify: `tests/test_search_openings.py`
- Generate: `reports/opening_search_v2.md`

**Goal:** Reuse the existing opening search script, but align its report and validation text with the stricter AI strengthening spec.

- [ ] **Step 1: Add a report gate text test**

Append to `tests/test_search_openings.py`:

```python
from scripts.search_openings import promotion_gate_lines


def test_promotion_gate_lines_match_ai_strengthening_spec():
    text = "\n".join(promotion_gate_lines())

    assert "candidate layout vs current default layout 双边合并胜率 >= 55%" in text
    assert "Wilson 95% CI 下界 >= 50%" in text
    assert "至少 3 个不同 seed 池复验" in text
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_search_openings.py::test_promotion_gate_lines_match_ai_strengthening_spec -v
```

Expected:

```text
FAIL because promotion_gate_lines is not defined
```

- [ ] **Step 3: Add `promotion_gate_lines()` to `scripts/search_openings.py`**

Add near the report formatting helpers:

```python
def promotion_gate_lines() -> list[str]:
    return [
        "候选布局晋升需通过：",
        "",
        "- candidate layout vs current default layout 双边合并胜率 >= 55%",
        "- Wilson 95% CI 下界 >= 50%",
        "- 至少 3 个不同 seed 池复验",
        "- illegal_moves = 0, crashes = 0, 基于 bench 聚合的真实 timeouts = 0",
        "- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局",
        "- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选",
    ]
```

Replace the existing hard-coded gate text in `main()` with:

```python
    lines.extend(promotion_gate_lines())
```

- [ ] **Step 4: Run opening search tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_search_openings.py tests/test_opening_layouts.py -v
```

Expected:

```text
tests pass
```

- [ ] **Step 5: Generate a smoke report**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --sample-size 5 --games 10 --validation-games 10 --seed 2026 --output reports/opening_search_v2_smoke.md
```

Expected:

```text
reports/opening_search_v2_smoke.md exists
Report includes the 55% opening gate and Wilson lower-bound text
```

- [ ] **Step 6: Run the real opening search**

Run:

Approval required before running this large command on the laptop; see Resource safety note.

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --sample-size 120 --games 50 --validation-games 200 --seed 2026 --top-k 10 --output reports/opening_search_v2.md
```

Expected:

```text
reports/opening_search_v2.md exists
Report lists train and validation rows
No preset is changed by this task
```

---

## Task 3: A2 Parameter Sweep V2 Gate Alignment

**Files:**
- Modify: `scripts/param_sweep.py`
- Modify: `tests/test_param_sweep.py`
- Generate: `reports/param_sweep_v2.md`

**Goal:** Reuse the current parameter sweep but align reporting with the stricter candidate promotion gate.

- [ ] **Step 1: Add a promotion gate test**

Append to `tests/test_param_sweep.py`:

```python
from scripts.param_sweep import promotion_gate_lines


def test_param_sweep_promotion_gate_lines_match_ai_strengthening_spec():
    text = "\n".join(promotion_gate_lines())

    assert "candidate vs greedy_risk 双边合并胜率 >= 60%" in text
    assert "Wilson 95% CI 下界 >= 52%" in text
    assert "avg_step_time_ms < 1000, max_step_time_ms < 5000" in text
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_param_sweep.py::test_param_sweep_promotion_gate_lines_match_ai_strengthening_spec -v
```

Expected:

```text
FAIL because promotion_gate_lines is not defined
```

- [ ] **Step 3: Add `promotion_gate_lines()` to `scripts/param_sweep.py`**

Add near report formatting helpers:

```python
def promotion_gate_lines() -> list[str]:
    return [
        "候选晋升判断由 `reports/ai_promotion_decision.md` 单独决定，并需通过：",
        "",
        "- candidate vs greedy_risk 双边合并胜率 >= 60%",
        "- Wilson 95% CI 下界 >= 52%",
        "- 每个方向至少 400 局，合并至少 800 局；若时间不足，最小可接受为双边各 200 局",
        "- illegal_moves = 0, crashes = 0, 基于 bench 聚合的真实 timeouts = 0",
        "- avg_step_time_ms < 1000, max_step_time_ms < 5000",
        "- 报告写入 reports/",
    ]
```

Replace the existing hard-coded promotion text with:

```python
    lines.extend(promotion_gate_lines())
```

- [ ] **Step 4: Run parameter sweep tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_param_sweep.py tests/test_evaluator.py tests/test_ai_basic.py -v
```

Expected:

```text
tests pass
```

- [ ] **Step 5: Generate a smoke report**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/param_sweep.py" --sample-size 3 --games 10 --validation-games 10 --seed 2026 --output reports/param_sweep_v2_smoke.md
```

Expected:

```text
reports/param_sweep_v2_smoke.md exists
Report includes the 60% candidate gate and Wilson lower-bound text
```

- [ ] **Step 6: Run the real parameter sweep**

Run:

Approval required before running this large command on the laptop; see Resource safety note.

```powershell
& ".venv/Scripts/python.exe" "scripts/param_sweep.py" --sample-size 40 --games 100 --validation-games 200 --seed 2026 --top-k 8 --output reports/param_sweep_v2.md
```

Expected:

```text
reports/param_sweep_v2.md exists
Report lists train and validation rows
No GUI default changes
```

---

## Task 4: A3 RolloutAI Candidate

**Files:**
- Create: `ai/rollout_ai.py`
- Create: `tests/test_rollout_ai.py`
- Modify: `ai/__init__.py`
- Modify: `ai/match.py`
- Generate: `reports/rollout_viability.md`

**Goal:** Add a bounded flat rollout AI candidate with deterministic seeds and safe fallback.

- [ ] **Step 1: Write RolloutAI tests**

Create `tests/test_rollout_ai.py`:

```python
import random

from ai.rollout_ai import RolloutAI
from core.game_state import GameState
from core.types import Player, Position


def test_rollout_ai_returns_legal_move():
    state = GameState.from_layout()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)


def test_rollout_ai_does_not_mutate_state():
    state = GameState.from_layout()
    before = state.serialize()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    ai.choose_move(state, 6)

    assert state.serialize() == before


def test_rollout_ai_is_deterministic_with_same_seed():
    state_a = GameState.from_layout()
    state_b = GameState.from_layout()
    ai_a = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))
    ai_b = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))

    assert ai_a.choose_move(state_a, 6) == ai_b.choose_move(state_b, 6)


def test_rollout_ai_returns_none_when_no_legal_moves():
    state = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    assert ai.choose_move(state, 1) is None


def test_rollout_ai_timeout_fallback_returns_legal_move():
    state = GameState.from_layout()
    ai = RolloutAI(rollouts_per_move=1000, max_rollout_turns=100, max_step_time_ms=0, rng=random.Random(2))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
    assert ai.fallback_count >= 1
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_rollout_ai.py -v
```

Expected:

```text
FAIL because ai.rollout_ai does not exist
```

- [ ] **Step 3: Implement `ai/rollout_ai.py`**

Create:

```python
from __future__ import annotations

import random
import time

from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move
from core.types import Player


class RolloutAI:
    """Bounded flat rollout candidate. It never mutates the input state."""

    def __init__(
        self,
        *,
        rollouts_per_move: int = 16,
        max_rollout_turns: int = 80,
        max_step_time_ms: float = 500.0,
        epsilon: float = 0.15,
        rng: random.Random | None = None,
        name: str = "rollout",
    ) -> None:
        self.rollouts_per_move = int(rollouts_per_move)
        self.max_rollout_turns = int(max_rollout_turns)
        self.max_step_time_ms = float(max_step_time_ms)
        self.epsilon = float(epsilon)
        self._rng = rng or random.Random()
        self.name = name
        self.fallback_count = 0

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        deadline = time.perf_counter() + self.max_step_time_ms / 1000.0
        perspective = state.current_player
        fallback = GreedyAI(rng=random.Random(self._rng.randrange(2**31)), name="rollout_fallback")
        best_move = fallback.choose_move(state, dice) or self._rng.choice(legal)
        best_score = float("-inf")
        scored_any = False

        for move in legal:
            if time.perf_counter() >= deadline:
                self.fallback_count += 1
                return best_move
            wins = 0.0
            completed = 0
            for _ in range(self.rollouts_per_move):
                if time.perf_counter() >= deadline:
                    self.fallback_count += 1
                    return best_move
                sim = GameState.deserialize(state.serialize())
                applied = sim.apply_move(move, dice=dice)
                winner = self._playout(sim, deadline=deadline)
                if winner is perspective:
                    wins += 1.0
                elif winner is None:
                    wins += 0.5
                completed += 1
            if completed:
                score = wins / completed
                scored_any = True
                if score > best_score:
                    best_score = score
                    best_move = move

        if not scored_any:
            self.fallback_count += 1
        return best_move

    def _playout(self, state: GameState, *, deadline: float) -> Player | None:
        policy = GreedyAI(rng=random.Random(self._rng.randrange(2**31)), name="rollout_policy")
        for _ in range(self.max_rollout_turns):
            winner = state.get_winner()
            if winner is not None:
                return winner
            if time.perf_counter() >= deadline:
                return None
            dice = self._rng.randint(1, 6)
            legal = state.legal_moves(state.current_player, dice)
            if not legal:
                return state.current_player.opponent
            if self._rng.random() < self.epsilon:
                move = self._rng.choice(legal)
            else:
                move = policy.choose_move(state, dice) or self._rng.choice(legal)
            state.apply_move(move, dice=dice)
        return state.get_winner()
```

- [ ] **Step 4: Register RolloutAI**

In `ai/__init__.py`, export:

```python
from ai.rollout_ai import RolloutAI
```

Add `"RolloutAI"` to `__all__`.

In `ai/match.py`, import lazily inside `build_ai`:

```python
    if kind == "rollout":
        from ai.rollout_ai import RolloutAI
        return RolloutAI(rng=rng, **ai_kwargs)
```

- [ ] **Step 5: Add build and signature tests**

Append to `tests/test_ai_basic.py`:

```python
from ai.match import ai_version_signature, build_ai


def test_build_ai_rollout_registers_signature_fields():
    ai = build_ai("rollout", seed=1, rollouts_per_move=3, max_rollout_turns=9, max_step_time_ms=250)
    signature = ai_version_signature(ai)

    assert signature["name"] == "rollout"
    assert signature["rollouts_per_move"] == 3
    assert signature["max_rollout_turns"] == 9
    assert signature["max_step_time_ms"] == 250.0
```

If `ai_version_signature()` does not currently reflect these public attributes, update it in `ai/match.py` by adding them to the reflected attribute list:

```python
for attr in (
    "distance_weight",
    "material_weight",
    "expected_risk_weight",
    "expected_win_risk_weight",
    "self_capture_weight",
    "depth",
    "time_limit_ms",
    "rollouts_per_move",
    "max_rollout_turns",
    "max_step_time_ms",
    "epsilon",
):
```

- [ ] **Step 6: Run RolloutAI tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_rollout_ai.py tests/test_ai_basic.py tests/test_ai_match.py -v
```

Expected:

```text
tests pass
```

- [ ] **Step 7: Run RolloutAI smoke bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy --games 50 --seed 2026 --report-name rollout_vs_greedy_smoke
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue rollout --games 50 --seed 2026 --report-name greedy_vs_rollout_smoke
```

Expected:

```text
Both commands exit 0
illegal_moves = 0
crashes = 0
max_step_time_ms < 5000
```

- [ ] **Step 8: Write rollout viability report**

Create `reports/rollout_viability.md`:

````markdown
# RolloutAI Viability

## Candidate

- kind: `rollout`
- rollouts_per_move: 16
- max_rollout_turns: 80
- max_step_time_ms: 500
- epsilon: 0.15

## Smoke Commands

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy --games 50 --seed 2026 --report-name rollout_vs_greedy_smoke
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue rollout --games 50 --seed 2026 --report-name greedy_vs_rollout_smoke
````

## Decision

- Historical default AI: keep `greedy_risk`
- Promotion: not decided by smoke; run Task 6 promotion gate if smoke is stable
```

---

## Task 5: A4 ExpectimaxV2 Candidate

**Condition:** Start this task only after Task 1, Task 2, Task 3, and Task 4 are complete and no candidate has passed promotion gate.

**Files:**
- Create: `ai/expectimax_v2.py`
- Create: `tests/test_expectimax_v2.py`
- Modify: `ai/match.py`
- Generate: `reports/expectimax_v2_experiment.md`

**Goal:** Test a fixed-risk expectimax candidate without replacing the existing experimental `expectimax`.

- [ ] **Step 1: Write core behavior tests**

Create `tests/test_expectimax_v2.py`:

```python
import random

from ai.expectimax_v2 import ExpectimaxV2
from ai.greedy_ai import GreedyAI
from core.game_state import GameState


def test_expectimax_v2_depth_zero_matches_greedy_without_tie_randomness():
    state_a = GameState.from_layout()
    state_b = GameState.from_layout()
    expectimax = ExpectimaxV2(depth=0, rng=random.Random(1), randomize_ties=False)
    greedy = GreedyAI(rng=random.Random(1), randomize_ties=False)

    assert expectimax.choose_move(state_a, 6) == greedy.choose_move(state_b, 6)


def test_expectimax_v2_does_not_mutate_state():
    state = GameState.from_layout()
    before = state.serialize()
    ai = ExpectimaxV2(depth=1, rng=random.Random(1), time_limit_ms=1000)

    ai.choose_move(state, 6)

    assert state.serialize() == before


def test_expectimax_v2_timeout_returns_legal_move():
    state = GameState.from_layout()
    ai = ExpectimaxV2(depth=2, rng=random.Random(1), time_limit_ms=0)

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_expectimax_v2.py -v
```

Expected:

```text
FAIL because ai.expectimax_v2 does not exist
```

- [ ] **Step 3: Implement `ExpectimaxV2` as a safe wrapper first**

Create `ai/expectimax_v2.py`:

```python
from __future__ import annotations

import random
import time

from ai.evaluator import evaluate
from ai.greedy_ai import GreedyAI
from core.game_state import GameState
from core.move import Move


class ExpectimaxV2:
    """Experimental expectimax candidate with leaf risk disabled by default."""

    def __init__(
        self,
        *,
        depth: int = 1,
        time_limit_ms: float = 500.0,
        rng: random.Random | None = None,
        name: str = "expectimax_v2",
        randomize_ties: bool = True,
    ) -> None:
        self.depth = int(depth)
        self.time_limit_ms = float(time_limit_ms)
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = bool(randomize_ties)

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        if self.depth <= 0:
            return GreedyAI(rng=self._rng, randomize_ties=self.randomize_ties).choose_move(state, dice)

        deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        perspective = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal:
            if time.perf_counter() >= deadline:
                return self._fallback(legal, best_moves)
            applied = state.apply_move(move, dice=dice)
            try:
                score = self._chance_value(state, perspective=perspective, depth=self.depth - 1, deadline=deadline)
            finally:
                state.undo_move()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self._fallback(legal, best_moves)

    def _chance_value(self, state: GameState, *, perspective, depth: int, deadline: float) -> float:
        if time.perf_counter() >= deadline or depth <= 0 or state.get_winner() is not None:
            return evaluate(
                state,
                perspective=perspective,
                expected_risk_weight=0.0,
                expected_win_risk_weight=0.0,
            )
        total = 0.0
        for dice in range(1, 7):
            total += self._turn_value(state, dice=dice, perspective=perspective, depth=depth, deadline=deadline)
        return total / 6.0

    def _turn_value(self, state: GameState, *, dice: int, perspective, depth: int, deadline: float) -> float:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return evaluate(state, perspective=perspective, expected_risk_weight=0.0, expected_win_risk_weight=0.0)
        scores = []
        for move in legal:
            if time.perf_counter() >= deadline:
                break
            state.apply_move(move, dice=dice)
            try:
                scores.append(self._chance_value(state, perspective=perspective, depth=depth - 1, deadline=deadline))
            finally:
                state.undo_move()
        if not scores:
            return evaluate(state, perspective=perspective, expected_risk_weight=0.0, expected_win_risk_weight=0.0)
        return max(scores) if state.current_player is perspective else min(scores)

    def _fallback(self, legal: list[Move], best_moves: list[Move]) -> Move:
        choices = best_moves or legal
        return self._rng.choice(choices) if self.randomize_ties else choices[0]
```

- [ ] **Step 4: Register `expectimax_v2`**

In `ai/match.py` `build_ai()`:

```python
    if kind == "expectimax_v2":
        from ai.expectimax_v2 import ExpectimaxV2
        return ExpectimaxV2(rng=rng, **ai_kwargs)
```

Update `ai/__init__.py`:

```python
from ai.expectimax_v2 import ExpectimaxV2
```

Add `"ExpectimaxV2"` to `__all__`.

- [ ] **Step 5: Run tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_expectimax_v2.py tests/test_expectimax.py tests/test_ai_basic.py tests/test_ai_match.py -v
```

Expected:

```text
tests pass
```

- [ ] **Step 6: Run smoke bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red expectimax_v2 --blue greedy --games 50 --seed 2026 --report-name expectimax_v2_vs_greedy_smoke
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue expectimax_v2 --games 50 --seed 2026 --report-name greedy_vs_expectimax_v2_smoke
```

Expected:

```text
Both commands exit 0
illegal_moves = 0
crashes = 0
max_step_time_ms < 5000
```

- [ ] **Step 7: Write experiment report**

Create `reports/expectimax_v2_experiment.md`:

````markdown
# ExpectimaxV2 Experiment

## Candidate

- kind: `expectimax_v2`
- depth: 1
- leaf risk: disabled
- historical default AI unchanged: `greedy_risk`

## Smoke Commands

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red expectimax_v2 --blue greedy --games 50 --seed 2026 --report-name expectimax_v2_vs_greedy_smoke
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue expectimax_v2 --games 50 --seed 2026 --report-name greedy_vs_expectimax_v2_smoke
````

## Decision

- Historical default AI: keep `greedy_risk`
- Promotion: not decided by smoke; run Task 6 promotion gate if smoke is stable and stronger than the then-current baseline
```

---

## Task 6: Promotion Gate and Decision Report

**Files:**
- Modify: `reports/ai_promotion_decision.md`
- Modify: `ai/opening_layouts.py` only if opening gate passes
- Modify: `gui/opening_panel.py` only if opening default changes
- Modify: `gui/main_window.py` only if AI gate passes
- Modify: `release/v1.0/default_params.json` or create `release/v1.1/default_params.json` only after gate

**Goal:** Decide whether any candidate is promoted. Historical default outcome was to keep `greedy_risk`; current replacement work must compare against the current default rollout.

- [ ] **Step 1: Run candidate vs then-current baseline both directions**

For a candidate AI kind such as `rollout` or `expectimax_v2`, run:

Approval required before running this large command on the laptop; see Resource safety note.

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy_risk --games 400 --seed 2026 --report-name rollout_vs_greedy_risk_red
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue rollout --games 400 --seed 2026 --report-name greedy_risk_vs_rollout_blue
```

Expected:

```text
Both commands exit 0
Combined candidate win rate can be computed from red candidate wins plus blue candidate wins
Reports include illegal_moves, crashes, avg_step_time_ms, max_step_time_ms
```

- [ ] **Step 2: Write the decision report**

Update `reports/ai_promotion_decision.md` with:

````markdown
# AI Promotion Decision

Date: 2026-05-13

## Baseline

- default AI: `greedy_risk`
- default layout: `balanced_v1`

## Candidate Summary

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Gate

- candidate vs greedy_risk 双边合并胜率 >= 60%
- Wilson 95% CI 下界 >= 52%
- illegal_moves = 0
- crashes = 0
- 基于 bench 聚合的真实 timeouts = 0
- avg_step_time_ms < 1000
- max_step_time_ms < 5000

## Decision

Default AI remains `greedy_risk` unless every gate row above is satisfied.
````

Fill the table with actual numbers from reports generated in Step 1.

- [ ] **Step 3: Promote an AI only if all gates pass**

If and only if the report satisfies all AI gates, update `gui/main_window.py`:

```python
self._recommender = build_ai("rollout", seed=0)
```

If the promoted AI needs parameters, prefer a named factory kind in `ai/match.py` rather than embedding a large parameter dict in GUI.

If gates do not pass, leave `gui/main_window.py` unchanged.

- [ ] **Step 4: Promote a layout only if opening gate passes**

If and only if `reports/opening_search_v2.md` satisfies opening gates, add a preset to `ai/opening_layouts.py`:

```python
"balanced_tuned_v1": OpeningLayout(
    id="balanced_tuned_v1",
    name="数据候选均衡 V1",
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
),
```

Replace the coordinates above with the actual winning candidate from the report. Do not use this example layout as evidence.

- [ ] **Step 5: Run final verification**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

Expected:

```text
pytest exits 0
smoke_test.py exits 0
s2_rehearsal.py exits 0 and prints Total: 8/8 scenarios passed
```

---

## Task 7: Full Matrix Regression

**Files:**
- Generate: `reports/tournament_matrix_ai_strengthening.md`

**Goal:** Confirm the promoted or best experimental candidate does not only beat one opponent while collapsing elsewhere.

- [ ] **Step 1: Run pairwise matrix**

Run:

Approval required before running this large command on the laptop; see Resource safety note.

```powershell
& ".venv/Scripts/python.exe" "scripts/tournament.py" --ais random,greedy,greedy_risk,rollout --games 200 --seed 2026 --report reports/tournament_matrix_ai_strengthening.md
```

If `rollout` was not implemented or was rejected before this task, replace it with `expectimax_v2` only if Task 5 was implemented.

Expected:

```text
Command exits 0
Report includes pairwise matrix
illegal_total = 0
crashes_total = 0
```

- [ ] **Step 2: Update promotion report with matrix conclusion**

Append to `reports/ai_promotion_decision.md`:

````markdown
## Pairwise Matrix Check

Source: `reports/tournament_matrix_ai_strengthening.md`

Conclusion:
- Candidate does not replace `greedy_risk` unless it improves the main baseline and avoids severe regressions against `random` and `greedy`.
````

Fill the conclusion with actual matrix facts.

---

## Self-Review Checklist

- [x] Spec coverage: A0 diagnostics, A1 opening search, A2 parameter/evaluator sweep, A3 RolloutAI, A4 ExpectimaxV2, A5 promotion are all mapped to tasks.
- [x] External references stay references only; no OpenSpiel, Gymnasium, SB3, PyTorch, or network dependency is introduced.
- [x] Rules remain in `core/`; AI tasks call `GameState`, `legal_moves`, `apply_move`, `undo_move`, and harness APIs.
- [x] Default AI remains `greedy_risk` unless the promotion task passes explicit gates.
- [x] No git commit/push/branch steps are included, matching project instructions.
- [x] Placeholder scan completed; no unresolved implementation markers are intentionally present.
