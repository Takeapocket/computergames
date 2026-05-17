# P6 Timing Budget Probe

默认 AI、默认布局、release 配置未变。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `16`
- avg_ms: `380.74`
- p50_ms: `431.13`
- p95_ms: `621.28`
- p99_ms: `635.14`
- max_ms: `638.60`
- rollout_timed_out_count: `0`
- rollout_used_fallback_count: `0`
- illegal_recommendations: `0`
- exceptions: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 26016 --layout balanced_v1 --output "reports\preflight_timing_budget_probe.md" --json-output "reports\preflight_timing_budget_probe.json"
```
