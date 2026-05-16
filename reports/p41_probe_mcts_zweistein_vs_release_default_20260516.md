# mcts_eval_v1 bench: stage=candidate

- 生成时间：2026-05-16T13:40:43
- 命令：`python scripts/bench_ai.py --candidate mcts_eval_v1 --stage candidate --games-per-side 10 --candidate-arg leaf_evaluator=zweistein --report-name p41_probe_mcts_zweistein_vs_release_default_20260516`
- 候选：`mcts_eval_v1`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：10
- 最大半步：200
- 候选参数（有效）：`{"leaf_evaluator": "zweistein"}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"c_uct": 1.4142135623730951, "leaf_evaluator": "zweistein", "max_iterations": null, "name": "mcts_eval_v1", "scale": 100.0, "time_limit_ms": 500.0}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选参数：leaf_evaluator=zweistein
- 总耗时：129.6s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 25.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 348.9ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.2ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 25.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms | avg_iters | max_depth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 10 | 3 | 7 | 0 | 30.0% | 356.7 | 501.4 | 658.2 | 704.5 | 13795.3 | 11 |
| rollout 红 vs 候选 蓝 | 10 | 2 | 8 | 0 | 20.0% | 341.2 | 501.5 | 537.2 | 720.2 | 10182.5 | 9 |
| **合并** | **20** | **5** | — | — | **25.0%** (Wilson 95% CI [11.2%, 46.9%]) | 348.9 | 501.5 | 658.2 | 720.2 | 11988.9 | 11 |
