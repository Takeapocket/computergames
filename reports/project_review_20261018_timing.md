# P6 Timing Budget Probe

默认 AI、默认布局、release 配置未变。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- rules_version: `einstein-nearest-sides-v2`
- sample_count: `16`
- avg_ms: `1346.49`
- p50_ms: `1513.11`
- p95_ms: `1920.32`
- p99_ms: `1920.45`
- max_ms: `1920.48`
- rollout_timed_out_count: `5`
- rollout_used_fallback_count: `1`
- illegal_recommendations: `0`
- exceptions: `0`

rollout_timed_out_count 是 RolloutAI 内部 deadline 信号；它记录推荐器在本步接近自身搜索预算时停止采样，不等同于 bench 对局 `timeouts` 或现场超时判负。preflight 硬失败条件仍是脚本异常、非法推荐、命令失败，或显式硬时间门超过阈值。

## Flagged Samples

- index=1 player=blue dice=3 elapsed_ms=1920.18 timeout=True fallback=False illegal=False exception=
- index=3 player=blue dice=4 elapsed_ms=1920.27 timeout=True fallback=False illegal=False exception=
- index=13 player=red dice=2 elapsed_ms=1920.13 timeout=True fallback=False illegal=False exception=
- index=14 player=blue dice=6 elapsed_ms=1920.24 timeout=True fallback=False illegal=False exception=
- index=15 player=red dice=5 elapsed_ms=1920.48 timeout=True fallback=True illegal=False exception=

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 20261018 --layout balanced_v1 --output "reports\project_review_20261018_timing.md" --json-output "reports\project_review_20261018_timing.json"
```
