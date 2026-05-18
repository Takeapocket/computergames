# rollout_paired bench: stage=candidate

- 生成时间：2026-05-18T23:03:19
- 命令：`python scripts/bench_ai.py --candidate rollout_paired --stage candidate --report-name p12_candidate_rollout_paired_20260518`
- 候选：`rollout_paired`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout_paired", "paired_shuffle_moves": false, "paired_trial_seed_stride": 1000003, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：284.7s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 50.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 314.2ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 720.8ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 50.0%（要求 ≥ 55.0%）

## P12 paired rollout 决策

- candidate gate：FAIL
- candidate win rate：50.0%
- Wilson 95% CI：[36.6%, 63.4%]
- illegal/crash/timeout：0 / 0 / 0
- avg/max step time：314.2ms / 720.8ms
- 是否修改默认配置：没有
- 是否修改 core 规则：没有
- 是否建议扩样：否
- 结论：不默认启用，不扩样。

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 15 | 10 | 0 | 60.0% | 315.6 | 629.7 | 720.3 | 720.6 |
| rollout 红 vs 候选 蓝 | 25 | 10 | 15 | 0 | 40.0% | 312.9 | 630.0 | 720.3 | 720.8 |
| **合并** | **50** | **25** | — | — | **50.0%** (Wilson 95% CI [36.6%, 63.4%]) | 314.2 | 630.0 | 720.3 | 720.8 |
