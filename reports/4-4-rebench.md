# 阶段 4.4 重跑（R-0 合规规则）

> 历史报告（2026-05-11）。本文中 `greedy_risk` 作为竞赛主力或 GUI 默认引用的表述是当时上下文；当前默认 AI 已升级为旧 flat `rollout`。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

更新时间：2026-05-11
关联：阶段 R-0；原报告 `reports/4-4-failure-analysis.md`。

## TL;DR

R-0 合规修复后重跑 `ExpectimaxAI(depth=1)` vs `greedy_risk`，合并胜率 **45.0%**（旧 46.5%，-1.5pp，统计上不可区分）。

**ExpectimaxAI 在合规规则下仍显著弱于 `greedy_risk`**。原 PROJECT_PHASES 的猜想"R-0 后吃自己子的策略让多步 lookahead 价值上升"在 depth=1 下不成立；保留为研究代码的决策不变。

## 数据（n=200 / direction，n=400 合并）

固定参数：master_seed=2026，max_turns=200，layout=`default_no_stuck_corner_v1`，`depth=1`，`expected_risk_weight=3.0`，`expected_win_risk_weight=500.0`（与原 4.4 一致）。

| 对局 | 局数 | expectimax 胜率 | avg_step_ms | illegal | crashes | 报告 |
|---|---:|---:|---:|:---:|:---:|---|
| 红 `expectimax` vs 蓝 `greedy_risk` | 200 | **45.0%** (90/200) | 4.30 | 0 | 0 | `bench_phase_4_4_expectimax_vs_greedy_risk.json` |
| 红 `greedy_risk` vs 蓝 `expectimax` | 200 | **45.0%** (90/200 blue) | 3.98 | 0 | 0 | `bench_phase_4_4_greedy_risk_vs_expectimax.json` |
| **合并** | 400 | **45.0%** (180/400) | — | 0 | 0 | — |

旧合并：46.5%（n=400，相同 seed）。新差 -1.5pp ≈ 0.6σ，无显著变化。

## 解读

- **PROJECT_PHASES 主线调整建议中的猜想被证伪**：合规规则下吃自己子是合法走法，但 `depth=1` 的 ExpectimaxAI 没有从这个扩张的搜索空间中获得净收益。原 4-4-failure-analysis 中的根因分析（"风险项与 lookahead 的耦合错位"）仍然成立——evaluator 中 `expected_target_win_risk` / `distance_weighted_capture_risk` 为 1-ply 设计，在 expectimax 内部节点上语义错位。
- **不在竞赛主力上使用**：决策不变。`build_ai("expectimax", ...)` 保留为实验入口；当前 GUI 默认不引用 expectimax。
- **step time**：~4ms / 步，远低于赛事 4 分钟包干（n=200 平均每局 19 步 ≈ 76ms 总耗时）。性能不是当前 ExpectimaxAI 弱的原因，evaluator 错位才是。

## R-0-followup / 后续 Expectimax 实验入口

下列 4 个假设源自 `reports/4-4-failure-analysis.md`，R-0 未执行；R-0 重跑数据没有否定它们，只是确认"什么都不改的 ExpectimaxAI 在合规规则下仍弱"：

1. **裸 ExpectimaxAI**：`expectimax(depth=1, expected_risk_weight=0, expected_win_risk_weight=0)` vs `greedy`（裸 evaluator）。若打平，则锁定根因是 risk 项与 lookahead 耦合。
2. **风险项在 leaf 关闭**：让 ExpectimaxAI 在 leaf eval 强制 `expected_*_weight=0`，中间节点保留。
3. **改写 risk 函数**：让 `expected_*_risk` 接受"哪一方的下一回合"参数，而不是默认对手。
4. **depth=2 / depth=3**：增大 lookahead。注意 depth=2 单步可能数十 ms × 6^2 分支，需要先评估时限预算。

这些都不属于赛前必须，赛后或时间允许时再做。

## 复现命令

```bash
.venv/Scripts/python.exe scripts/quick_bench.py --red expectimax --blue greedy_risk --games 200 --seed 2026 --report-name bench_phase_4_4_expectimax_vs_greedy_risk
.venv/Scripts/python.exe scripts/quick_bench.py --red greedy_risk --blue expectimax --games 200 --seed 2026 --report-name bench_phase_4_4_greedy_risk_vs_expectimax
```
