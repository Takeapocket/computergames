# rollout_zweistein_cutoff bench: stage=promotion

- 生成时间：2026-05-15T20:59:38
- 命令：`python scripts/bench_ai.py --candidate rollout_zweistein_cutoff --stage promotion --report-name p3_promotion_rollout_zweistein_cutoff_20260515`
- 候选：`rollout_zweistein_cutoff`
- 阶段：`promotion`
- 对手：`rollout`
- master seed：2026
- 每方局数：400
- 最大半步：200
- 候选参数（有效）：`{"deadline_safety_ms": 30.0}`
- 对手参数（有效）：`{}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_zweistein_cutoff", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 16, "cutoff_eval": "draw", "deadline_safety_ms": 0.0, "epsilon": 0.15, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 500.0, "name": "rollout", "playout_policy": "greedy", "rollouts_per_move": 16}`
- 总耗时：2380.1s

## 门禁（stage=promotion）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 56.8%)
- candidate_win_ci_lower ≥ 52.0%：PASS (实测 53.3%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 175.8ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.7ms)

**Promotion 结论：PASS**

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 400 | 240 | 160 | 0 | 60.0% | 179.5 | 481.3 | 587.8 | 720.7 |
| rollout 红 vs 候选 蓝 | 400 | 214 | 186 | 0 | 53.5% | 172.0 | 441.7 | 556.2 | 720.6 |
| **合并** | **800** | **454** | — | — | **56.8%** (Wilson 95% CI [53.3%, 60.1%]) | 175.8 | 481.3 | 587.8 | 720.7 |
