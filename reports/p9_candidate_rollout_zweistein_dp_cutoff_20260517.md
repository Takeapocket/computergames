# rollout_zweistein_dp_cutoff bench: stage=candidate

- 生成时间：2026-05-17T17:01:42
- 命令：`python scripts/bench_ai.py --candidate rollout_zweistein_dp_cutoff --stage candidate --report-name p9_candidate_rollout_zweistein_dp_cutoff_20260517`
- 候选：`rollout_zweistein_dp_cutoff`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein_dp", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_zweistein_dp_cutoff", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：1083.9s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 45.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 293.8ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.9ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 45.0%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 51 | 49 | 0 | 51.0% | 287.5 | 595.0 | 720.2 | 720.9 |
| rollout 红 vs 候选 蓝 | 100 | 39 | 61 | 0 | 39.0% | 300.0 | 597.4 | 720.3 | 720.8 |
| **合并** | **200** | **90** | — | — | **45.0%** (Wilson 95% CI [38.3%, 51.9%]) | 293.8 | 597.4 | 720.3 | 720.9 |
