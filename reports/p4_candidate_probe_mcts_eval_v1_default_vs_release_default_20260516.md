# mcts_eval_v1 bench: stage=candidate

- 生成时间：2026-05-16T13:09:31
- 命令：`python scripts/bench_ai.py --candidate mcts_eval_v1 --stage candidate --games-per-side 10 --report-name p4_candidate_probe_mcts_eval_v1_default_vs_release_default_20260516`
- 候选：`mcts_eval_v1`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：10
- 最大半步：200
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"c_uct": 1.4142135623730951, "max_iterations": null, "name": "mcts_eval_v1", "scale": 100.0, "time_limit_ms": 500.0}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：130.8s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 30.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 351.4ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 719.7ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 30.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms | avg_iters | max_depth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 10 | 3 | 7 | 0 | 30.0% | 356.2 | 502.6 | 647.6 | 656.4 | 12519.5 | 11 |
| rollout 红 vs 候选 蓝 | 10 | 3 | 7 | 0 | 30.0% | 346.7 | 502.6 | 525.9 | 719.7 | 15217.1 | 3 |
| **合并** | **20** | **6** | — | — | **30.0%** (Wilson 95% CI [14.5%, 51.9%]) | 351.4 | 502.6 | 647.6 | 719.7 | 13868.3 | 11 |
