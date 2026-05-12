# Task Group 04 - Release v1.0 And Final Verification

目标：冻结比赛版本，形成现场可读、可执行、可恢复、可解释的 release 材料。这个任务包必须做，即使 AI 实验全部跳过。

---

## Task 11: release/v1.0 封版材料

**Files:**

- Create: `release/v1.0/README.md`
- Create: `release/v1.0/config.json`
- Create: `release/v1.0/default_params.json`
- Create: `release/v1.0/test_report.md`
- Create: `release/v1.0/known_limitations.md`
- Optionally create: `release/v1.0/sample_records/`

**Goal:** 让比赛现场能按文档启动、操作、恢复、解释默认 AI。

### Steps

- [ ] Create `release/v1.0/config.json`:

```json
{
  "version": "1.0",
  "default_ai": "greedy_risk",
  "default_layout": "balanced_v1",
  "board_size": 5,
  "time_limit_seconds": 240,
  "max_games_per_match": 7,
  "games_to_win_match": 4,
  "offline_required": true
}
```

If Task Group 02 promoted a candidate, update `default_ai` or `default_layout` and cite the report path in README.

- [ ] Create `release/v1.0/default_params.json`:

```json
{
  "ai": "greedy_risk",
  "distance_weight": 1.0,
  "material_weight": 10.0,
  "expected_risk_weight": 3.0,
  "expected_win_risk_weight": 500.0,
  "self_capture_weight": 0.0,
  "promotion_report": null
}
```

Adjust values only if promotion passed.

- [ ] Create `release/v1.0/README.md`.

Must include:

```markdown
# 爱恩斯坦棋参赛程序 v1.0

## 运行环境
- Python 3.11
- Windows + Tkinter
- 离线运行，不需要网络

## 启动
```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

## 比赛模式操作
1. 启动 GUI。
2. 进入比赛模式。
3. 选择我方甲乙身份和红蓝颜色。
4. 选择我方开局布局。
5. 录入对方开局。
6. 每回合录入骰子。
7. 对方回合录入对方走法。
8. 我方回合读取 `greedy_risk` 推荐并执行。
9. 单盘结束后记录胜方，进入下一盘。
10. 任一方 4 胜后结束本轮。

## 崩溃恢复
说明启动后如何接受 auto-save 恢复，以及何时拒绝恢复。

## 默认 AI
说明默认 AI 名称、是否经过 promotion gate、对应报告路径。

## 已知限制
See known_limitations.md
```

Do not claim tests pass until Task 12 has fresh verification output.

- [ ] Create `release/v1.0/known_limitations.md`.

Summarize from `reports/gui-rehearsal.md`:

```text
No fast-forward timer button
Timeout manual testing may require waiting or internal trigger
Experimental AIs are not default unless promotion report says otherwise
No unified platform adapter until official protocol exists
```

- [ ] Create `release/v1.0/test_report.md` skeleton:

```markdown
# Test Report

Date:

## Commands

| command | exit code | result |
|---|---:|---|

## pytest

## smoke_test

## s2_rehearsal

## GUI manual rehearsal

## AI baseline

## Promotion decisions

## Known limitations
```

Fill final outputs in Task 12.

---

## Task 12: 最终验证与交接

**Files:**

- Modify: `release/v1.0/test_report.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`
- Modify: `docs/PROJECT_BRIEF.md`

**Goal:** 用新鲜验证输出证明当前 release 状态，不用假设。

### Steps

- [ ] Full pytest:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Record in `release/v1.0/test_report.md`:

```text
command
exit code
pass/fail count from output
date/time
```

- [ ] Smoke test:

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Record output summary.

- [ ] S2 rehearsal:

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

Record whether 8/8 scenarios pass.

- [ ] AI baseline:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026 --report-name release_greedy_risk_vs_greedy
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026 --report-name release_greedy_vs_greedy_risk
```

Record:

```text
win rates
CI if available
illegal_moves
crashes
timeouts
avg_step_time_ms
max_step_time_ms
report paths
```

- [ ] Offline dependency check:

```powershell
rg "import socket|import urllib|import requests" --glob "*.py"
```

Expected:

```text
No production network import
```

- [ ] stuck cleanup check:

```powershell
rg "stuck_penalty|STUCK_PIECE_PENALTY|count_stuck_pieces" --glob "*.py"
```

Expected:

```text
No Python references if Task Group 01 cleanup was completed
```

If output exists, either finish cleanup or document why it was intentionally deferred.

- [ ] Manual GUI confirmation:

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

Manual checklist:

```text
GUI starts
opening panel visible
match mode available
dice input works
AI recommendation visible after dice input
save/load menus work
```

Record in `release/v1.0/test_report.md`.

- [ ] Update project docs:

```text
PROJECT_MEMORY.md
PROJECT_PHASES.md
docs/PROJECT_BRIEF.md
```

Must state:

```text
S2 manual status
AI default status
whether stuck cleanup completed
whether parameter/opening candidate promoted
release/v1.0 status
latest verification commands and dates
```

- [ ] Final diff review:

```powershell
git diff -- docs/superpowers PROJECT_MEMORY.md PROJECT_PHASES.md docs/PROJECT_BRIEF.md release/v1.0
git status --short
```

Allowed:

```text
Modified docs and reports
New release files
New AI/harness files only if corresponding tasks were executed
```

Do not commit unless the user explicitly asks.
