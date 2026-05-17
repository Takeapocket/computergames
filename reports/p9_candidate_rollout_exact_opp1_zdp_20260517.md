# rollout_exact_opp1_zdp bench: stage=candidate

- 生成时间：2026-05-17T17:19:35
- 命令：`python scripts/bench_ai.py --candidate rollout_exact_opp1_zdp --stage candidate --report-name p9_candidate_rollout_exact_opp1_zdp_20260517`
- 候选：`rollout_exact_opp1_zdp`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"base": {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}, "exact_mix": 0.35, "max_step_time_ms": 750.0, "min_time_remaining_ms": 20.0, "name": "rollout_exact_opp1_zdp", "top_k": 3}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：1056.4s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 51.5%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 289.7ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 723.2ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 51.5%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 56 | 44 | 0 | 56.0% | 296.8 | 598.1 | 721.9 | 723.0 |
| rollout 红 vs 候选 蓝 | 100 | 47 | 53 | 0 | 47.0% | 282.5 | 586.9 | 720.3 | 723.2 |
| **合并** | **200** | **103** | — | — | **51.5%** (Wilson 95% CI [44.6%, 58.3%]) | 289.7 | 598.1 | 721.9 | 723.2 |

## 战术分支命中统计

- fire_applied: 9
- fire_considered: 200
- fire_passthrough_no_change: 191
