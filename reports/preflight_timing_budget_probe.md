# Preflight Timing Budget Probe

默认 AI、默认布局、release 配置未变。

本报告是 16 样本赛前快速核对，不替代历史 P6 120 样本 timing probe 证据。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `16`
- avg_ms: `393.77`
- p50_ms: `440.40`
- p95_ms: `646.91`
- p99_ms: `647.92`
- max_ms: `648.17`
- rollout_timed_out_count: `0`
- rollout_used_fallback_count: `0`
- illegal_recommendations: `0`
- exceptions: `0`

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 26016 --layout balanced_v1 --output "reports\preflight_timing_budget_probe.md" --json-output "reports\preflight_timing_budget_probe.json"
```
