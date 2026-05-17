# P8 Threat Defense Audit

默认 AI、默认布局、release 配置未变。

本报告只审计 threat-reducing alternative 是否存在；它不是默认 AI 晋升证据。
P8.4 候选名为 `rollout_threat_rerank`，只有审计 gate 支持且用户明确批准后才可继续实现。

- subject: `rollout`
- opponent: `greedy_risk`
- games: `6`
- seed_pool: `[28016]`
- default_layout: `balanced_v1`
- audited_positions: `17`

## Summary

- subject_wins: `4`
- subject_losses: `2`
- illegal_moves: `0`
- crashes: `0`
- timeouts: `0`
- draw_max_turns: `0`
- audited_positions: `17`

## Threat Defense

- chosen_allowed_direct_loss_positions: `3`
- threat_reducing_alternative_positions: `1`
- full_block_alternative_positions: `1`
- partial_reduction_alternative_positions: `0`
- average_chosen_threat_count: `0.47058823529411764`
- average_best_alternative_threat_count: `0.35294117647058826`
- average_reduction_when_available: `2.0`

## Low Confidence

- positions: `11`
- with_allowed_direct_loss: `2`
- with_threat_reducing_alternative: `1`
- with_full_block_alternative: `1`
- threat_reducing_ratio: `0.09090909090909091`
- full_block_ratio: `0.09090909090909091`
- best_threat_reducing_in_top_k: `1`
- best_threat_reducing_in_top_k_ratio: `1.0`

## Self-capture Correlation

- self_capture_positions: `3`
- self_capture_and_allowed_direct_loss: `0`
- non_self_capture_positions: `14`
- non_self_capture_and_allowed_direct_loss: `3`
- allowed_direct_loss_rate_given_self_capture: `0.0`
- allowed_direct_loss_rate_given_non_self_capture: `0.21428571428571427`
- self_capture_with_threat_reducing_alternative: `0`
- self_capture_with_full_block_alternative: `0`

## Score Margin Buckets

- <=0.02: positions=`6`, with_threat_reducing_alternative=`0`
- (0.02,0.04]: positions=`4`, with_threat_reducing_alternative=`1`
- (0.04,0.08]: positions=`1`, with_threat_reducing_alternative=`0`
- >0.08_or_null: positions=`6`, with_threat_reducing_alternative=`0`

## Top-k Coverage

- threat_reducing_positions: `1`
- best_threat_reducing_in_top_k: `1`
- best_threat_reducing_in_top_k_ratio: `1.0`

## Decision

- supports_threat_rerank_candidate: `False`
- reason: `low_confidence positions 11 < 30`
- reason: `low_confidence threat_reducing_ratio 0.091 < 0.250`

## Examples


### Threat-reducing Examples

- game=1 turn=19 dice=2 chosen_threat=2 best_threat=0 low_confidence=True

### Low-confidence Threat-reducing Examples

- game=1 turn=19 dice=2 chosen_threat=2 best_threat=0 low_confidence=True

### Allowed Direct-loss Examples

- game=1 turn=19 dice=2 chosen_threat=2 best_threat=0 low_confidence=True
- game=1 turn=21 dice=6 chosen_threat=4 best_threat=4 low_confidence=False
- game=4 turn=10 dice=4 chosen_threat=2 best_threat=2 low_confidence=True

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" --games 6 --seed-pool 28016 --opponent greedy_risk --starting-layout balanced_v1 --max-turns 80 --score-margin 0.08 --top-k 5 --max-examples 5 --output "reports\p8_threat_defense_audit_smoke.md" --json-output "reports\p8_threat_defense_audit_smoke.json"
```
