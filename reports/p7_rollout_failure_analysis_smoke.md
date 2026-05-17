# P7 Rollout Failure Analysis

默认 AI、默认布局、release 配置未变。

标签是归因线索，不是因果证明。

- subject: `rollout`
- opponent: `greedy_risk`
- games: `2`
- seed_pool: `[27016]`
- default_layout: `balanced_v1`

## Summary

- subject_wins: `1`
- subject_losses: `1`
- illegal_moves: `0`
- crashes: `0`
- timeouts: `0`

## Failure Buckets

- missed_direct_win: `0`
- allowed_direct_loss: `4`
- low_confidence_loss: `5`
- timeout_or_fallback: `0`
- bad_self_capture: `3`
- opening_side_bias: `0`
- material_race_loss: `0`
- unclassified: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" --games 2 --seed-pool 27016 --opponent greedy_risk --starting-layout balanced_v1 --max-turns 200 --output "reports\p7_rollout_failure_analysis_smoke.md" --json-output "reports\p7_rollout_failure_analysis_smoke.json"
```
