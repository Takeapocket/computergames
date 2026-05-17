# rollout_adaptive_close_sample bench: stage=candidate

- 生成时间：2026-05-17T13:07:53
- 命令：`python scripts/bench_ai.py --candidate rollout_adaptive_close_sample --opponent rollout --stage candidate --games-per-side 100 --report-name p72_candidate_rollout_adaptive_close_sample_20260516`
- 候选：`rollout_adaptive_close_sample`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.06, "close_sample_rollouts_per_move": 64, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.06, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_adaptive_close_sample", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：1134.4s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 50.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 310.3ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 721.3ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 50.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 53 | 47 | 0 | 53.0% | 315.7 | 720.1 | 720.4 | 720.8 |
| rollout 红 vs 候选 蓝 | 100 | 47 | 53 | 0 | 47.0% | 304.9 | 720.1 | 720.3 | 721.3 |
| **合并** | **200** | **100** | — | — | **50.0%** (Wilson 95% CI [43.1%, 56.9%]) | 310.3 | 720.1 | 720.4 | 721.3 |
