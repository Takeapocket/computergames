# R-P2A ExpectimaxV2 Star1 Bench Smoke

Date: 2026-06-14

## Scope

This is a bench-only smoke for the R-P2A classic-search line. It verifies that the configured `expectimax_v2` research player can enter the persistent ladder and perf probe with TT, move ordering, iterative deepening, and root-level `star1` chance pruning enabled.

This is not a promotion run and does not support any strength claim.

## Player Config

Config file:

```text
reports/rp2a_expectimax_v2_star1_ladder_players_20260614.json
```

Research player:

```text
player_id=expectimax_v2_d2_tt_order_star1
kind=expectimax_v2
depth=2
time_limit_ms=250.0
randomize_ties=false
use_transposition_table=true
move_ordering=true
iterative_deepening=true
chance_pruning=star1
```

Baseline player:

```text
p14_default
```

## Ladder Smoke

Command:

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --players-config "reports/rp2a_expectimax_v2_star1_ladder_players_20260614.json" --games-per-pair 1 --seed 62014 --layout-id balanced_v1 --max-turns 24 --output-dir "E:/computergame-data/ladder/rp2a_expectimax_v2_star1_smoke_20260614"
```

Output:

```text
E:/computergame-data/ladder/rp2a_expectimax_v2_star1_smoke_20260614/report.json
E:/computergame-data/ladder/rp2a_expectimax_v2_star1_smoke_20260614/report.md
E:/computergame-data/ladder/rp2a_expectimax_v2_star1_smoke_20260614/games.jsonl
```

Observed:

```text
games=1
seed=62014
layout_id=balanced_v1
max_turns=24
p14_default rating=1516.0
expectimax_v2_d2_tt_order_star1 rating=1484.0
```

The sample is intentionally too small for chess-strength interpretation. Because `games_per_pair=1` is odd, ladder reports one extra red game for the first player; this is acceptable for smoke only.

## Perf Probe Smoke

Command:

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 1 --samples 4 --seed 62014 --red expectimax_v2 --red-kwargs '{"depth":2,"time_limit_ms":250.0,"randomize_ties":false,"use_transposition_table":true,"move_ordering":true,"iterative_deepening":true,"chance_pruning":"star1"}' --blue rollout --blue-kwargs '{"rollouts_per_move":64,"max_rollout_turns":80,"max_step_time_ms":2000.0,"epsilon":0.05,"close_sample_margin":0.08,"close_sample_rollouts_per_move":96,"low_confidence_margin":0.08,"playout_policy":"greedy_risk","cutoff_eval":"zweistein","deadline_safety_ms":80.0}' --layout-id balanced_v1 --max-turns 24 --output "reports/rp2a_expectimax_v2_star1_perf_probe_20260614.json"
```

Output:

```text
reports/rp2a_expectimax_v2_star1_perf_probe_20260614.json
```

Observed:

```text
match_probe.games=1
match_probe.turns=14
match_probe.steps=14
match_probe.average_step_time_ms=563.0974928577156
match_probe.max_step_time_ms=1774.8535999999149
match_probe.illegal_moves=0
match_probe.crashes=0
match_probe.timeouts=0
rollout_decision_probe.samples=4
rollout_decision_probe.root_visits=970
rollout_decision_probe.root_visits_per_second=137.8185592524542
rollout_decision_probe.instrumentation.game_state_clone_calls=971
rollout_decision_probe.instrumentation.game_state_serialize_calls=0
rollout_decision_probe.instrumentation.game_state_deserialize_calls=0
```

## Verification

Targeted checks:

```text
tests/test_perf_probe.py tests/test_ladder.py tests/test_expectimax_v2.py: 55 passed in 2.31s
```

Full regression:

```text
pytest -q: 941 passed in 73.09s
```

Whitespace check:

```text
git diff --check: no whitespace errors; only existing LF/CRLF working-copy warnings in documentation files
```

## Decision

R-P2A bench wiring is usable for configured `expectimax_v2` players. No GUI, release default, P14 baseline, or core rule behavior changed.
