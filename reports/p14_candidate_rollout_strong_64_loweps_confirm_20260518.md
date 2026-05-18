# rollout_strong_64_loweps bench: stage=candidate

- 生成时间：2026-05-19T01:08:43
- 命令：`python scripts/bench_ai.py --candidate rollout_strong_64_loweps --stage candidate --games-per-side 50 --seed 33026 --report-name p14_candidate_rollout_strong_64_loweps_confirm_20260518`
- 候选：`rollout_strong_64_loweps`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：33026
- 每方局数：50
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 96, "cutoff_eval": "zweistein", "deadline_safety_ms": 80.0, "epsilon": 0.05, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 2000.0, "name": "rollout_strong_64_loweps", "playout_policy": "greedy_risk", "rollouts_per_move": 64}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：987.8s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：PASS (实测 59.0%)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 1920.8ms)

**Candidate 结论：PASS**

## P14 strong rollout 决策

- candidate gate：PASS
- 52% 门槛：PASS
- 55% 门槛：PASS
- 50+50 门槛：未执行或未通过
- candidate win rate：59.0%
- Wilson 95% CI：[49.2%, 68.1%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：567.7 / 1770.3 / 1920.4 / 1920.8
- per-side thinking time：max_red_thinking_seconds=11.2, max_blue_thinking_seconds=9.5, avg_red_thinking_seconds=5.2, avg_blue_thinking_seconds=4.7
- timing risk：否
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 是否建议扩样：否
- 结论：50+50 胜率达到 55%，但 Wilson lower < 50%；不 promotion。

## 步时与包干估算

- total_step_time_ms：987704.1
- average_turns：17.53
- avg/p95/p99/max step ms：567.7 / 1770.3 / 1920.4 / 1920.8
- max_red_thinking_seconds：11.2
- max_blue_thinking_seconds：9.5
- avg_red_thinking_seconds：5.2
- avg_blue_thinking_seconds：4.7

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 50 | 34 | 16 | 0 | 68.0% | 620.3 | 1770.3 | 1920.4 | 1920.8 |
| rollout 红 vs 候选 蓝 | 50 | 25 | 25 | 0 | 50.0% | 515.0 | 1573.2 | 1889.5 | 1920.3 |
| **合并** | **100** | **59** | — | — | **59.0%** (Wilson 95% CI [49.2%, 68.1%]) | 567.7 | 1770.3 | 1920.4 | 1920.8 |

## P14 二轮 50+50 合并确认

- 上一轮报告：`reports/p14_candidate_rollout_strong_64_loweps_50x2_20260518.json`
- 本轮报告：`reports/p14_candidate_rollout_strong_64_loweps_confirm_20260518.json`
- 合并局数：200
- 合并胜局：118
- 合并胜率：59.0%
- 合并 Wilson 95% CI：[52.1%, 65.6%]
- illegal/crash/timeout：0 / 0 / 0
- avg/p95/p99/max step ms：557.0 / 1770.3 / 1920.4 / 1920.8
- per-side thinking time：max_red_thinking_seconds=11.4, max_blue_thinking_seconds=10.9, avg_red_thinking_seconds=5.3, avg_blue_thinking_seconds=4.8
- p95/p99 合并说明：bench JSON 未保存原始逐步 step times；这里保守取两轮 100 局 summary 的较大 p95/p99。
- 当前 release 默认配置：未修改
- core 规则语义：未修改
- 结论：本轮 59/100 >= 55/100，合并 118/200，可进入候选可晋升讨论；本报告不自动修改默认配置，等待用户确认。2026-05-18 用户确认后，已在 `reports/ai_promotion_decision.md` 记录受控默认替换，GUI/release 默认 kwargs 改为 P14 参数集。

