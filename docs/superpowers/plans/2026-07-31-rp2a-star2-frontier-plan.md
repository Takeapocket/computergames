# R-P2A Star2 Frontier Probe Implementation Plan

**Goal:** Add an opt-in `chance_pruning="star2"` mode that uses safe one-move probes at `depth=1` chance nodes, while retaining Star1 behavior at deeper nodes and preserving exact search choices.

**Source:** Bruce W. Ballard, “The *-Minimax Search Procedure for Trees Containing Chance Nodes,” *Artificial Intelligence* 21 (1983), 327–350, DOI `10.1016/S0004-3702(83)80015-0`. Star2 is valid for regular trees whose chance-node children are all minimizing nodes or all maximizing nodes; one child of each decision node supplies a one-sided bound before full search.

**Architecture:** Keep `none` as the default. Extend the existing Star1 entry points so `star2` inherits all upper/lower cutoff behavior. At `depth=1`, probe one ordered legal move for each dice outcome: a move below a minimizing node is an upper bound on that node, while a move below a maximizing node is a lower bound. If the aggregate probe bound strictly refutes the incumbent, return an incomplete bound; otherwise run the existing Star1 search. Deeper chance nodes do not probe in this slice.

**Stop Conditions:** Stop or revert if Star2 disagrees with exhaustive depth-1 search, prunes equal-score candidates, leaks state mutation, stores probe bounds as exact TT entries, times out without returning an incomplete result, or changes default/release behavior.

---

### Task 1: Register The Experimental Mode

**Files:**
- Modify: `ai/expectimax_v2.py`
- Modify: `tests/test_expectimax_v2.py`
- Modify: `tests/test_ai_basic.py`

- [x] Add a failing test that constructs `ExpectimaxV2(chance_pruning="star2")` and verifies the AI signature records `star2`.
- [x] Change the invalid-mode test to use an actually unsupported value such as `star3`.
- [x] Run the two tests and verify RED because `star2` is currently rejected.
- [x] Extend `ExpectimaxV2ChancePruning`, constructor validation, root cutoff entry, recursive turn cutoff entry, and signature behavior to accept `star2` without changing the default.
- [x] Add `chance_probes` and `chance_probe_cutoffs` to `ExpectimaxV2SearchStats`, both defaulting to zero.
- [x] Run the registration tests and verify GREEN.

### Task 2: Implement A Safe Frontier Probe

**Files:**
- Modify: `ai/expectimax_v2.py`
- Modify: `tests/test_expectimax_v2.py`

- [x] Add a failing scripted-evaluator test where exhaustive search and Star2 choose the same root move, but Star2 probes six opponent/minimizing dice children and cuts a dominated root candidate.
- [x] Add a failing equality test where the aggregate probe upper bound equals the incumbent; Star2 must not cut and must complete the full search.
- [x] Implement `_probe_frontier_turn_bound()`:
  - obtain legal moves for the current player and dice;
  - return the existing exact no-move value if none exist;
  - choose the first `_ordered_moves()` result;
  - apply the move, evaluate the resulting `depth=0` chance node, and always undo;
  - increment `chance_probes` only for an applied probe move;
  - propagate timeout/incomplete status without using it as a bound.
- [x] Implement `_chance_value_star2_frontier()`:
  - require `depth == 1` and exactly one directionally valid cutoff;
  - for an upper cutoff, require opponent/minimizing turn children and average their probe upper bounds;
  - for a lower cutoff, require perspective/maximizing turn children and average their probe lower bounds;
  - use strict `<` / `>` comparisons to preserve ties;
  - on a probe cutoff, increment `chance_probe_cutoffs`, leave the Star1-only
    `chance_prunes` counter unchanged, and return `(bound, False)`;
  - otherwise delegate to `_chance_value_star1()`.
- [x] Dispatch `star2` to the frontier helper only when `depth == 1`; otherwise delegate to Star1.
- [x] Run the scripted cutoff and equality tests and verify GREEN.

### Task 3: Lock Search Invariants

**Files:**
- Modify: `tests/test_expectimax_v2.py`

- [x] Add a real-state depth-1 equivalence test comparing `none` and `star2` move choice and caller-state serialization.
- [x] Add a TT test showing a probe-cut chance node returns `complete=False` and is not stored as an exact chance entry.
- [x] Add a timeout test showing an incomplete probe does not become a usable cutoff.
- [x] Run all Star1/Star2 tests and the AI signature test.
- [x] Run full `pytest -q`.

### Task 4: Bench-Only Evidence And Documentation

**Files:**
- Create: `reports/rp2a_star2_frontier_20260731.md`
- Create: `reports/rp2a_star2_frontier_perf_probe_20260731.json`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] Run `scripts/perf_probe.py` with an explicit depth-2 Star2 configuration and E-drive research paths. Treat it as wiring/performance evidence only, not a strength claim.
- [x] Record probe counts, timing, illegal/crash/timeout telemetry, exact commands, source citation, and the frontier-only limitation.
- [x] Update project status docs without changing GUI/release/P14 defaults.
- [x] Run `git diff --check`.

### Task 5: Independent Code Review

- [x] Request a read-only reviewer focused on bound direction, depth semantics, strict tie behavior, timeout/TT safety, and whether the tests execute production probe code.
- [x] Fix all Critical/Important findings and rerun affected tests plus full pytest when production code changes.
- [x] Obtain review confirmation that blockers are closed.
