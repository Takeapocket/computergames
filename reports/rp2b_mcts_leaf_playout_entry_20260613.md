# R-P2B MCTS Leaf Playout Entry

Date: 2026-06-13

## Scope

This report records the first R-P2B L0 implementation slice: `MCTSAI` can now
evaluate leaf nodes with a bounded random playout when explicitly requested.

This is a diagnostic entry point for the design hypothesis that the old MCTS
candidate was structurally weak because its leaves used static evaluation only.
It does not change the default AI, GUI, release configuration, or any promotion
decision.

## Implementation

`MCTSAI` now exposes two explicit parameters:

```text
leaf_policy="static"      # default, previous behavior
leaf_policy="playout"     # bounded random playout from the leaf position
leaf_playout_turns=20     # maximum playout half-turns when leaf_policy="playout"
```

The playout path:

```text
uses the existing MCTS RNG
samples dice uniformly
chooses a random legal move
returns WIN_VALUE / -WIN_VALUE on terminal or no-move outcomes
falls back to the configured static evaluator at the cutoff
undoes all simulated moves before returning
```

`ai_version_signature()` records `leaf_policy` and `leaf_playout_turns`, so
future ladder or replay metadata can distinguish static-leaf MCTS from the
playout-leaf diagnostic candidate.

## Verification

Targeted tests:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_mcts.py" -q
```

Observed:

```text
25 passed in 0.93s
```

Full regression:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Observed:

```text
921 passed in 72.91s
```

The new tests cover:

```text
static leaf policy remains the default
unknown leaf_policy values fail loudly
negative leaf_playout_turns fail loudly
playout leaf can resolve a direct leaf win
playout leaf restores caller state
MCTS iteration dispatches to the playout leaf path
build_ai("mcts_eval_v1") accepts and signs leaf_policy / leaf_playout_turns
```

## Ladder Smoke

Follow-up tooling:

```text
scripts/ladder.py now accepts --players-config for JSON player definitions with kwargs
scripts/ladder.py now accepts --max-turns to bound diagnostic runs
MCTSAI exposes max_step_time_ms = time_limit_ms so match timeout telemetry can see its budget
```

Player config:

```text
reports/rp2b_mcts_leaf_playout_ladder_players_20260613.json
```

Command:

```powershell
& ".venv/Scripts/python.exe" "scripts/ladder.py" --players-config "reports/rp2b_mcts_leaf_playout_ladder_players_20260613.json" --games-per-pair 2 --seed 62013 --max-turns 40 --output-dir "E:/computergame-data/ladder/rp2b_mcts_leaf_playout_l0_20260613_v2"
```

Output:

```text
E:/computergame-data/ladder/rp2b_mcts_leaf_playout_l0_20260613_v2/report.json
E:/computergame-data/ladder/rp2b_mcts_leaf_playout_l0_20260613_v2/games.jsonl
```

Observed smoke result:

```text
games=6, seed=62013, layout=balanced_v1, max_turns=40
illegal_moves=0, crashes=0, timeouts=0

mcts_static_z_l0   rating=1523.576 +/- 156.525, games=4
p14_default        rating=1502.675 +/- 156.525, games=4
mcts_playout_z_l8  rating=1473.749 +/- 156.525, games=4
```

Pair-level result:

```text
mcts_static_z_l0 vs p14_default:       2-0
p14_default vs mcts_playout_z_l8:      2-0
mcts_static_z_l0 vs mcts_playout_z_l8: 1-1
```

Interpretation:

```text
This validates that the playout-leaf MCTS candidate can enter the persistent ladder with reproducible metadata.
It does not validate playing strength.
At this L0 sample size there is no positive signal that leaf_policy="playout" improves the static-leaf MCTS baseline.
```

## Remaining Gate

R-P2B L0 still needs meaningful ladder evidence before any strength claim:

```text
increase games beyond smoke scale
use fixed seed pools and balanced colors
compare static leaf, playout leaf, and P14 anchor with enough games for uncertainty to shrink
record games, seeds, Elo / uncertainty, illegal moves, crashes, timeouts, and step times
stop or redesign if playout leaf keeps failing to separate from static leaf
```

No `core/`, GUI, `release/v1.0/`, P14 rollout defaults, or default AI behavior changed in this slice.
