# rollout_strong_48 bench: stage=candidate

- 生成时间：2026-05-19T00:00:50
- 命令：`python scripts/bench_ai.py --candidate rollout_strong_48 --stage candidate --report-name p14_candidate_rollout_strong_48_20260518`
- 候选：`rollout_strong_48`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 64, "cutoff_eval": "zweistein", "deadline_safety_ms": 50.0, "epsilon": 0.08, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 1500.0, "name": "rollout_strong_48", "playout_policy": "greedy_risk", "rollouts_per_move": 48}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：383.6s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 54.0%)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 1451.9ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 54.0%（要求 ≥ 55.0%）

## P14 strong rollout 决策

- candidate gate：FAIL
- 52% 门槛：PASS
- 55% 门槛：FAIL
- 50+50 门槛：未执行或未通过
- candidate win rate：54.0%
- Wilson 95% CI：[40.4%, 67.0%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：418.7 / 1131.4 / 1450.1 / 1451.9
- per-side thinking time：max_red_thinking_seconds=6.7, max_blue_thinking_seconds=6.2, avg_red_thinking_seconds=4.1, avg_blue_thinking_seconds=3.6
- timing risk：否
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 是否建议扩样：否
- 结论：有信号但不足；最多只跑 50+50 复验，不默认启用。

## 步时与包干估算

- total_step_time_ms：383514.7
- average_turns：18.32
- avg/p95/p99/max step ms：418.7 / 1131.4 / 1450.1 / 1451.9
- max_red_thinking_seconds：6.7
- max_blue_thinking_seconds：6.2
- avg_red_thinking_seconds：4.1
- avg_blue_thinking_seconds：3.6

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 14 | 11 | 0 | 56.0% | 417.2 | 1131.4 | 1450.1 | 1451.9 |
| rollout 红 vs 候选 蓝 | 25 | 13 | 12 | 0 | 52.0% | 420.3 | 1011.9 | 1234.6 | 1450.4 |
| **合并** | **50** | **27** | — | — | **54.0%** (Wilson 95% CI [40.4%, 67.0%]) | 418.7 | 1131.4 | 1450.1 | 1451.9 |
