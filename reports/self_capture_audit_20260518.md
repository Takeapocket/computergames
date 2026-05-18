# Self-capture Choice Audit

默认 AI、默认布局、release 配置未变。

本审计不是 promotion evidence；它只量化当前 release 默认 rollout 的 root 推荐行为，不默认启用任何候选。
losses_with_self_capture 表示输掉的对局中曾发生 self-capture，是相关性统计，不代表 self-capture 导致失败。

- subject: `rollout`
- subject_kwargs_source: `release/v1.0/default_params.json`
- opponent: `greedy_risk`
- games: `60`
- seed_pool: `[31026, 31027, 31028]`
- default_layout: `balanced_v1`

## Summary

- games: `60`
- subject_wins: `43`
- subject_losses: `17`
- total_subject_moves: `588`
- chosen_self_capture: `89`
- chosen_self_capture_rate: `0.15136054421768708`
- chosen_self_capture_with_enemy_capture_alt: `7`
- chosen_self_capture_with_non_self_alt: `82`
- chosen_self_capture_when_own_alive_le_3: `18`
- chosen_self_capture_when_own_alive_le_2: `6`
- self_capture_direct_win_count: `0`
- losses_with_self_capture: `15`
- enemy_capture_alt_available: `135`
- non_self_alt_available: `498`
- avg_score_margin_when_self_capture: `0.11928353658536585`
- illegal_moves: `0`
- crashes: `0`
- timeouts: `0`

## Examples

- game=0 turn=0 player=red dice=2 move=2:[0, 1]->[1, 1] score=0.6875 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=0 turn=8 player=red dice=1 move=1:[0, 0]->[1, 0] score=0.5 own=4->3 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=1 turn=1 player=blue dice=4 move=4:[3, 4]->[3, 3] score=0.5625 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=2 turn=2 player=red dice=2 move=2:[0, 1]->[1, 1] score=0.625 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=2 turn=4 player=red dice=1 move=1:[0, 0]->[1, 0] score=0.59375 own=5->4 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=3 turn=1 player=blue dice=4 move=4:[3, 4]->[2, 4] score=0.65625 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=3 turn=3 player=blue dice=2 move=2:[4, 3]->[3, 3] score=0.59375 own=5->4 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=4 turn=0 player=red dice=4 move=4:[1, 0]->[2, 0] score=0.6875 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=4 turn=2 player=red dice=2 move=2:[0, 1]->[1, 1] score=0.5625 own=5->4 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=5 turn=1 player=blue dice=1 move=1:[4, 4]->[3, 3] score=0.5625 own=6->5 enemy_alt=0 non_self_alt=0 opp_win_dice=[]
- game=5 turn=3 player=blue dice=2 move=2:[4, 3]->[4, 2] score=0.6875 own=5->4 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=6 turn=0 player=red dice=2 move=2:[0, 1]->[0, 2] score=0.5 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=6 turn=6 player=red dice=4 move=4:[1, 0]->[1, 1] score=0.53125 own=5->4 enemy_alt=0 non_self_alt=2 opp_win_dice=[]
- game=7 turn=1 player=blue dice=4 move=4:[3, 4]->[3, 3] score=0.59375 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=7 turn=7 player=blue dice=4 move=4:[3, 3]->[2, 3] score=0.71875 own=5->4 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=8 turn=2 player=red dice=1 move=1:[0, 0]->[1, 0] score=0.59375 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=9 turn=3 player=blue dice=5 move=5:[3, 3]->[2, 3] score=0.53125 own=6->5 enemy_alt=1 non_self_alt=2 opp_win_dice=[]
- game=9 turn=11 player=blue dice=1 move=1:[4, 3]->[3, 3] score=0.46875 own=3->2 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=10 turn=0 player=red dice=4 move=4:[1, 0]->[2, 0] score=0.5625 own=6->5 enemy_alt=0 non_self_alt=1 opp_win_dice=[]
- game=11 turn=5 player=blue dice=1 move=1:[4, 4]->[4, 3] score=0.53125 own=5->4 enemy_alt=0 non_self_alt=0 opp_win_dice=[]

## Reproduce

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_self_capture_choices.py" --games 60 --seed-pool 31026,31027,31028 --opponent greedy_risk --starting-layout balanced_v1 --max-turns 200 --output "reports\self_capture_audit_20260518.md" --json-output "reports\self_capture_audit_20260518.json"
```
