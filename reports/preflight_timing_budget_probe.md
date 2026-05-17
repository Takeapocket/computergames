# P6 Timing Budget Probe

默认 AI、默认布局、release 配置未变。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `16`
- avg_ms: `375.24`
- p50_ms: `418.08`
- p95_ms: `608.41`
- p99_ms: `615.38`
- max_ms: `617.13`
- rollout_timed_out_count: `0`
- rollout_used_fallback_count: `0`
- illegal_recommendations: `0`
- exceptions: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 26016 --layout balanced_v1 --output "reports\preflight_timing_budget_probe.md" --json-output "reports\preflight_timing_budget_probe.json"
```
