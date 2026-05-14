# rollout_tactical bench: stage=candidate

- 生成时间：2026-05-14T23:08:46
- 命令：`python scripts/bench_ai.py --candidate rollout_tactical --stage candidate --report-name candidate_rollout_tactical_2026-05-14`
- 候选：`rollout_tactical`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：400
- 最大半步：200
- 总耗时：1601.7s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- candidate_win_rate ≥ 55.0%：FAIL (实测 52.5%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 114.7ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 442.2ms)
- candidate_win_ci_lower ≥ 52.0%：FAIL (实测 49.0%)

**Candidate 结论：FAIL**

失败原因：
- candidate_win_rate = 52.5%（要求 ≥ 55.0%）
- candidate_win_ci_lower = 49.0%（要求 ≥ 52.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 400 | 212 | 188 | 0 | 53.0% | 115.7 | 436.2 |
| rollout 红 vs 候选 蓝 | 400 | 208 | 192 | 0 | 52.0% | 113.8 | 442.2 |
| **合并** | **800** | **420** | — | — | **52.5%** (Wilson 95% CI [49.0%, 55.9%]) | 114.7 | 442.2 |
