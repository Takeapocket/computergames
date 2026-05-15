# Task Group 00 - Context, Gates, And File Map

> 历史执行上下文。当前默认 AI 是旧 flat `rollout`；新候选默认晋升基线为 current default rollout，`greedy_risk` 只作应急回退或辅助对手。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

本文件是收官冲刺的前置上下文。任何后续任务包开始前，先完成这里的检查。

---

## 1. 固定上下文读取

Read:

```powershell
Get-Content -Raw "PROJECT_MEMORY.md"
Get-Content -Raw "PROJECT_PHASES.md"
Get-Content -Raw "README.md"
Get-Content -Raw "docs/RULE_ASSUMPTIONS.md"
Get-Content -Raw "docs/PROJECT_BRIEF.md"
Get-Content -Raw "docs/superpowers/specs/2026-05-12-final-sprint-design.md"
Get-Content -Raw "docs/superpowers/plans/2026-05-12-final-sprint-plan.md"
```

Expected conclusion:

```text
S2 真实 GUI 手动表仍是最近 P0
历史上下文：当时默认 AI 是 greedy_risk；当前默认 AI 是旧 flat rollout
Expectimax 是实验性，不能作为默认 AI
比赛现场默认离线、不依赖统一平台
```

---

## 2. S0 基线

Run before every code task:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected:

```text
Both commands exit 0
```

Failure policy:

```text
不开始新任务
先定位失败
只修相关最小范围
重跑失败测试和 S0
```

---

## 3. AI 晋升门禁

替换 GUI 默认 AI 或 release 默认 AI 前，候选必须满足：

```text
candidate vs current default old flat rollout: red/blue each 200 games, total 400
candidate vs greedy: red/blue each 200 games, total 400
candidate merged win rate vs current default > 55%
Wilson 95% CI lower bound >= 50%
illegal_moves = 0
crashes = 0
real timeout telemetry = 0
avg_step_time_ms < 1000
max_step_time_ms < 5000
report written to reports/
```

未过 gate 的候选只能保留为实验入口。

---

## 4. 开局晋升门禁

替换 GUI 默认布局或 release 推荐布局前，候选必须满足：

```text
candidate layout vs current layout: at least 400 total games
both red and blue roles covered
merged win rate > 53%
Wilson 95% CI lower bound >= 50%
illegal_moves = 0
crashes = 0
real timeout telemetry = 0
real timeout telemetry = 0
layout appears in GUI OpeningPanel preset menu
report written to reports/opening_report.md
```

---

## 5. 文件责任图

### 5.1 任务包 01 可能修改

```text
reports/gui-rehearsal.md
scripts/quick_bench.py
scripts/tournament.py
tests/test_quick_bench_ci.py
tests/test_tournament.py
ai/evaluator.py
ai/greedy_ai.py
ai/match.py
scripts/run_match.py
scripts/_bench_meta.py
tests/test_evaluator.py
tests/test_evaluator_injection.py
tests/test_bench_cli_metadata.py
```

### 5.2 任务包 02 可能修改

```text
ai/self_capture.py
tests/test_self_capture.py
scripts/param_sweep.py
tests/test_param_sweep.py
scripts/search_openings.py
tests/test_search_openings.py
ai/opening_layouts.py
gui/opening_panel.py
gui/main_window.py
reports/param_sweep.md
reports/opening_report.md
reports/ai_promotion_decision.md
```

### 5.3 任务包 03 可能修改

```text
ai/expectimax_v2.py
tests/test_expectimax_v2.py
ai/rollout_ai.py
tests/test_rollout_ai.py
ai/match.py
scripts/quick_bench.py
reports/expectimax_v2_experiment.md
reports/rollout_viability.md
```

### 5.4 任务包 04 可能修改

```text
release/v1.0/README.md
release/v1.0/config.json
release/v1.0/default_params.json
release/v1.0/test_report.md
release/v1.0/known_limitations.md
PROJECT_MEMORY.md
PROJECT_PHASES.md
docs/PROJECT_BRIEF.md
```

---

## 6. 禁止事项

- 不改 `core/` 规则语义，除非有规则 bug 和测试先行。
- 不在 `gui/` 中复制规则逻辑。
- 不新增网络依赖。
- 不引入大依赖。
- 不用单局胜负替换默认 AI。
- 不执行 git commit/push/reset，除非用户明确要求。
