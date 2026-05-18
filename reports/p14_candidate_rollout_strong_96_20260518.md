# rollout_strong_96 bench: stage=candidate

- 生成时间：2026-05-19T00:29:21
- 命令：`python scripts/bench_ai.py --candidate rollout_strong_96 --stage candidate --report-name p14_candidate_rollout_strong_96_20260518`
- 候选：`rollout_strong_96`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 128, "cutoff_eval": "zweistein", "deadline_safety_ms": 120.0, "epsilon": 0.08, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 3000.0, "name": "rollout_strong_96", "playout_policy": "greedy_risk", "rollouts_per_move": 96}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：647.0s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 60.0%)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 2880.6ms)

**Candidate 结论：PASS**

## P14 strong rollout 决策

- candidate gate：PASS
- 52% 门槛：PASS
- 55% 门槛：PASS
- 50+50 门槛：未执行或未通过
- candidate win rate：60.0%
- Wilson 95% CI：[46.2%, 72.4%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：702.9 / 2288.7 / 2773.9 / 2880.6
- per-side thinking time：max_red_thinking_seconds=15.9, max_blue_thinking_seconds=15.0, avg_red_thinking_seconds=6.8, avg_blue_thinking_seconds=6.2
- timing risk：否
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 是否建议扩样：是
- 结论：通过 55% 初筛；建议扩到 50+50，不默认启用。

## 步时与包干估算

- total_step_time_ms：646914.0
- average_turns：18.42
- avg/p95/p99/max step ms：702.9 / 2288.7 / 2773.9 / 2880.6
- max_red_thinking_seconds：15.9
- max_blue_thinking_seconds：15.0
- avg_red_thinking_seconds：6.8
- avg_blue_thinking_seconds：6.2

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 17 | 8 | 0 | 68.0% | 727.0 | 2288.7 | 2585.6 | 2880.3 |
| rollout 红 vs 候选 蓝 | 25 | 13 | 12 | 0 | 52.0% | 678.8 | 2188.3 | 2773.9 | 2880.6 |
| **合并** | **50** | **30** | — | — | **60.0%** (Wilson 95% CI [46.2%, 72.4%]) | 702.9 | 2288.7 | 2773.9 | 2880.6 |
