# P7 Rollout Failure Analysis

默认 AI、默认布局、release 配置未变。

标签是归因线索，不是因果证明。

- subject: `rollout`
- opponent: `greedy_risk`
- games: `120`
- seed_pool: `[27016, 27017, 27018]`
- default_layout: `balanced_v1`

## Summary

- subject_wins: `87`
- subject_losses: `33`
- illegal_moves: `0`
- crashes: `0`
- timeouts: `0`

## Failure Buckets

- missed_direct_win: `0`
- allowed_direct_loss: `63`
- low_confidence_loss: `145`
- timeout_or_fallback: `4`
- bad_self_capture: `33`
- opening_side_bias: `0`
- material_race_loss: `0`
- unclassified: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" --games 120 --seed-pool 27016,27017,27018 --opponent greedy_risk --starting-layout balanced_v1 --max-turns 200 --output "reports\p7_rollout_failure_analysis_20260516.md" --json-output "reports\p7_rollout_failure_analysis_20260516.json"
```
