# rollout_root_racing bench: stage=candidate

- 生成时间：2026-05-18T14:31:28
- 命令：`python scripts/bench_ai.py --candidate rollout_root_racing --stage candidate --report-name p10_candidate_rollout_root_racing_20260518`
- 候选：`rollout_root_racing`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_root_racing", "playout_policy": "greedy_risk", "racing_batch_rollouts_per_move": 2, "racing_final_survivor_count": 2, "racing_initial_rollouts_per_move": 6, "racing_survivor_count": 4, "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：290.8s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 40.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 305.1ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.5ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 40.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 7 | 18 | 0 | 28.0% | 318.2 | 641.1 | 720.2 | 720.5 |
| rollout 红 vs 候选 蓝 | 25 | 13 | 12 | 0 | 52.0% | 291.9 | 623.8 | 720.3 | 720.4 |
| **合并** | **50** | **20** | — | — | **40.0%** (Wilson 95% CI [27.6%, 53.8%]) | 305.1 | 641.1 | 720.3 | 720.5 |
