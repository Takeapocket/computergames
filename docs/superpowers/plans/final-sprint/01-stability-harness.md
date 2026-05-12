# Task Group 01 - Stability, Harness, And R-0 Followup

目标：先完成真实 GUI 现场链路，再让 AI 评测工具可信，最后清理 R-0 后的 `stuck_penalty` 准死代码。

---

## Task 1: S2 真实 GUI 手动演练闭环

**Files:**

- Modify: `reports/gui-rehearsal.md`

**Goal:** 把 S2 从“headless 自动演练完成”推进到“真实 GUI 现场链路已验证”。

### Steps

- [ ] Start GUI:

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

Check:

```text
窗口正常启动
开局录入面板可见
我方颜色可选
布局下拉可用
棋盘可点击录入对方布局
```

- [ ] Fill `reports/gui-rehearsal.md` section 4.1 for 4:0 flow.

Must cover:

```text
进入比赛模式
选择甲/乙身份
选择我方颜色
录入双方开局
连续结束 4 盘
比分达到 4:0 后整轮结束
```

- [ ] Fill section 4.2 for 4:3 flow.

Must verify:

```text
第 7 盘可进入
比分显示 3:3 -> 4:3
第 7 盘先手符合甲乙先手序列
整轮结束后不继续开第 8 盘
```

- [ ] Fill section 4.3 and 4.4 crash recovery.

Manual procedure:

```text
盘中走 1-2 手
关闭 Python 进程
重新启动 scripts/run_gui.py
选择恢复
核对棋盘、当前方、骰子阶段、计时、棋谱步数
```

Repeat between-game crash:

```text
结束一盘并保存整轮状态
关闭 Python 进程
重新启动
恢复整轮
核对比分、当前第几盘、下一盘开局阶段
```

- [ ] Fill section 4.5 and 4.6 for undo and post-match operations.

Must cover:

```text
悔棋按钮状态
悔棋后棋盘和棋谱一致
加载棋谱能恢复局面
拒绝错误恢复不会污染当前局面
整轮结束后保存、重置、进入下一轮或 debug 模式
```

- [ ] Update S2 decision in section 8.

If all rows pass:

```text
将 S2 状态改为真实 GUI 手动演练完成
```

If any row fails:

```text
记录复现步骤、实际结果、期望结果、影响等级 P0/P1/P2/P3、是否阻塞封版、建议修复文件
P0/P1 必须先修
P2/P3 可写入 known limitations
```

- [ ] Run automatic regression:

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
& ".venv/Scripts/python.exe" -m pytest -q
```

Expected:

```text
s2_rehearsal 8/8 PASS
pytest exit 0
```

---

## Task 2: quick_bench 增加 Wilson CI

**Files:**

- Modify: `scripts/quick_bench.py`
- Create: `tests/test_quick_bench_ci.py`

**Goal:** bench 输出胜率时同时输出 95% Wilson confidence interval，降低小样本误判风险。

### Steps

- [ ] Create `tests/test_quick_bench_ci.py`:

```python
from types import SimpleNamespace

from core.types import Player
from scripts.quick_bench import _aggregate, wilson_ci


def test_wilson_ci_bounds_are_inside_zero_one():
    lower, upper = wilson_ci(58, 100)
    assert 0.0 <= lower <= upper <= 1.0


def test_wilson_ci_gets_narrower_with_more_games():
    low_small, high_small = wilson_ci(5, 10)
    low_large, high_large = wilson_ci(500, 1000)
    assert (high_large - low_large) < (high_small - low_small)


def test_aggregate_includes_red_and_blue_ci():
    results = [
        SimpleNamespace(winner=Player.RED, turns=10, illegal_moves=0, crashes=0, step_times_ms=[1.0, 2.0]),
        SimpleNamespace(winner=Player.BLUE, turns=12, illegal_moves=0, crashes=0, step_times_ms=[3.0]),
    ]

    summary = _aggregate(results)

    assert "red_win_ci95" in summary
    assert "blue_win_ci95" in summary
    assert len(summary["red_win_ci95"]) == 2
    assert len(summary["blue_win_ci95"]) == 2
```

- [ ] Run failing test:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_quick_bench_ci.py -v
```

Expected before implementation:

```text
FAIL: cannot import name 'wilson_ci'
```

- [ ] Add to `scripts/quick_bench.py`:

```python
def wilson_ci(wins: int, games: int, z: float = 1.96) -> tuple[float, float]:
    """Return Wilson score interval for a win proportion."""
    if games <= 0:
        return 0.0, 0.0
    p = wins / games
    denom = 1.0 + z * z / games
    center = (p + z * z / (2.0 * games)) / denom
    margin = z * ((p * (1.0 - p) / games + z * z / (4.0 * games * games)) ** 0.5) / denom
    return max(0.0, center - margin), min(1.0, center + margin)
```

Update `_aggregate()` summary:

```python
red_ci = wilson_ci(winners[Player.RED], games)
blue_ci = wilson_ci(winners[Player.BLUE], games)

"red_win_ci95": [red_ci[0], red_ci[1]],
"blue_win_ci95": [blue_ci[0], blue_ci[1]],
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_quick_bench_ci.py tests/test_ai_match.py tests/test_bench_cli_metadata.py -v
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 20 --seed 2026 --no-save-report
```

Expected:

```text
tests pass
JSON stdout includes red_win_ci95 and blue_win_ci95
illegal_moves = 0
crashes = 0
```

---

## Task 3: 新增 pairwise tournament

**Files:**

- Create: `scripts/tournament.py`
- Create: `tests/test_tournament.py`

**Goal:** 对多个 AI 做双边 pairwise matrix，作为后续参数和新 AI 的统一比较基线。

### Steps

- [ ] Create `tests/test_tournament.py`:

```python
from scripts.tournament import format_markdown_matrix, parse_ai_list


def test_parse_ai_list_strips_spaces():
    assert parse_ai_list("random, greedy,greedy_risk") == ["random", "greedy", "greedy_risk"]


def test_format_markdown_matrix_contains_headers_and_diagonal():
    ais = ["random", "greedy"]
    matrix = {
        "random": {"greedy": 25.0},
        "greedy": {"random": 75.0},
    }

    output = format_markdown_matrix(ais, matrix)

    assert "| AI | random | greedy |" in output
    assert "| random | - | 25.0% |" in output
    assert "| greedy | 75.0% | - |" in output
```

- [ ] Run failing test:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_tournament.py -v
```

Expected:

```text
FAIL: No module named scripts.tournament
```

- [ ] Implement `scripts/tournament.py`.

Required CLI:

```text
--ais random,greedy,greedy_risk
--games 100
--seed 2026
--starting-layout default_no_stuck_corner_v1
--report reports/tournament_matrix.md
```

Implementation rules:

```text
Use build_ai(), play_one_game(), starting_state_for()
Run each unordered pair in both red/blue orientations
Use deterministic per-game seeds
Write markdown matrix and summary metadata
```

Markdown format:

```markdown
# AI Tournament Matrix

seed: 2026
games_per_orientation: 100
layout: default_no_stuck_corner_v1

| AI | random | greedy | greedy_risk |
|---|---:|---:|---:|
| random | - | 12.0% | 8.0% |
| greedy | 88.0% | - | 42.0% |
| greedy_risk | 92.0% | 58.0% | - |
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_tournament.py -v
& ".venv/Scripts/python.exe" "scripts/tournament.py" --ais random,greedy,greedy_risk --games 10 --seed 2026 --report reports/tournament_matrix_smoke.md
```

Expected:

```text
tests pass
reports/tournament_matrix_smoke.md exists
matrix has random, greedy, greedy_risk
```

---

## Task 4: R-0 followup 清理 stuck_penalty

**Files:**

- Modify: `ai/evaluator.py`
- Modify: `ai/greedy_ai.py`
- Modify: `ai/match.py`
- Modify: `scripts/quick_bench.py`
- Modify: `scripts/run_match.py`
- Modify: `scripts/_bench_meta.py`
- Modify: affected tests under `tests/`

**Goal:** 删除 R-0 后基本无效的 stuck penalty，避免后续参数搜索继续围绕准死代码展开。

### Steps

- [ ] Search current references:

```powershell
rg "stuck_penalty|STUCK_PIECE_PENALTY|count_stuck_pieces" --glob "*.py"
```

Expected before cleanup:

```text
References exist in ai/, scripts/, tests/
```

- [ ] Update tests first.

Remove or rewrite tests whose only purpose is stuck penalty:

```text
test_count_stuck_pieces_zero_when_all_have_moves
test_count_stuck_pieces_zero_for_corner_surrounded_by_own_post_R0
test_count_stuck_pieces_dead_pieces_not_counted
test_evaluate_penalizes_state_with_own_stuck_piece
test_evaluate_zero_sum_still_holds_with_stuck_penalty
test_stuck_penalty_constant_is_finite_and_positive
test_evaluate_accepts_stuck_penalty_kwarg_and_zero_disables_penalty
test_greedy_ai_accepts_zero_stuck_penalty
test_ai_version_signature_for_baseline_greedy_records_zero_penalty
```

Keep tests for terminal scoring, distance, material, expected risk, expected win risk, and zero-sum when risk weights are zero.

- [ ] Update `ai/evaluator.py`.

Remove:

```text
STUCK_PIECE_PENALTY
count_stuck_pieces()
stuck_penalty parameter in evaluate()
own_stuck / opp_stuck calculations
stuck term in return expression
```

Expected non-risk return shape:

```python
return (
    distance_weight * (opp_distance_total - own_distance_total)
    + material_weight * (own_alive - opp_alive)
    - expected_risk_weight * own_expected_risk
    - expected_win_risk_weight * own_expected_win_risk
)
```

- [ ] Update `ai/greedy_ai.py`.

Remove:

```text
STUCK_PIECE_PENALTY import
stuck_penalty constructor parameter
self.stuck_penalty
stuck_penalty=... in evaluate()
```

- [ ] Update harness and CLI.

In `ai/match.py`:

```text
Remove stuck_penalty from docstring
Remove stuck_penalty from ai_version_signature attr list
```

In `scripts/_bench_meta.py`, `scripts/quick_bench.py`, `scripts/run_match.py`:

```text
Remove greedy_kwargs(stuck_penalty)
Remove --red-stuck-penalty and --blue-stuck-penalty
Remove metadata field for stuck penalty
```

- [ ] Run:

```powershell
rg "stuck_penalty|STUCK_PIECE_PENALTY|count_stuck_pieces" --glob "*.py"
& ".venv/Scripts/python.exe" -m pytest tests/test_evaluator.py tests/test_evaluator_injection.py tests/test_ai_basic.py tests/test_ai_match.py tests/test_bench_cli_metadata.py -v
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected:

```text
rg returns no Python references
all selected tests pass
full pytest exits 0
smoke exits 0
```
