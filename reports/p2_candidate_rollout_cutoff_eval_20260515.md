# rollout_cutoff_eval bench: stage=candidate

- 生成时间：2026-05-15T16:56:33
- 命令：`python scripts/bench_ai.py --candidate rollout_cutoff_eval --stage candidate --report-name p2_candidate_rollout_cutoff_eval_20260515`
- 候选：`rollout_cutoff_eval`
- 阶段：`candidate`
- 对手：`rollout`
- master seed：2026
- 每方局数：100
- 最大半步：200
- 总耗时：610.2s

## 门禁（stage=candidate）

- illegal_moves = 0：PASS (实测 0)
- crashes = 0：PASS (实测 0)
- timeouts = 0：FAIL (实测 11)
- candidate_win_rate ≥ 55.0%：PASS (实测 57.5%)
- average_step_time_ms ≤ 500.0ms：PASS (实测 181.6ms)
- max_step_time_ms ≤ 5000.0ms：PASS (实测 750.3ms)

**Candidate 结论：FAIL**

失败原因：
- timeouts = 11（要求 = 0）

## 双向胜率

| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 候选 红 vs rollout 蓝 | 100 | 63 | 37 | 0 | 63.0% | 183.1 | 482.5 | 584.2 | 750.3 |
| rollout 红 vs 候选 蓝 | 100 | 52 | 48 | 0 | 52.0% | 180.1 | 453.7 | 590.5 | 750.3 |
| **合并** | **200** | **115** | — | — | **57.5%** (Wilson 95% CI [50.6%, 64.1%]) | 181.6 | 482.5 | 590.5 | 750.3 |
