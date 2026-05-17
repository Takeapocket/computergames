# P8 Threat Defense Audit

默认 AI、默认布局、release 配置未变。

本报告只审计 threat-reducing alternative 是否存在；它不是默认 AI 晋升证据。
P8.4 候选名为 `rollout_threat_rerank`，只有审计 gate 支持且用户明确批准后才可继续实现。

- subject: `rollout`
- opponent: `greedy_risk`
- games: `120`
- seed_pool: `[28016, 28017, 28018]`
- default_layout: `balanced_v1`
- audited_positions: `361`

## Summary

- subject_wins: `80`
- subject_losses: `40`
- illegal_moves: `0`
- crashes: `0`
- timeouts: `0`
- draw_max_turns: `0`
- audited_positions: `361`

## Threat Defense

- chosen_allowed_direct_loss_positions: `69`
- threat_reducing_alternative_positions: `5`
- full_block_alternative_positions: `3`
- partial_reduction_alternative_positions: `2`
- average_chosen_threat_count: `0.37119113573407203`
- average_best_alternative_threat_count: `0.3518005540166205`
- average_reduction_when_available: `1.4`

## Low Confidence

- positions: `189`
- with_allowed_direct_loss: `28`
- with_threat_reducing_alternative: `1`
- with_full_block_alternative: `1`
- threat_reducing_ratio: `0.005291005291005291`
- full_block_ratio: `0.005291005291005291`
- best_threat_reducing_in_top_k: `0`
- best_threat_reducing_in_top_k_ratio: `0.0`

## Self-capture Correlation

- self_capture_positions: `68`
- self_capture_and_allowed_direct_loss: `1`
- non_self_capture_positions: `293`
- non_self_capture_and_allowed_direct_loss: `68`
- allowed_direct_loss_rate_given_self_capture: `0.014705882352941176`
- allowed_direct_loss_rate_given_non_self_capture: `0.23208191126279865`
- self_capture_with_threat_reducing_alternative: `0`
- self_capture_with_full_block_alternative: `0`

## Score Margin Buckets

- <=0.02: positions=`48`, with_threat_reducing_alternative=`0`
- (0.02,0.04]: positions=`73`, with_threat_reducing_alternative=`1`
- (0.04,0.08]: positions=`68`, with_threat_reducing_alternative=`0`
- >0.08_or_null: positions=`172`, with_threat_reducing_alternative=`4`

## Top-k Coverage

- threat_reducing_positions: `5`
- best_threat_reducing_in_top_k: `4`
- best_threat_reducing_in_top_k_ratio: `0.8`

## Decision

- supports_threat_rerank_candidate: `False`
- reason: `low_confidence threat_reducing_ratio 0.005 < 0.250`
- reason: `low-confidence best threat-reducing in top_k ratio 0.000 < 0.600`

## Examples


### Threat-reducing Examples

- game=7 turn=17 dice=2 chosen_threat=5 best_threat=3 low_confidence=False
- game=42 turn=14 dice=5 chosen_threat=2 best_threat=0 low_confidence=True
- game=72 turn=12 dice=6 chosen_threat=1 best_threat=0 low_confidence=False
- game=75 turn=17 dice=3 chosen_threat=1 best_threat=0 low_confidence=False
- game=114 turn=16 dice=2 chosen_threat=3 best_threat=2 low_confidence=False

### Low-confidence Threat-reducing Examples

- game=42 turn=14 dice=5 chosen_threat=2 best_threat=0 low_confidence=True

### Allowed Direct-loss Examples

- game=6 turn=18 dice=2 chosen_threat=3 best_threat=3 low_confidence=True
- game=7 turn=17 dice=2 chosen_threat=5 best_threat=3 low_confidence=False
- game=10 turn=16 dice=2 chosen_threat=2 best_threat=2 low_confidence=False
- game=11 turn=17 dice=4 chosen_threat=1 best_threat=1 low_confidence=False
- game=11 turn=19 dice=6 chosen_threat=1 best_threat=1 low_confidence=False

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" --games 120 --seed-pool 28016,28017,28018 --opponent greedy_risk --starting-layout balanced_v1 --max-turns 200 --score-margin 0.08 --top-k 5 --max-examples 20 --output "reports\p8_threat_defense_audit_20260517.md" --json-output "reports\p8_threat_defense_audit_20260517.json"
```
