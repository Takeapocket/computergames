# Task Group 03 - Experimental AI Timeboxes

> 历史执行计划。本文中“不能替换默认 `greedy_risk`”是 2026-05-12 当时的默认基线；当前默认 AI 已升级为旧 flat `rollout`，adaptive rollout 是显式实验候选而非 release 默认。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

目标：只在稳定性和低风险 AI 工作完成后，才用严格时间盒尝试 ExpectimaxV2 或 RolloutAI。历史上下文中的实验不能替换当时默认 `greedy_risk`；当前实验候选必须对 current default rollout 过门禁。

---

## Task 9: ExpectimaxV2 时间盒实验

**Condition:** Only start if Task Group 01 is done and there is still time before release freeze.

**Files:**

- Create: `ai/expectimax_v2.py`
- Create: `tests/test_expectimax_v2.py`
- Modify: `ai/match.py`
- Modify: `scripts/quick_bench.py` only if needed for explicit AI kwargs CLI
- Create: `reports/expectimax_v2_experiment.md`

**Goal:** 验证 risk/lookahead 语义错位假设。未过 gate 不接默认。

### Critical correction

不要把当前 Expectimax 弱因写死为“chance node 错误”。现有 `ai/expectimax_ai.py` 已经枚举骰子并平均。更可信的假设是：

```text
risk evaluator 与 lookahead 语义错位
leaf risk 可能重复计算下一手风险
turn-aware risk 可能需要显式 next mover
```

### Steps

- [ ] Register harness path first.

In `ai/match.py`:

```text
Add build_ai("expectimax_v2", depth=1, heuristic="default", time_limit_ms=5000, ...)
Add signature attrs: depth, heuristic, time_limit_ms
```

If `quick_bench.py` cannot pass these kwargs, add minimal explicit args:

```text
--red-depth
--blue-depth
--red-time-limit-ms
--blue-time-limit-ms
```

Do not add generic arbitrary eval strings unless tests cover them.

- [ ] Create `tests/test_expectimax_v2.py`.

Required tests:

```text
depth=0 returns same move as GreedyAI with same evaluator and randomize_ties=False
terminal state returns winning move when available
no legal moves returns None
timeout fallback returns legal move
choose_move does not mutate state
deterministic with same seed
```

- [ ] Implement `ai/expectimax_v2.py`.

Required structure:

```text
choose_move(state, dice)
  known current player and known current dice
  evaluate each legal root move

_max_chance_node(state, perspective, depth, deadline)
  average over perspective dice 1..6
  choose max move for each dice

_min_chance_node(state, perspective, depth, deadline)
  average over opponent dice 1..6
  choose min move for each dice
```

Rules:

```text
Use apply_move()/undo_move(); do not call a clone method because GameState does not expose one.
Check deadline at every loop.
On timeout, return best scored root move.
If no move scored, return seeded random legal move.
Leaf evaluator defaults to risk weights disabled unless explicitly enabled.
```

- [ ] Run unit tests:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_expectimax_v2.py tests/test_ai_match.py -v
```

Expected:

```text
tests pass
```

- [ ] Run E0 smoke:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red expectimax_v2 --blue greedy --games 50 --seed 2026 --no-save-report
```

Expected:

```text
illegal_moves = 0
crashes = 0
max_step_time_ms < 5000
```

- [ ] Stop or continue.

Continue only if:

```text
E0 shows no stability problems
step time is safe
small sample is not clearly worse than greedy
```

Otherwise:

```text
Write reports/expectimax_v2_experiment.md as "not promoted"
Do not continue E1-E5
```

- [ ] If promising, run full promotion gate from the main plan.

No GUI default change is allowed until the full gate passes.

---

## Task 10: RolloutAI 时间盒实验

**Condition:** Only start if ExpectimaxV2 is not promising and there is still time.

**Files:**

- Create: `ai/rollout_ai.py`
- Create: `tests/test_rollout_ai.py`
- Modify: `ai/match.py`
- Create: `reports/rollout_viability.md`

**Goal:** 提供简单 flat rollout 候选，但不让随机模拟拖垮现场时限。

### Steps

- [ ] Create `tests/test_rollout_ai.py`.

Required tests:

```text
returns a legal move when legal moves exist
returns None when no legal moves exist
does not mutate input state
deterministic with same seed
respects max_turns in rollout
respects time_limit_ms by falling back to legal move
```

- [ ] Implement `ai/rollout_ai.py`.

Required constructor:

```python
class RolloutAI:
    def __init__(
        self,
        *,
        num_simulations: int = 50,
        max_turns: int = 120,
        time_limit_ms: float = 1000.0,
        rng: random.Random | None = None,
        name: str = "rollout",
    ) -> None:
        ...
```

Rules:

```text
For each legal root move, run bounded random playouts.
Use GameState.deserialize(state.serialize()) for copied simulation.
Never mutate input state.
If deadline hits before scoring all moves, return best scored move.
If no move scored, return seeded random legal move.
```

- [ ] Register in `ai/match.py`:

```text
Add build_ai("rollout", num_simulations=..., max_turns=..., time_limit_ms=...)
Add signature attrs: num_simulations, max_turns, time_limit_ms
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_rollout_ai.py tests/test_ai_match.py -v
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy --games 100 --seed 2026 --report-name rollout_vs_greedy
```

Promotion rules:

```text
If rollout < 40% vs greedy, keep only as experiment or remove from release discussion.
If rollout > 55% vs greedy_risk, run full AI promotion gate before any default change.
```
