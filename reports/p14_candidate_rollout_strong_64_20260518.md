# rollout_strong_64 bench: stage=candidate

- 生成时间：2026-05-19T00:09:19
- 命令：`python scripts/bench_ai.py --candidate rollout_strong_64 --stage candidate --report-name p14_candidate_rollout_strong_64_20260518`
- 候选：`rollout_strong_64`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 96, "cutoff_eval": "zweistein", "deadline_safety_ms": 80.0, "epsilon": 0.08, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 2000.0, "name": "rollout_strong_64", "playout_policy": "greedy_risk", "rollouts_per_move": 64}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：493.1s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 58.0%)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 1920.7ms)

**Candidate 结论：PASS**

## P14 strong rollout 决策

- candidate gate：PASS
- 52% 门槛：PASS
- 55% 门槛：PASS
- 50+50 门槛：未执行或未通过
- candidate win rate：58.0%
- Wilson 95% CI：[44.2%, 70.6%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：549.8 / 1691.2 / 1920.2 / 1920.7
- per-side thinking time：max_red_thinking_seconds=10.5, max_blue_thinking_seconds=8.4, avg_red_thinking_seconds=5.3, avg_blue_thinking_seconds=4.6
- timing risk：否
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 是否建议扩样：是
- 结论：通过 55% 初筛；建议扩到 50+50，不默认启用。

## 步时与包干估算

- total_step_time_ms：493007.3
- average_turns：17.92
- avg/p95/p99/max step ms：549.8 / 1691.2 / 1920.2 / 1920.7
- max_red_thinking_seconds：10.5
- max_blue_thinking_seconds：8.4
- avg_red_thinking_seconds：5.3
- avg_blue_thinking_seconds：4.6

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 13 | 12 | 0 | 52.0% | 557.8 | 1691.2 | 1920.2 | 1920.4 |
| rollout 红 vs 候选 蓝 | 25 | 16 | 9 | 0 | 64.0% | 541.7 | 1621.1 | 1871.2 | 1920.7 |
| **合并** | **50** | **29** | — | — | **58.0%** (Wilson 95% CI [44.2%, 70.6%]) | 549.8 | 1691.2 | 1920.2 | 1920.7 |
