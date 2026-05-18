# rollout_strong_64_loweps bench: stage=candidate

- 生成时间：2026-05-19T00:18:11
- 命令：`python scripts/bench_ai.py --candidate rollout_strong_64_loweps --stage candidate --report-name p14_candidate_rollout_strong_64_loweps_20260518`
- 候选：`rollout_strong_64_loweps`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 96, "cutoff_eval": "zweistein", "deadline_safety_ms": 80.0, "epsilon": 0.05, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 2000.0, "name": "rollout_strong_64_loweps", "playout_policy": "greedy_risk", "rollouts_per_move": 64}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：513.1s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 62.0%)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 1922.4ms)

**Candidate 结论：PASS**

## P14 strong rollout 决策

- candidate gate：PASS
- 52% 门槛：PASS
- 55% 门槛：PASS
- 50+50 门槛：未执行或未通过
- candidate win rate：62.0%
- Wilson 95% CI：[48.2%, 74.1%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：549.8 / 1717.3 / 1920.3 / 1922.4
- per-side thinking time：max_red_thinking_seconds=9.9, max_blue_thinking_seconds=11.2, avg_red_thinking_seconds=5.3, avg_blue_thinking_seconds=5.0
- timing risk：否
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 是否建议扩样：是
- 结论：通过 55% 初筛；建议扩到 50+50，不默认启用。

## 步时与包干估算

- total_step_time_ms：513006.2
- average_turns：18.68
- avg/p95/p99/max step ms：549.8 / 1717.3 / 1920.3 / 1922.4
- max_red_thinking_seconds：9.9
- max_blue_thinking_seconds：11.2
- avg_red_thinking_seconds：5.3
- avg_blue_thinking_seconds：5.0

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 16 | 9 | 0 | 64.0% | 562.7 | 1717.3 | 1920.3 | 1922.4 |
| rollout 红 vs 候选 蓝 | 25 | 15 | 10 | 0 | 60.0% | 536.9 | 1651.1 | 1902.4 | 1920.5 |
| **合并** | **50** | **31** | — | — | **62.0%** (Wilson 95% CI [48.2%, 74.1%]) | 549.8 | 1717.3 | 1920.3 | 1922.4 |
