# rollout_zweistein_cutoff bench: stage=candidate

- 生成时间：2026-05-15T18:30:28
- 命令：`python scripts/bench_ai.py --candidate rollout_zweistein_cutoff --stage candidate --report-name p3_candidate_rollout_zweistein_cutoff_20260515`
- 候选：`rollout_zweistein_cutoff`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 候选参数（有效）：`{"deadline_safety_ms": 30.0}`
- 对手参数（有效）：`{}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_zweistein_cutoff", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 16, "cutoff_eval": "draw", "deadline_safety_ms": 0.0, "epsilon": 0.15, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 500.0, "name": "rollout", "playout_policy": "greedy", "rollouts_per_move": 16}`
- 总耗时：599.1s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 58.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 177.6ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.5ms)

**Candidate 结论：PASS**

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 62 | 38 | 0 | 62.0% | 181.1 | 478.0 | 564.3 | 720.5 |
| rollout 红 vs 候选 蓝 | 100 | 54 | 46 | 0 | 54.0% | 174.2 | 442.3 | 558.7 | 720.4 |
| **合并** | **200** | **116** | — | — | **58.0%** (Wilson 95% CI [51.1%, 64.6%]) | 177.6 | 478.0 | 564.3 | 720.5 |
