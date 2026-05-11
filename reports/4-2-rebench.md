# 阶段 4.2 重跑（R-0 合规规则）

更新时间：2026-05-11
关联：阶段 R-0；原报告 `reports/4-2-failure-analysis.md`。

## TL;DR

R-0 合规修复后重跑 4.2 `greedy_risk` vs `greedy`（默认 `expected_risk_weight=3.0`, `expected_win_risk_weight=500.0`），合并胜率 **55.75%**（旧 n=2000 真值 53.8%，差 +2pp，远小于 ≤ 5pp 门槛 ✓）。

`greedy_risk` 仍稳定优于 `greedy`；distance-weighted capture risk 的工程价值不受规则修复影响。

## 数据（n=200 / direction，n=400 合并）

固定参数：master_seed=2026，max_turns=200，layout=`default_no_stuck_corner_v1`，`expected_risk_weight=3.0`，`expected_win_risk_weight=500.0`。

| 对局 | 局数 | candidate 胜率 | illegal | crashes | 报告 |
|---|---:|---:|:---:|:---:|---|
| 红 `greedy_risk` vs 蓝 `greedy` | 200 | **58.0%** (116/200) | 0 | 0 | `bench_phase_4_2_greedy_risk_vs_greedy.json` |
| 红 `greedy` vs 蓝 `greedy_risk` | 200 | **53.5%** (107/200 blue) | 0 | 0 | `bench_phase_4_2_greedy_vs_greedy_risk.json` |
| **合并** | 400 | **55.75%** (223/400) | 0 | 0 | — |

n=400 σ ≈ 2.5%，新合并 55.75% 与旧 n=2000 真值 53.8% 差 +2pp ≈ 0.8σ，统计学上无法区分。

## 解读

- **门槛通过**：≤ 5pp 差异要求达成。"风险感知评估对 1-ply greedy 有约 +4pp 的稳定提升"这一结论在合规规则下成立。
- **未做 weight grid 重跑**：原 `scripts/_grid_validate_4_2.py` n=2000 grid 显示 weight ∈ [1.0, 5.0] 在统计上不可区分；R-0 重跑没有改变 evaluator 的可观察行为（distance / material / capture risk 全部基于 core API，core 的语义扩张不影响这些函数的输出），因此 grid 重跑被推迟到 R-0-followup（若届时仍要做参数微调时再跑）。
- **expected_capture_risk 是否需要扩展到 self-capture risk**：当前 `ai/risk.py:expected_capture_risk` 枚举对手下回合骰子下的合法走法，过滤 `captured.player is player`——对手的自残走法因 `captured.player is opponent` 被自动排除，对我方威胁评估无误。但 evaluator 不感知 "我方自己下一步可能为了占位/吃子而自残"的战略，这是 evaluator 评估的盲点之一。是否新增 `expected_self_capture_risk` 取决于实战需要，R-0 不做。

## R-0-followup（可选）

- 跑一次 n=1000 / direction 的 weight grid，确认 weight ∈ [1.0, 5.0] 不可区分在合规规则下仍成立。
- 在 evaluator 加入 self-capture 战略价值项（例如：自残后释放出 stuck piece 的"距离改善 - 子力损失"）。这是 4.2 范畴的增量改进，不属于规则合规。

## 复现命令

```bash
.venv/Scripts/python.exe scripts/quick_bench.py --red greedy_risk --blue greedy --games 200 --seed 2026 --report-name bench_phase_4_2_greedy_risk_vs_greedy
.venv/Scripts/python.exe scripts/quick_bench.py --red greedy --blue greedy_risk --games 200 --seed 2026 --report-name bench_phase_4_2_greedy_vs_greedy_risk
```
