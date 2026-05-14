# mcts_eval_v1 Phase 1 Candidate Bench

- 生成时间：2026-05-14T10:40:33
- 命令：`python scripts/bench_mcts.py --stage candidate --seed 2026 --time-limit-ms 500 --report-name candidate_mcts_eval_v1_500ms_20260514_101344`
- 阶段：`candidate`
- 对手：`greedy_risk`
- master seed：2026
- 每方局数：200
- 最大半步：200
- mcts_eval_v1 参数：time_limit_ms=500.0, max_iterations=None
- 总耗时：1608.1s

## 门禁（设计文档 §10 候选）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- mcts_win_rate ≥ 55.0%：FAIL (实测 50.2%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 227.4ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 557.1ms)

**Candidate 结论：FAIL**

失败原因：
- mcts_win_rate = 50.2%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | MCTS 胜 | 对手胜 | 平 | MCTS 胜率 | avg_step_ms | max_step_ms | avg_iters | max_depth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MCTS 红 vs greedy_risk 蓝 | 200 | 106 | 94 | 0 | 53.0% | 233.4 | 517.5 | 9181.4 | 11 |
| greedy_risk 红 vs MCTS 蓝 | 200 | 95 | 105 | 0 | 47.5% | 221.5 | 557.1 | 9029.0 | 11 |
| **合并** | **400** | **201** | — | — | **50.2%** (Wilson 95% CI [45.4%, 55.1%]) | 227.4 | 557.1 | 9105.2 | 11 |

## 注意

候选阶段证明 mcts_eval_v1 在标准对手 `greedy_risk` 上有统计优势。
晋升为默认 AI 仍需对 `rollout` 跑晋升阶段（≥400 局/方向，Wilson 下界 ≥52%）。
