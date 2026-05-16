# P4 Candidate Probe Summary

Date: 2026-05-16

## Decision

`mcts_eval_v1` does not advance to official candidate enlargement or promotion discussion.

Both probes used the current release default baseline:

```json
{
  "kind": "rollout",
  "kwargs": {
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
}
```

No GUI/release default change is authorized by this probe.

## Results

| Probe | Games | Candidate Wins | Win Rate | Wilson 95% CI | illegal | crash | timeout | avg step | max step | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `mcts_eval_v1(time_limit_ms=200)` | 50 | 15 | 30.0% | [19.1%, 43.8%] | 0 | 0 | 0 | 214.5ms | 720.4ms | FAIL |
| `mcts_eval_v1` default (`time_limit_ms=500`) | 20 | 6 | 30.0% | [14.5%, 51.9%] | 0 | 0 | 0 | 351.4ms | 719.7ms | FAIL |

Failure reason in both runs:

```text
candidate_win_rate = 30.0%（要求 >= 55.0%）
```

## Commands

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate mcts_eval_v1 --stage candidate --games-per-side 25 --candidate-arg time_limit_ms=200 --report-name p4_candidate_probe_mcts_eval_v1_vs_release_default_20260516
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate mcts_eval_v1 --stage candidate --games-per-side 10 --report-name p4_candidate_probe_mcts_eval_v1_default_vs_release_default_20260516
```

## Interpretation

The P4 entry guard fix produced clean stability telemetry, but MCTS is still much weaker than the current `rollout` working default. Increasing to official 200+200 candidate or 400+400 promotion would spend time on a candidate that has already missed the strength gate by a large margin.

Next MCTS work, if pursued, should be a new bounded hypothesis such as leaf evaluator replacement or rollout leaf fallback, and must start with targeted tests plus another small probe before any large benchmark.
