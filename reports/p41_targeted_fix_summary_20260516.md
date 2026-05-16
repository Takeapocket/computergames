# P4.1 Targeted Fix Summary

Date: 2026-05-16

## Scope

This was a targeted P4.1 pass only. It did not run a large benchmark and did not modify GUI or release defaults.

## Fixes

- Added a minimal real-position test proving opponent DecisionNode selection chooses the reply that is worst for `root_player`.
- Added `MCTSAI.leaf_evaluator`, supporting `current` and `zweistein`.
- Default MCTS behavior remains `leaf_evaluator="current"`.
- `ai_version_signature()` records `leaf_evaluator` through the existing reflection path.

## Probe

Opponent was the current release default rollout kwargs from `release/v1.0/default_params.json`.

Command:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate mcts_eval_v1 --stage candidate --games-per-side 10 --candidate-arg leaf_evaluator=zweistein --report-name p41_probe_mcts_zweistein_vs_release_default_20260516
```

Result:

| Probe | Games | Candidate Wins | Win Rate | Wilson 95% CI | illegal | crash | timeout | avg step | max step | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `mcts_eval_v1(leaf_evaluator="zweistein")` | 20 | 5 | 25.0% | [11.2%, 46.9%] | 0 | 0 | 0 | 348.9ms | 720.2ms | FAIL |

Direction detail:

| Direction | Games | Candidate Wins | Opponent Wins | Candidate Win Rate |
|---|---:|---:|---:|---:|
| Candidate red vs rollout blue | 10 | 3 | 7 | 30.0% |
| Rollout red vs candidate blue | 10 | 2 | 8 | 20.0% |

## Decision

Stop MCTS and move to P5.

Reason: the P4.1 probe scored 25.0%, below the user-defined 45% stop threshold. There is no basis for formal candidate enlargement or promotion discussion.
