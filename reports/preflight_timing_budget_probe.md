# Preflight Timing Budget Probe

默认 AI、默认布局、release 配置未变。

本报告是 16 样本赛前快速核对，不替代历史 P6 120 样本 timing probe 证据。

- ai_kind: `rollout`
- default_layout: `balanced_v1`
- sample_count: `16`
- avg_ms: `1308.10`
- p50_ms: `1282.74`
- p95_ms: `1920.18`
- p99_ms: `1920.32`
- max_ms: `1920.35`
- rollout_timed_out_count: `3`
- rollout_used_fallback_count: `1`
- illegal_recommendations: `0`
- exceptions: `0`

rollout_timed_out_count 是 RolloutAI 内部 deadline 信号；它记录推荐器在本步接近自身搜索预算时停止采样，不等同于 bench 对局 `timeouts` 或现场超时判负。preflight 硬失败条件仍是脚本异常、非法推荐、命令失败，或显式硬时间门超过阈值。

## Flagged Samples

- index=4 player=red dice=5 elapsed_ms=1920.10 timeout=True fallback=False illegal=False exception=
- index=11 player=red dice=5 elapsed_ms=1920.12 timeout=True fallback=True illegal=False exception=
- index=13 player=red dice=5 elapsed_ms=1920.35 timeout=True fallback=False illegal=False exception=

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 16 --seed 26016 --layout balanced_v1 --output "reports\preflight_timing_budget_probe.md" --json-output "reports\preflight_timing_budget_probe.json"
```
