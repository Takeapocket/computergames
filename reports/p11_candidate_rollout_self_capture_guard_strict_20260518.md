# rollout_self_capture_guard_strict bench: stage=candidate

- 生成时间：2026-05-18T22:34:19
- 命令：`python scripts/bench_ai.py --candidate rollout_self_capture_guard_strict --stage candidate --report-name p11_candidate_rollout_self_capture_guard_strict_20260518`
- 候选：`rollout_self_capture_guard_strict`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：25
- 最大半步：200
- 开局布局：`balanced_v1`
- 候选参数（有效）：`{}`
- 对手参数（有效）：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 候选签名：`{"base": {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}, "enemy_capture_margin": 0.14, "low_material_threshold": 4, "max_score_gap_for_override": 0.18, "name": "rollout_self_capture_guard_strict", "non_self_low_material_margin": 0.18, "prefer_enemy_capture_margin": 0.06, "require_safe_alternative": true}`
- 对手签名：`{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "name": "rollout", "playout_policy": "greedy_risk", "rollouts_per_move": 32}`
- 总耗时：294.2s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 34.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 307.0ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 724.4ms)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 34.0%（要求 ≥ 55.0%）

## P11 self-capture guard 决策

**默认启用决策：不默认启用。**
- candidate gate：FAIL
- candidate win rate：34.0%
- Wilson 95% CI：[22.4%, 47.8%]
- illegal/crash/timeout：0 / 0 / 0
- avg/max step time：307.0ms / 724.4ms
- 是否修改默认配置：没有
- 是否修改 core 规则：没有
- 是否建议扩样：否
- 结论：candidate_win_rate 34.0% < 52%，按 P11 停止规则不扩样。

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 25 | 9 | 16 | 0 | 36.0% | 316.1 | 637.8 | 722.8 | 724.2 |
| rollout 红 vs 候选 蓝 | 25 | 8 | 17 | 0 | 32.0% | 297.9 | 634.8 | 722.6 | 724.4 |
| **合并** | **50** | **17** | — | — | **34.0%** (Wilson 95% CI [22.4%, 47.8%]) | 307.0 | 637.8 | 722.8 | 724.4 |

## 战术分支命中统计

- fire_kept_self_no_alt: 11
- fire_kept_self_score_gap: 41
- fire_kept_self_unsafe_alt: 4
- fire_override_self_to_enemy_capture: 8
- fire_override_self_to_non_self_low_material: 37
- fire_override_to_enemy_capture_soft: 7
