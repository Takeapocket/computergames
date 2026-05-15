# rollout_32 bench: stage=candidate

- 生成时间：2026-05-15T16:35:17
- 命令：`python scripts/bench_ai.py --candidate rollout_32 --stage candidate --report-name p2_candidate_rollout_32_20260515`
- 候选：`rollout_32`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 总耗时：583.9s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：FAIL (实测 4)
- candidate_win_rate ≥ 55.0%：FAIL (实测 54.5%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 168.9ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 750.3ms)

**Candidate 结论：FAIL**

失败原因：
- timeouts = 4（要求 = 0）
- candidate_win_rate = 54.5%（要求 ≥ 55.0%）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 59 | 41 | 0 | 59.0% | 177.2 | 448.4 | 610.8 | 750.3 |
| rollout 红 vs 候选 蓝 | 100 | 50 | 50 | 0 | 50.0% | 160.6 | 407.4 | 461.3 | 684.6 |
| **合并** | **200** | **109** | — | — | **54.5%** (Wilson 95% CI [47.6%, 61.3%]) | 168.9 | 448.4 | 610.8 | 750.3 |
