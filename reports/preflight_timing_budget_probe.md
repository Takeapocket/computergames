# Preflight Timing Budget Probe

默认 AI、默认布局、release 配置未变。
本报告是 16 样本赛前快速核对，不替代历史 P6 120 样本 timing probe 证据。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `16`
- avg_ms: `371.82`
- p50_ms: `414.97`
- p95_ms: `604.52`
- p99_ms: `610.83`
- max_ms: `612.40`
- rollout_timed_out_count: `0`
- rollout_used_fallback_count: `0`
- illegal_recommendations: `0`
- exceptions: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 26016 --layout balanced_v1 --output "reports\preflight_timing_budget_probe.md" --json-output "reports\preflight_timing_budget_probe.json"
```
