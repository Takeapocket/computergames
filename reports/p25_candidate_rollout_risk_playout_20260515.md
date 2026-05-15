# rollout_risk_playout bench: stage=candidate

- 生成时间：2026-05-15T17:50:35
- 命令：`python scripts/bench_ai.py --candidate rollout_risk_playout --stage candidate --report-name p25_candidate_rollout_risk_playout_20260515`
- 候选：`rollout_risk_playout`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 候选参数（有效）：`{"deadline_safety_ms": 30.0}`
- 对手参数（有效）：`{}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "draw", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_risk_playout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 16, "cutoff_eval": "draw", "deadline_safety_ms": 0.0, "epsilon": 0.15, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 500.0, "name": "rollout", "playout_policy": "greedy", "rollouts_per_move": 16}`
- 总耗时：616.8s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：FAIL (实测 1)
- candidate_win_rate ≥ 55.0%：PASS (实测 58.5%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 182.9ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.8ms)

**Candidate 结论：FAIL**

失败原因：
- timeouts = 1（要求 = 0）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 63 | 37 | 0 | 63.0% | 186.8 | 493.2 | 615.8 | 720.4 |
| rollout 红 vs 候选 蓝 | 100 | 54 | 46 | 0 | 54.0% | 178.9 | 453.3 | 573.5 | 720.8 |
| **合并** | **200** | **117** | — | — | **58.5%** (Wilson 95% CI [51.6%, 65.1%]) | 182.9 | 493.2 | 615.8 | 720.8 |
