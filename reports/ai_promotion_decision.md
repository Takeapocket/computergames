# AI Promotion Decision

Date: 2026-05-13

## Baseline

- default AI: `greedy_risk`
- default layout: `balanced_v1`

## Candidate Summary

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rollout | red vs greedy_risk | 400 | 242 | 60.50% | 55.63% | 0 | 0 | 0 | 61.58 | 469.14 |
| rollout | blue vs greedy_risk | 400 | 259 | 64.75% | 59.95% | 0 | 0 | 0 | 54.66 | 418.91 |
| **rollout combined** | combined | **800** | **501** | **62.62%** | **59.22%** | **0** | **0** | **0** | **61.58** | **469.14** |
| expectimax_v2 | red vs greedy_risk | 400 | 178 | 44.50% | 39.70% | 0 | 0 | 0 | 0.33 | 17.85 |
| expectimax_v2 | blue vs greedy_risk | 400 | 192 | 48.00% | 43.15% | 0 | 0 | 0 | 0.35 | 22.28 |
| **expectimax_v2 combined** | combined | **800** | **370** | **46.25%** | **42.82%** | **0** | **0** | **0** | **0.35** | **22.28** |

Timing note: combined `avg ms` and `max ms` use the slower observed direction as a conservative summary, not a weighted average.

Expectimax note: the `expectimax_v2` rows are retained as historical evidence from the pre-depth-fix implementation. After the 2026-05-13 depth semantics fix, `expectimax_v2` needs a fresh resource-approved harness rerun before any promotion decision.

## Gate (for AI promotion)

- candidate vs greedy_risk 双边合并胜率 >= 60%
- Wilson 95% CI 下界 >= 52%
- illegal_moves = 0
- crashes = 0
- timeouts = 0
- avg_step_time_ms < 1000
- max_step_time_ms < 5000

## Decision

**rollout** passes the numerical harness gates:

| gate | threshold | actual | pass |
|---|---:|---:|---|
| combined win rate | >= 60% | 62.62% | PASS |
| Wilson 95% CI lower | >= 52% | 59.22% | PASS |
| illegal_moves | = 0 | 0 | PASS |
| crashes | = 0 | 0 | PASS |
| timeouts | = 0 | 0 | PASS |
| avg_step_time_ms | < 1000 | 61.58 | PASS |
| max_step_time_ms | < 5000 | 469.14 | PASS |

**expectimax_v2** is not promotion-eligible:

| gate | threshold | actual | pass |
|---|---:|---:|---|
| combined win rate | >= 60% | 46.25% | FAIL |
| Wilson 95% CI lower | >= 52% | 42.82% | FAIL |
| illegal_moves | = 0 | 0 | PASS |
| crashes | = 0 | 0 | PASS |
| timeouts | = 0 | 0 | PASS |
| avg_step_time_ms | < 1000 | 0.35 | PASS |
| max_step_time_ms | < 5000 | 22.28 | PASS |

Default AI remains `greedy_risk`. Neither candidate is promoted at this time: `rollout` passed the recorded numerical harness gates, but default promotion requires a separate explicit decision to update `gui/main_window.py` and `release/` configs, plus a resource-safe rerun plan for long harness jobs. `expectimax_v2` has no current promotion evidence after the depth semantics fix. No default or release config changes are performed here.

## Raw report files

- `reports/rollout_vs_greedy_risk_red.json`
- `reports/greedy_risk_vs_rollout_blue.json`
- `reports/expectimax_v2_vs_greedy_risk_red.json`
- `reports/greedy_risk_vs_expectimax_v2_blue.json`
