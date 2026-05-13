# AI Promotion Decision

Date: 2026-05-13

## Baseline

- previous default AI: `greedy_risk`
- promoted default AI: `rollout`
- default layout: `balanced_v1`

## Candidate Summary

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rollout | red vs greedy_risk | 400 | 242 | 60.50% | 55.63% | 0 | 0 | 0 | 61.58 | 469.14 |
| rollout | blue vs greedy_risk | 400 | 259 | 64.75% | 59.95% | 0 | 0 | 0 | 54.66 | 418.91 |
| **rollout combined** | combined | **800** | **501** | **62.62%** | **59.22%** | **0** | **0** | **0** | **61.58** | **469.14** |

Timing note: combined `avg ms` and `max ms` use the slower observed direction as a conservative summary, not a weighted average.

## Gate

- candidate vs greedy_risk 双边合并胜率 >= 60%
- Wilson 95% CI 下界 >= 52%
- illegal_moves = 0
- crashes = 0
- timeouts = 0
- avg_step_time_ms < 1000
- max_step_time_ms < 5000

## Decision

`rollout` passes the numerical harness gates and is promoted to the GUI / release default AI.

| gate | threshold | actual | pass |
|---|---:|---:|---|
| combined win rate | >= 60% | 62.62% | PASS |
| Wilson 95% CI lower | >= 52% | 59.22% | PASS |
| illegal_moves | = 0 | 0 | PASS |
| crashes | = 0 | 0 | PASS |
| timeouts | = 0 | 0 | PASS |
| avg_step_time_ms | < 1000 | 61.58 | PASS |
| max_step_time_ms | < 5000 | 469.14 | PASS |

Implementation:

- `gui/main_window.py` default recommender: `rollout`
- `release/v1.0/default_params.json`: rollout parameters and `fallback_ai = greedy_risk`
- emergency fallback: set `DEFAULT_RECOMMENDER_KIND = "greedy_risk"` and `DEFAULT_RECOMMENDER_KWARGS = {}`

## Raw report files

- `reports/rollout_vs_greedy_risk_red.json`
- `reports/greedy_risk_vs_rollout_blue.json`
