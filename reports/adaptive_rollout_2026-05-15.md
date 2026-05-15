# Adaptive Rollout Follow-up

Date: 2026-05-15

## Context

This follow-up was triggered by the fixed-position audit where default rollout repeatedly switched between:

- `红方 5: (2,1) -> (3,1) 吃子`
- `红方 5: (2,1) -> (2,2) 自吃`
- `红方 5: (2,1) -> (3,2) 吃子`

The issue was not rule legality. Self-capture is legal. The issue was rollout observability and root-move sampling noise.

## Candidate

`rollout` with root adaptive sampling:

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

Behavior:

- Score all legal root moves with 32 rollouts.
- If the top two candidates are within 0.08 winrate, resample close candidates up to 128 visits.
- If the final top-two margin is still below 0.08, expose `low_confidence=True` for the GUI.
- Keep `greedy_risk` fallback under the existing `max_step_time_ms` deadline.

## Fixed-position Stability

Command:

```powershell
& ".venv/Scripts/python.exe" "scripts/rollout_stability.py" --runs 10 --seed 0
```

Result:

| move | recommendations |
|---|---:|
| `红方 5: (2,1) -> (2,2) 自吃` | 6 |
| `红方 5: (2,1) -> (3,2) 吃子` | 2 |
| `红方 5: (2,1) -> (3,1) 吃子` | 2 |

Interpretation: this fixed position remains noisy even after adaptive sampling. The exact 10-run distribution is deadline-sensitive, but the important signal is stable: more than one candidate remains plausible, and low-confidence cases are visible. The useful change is observability: the GUI can surface score / winrate / cutoffs / avg instead of presenting a close rollout result as certain.

## Greedy-risk Comparison

### Adaptive rollout, seed 20260516

| candidate side | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts (legacy) | avg ms | max ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red vs `greedy_risk` | 100 | 77 | 77.00% | 67.85% | 0 | 0 | 0 | 158.23 | 500.74 |
| blue vs `greedy_risk` | 100 | 78 | 78.00% | 68.93% | 0 | 0 | 0 | 147.12 | 500.75 |
| **combined** | **200** | **155** | **77.50%** | **71.23%** | **0** | **0** | **0** | **158.23** | **500.75** |

Commands:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy_risk --red-kwargs '{"rollouts_per_move":32,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_margin":0.08,"close_sample_rollouts_per_move":128,"low_confidence_margin":0.08}' --games 100 --seed 20260516 --report-name bench_20260515_adaptive_rollout_red_vs_greedy_risk_100
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue rollout --blue-kwargs '{"rollouts_per_move":32,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_margin":0.08,"close_sample_rollouts_per_move":128,"low_confidence_margin":0.08}' --games 100 --seed 20260516 --report-name bench_20260515_greedy_risk_vs_adaptive_rollout_blue_100
```

### Same-seed smoke comparison against old rollout shape, seed 20260515

| candidate | games | candidate wins | win rate | Wilson lower | avg ms max direction | max ms |
|---|---:|---:|---:|---:|---:|---:|
| old rollout shape | 100 | 65 | 65.00% | 55.25% | 63.09 | 416.30 |
| adaptive rollout | 100 | 76 | 76.00% | 66.77% | 159.82 | 500.56 |

The same-seed smoke comparison suggests the adaptive candidate is stronger, but around 2.5x slower on average.

## Candidate Screening Gate

Candidate screening gate against `greedy_risk` only, not the release-default promotion gate:

- candidate vs `greedy_risk` at least 200 games
- combined win rate >= 60%
- Wilson 95% lower >= 52%
- illegal_moves = 0
- crashes = 0
- real timeout telemetry = 0；if a report was generated before the 2026-05-15 quick_bench/bench_ai fix, timeout is only a legacy field
- avg_step_time_ms < 1000
- max_step_time_ms < 5000

Result: adaptive rollout passes this 200-game candidate screen against `greedy_risk`. This only proves it can continue as an experiment; it cannot replace the v1.0 old flat rollout default without clearing the direct current-default promotion gate.

## Direct Comparison Against Old Rollout

Reviewer follow-up: a candidate that only beats `greedy_risk` may be specialized against that opponent. The stronger check is direct play against the old rollout shape.

Old rollout shape used for this comparison:

```json
{
  "rollouts_per_move": 16,
  "max_rollout_turns": 80,
  "max_step_time_ms": 500.0,
  "epsilon": 0.15,
  "close_sample_rollouts_per_move": 16
}
```

Command pair:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue rollout --red-kwargs '{"rollouts_per_move":32,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_margin":0.08,"close_sample_rollouts_per_move":128,"low_confidence_margin":0.08}' --blue-kwargs '{"rollouts_per_move":16,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_rollouts_per_move":16}' --games 400 --seed 20260517 --report-name bench_20260515_adaptive_rollout_red_vs_old_rollout_400
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue rollout --red-kwargs '{"rollouts_per_move":16,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_rollouts_per_move":16}' --blue-kwargs '{"rollouts_per_move":32,"max_rollout_turns":80,"max_step_time_ms":500.0,"epsilon":0.15,"close_sample_margin":0.08,"close_sample_rollouts_per_move":128,"low_confidence_margin":0.08}' --games 400 --seed 20260517 --report-name bench_20260515_old_rollout_red_vs_adaptive_rollout_blue_400
```

Result:

| candidate side | games | candidate wins | win rate | Wilson lower | illegal | crashes | timeouts (legacy) | avg ms | P95 ms | P99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive red vs old rollout | 400 | 230 | 57.50% | 52.61% | 0 | 0 | 0 | 211.41 | 500.27 | 500.44 | 502.15 |
| adaptive blue vs old rollout | 400 | 242 | 60.50% | 55.63% | 0 | 0 | 0 | 204.03 | 500.24 | 500.42 | 500.99 |
| **combined** | **800** | **472** | **59.00%** | **55.56%** | **0** | **0** | **0** | **211.41** | **500.27** | **500.44** | **502.15** |

Interpretation:

- Adaptive rollout passes the direct candidate screen against old rollout: combined win rate 59.00%, Wilson lower 55.56%, 0 illegal/crash.
- It does not meet the stricter default-promotion target of combined win rate >= 60% against the current default. The shortfall is small but should be recorded honestly.
- Tail latency is deadline-bound: P95/P99 are both around 500 ms. These historical reports were generated before real timeout telemetry was added to `quick_bench.py` / `bench_ai.py`, so the legacy timeout column must not be used as promotion evidence.

## Decision

Do not promote adaptive rollout into `release/v1.0/default_params.json`. It improves the audited tactical position's transparency and passes the 800-game direct candidate screen against old rollout, but it does not clear the stricter 60% default-promotion target.

Risk note: the candidate frequently reaches the configured 500 ms step deadline and is materially slower than the previous rollout shape. Because direct adaptive-vs-old combined win rate is 59.00%, treat it as an explicit experimental candidate rather than an overclaimed final sealed competition conclusion.

## Raw Reports

- `reports/bench_20260515_adaptive_rollout_red_vs_greedy_risk_50.json`
- `reports/bench_20260515_greedy_risk_vs_adaptive_rollout_blue_50.json`
- `reports/bench_20260515_old_rollout_red_vs_greedy_risk_50.json`
- `reports/bench_20260515_greedy_risk_vs_old_rollout_blue_50.json`
- `reports/bench_20260515_adaptive_rollout_red_vs_greedy_risk_100.json`
- `reports/bench_20260515_greedy_risk_vs_adaptive_rollout_blue_100.json`
- `reports/bench_20260515_adaptive_rollout_red_vs_old_rollout_400.json`
- `reports/bench_20260515_old_rollout_red_vs_adaptive_rollout_blue_400.json`
