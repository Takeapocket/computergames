# R-P2A Recursive Star2 Implementation Plan

**Goal:** Add an opt-in `chance_pruning="star2_recursive"` mode that extends the
proven `star2` depth-1 frontier to every positive search depth, while preserving
the frontier experiment signature, exhaustive expectimax choices, exact-only TT
storage, caller-state restoration, and all default/release behavior.

**Source:** Bruce W. Ballard, “The *-Minimax Search Procedure for Trees
Containing Chance Nodes,” *Artificial Intelligence* 21 (1983), 327-350, DOI
`10.1016/S0004-3702(83)80015-0`. For a regular chance node whose children are
all minimizing nodes, one searched move below each child gives an upper bound;
for maximizing children it gives a lower bound.

**Technical Hypothesis:** At any search depth, the exact value of one ordered
move below a minimizing turn node is a sound upper bound on that turn node, and
the exact value of one ordered move below a maximizing turn node is a sound
lower bound. Averaging six same-direction bounds can therefore refute a chance
candidate before its remaining moves are searched. Exact probe subtrees can be
stored under the existing exact TT keys and reused if the search falls back to
Star1.

**Architecture:** Preserve `chance_pruning="star2"` as the frontier-only mode so
its report and AI signature remain reproducible. The new `star2_recursive` mode
uses the same probe helper at every positive depth. A recursive probe applies one
ordered legal move, then evaluates the resulting chance subtree through a
dedicated no-pruning exact path. That path may read/write only complete exact TT
entries. If any probe times out or is otherwise incomplete, it cannot form a
bound. A probe cutoff returns `complete=False` and never stores the aggregate
bound; otherwise the existing Star1 implementation completes the node. This is
an exact one-child recursive probe variant; it does not claim Ballard's full
transformed alpha/beta window optimization.

**Stop Conditions:** Stop or revert if recursive Star2 disagrees with exhaustive
depth-2 search, prunes an equal bound, treats an incomplete probe as usable,
leaks state mutation, stores a probe aggregate as exact, changes `none`/`star1`
behavior, or changes GUI/release/P14 defaults. Performance evidence is a wiring
gate only; no strength or speed claim follows from a one-game probe.

---

### Task 1: Lock Recursive Correctness With Failing Tests

**Files:**
- Modify: `tests/test_expectimax_v2.py`

- [x] Add a production-path depth-2 test for opponent/minimizing upper probes.
- [x] Add the symmetric depth-2 test for perspective/maximizing lower probes.
- [x] Require strict equality at depth 2 to fall back to exact Star1 search.
- [x] Verify RED because current `star2` dispatches depth > 1 directly to Star1.

### Task 2: Add An Exact Recursive Probe Path

**Files:**
- Modify: `ai/expectimax_v2.py`
- Modify: `tests/test_expectimax_v2.py`
- Modify: `tests/test_ai_basic.py`

- [x] Generalize the probe helper to accept `depth` and the per-search TT.
- [x] Add dedicated exact chance/turn probe helpers that:
  - preserve existing terminal, no-move, evaluator, ordering, and timeout rules;
  - search all descendants without Star1/Star2 sibling cutoffs;
  - always undo applied moves;
  - read and write only complete exact TT entries.
- [x] Register the independent `star2_recursive` experiment signature and keep
  `star2` frontier-only for report reproducibility.
- [x] Dispatch every positive-depth `star2_recursive` chance node through the
  generalized probe helper when exactly one directionally valid incumbent bound
  is present.
- [x] Keep strict `<` / `>` cutoffs and the existing counter units.
- [x] Run the new depth-2 tests and verify GREEN.

### Task 3: Lock TT, Timeout, And State Invariants

**Files:**
- Modify: `tests/test_expectimax_v2.py`

- [x] Prove a recursive probe cutoff does not store the parent chance bound,
  while complete child probe entries may be reused as exact TT entries.
- [x] Prove an incomplete recursive probe cannot cut or store the parent and
  always restores caller state.
- [x] Compare `none` and recursive `star2` choices on small real states at depth
  2 for both player-to-move directions.
- [x] Run all ExpectimaxV2 and AI signature tests.
- [x] Run full `pytest -q` and production-file diagnostics.

### Task 4: Bench-Only Evidence And Documentation

**Files:**
- Create: `reports/rp2a_recursive_star2_20260731.md`
- Create: `reports/rp2a_recursive_star2_perf_probe_20260731.json`
- Modify: `reports/rp2a_star2_frontier_20260731.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] Run a bounded single-decision probe and one short `scripts/perf_probe.py`
  match with explicit recursive Star2 kwargs and E-drive research paths.
- [x] Record exact commands, node/probe/cutoff/TT/timing telemetry, counter units,
  source citation, and the exact-probe limitation.
- [x] Record that the frontier AI signature and decision configuration remain
  independently reproducible; treat dated test/timing counts as snapshots and do
  not reuse them as recursive-mode evidence.
- [x] Run `git diff --check`.

### Task 5: Independent Code Review

- [x] Request a read-only reviewer focused on recursive bound validity, depth
  accounting, exact-helper duplication, TT key safety, timeout propagation,
  apply/undo restoration, counter semantics, and production-path test coverage.
- [x] Fix every Critical/Important finding and rerun affected tests plus full
  pytest whenever production code changes.
- [x] Obtain review confirmation that all blockers are closed.
