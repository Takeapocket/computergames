# rollout_cutoff_eval bench: stage=candidate

- 生成时间：2026-05-15T18:02:52
- 命令：`python scripts/bench_ai.py --candidate rollout_cutoff_eval --stage candidate --report-name p25_candidate_rollout_cutoff_eval_20260515`
- 候选：`rollout_cutoff_eval`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 候选参数（有效）：`{"deadline_safety_ms": 30.0}`
- 对手参数（有效）：`{}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "current", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_cutoff_eval", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 16, "cutoff_eval": "draw", "deadline_safety_ms": 0.0, "epsilon": 0.15, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 500.0, "name": "rollout", "playout_policy": "greedy", "rollouts_per_move": 16}`
- 总耗时：612.5s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 57.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 179.9ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 721.0ms)

**Candidate 结论：PASS**

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 61 | 39 | 0 | 61.0% | 182.8 | 485.5 | 570.9 | 721.0 |
| rollout 红 vs 候选 蓝 | 100 | 53 | 47 | 0 | 53.0% | 177.0 | 450.8 | 556.7 | 720.5 |
| **合并** | **200** | **114** | — | — | **57.0%** (Wilson 95% CI [50.1%, 63.7%]) | 179.9 | 485.5 | 570.9 | 721.0 |
