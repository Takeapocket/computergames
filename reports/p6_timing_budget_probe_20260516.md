# P6 Timing Budget Probe

默认 AI、默认布局、release 配置未变。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `120`
- avg_ms: `284.77`
- p50_ms: `282.20`
- p95_ms: `575.95`
- p99_ms: `641.33`
- max_ms: `720.17`
- rollout_timed_out_count: `1`
- rollout_used_fallback_count: `1`
- illegal_recommendations: `0`
- exceptions: `0`

## Flagged Samples

- index=103 player=red dice=5 elapsed_ms=720.17 timeout=True fallback=True illegal=False exception=

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 120 --seed 26016 --layout balanced_v1 --output "reports\p6_timing_budget_probe_20260516.md" --json-output "reports\p6_timing_budget_probe_20260516.json"
```
