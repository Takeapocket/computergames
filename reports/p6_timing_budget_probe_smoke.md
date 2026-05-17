# P6 Timing Budget Probe

默认 AI、默认布局、release 配置未变。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `3`
- avg_ms: `505.88`
- p50_ms: `505.23`
- p95_ms: `555.32`
- p99_ms: `559.78`
- max_ms: `560.89`
- rollout_timed_out_count: `0`
- rollout_used_fallback_count: `0`
- illegal_recommendations: `0`
- exceptions: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 3 --seed 26016 --layout balanced_v1 --output "reports\p6_timing_budget_probe_smoke.md" --json-output "reports\p6_timing_budget_probe_smoke.json"
```
