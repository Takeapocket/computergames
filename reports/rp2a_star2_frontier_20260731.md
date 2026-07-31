# R-P2A Star2 Frontier Probe

Date: 2026-07-31

## Technical Basis

Ballard's Star2 algorithm improves Star1 on regular *-minimax trees by probing one child below each same-type decision node under a chance node. A child of a minimizing node is an upper bound on that node; a child of a maximizing node is a lower bound.

Source: Bruce W. Ballard, “The *-Minimax Search Procedure for Trees Containing Chance Nodes,” *Artificial Intelligence* 21 (1983), 327–350, DOI `10.1016/S0004-3702(83)80015-0`.

This implementation deliberately limits probing to `depth=1`, where every probe lands on the configured leaf evaluator and its bound direction is directly provable. Deeper Star2 probing remains future work; deeper nodes currently use the completed Star1 upper/lower implementation.

## Implementation

- Added opt-in `chance_pruning="star2"`; `none` remains the default.
- At a depth-1 chance node with opponent/minimizing children, one ordered move per dice outcome supplies an upper bound.
- At a depth-1 chance node with perspective/maximizing children, one ordered move per dice outcome supplies a lower bound.
- Aggregate probe bounds use strict `<` / `>` cutoffs, so equal candidates are fully searched.
- A probe timeout returns an incomplete result and cannot trigger a cutoff.
- Probe cutoffs return `complete=False`; they are not stored as exact TT entries.
- Added `chance_probes` and `chance_probe_cutoffs` search counters. A probe is one
  applied candidate move, including an attempt that later times out.
- `chance_prunes` retains its Star1 meaning: dice outcomes skipped without being
  visited. Star2 probe cutoffs are counted only by `chance_probe_cutoffs`, because
  all six dice outcomes have already been partially visited.
- `nodes` does not include the probe turn entry itself; that work is represented
  separately by `chance_probes`, so cross-mode node counts are not directly
  comparable.

## Verification

- Star2 mode/AI signature, scripted cutoff, upper- and lower-bound strict equality,
  real-state depth-1 equivalence, symmetric bound direction, TT safety, timeout
  safety, and caller-state restoration are covered.
- ExpectimaxV2 target group: `48 passed in 2.14s`.
- Full `pytest -q`: `957 passed in 75.84s`.

Single decision on `balanced_v1`, dice 1, depth 2, 250ms, TT + ordering + iterative deepening:

```text
nodes=1674
tt_stores=369
chance_prunes=0
chance_probes=228
chance_probe_cutoffs=6
timed_out=False
completed_depth=2
caller_state_unchanged=True
```

Bench-only match probe (`reports/rp2a_star2_frontier_perf_probe_20260731.json`):

```text
games=1
turns=19
steps=19
average_step_time_ms=45.2437
max_step_time_ms=166.0945
illegal_moves=0
crashes=0
timeouts=0
```

The JSON file also contains the script's existing `rollout_decision_probe`; that section measures the P14 rollout micro-baseline and is not Star2 telemetry.

## Reproduction

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_star2_signature" -q
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" -c "from ai.match import build_ai, starting_state_for; ai=build_ai('expectimax_v2', seed=73102, depth=2, time_limit_ms=250.0, randomize_ties=False, use_transposition_table=True, move_ordering=True, iterative_deepening=True, chance_pruning='star2'); state=starting_state_for('balanced_v1'); before=state.serialize(); move=ai.choose_move(state, 1); print(move); print(ai.last_search_stats); print(state.serialize() == before)"
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --red expectimax_v2 --red-kwargs '{"depth":2,"time_limit_ms":250.0,"randomize_ties":false,"use_transposition_table":true,"move_ordering":true,"iterative_deepening":true,"chance_pruning":"star2"}' --blue random --games 1 --samples 4 --seed 73102 --layout-id balanced_v1 --max-turns 20 --output "reports/rp2a_star2_frontier_perf_probe_20260731.json"
```

## Code Review

The independent review found no Critical issue. Its one Important finding was
the incompatible `chance_prunes` meaning between Star1 and Star2. The counter
update was removed from the Star2 cutoff path, the report now defines each unit,
and a direct lower-bound equality regression was added. The affected target group
and full suite both pass after the fix.

## Boundaries

This is correctness and wiring evidence, not a chess-strength result. No default AI, GUI, release/v1.0, P14 rollout parameter, or core rule behavior changed. This report covers only the frontier experiment; the follow-up below records the separate recursive mode.

## Follow-up

The recursive follow-up is complete under the separate, reproducible
`chance_pruning="star2_recursive"` signature; see
`reports/rp2a_recursive_star2_20260731.md`. The `star2` AI signature and
single-decision configuration remain frontier-only and reproducible. The test
totals and timing values above are dated snapshots and naturally change as the
suite and runtime evolve. The exact endgame solver remains pending.
