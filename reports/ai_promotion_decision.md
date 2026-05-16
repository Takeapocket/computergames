# AI Promotion Decision

Date: 2026-05-13

2026-05-15 note: the original rollout promotion data below is historical. New default replacements must be tested against the current default old flat `rollout`, and must use bench output with real timeout telemetry. Legacy `timeouts=0` fields from older quick_bench reports are not sufficient by themselves for promotion evidence.

## Baseline

- previous default AI: `greedy_risk`
- promoted default AI: `rollout`
- default layout: `balanced_v1`

## Candidate Summary

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts (legacy) | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rollout | red vs greedy_risk | 400 | 242 | 60.50% | 55.63% | 0 | 0 | 0 | 61.58 | 469.14 |
| rollout | blue vs greedy_risk | 400 | 259 | 64.75% | 59.95% | 0 | 0 | 0 | 54.66 | 418.91 |
| **rollout combined** | combined | **800** | **501** | **62.62%** | **59.22%** | **0** | **0** | **0** | **61.58** | **469.14** |
| expectimax_v2 | red vs greedy_risk | 400 | 178 | 44.50% | 39.70% | 0 | 0 | 0 | 0.33 | 17.85 |
| expectimax_v2 | blue vs greedy_risk | 400 | 192 | 48.00% | 43.15% | 0 | 0 | 0 | 0.35 | 22.28 |
| **expectimax_v2 combined** | combined | **800** | **370** | **46.25%** | **42.82%** | **0** | **0** | **0** | **0.35** | **22.28** |

Timing note: combined `avg ms` and `max ms` use the slower observed direction as a conservative summary, not a weighted average.

Expectimax note: the `expectimax_v2` rows are retained as historical evidence from the pre-depth-fix implementation. After the 2026-05-13 depth semantics fix, `expectimax_v2` needs a fresh resource-approved harness rerun before any promotion decision.

## Gate (for historical rollout promotion)

- historical rollout promotion: candidate vs greedy_risk 双边合并胜率 >= 60%
- current default replacement: candidate vs current default old flat rollout 双边合并胜率 >= 60%
- Wilson 95% CI 下界 >= 52%
- illegal_moves = 0
- crashes = 0
- real timeout telemetry = 0；旧 quick_bench legacy timeouts 字段不得单独作为晋升证据
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
| real timeout telemetry | = 0 | legacy 0 | PASS (historical) |
| avg_step_time_ms | < 1000 | 61.58 | PASS |
| max_step_time_ms | < 5000 | 469.14 | PASS |

**expectimax_v2** is not promotion-eligible:

| gate | threshold | actual | pass |
|---|---:|---:|---|
| combined win rate | >= 60% | 46.25% | FAIL |
| Wilson 95% CI lower | >= 52% | 42.82% | FAIL |
| illegal_moves | = 0 | 0 | PASS |
| crashes | = 0 | 0 | PASS |
| real timeout telemetry | = 0 | legacy 0 | PASS (historical) |
| avg_step_time_ms | < 1000 | 0.35 | PASS |
| max_step_time_ms | < 5000 | 22.28 | PASS |

Default AI is promoted to `rollout` for GUI and release configuration. `greedy_risk` remains the emergency fallback. `expectimax_v2` remains experimental and is not promotion-eligible on the recorded evidence.

Implementation:

- `gui/main_window.py` default recommender: `rollout`
- `release/v1.0/config.json`: `default_ai = rollout`
- `release/v1.0/default_params.json`: rollout parameters and `fallback_ai = greedy_risk`
- emergency fallback: set `DEFAULT_RECOMMENDER_KIND = "greedy_risk"` and `DEFAULT_RECOMMENDER_KWARGS = {}`

## Raw report files

- `reports/rollout_vs_greedy_risk_red.json`
- `reports/greedy_risk_vs_rollout_blue.json`
- `reports/expectimax_v2_vs_greedy_risk_red.json`
- `reports/greedy_risk_vs_expectimax_v2_blue.json`

## 2026-05-16 P3 Promotion Decision: rollout_zweistein_cutoff

Status: approved for GUI/release working default replacement on 2026-05-16. The implementation intentionally keeps `kind="rollout"` and copies the candidate parameters explicitly into GUI/release config instead of relying on the `rollout_zweistein_cutoff` factory shortcut.

Command:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_zweistein_cutoff --stage promotion --report-name p3_promotion_rollout_zweistein_cutoff_20260515
```

Candidate signature:

```json
{
  "name": "rollout_zweistein_cutoff",
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 750.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 32,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein",
  "deadline_safety_ms": 30.0
}
```

Comparison:

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | real timeouts | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **rollout_zweistein_cutoff** | vs old flat rollout | **800** | **454** | **56.75%** | **53.29%** | **0** | **0** | **0** | **175.75** | **720.69** |

Working-baseline promotion gate:

| gate | threshold | actual | pass |
|---|---:|---:|---|
| combined win rate | >= 55% | 56.75% | PASS |
| Wilson 95% CI lower | >= 52% | 53.29% | PASS |
| illegal_moves | = 0 | 0 | PASS |
| crashes | = 0 | 0 | PASS |
| real timeout telemetry | = 0 | 0 | PASS |
| average_step_time_ms | <= 500 | 175.75 | PASS |
| max_step_time_ms | <= 5000 | 720.69 | PASS |

Decision:

- `rollout_zweistein_cutoff` passes the P3 working-baseline promotion gate against the current old flat `rollout`.
- Replace the GUI/release working default with `kind="rollout"` plus the explicit candidate kwargs listed above.
- `gui/main_window.py::DEFAULT_RECOMMENDER_KIND` remains `"rollout"`.
- `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS` and `release/v1.0/default_params.json` are updated to match the candidate signature.
- `release/v1.0/config.json` does not need a semantic change because its default AI kind is still `rollout`.
- `greedy_risk` remains the emergency fallback.

Traceability:

- `reports/p3_promotion_rollout_zweistein_cutoff_20260515.json`
- `reports/p3_promotion_rollout_zweistein_cutoff_20260515.md`

## 2026-05-15 Adaptive Rollout Parameter Follow-up

The GUI/release default AI kind remains `rollout`. The adaptive parameters below were evaluated after the fixed-position self-capture audit, but they are not promoted into `release/v1.0/default_params.json` because the direct comparison against the old rollout default did not clear the stricter 60% default-promotion target.

Adaptive rollout parameters:

```json
{
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 500.0,
  "epsilon": 0.15,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 128,
  "low_confidence_margin": 0.08
}
```

200-game follow-up against `greedy_risk`:

Note: the adaptive rows below were generated before the 2026-05-15 real timeout telemetry fix; their timeout column is a legacy report field.

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts (legacy) | avg ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive rollout | red vs greedy_risk | 100 | 77 | 77.00% | 67.85% | 0 | 0 | 0 | 158.23 | 500.74 |
| adaptive rollout | blue vs greedy_risk | 100 | 78 | 78.00% | 68.93% | 0 | 0 | 0 | 147.12 | 500.75 |
| **adaptive rollout combined** | combined | **200** | **155** | **77.50%** | **71.23%** | **0** | **0** | **0** | **158.23** | **500.75** |

Decision: adaptive rollout passes the 200-game candidate screen against `greedy_risk`. Because this comparison is against `greedy_risk`, not directly against the old rollout default, it is not sufficient for release default promotion.

Direct 800-game follow-up against the old rollout shape:

Note: this direct comparison was also generated before the 2026-05-15 real timeout telemetry fix; its timeout column is a legacy report field.

| candidate | comparison | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts (legacy) | avg ms | P95 ms | P99 ms | max ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive rollout | red vs old rollout | 400 | 230 | 57.50% | 52.61% | 0 | 0 | 0 | 211.41 | 500.27 | 500.44 | 502.15 |
| adaptive rollout | blue vs old rollout | 400 | 242 | 60.50% | 55.63% | 0 | 0 | 0 | 204.03 | 500.24 | 500.42 | 500.99 |
| **adaptive vs old combined** | combined | **800** | **472** | **59.00%** | **55.56%** | **0** | **0** | **0** | **211.41** | **500.27** | **500.44** | **502.15** |

Follow-up interpretation: adaptive rollout passes the direct candidate screen against old rollout, but does not clear the stricter `>= 60%` default-promotion target on this direct comparison. Keep old flat rollout as the GUI/release default parameters; treat adaptive rollout as an explicit experimental candidate until a future run clears the default-promotion gate with real timeout telemetry.

Traceability:

- `reports/adaptive_rollout_2026-05-15.md`
- `release/v1.0/default_params.json`
- `gui/main_window.py`
