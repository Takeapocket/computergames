# 赛前收官冲刺 Implementation Plan

> 历史执行计划（2026-05-12）。本文中的 `greedy_risk` 默认、候选对 `greedy_risk` 的门禁等内容是执行前上下文；当前默认 AI 已升级为旧 flat `rollout`，adaptive rollout 是显式实验候选而非 release 默认。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or equivalent task-by-task execution.
>
> **Project override:** 未经用户明确要求，不执行 `git commit`、`git push`、`git reset --hard`。本计划使用“测试 + diff + 报告”作为 checkpoint。

**Goal:** 2026-05-18 前交付一个离线、稳定、可操作、默认 AI 有数据支撑、release 材料完整的爱恩斯坦棋参赛程序。

**Architecture:** `core/` 规则语义冻结；GUI 不复制规则；AI 只通过 `GameState` API 使用规则；所有 AI 候选先进入 harness 和 reports，只有通过晋升门禁才允许进入 GUI 默认或 release 默认。

**Tech Stack:** Python 3.11、pytest、tkinter、项目现有 `GameState` / `GameRecord` / `quick_bench` harness。不新增网络依赖，不引入 PyTorch、Gymnasium、OpenSpiel 运行时依赖。

---

## 0. 为什么拆分

上一版执行计划接近 2000 行，虽然细节完整，但不适合作为后续 AI 或人类开发者的主入口。主入口应该回答“现在做什么、为什么、做到什么程度算过”，详细步骤应拆到任务包里。

本文件现在只保留：

- 阶段顺序。
- 必须遵守的门禁。
- 每个任务包的入口链接。
- 最终完成定义。

详细执行步骤拆分到 `docs/superpowers/plans/final-sprint/`。

---

## 1. 接手前必须读取

每次新会话或新 AI 接手时，先读：

1. `PROJECT_MEMORY.md`
2. `PROJECT_PHASES.md`
3. `README.md`
4. `docs/RULE_ASSUMPTIONS.md`
5. `docs/PROJECT_BRIEF.md`
6. `docs/superpowers/specs/2026-05-12-final-sprint-design.md`
7. 本文件

不要只凭历史印象判断项目状态；以当前仓库文件和最新验证输出为准。

---

## 2. 阶段顺序

```text
Task Group 00  全局门禁与上下文
Task Group 01  S2 真实 GUI 手动演练 + harness 工程化 + stuck 清理
Task Group 02  低风险 AI：self-capture、参数搜索、开局搜索、晋升判定
Task Group 03  实验性 AI：ExpectimaxV2、RolloutAI
Task Group 04  release/v1.0 封版与最终验证
```

执行优先级：

```text
必须先做：00 -> 01
有收益才做：02
时间允许才做：03
最后必做：04
```

关键判断：

- 历史上下文：`greedy_risk` 是当时稳定参赛默认 AI；当前默认 AI 是旧 flat `rollout`。
- S2 真实 GUI 手动表未填完前，不应把主线切到 AI 大改。
- AI 可以优化，但必须被 harness 证明，不能凭单局或单 seed 决定。
- Expectimax 和 Rollout 都是实验项，不得阻塞封版。

---

## 3. 任务包入口

| 任务包 | 文件 | 目标 | 是否必做 |
|---|---|---|---|
| 00 | `docs/superpowers/plans/final-sprint/00-context-gates.md` | 统一上下文、S0 基线、AI/开局晋升门禁、文件责任图 | 必做 |
| 01 | `docs/superpowers/plans/final-sprint/01-stability-harness.md` | 补齐真实 GUI 手测；增加 Wilson CI；新增 tournament；清理 `stuck_penalty` | 必做，stuck 清理强烈建议 |
| 02 | `docs/superpowers/plans/final-sprint/02-low-risk-ai.md` | self-capture 评估、参数搜索、开局搜索、候选晋升判定 | 有时间就做，优先于实验 AI |
| 03 | `docs/superpowers/plans/final-sprint/03-experimental-ai.md` | ExpectimaxV2 / RolloutAI 时间盒实验 | 可跳过 |
| 04 | `docs/superpowers/plans/final-sprint/04-release.md` | release/v1.0 文档、最终验证、项目状态同步 | 必做 |

---

## 4. 全局禁止事项

- 不改 `core/` 规则语义，除非先发现规则 bug，并同步补 `tests/test_rules.py` / `tests/test_game_state.py`。
- 不在 `gui/` 中复制合法步、骰子映射、胜负判断。
- 不新增联网依赖，不 import `socket`、`urllib`、`requests`。
- 不引入大依赖，不新增深度学习、Gym、OpenSpiel runtime。
- 不因单局或单 seed 结果替换默认 AI。
- 不在封版阶段做大规模重构。
- 不执行 git commit/push/reset，除非用户明确要求。

---

## 5. 每个代码任务前的 S0 基线

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected:

```text
pytest exit code 0
smoke_test exit code 0
```

如果失败：

1. 不开始新功能。
2. 判断失败是否由当前工作区变更引起。
3. 只修与失败相关的最小范围。
4. 重跑失败测试和 S0。

---

## 6. AI 晋升门禁

任何替换 GUI 默认 AI 或 release 默认 AI 的候选必须满足：

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

未过 gate 的候选只能保留为实验入口，不接 GUI 默认。

---

## 7. 开局晋升门禁

任何替换 GUI 默认布局或 release 推荐布局的候选必须满足：

```text
candidate layout vs current layout: at least 400 total games
both red and blue roles covered
merged win rate > 53%
Wilson 95% CI lower bound >= 50%
illegal_moves = 0
crashes = 0
real timeout telemetry = 0
layout appears in GUI OpeningPanel preset menu
report written to reports/opening_report.md
```

---

## 8. 如果时间不足怎么取舍

优先级从高到低：

1. 完成 S2 真实 GUI 手动演练表。
2. 完成 release/v1.0 文档和最终验证。
3. 增加 harness CI / tournament，提高 AI 结论可信度。
4. 清理 `stuck_penalty`，避免参数搜索污染。
5. 做参数搜索和开局搜索。
6. 做 self-capture 评估实验。
7. 做 ExpectimaxV2。
8. 做 RolloutAI。

如果只剩一天，停止所有实验性 AI，只做 GUI 手测、release 和最终验证。

---

## 9. 完成定义

本计划不能用“写完代码”作为完成标准。完成必须满足：

```text
S2 真实 GUI 表已填
pytest 新鲜运行通过
smoke_test 新鲜运行通过
s2_rehearsal 新鲜运行通过
AI 默认是否变更有 promotion decision 报告
release/v1.0 文档完整
无生产网络依赖
用户未要求时没有 git commit/push/reset
```

---

## 10. 常用命令

```powershell
# baseline
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"

# GUI
& ".venv/Scripts/python.exe" "scripts/run_gui.py"

# S2
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"

# current AI baseline
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026

# network check
rg "import socket|import urllib|import requests" --glob "*.py"
```
