# mcts_eval_v1 Phase 1 Smoke Bench

- 生成时间：2026-05-13T22:36:52
- 命令：`python scripts/bench_mcts.py --stage smoke --seed 2026 --games-per-side 50 --time-limit-ms 200 --report-name smoke_parity_check_20260513_223413`
- 阶段：`smoke`
- 对手：`greedy`
- master seed：2026
- 每方局数：50
- 最大半步：200
- mcts_eval_v1 参数：time_limit_ms=200.0, max_iterations=None
- 总耗时：161.3s

## 门禁（设计文档 §10 smoke）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- max_step_time_ms < 1000.0ms：PASS (实测 204.5ms)

**Smoke 结论：PASS**

## 双向胜率

| 方向 | 局数 | MCTS 胜 | 对手胜 | 平 | MCTS 胜率 | avg_step_ms | max_step_ms | avg_iters | max_depth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MCTS 红 vs greedy 蓝 | 50 | 30 | 20 | 0 | 60.0% | 94.9 | 201.3 | 4319.4 | 9 |
| greedy 红 vs MCTS 蓝 | 50 | 24 | 26 | 0 | 48.0% | 89.4 | 204.5 | 3059.4 | 9 |
| **合并** | **100** | **54** | — | — | **54.0%** (Wilson 95% CI [44.3%, 63.4%]) | 92.2 | 204.5 | 3689.4 | 9 |

## 注意

本 smoke 只验证稳定性，胜率仅供参考；要判断 mcts_eval_v1 是否能晋升默认 AI，需要
对 `rollout` 做更大样本的候选/晋升阶段 bench（见设计文档 §10）。
