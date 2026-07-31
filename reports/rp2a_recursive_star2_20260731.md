# R-P2A Recursive Star2 Exact Probe

Date: 2026-07-31

## Technical Basis

Ballard's Star2 procedure probes one child below each same-type decision node of
a regular *-minimax chance node. One move below a minimizing node is an upper
bound on that node; one move below a maximizing node is a lower bound.

Source: Bruce W. Ballard, “The *-Minimax Search Procedure for Trees Containing
Chance Nodes,” *Artificial Intelligence* 21 (1983), 327-350, DOI
`10.1016/S0004-3702(83)80015-0`.

The implementation uses a conservative recursive variant: each selected move's
remaining chance subtree is searched to an exact value without Star1/Star2
sibling cutoffs. It does not implement Ballard's transformed alpha/beta probe
windows.

## Experiment Signature

- `chance_pruning="star2"` remains the depth-1 frontier experiment. Its AI
  signature and single-decision configuration remain reproducible; dated test
  totals and timing measurements remain historical snapshots.
- `chance_pruning="star2_recursive"` is the new all-positive-depth experiment.
- `chance_pruning="none"` remains the default. GUI, release/v1.0, P14 rollout,
  and core rule behavior are unchanged.

## Implementation

- A directionally valid chance node probes one ordered move for each dice result.
- The probe calls dedicated exact chance/turn helpers at `depth - 1`.
- Exact helpers preserve terminal, no-move, evaluator, ordering, timeout, and
  apply/undo semantics while disabling Star1/Star2 sibling cutoffs.
- Complete probe subtrees may read/write the existing exact TT keys. A later
  Star1 fallback can reuse those entries.
- An incomplete probe cannot form a bound. A probe-cut parent returns
  `complete=False`, so its aggregate upper/lower bound is never stored as exact.
- Strict `<` / `>` comparisons preserve equal candidates.
- `chance_probes` counts applied probe moves, `chance_probe_cutoffs` counts
  chance candidates refuted by aggregate probes, and `chance_prunes` remains the
  Star1 count of dice results skipped without being visited.
- `nodes` counts ordinary chance/turn entries and exact-probe descendant entries;
  the probe turn entry itself is represented by `chance_probes`, so `nodes` must
  not be compared across pruning modes without considering that separate count.

## Verification

- Production-path depth-2 tests cover minimizing upper and maximizing lower
  probes, strict equality, parent TT exclusion, exact child TT reuse, timeout,
  caller-state restoration, RED/BLUE real-state equivalence with unpruned search,
  and a nonconstant evaluator comparison between the recursive probe helper and
  the corresponding exact subtree.
- ExpectimaxV2 target group: `61 passed in 2.68s`.
- Full `pytest -q`: `970 passed in 75.41s`.
- `ai/expectimax_v2.py` diagnostics: no findings.

Single decision on `balanced_v1`, dice 1, depth 2, 250ms, TT + ordering +
iterative deepening:

```text
nodes=1686
tt_hits=12
tt_stores=369
chance_prunes=0
chance_probes=240
chance_probe_cutoffs=6
timed_out=False
completed_depth=2
caller_state_unchanged=True
```

Bench-only match probe (`reports/rp2a_recursive_star2_perf_probe_20260731.json`):

```text
games=1
turns=17
steps=17
average_step_time_ms=31.2422
max_step_time_ms=134.6452
illegal_moves=0
crashes=0
timeouts=0
```

The JSON file also contains the script's existing `rollout_decision_probe`; that
section measures the P14 rollout micro-baseline and is not recursive Star2
telemetry.

## Reproduction

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_star2_signature" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_recursive_star2_signature" -q
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" -c "from ai.match import build_ai, starting_state_for; ai=build_ai('expectimax_v2', seed=73103, depth=2, time_limit_ms=250.0, randomize_ties=False, use_transposition_table=True, move_ordering=True, iterative_deepening=True, chance_pruning='star2_recursive'); state=starting_state_for('balanced_v1'); before=state.serialize(); move=ai.choose_move(state, 1); print(move); print(ai.last_search_stats); print(state.serialize() == before)"
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --red expectimax_v2 --red-kwargs '{"depth":2,"time_limit_ms":250.0,"randomize_ties":false,"use_transposition_table":true,"move_ordering":true,"iterative_deepening":true,"chance_pruning":"star2_recursive"}' --blue random --games 1 --samples 4 --seed 73103 --layout-id balanced_v1 --max-turns 20 --output "reports/rp2a_recursive_star2_perf_probe_20260731.json"
```

## Boundaries

This is correctness, signature, and wiring evidence only. The one-game timing is
not a speed or strength result. Any promotion or strength claim still requires a
persistent ladder comparison against the P14 anchor. The remaining R-P2A item is
the exact endgame solver.
