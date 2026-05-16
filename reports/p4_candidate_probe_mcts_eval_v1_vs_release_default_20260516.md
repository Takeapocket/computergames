# mcts_eval_v1 bench: stage=candidate

- 生成时间：2026-05-16T13:06:57
- 命令：`python scripts/bench_ai.py --candidate mcts_eval_v1 --stage candidate --games-per-side 25 --candidate-arg time_limit_ms=200 --report-name p4_candidate_probe_mcts_eval_v1_vs_release_default_20260516`
- 候选：`mcts_eval_v1`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 候选参数（有效）：`{"time_limit_ms": 200}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"c_uct": 1.4142135623730951, "max_iterations": null, "name": "mcts_eval_v1", "scale": 100.0, "time_limit_ms": 200.0}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选参数：time_limit_ms=200
- 总耗时：197.8s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 30.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 214.5ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.4ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 30.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms | avg_iters | max_depth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 7 | 18 | 0 | 28.0% | 209.0 | 460.2 | 622.1 | 720.1 | 4938.1 | 11 |
| rollout 红 vs 候选 蓝 | 25 | 8 | 17 | 0 | 32.0% | 220.0 | 488.2 | 718.4 | 720.4 | 5305.4 | 11 |
| **合并** | **50** | **15** | — | — | **30.0%** (Wilson 95% CI [19.1%, 43.8%]) | 214.5 | 488.2 | 718.4 | 720.4 | 5121.7 | 11 |
