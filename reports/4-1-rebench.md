# 阶段 4.1 重跑（R-0 合规规则）

更新时间：2026-05-11
关联：阶段 R-0（`core/rules.py` 允许吃本方棋子）；原报告 `reports/4-1-decision-record.md` / `reports/4-1-failure-analysis.md`。

## TL;DR

R-0 合规修复后重跑 5 份 4.1 系列 bench（slim 格式，无 `per_game[]`）。所有验收门槛均通过：

- GreedyAI vs RandomAI 合并胜率 **63.75%**（旧 68.25%，-4.5pp，仍 ≥ 60% 门槛 ✓）
- illegal/crashes/timeouts 全为 0
- Greedy 自对弈红胜率 0.58（与旧版完全一致）

## 数据

固定参数：master_seed=2026，max_turns=200，stuck_penalty=100（除 baseline）。

| 对局 | layout | 局数 | 旧 candidate 胜率 | 新 candidate 胜率 | Δ | 报告 |
|---|---|---:|---:|---:|---:|---|
| 红 Greedy(stuck=0) vs 蓝 Random | standard_triangle_v1 | 200 | 0.590 | **0.660** (132/200) | +7.0 pp | `bench_phase_4_1_baseline_greedy_vs_random.json` |
| 红 Greedy(stuck=100) vs 蓝 Random | default_no_stuck_corner_v1 | 200 | 0.650 | **0.645** (129/200) | -0.5 pp | `bench_phase_4_1_greedy_vs_random.json` |
| 红 Random vs 蓝 Greedy(stuck=100) | default_no_stuck_corner_v1 | 200 | 0.715(蓝) | **0.630**(蓝, 126/200) | -8.5 pp | `bench_phase_4_1_random_vs_greedy.json` |
| 红 Greedy vs 蓝 Greedy（自对弈） | default_no_stuck_corner_v1 | 100 | 0.580(红) | **0.580**(红, 58/100) | 0 | `bench_phase_4_1_greedy_vs_greedy.json` |
| 红 Random vs 蓝 Random（4.0 sanity） | standard_triangle_v1 | 100 | — | 0.510 / 0.490 | — | `bench_phase_4_0_random_vs_random.json` |

合并 GreedyAI vs RandomAI：(129 + 126) / 400 = **63.75%**（旧 (130 + 143) / 400 = 68.25%）。

合并 n=400 下 σ ≈ 2.5%，差值 -4.5pp ≈ 1.8σ，处于噪声边界。各分支单方向差值在 n=200 σ ≈ 3.5% 下也都不超过 2.5σ。

## 解读

- **baseline 跳了 +7pp**：`standard_triangle_v1` 开局下 piece 1 在 (0,0)、被 piece 2/4/5 围死，旧规则下 dice=1 强制选 piece 1 + 无合法走法 → forfeit。新规则下 piece 1 可吃本方 2/4/5 任一个脱困，红方 forfeit 概率显著降低。失败分析里"baseline 48 局 forfeit 输"在合规规则下应大幅减少（未在本次 slim 重跑中逐局聚合，留待 R-0-followup 视需要再做）。
- **production 几乎不变**：`default_no_stuck_corner_v1` 本身就是为规避旧规则下的 forfeit 而设计的开局；R-0 合规修复后这层规避变得多余但不致害，胜率自然不动。
- **reverse 蓝 greedy 掉 -8.5pp**：噪声边界，且不影响门槛。可能与 GreedyAI 评估器没有显式建模 self-capture 战略价值有关——新规则把对手的合法走法数量也放大了，RandomAI 偶尔的自残走法可能恰好解开其困局。
- **self-play 完全不变**：master_seed + dice_rng 派生方式让两边随机源同步；双方都开放自残后，决策序列在该 seed 下与旧版逐字节一致是巧合，但红 0.58 / 蓝 0.42 的先手优势统计上稳定。

## 已知 R-0 副作用（不在本次修复范围）

- `count_stuck_pieces` 函数在合规规则下基本恒为 0（任何"被本方围死"的棋子都能自残脱困；唯一真正 stuck 的位置是目标角，但到达即胜，不进入评估），`STUCK_PIECE_PENALTY = 100.0` 实际乘子恒为 0。已在 `tests/test_evaluator.py::test_count_stuck_pieces_zero_for_corner_surrounded_by_own_post_R0` 与 `tests/test_evaluator_injection.py::test_evaluate_accepts_stuck_penalty_kwarg_and_zero_disables_penalty` 中明确这一新语义。
- 完整删除 `STUCK_PIECE_PENALTY` / `count_stuck_pieces` 及 CLI 上的 `--red/blue-stuck-penalty` flag 留待 R-0-followup。

## 复现命令

```bash
.venv/Scripts/python.exe scripts/reproduce_phase_4_1.py
```

bench schema 仍为 v2；R-0 重跑后默认 slim（无 `per_game[]`），文件体积从 ~600KB 降至 ~1.2KB。如需复跑某条诊断对局，从 `command` 字段取参数，加 `--include-per-game` 即可恢复 forensic 数据。
