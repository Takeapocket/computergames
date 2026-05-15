# rollout_risk_playout bench: stage=candidate

- 生成时间：2026-05-15T16:46:06
- 命令：`python scripts/bench_ai.py --candidate rollout_risk_playout --stage candidate --report-name p2_candidate_rollout_risk_playout_20260515`
- 候选：`rollout_risk_playout`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 总耗时：604.3s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：FAIL (实测 10)
- candidate_win_rate ≥ 55.0%：PASS (实测 57.0%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 179.8ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 750.6ms)

**Candidate 结论：FAIL**

失败原因：
- timeouts = 10（要求 = 0）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 63 | 37 | 0 | 63.0% | 182.6 | 483.3 | 573.1 | 750.4 |
| rollout 红 vs 候选 蓝 | 100 | 51 | 49 | 0 | 51.0% | 177.0 | 449.0 | 587.1 | 750.6 |
| **合并** | **200** | **114** | — | — | **57.0%** (Wilson 95% CI [50.1%, 63.7%]) | 179.8 | 483.3 | 587.1 | 750.6 |
