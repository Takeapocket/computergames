# R-P2A ExpectimaxV2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `ExpectimaxV2` from a depth-1 experimental probe into a measurable classic-search line: stable state keys, optional transposition table, move ordering, iterative deepening, then Star1/Star2 chance pruning only after value bounds are proven.

**Architecture:** Keep `core/`, GUI, `release/v1.0/`, and P14 rollout defaults unchanged. All R-P2A work stays under `ai/expectimax_v2.py`, focused tests under `tests/test_expectimax_v2.py`, and later bench evidence under `reports/` / `data/ladder/`.

**Tech Stack:** Python 3.11, pytest, existing `GameState.apply_move()/undo_move()`, existing `ai.evaluator.evaluate()`, `scripts/perf_probe.py`, `scripts/ladder.py`.

**Technical Hypothesis:** The historical depth-1 expectimax failure is not evidence that classic search is dead; it is evidence that the old implementation had no depth-enabling machinery. If state-keying, TT reuse, move ordering, and iterative deepening reduce effective node cost without changing shallow-search decisions, then R-P2A can safely test depth 3-6 before comparing against the P14 rollout anchor.

**Stop Conditions:**
- Stop immediately if any optimization changes the result of fixed-depth unoptimized expectimax on deterministic test positions.
- Stop Star1/Star2 if `evaluate()` value bounds are not explicit and mechanically tested.
- Stop TT work if timeout or partial-node values cannot be separated from exact values.
- Stop expansion if `ExpectimaxV2` cannot produce legal moves under timeout tests or mutates caller `GameState`.
- Do not claim strength improvement until ladder/bench evidence is produced against current release default rollout kwargs.
- Do not promote, change GUI defaults, or edit `release/v1.0/` during R-P2A implementation.

**Risk Notes From Read-Only Review:**
- TT keys must ignore `GameState.history` but include current player, live/dead pieces, node type, perspective, depth, dice, and evaluator/search version.
- Timeout paths in the current search can evaluate only part of a node; those values must never be stored as exact TT entries.
- Move ordering is allowed to change traversal and node count, but fixed-depth full-search results must remain equivalent to unordered search.
- Star1/Star2 is blocked until the search value range and evaluator version are fixed by tests.
- Current `depth` means opponent-response plies after the root move; iterative deepening must preserve and test that semantic.

---

### Task 1: Search Value Bounds And Stable Keys

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`

- [x] **Step 1: Write failing tests**

Add tests for:

```text
expectimax_v2_state_key(state) is stable across serialize/deserialize
expectimax_v2_state_key(state) excludes history but includes current player
expectimax_v2_transposition_key(...) includes node type, perspective, depth, dice, evaluator version
evaluate() outputs used by ExpectimaxV2 stay inside [-WIN_SCORE, WIN_SCORE]
```

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
```

- [x] **Step 2: Implement non-behavioral helpers**

Implement deterministic tuple keys in `ai/expectimax_v2.py`:

```text
expectimax_v2_state_key(state)
expectimax_v2_transposition_key(state, node_type, perspective, depth, dice)
EXPECTIMAX_V2_EVALUATOR_VERSION
EXPECTIMAX_V2_MIN_SCORE / EXPECTIMAX_V2_MAX_SCORE
expectimax_v2_score_in_bounds(score)
```

No `choose_move()` behavior change in this task.

- [x] **Step 3: Verify**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
```

Observed:

```text
tests/test_expectimax_v2.py: 8 passed in 0.75s
full pytest: 890 passed in 72.29s
```

### Task 2: Optional Transposition Table

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`

- [x] **Step 1: Write equivalence tests**

For deterministic positions and `randomize_ties=False`, compare:

```text
ExpectimaxV2(depth=1, use_transposition_table=False)
ExpectimaxV2(depth=1, use_transposition_table=True)
ExpectimaxV2(depth=2, use_transposition_table=False)
ExpectimaxV2(depth=2, use_transposition_table=True)
```

Expected: same selected move, same caller-state serialization after `choose_move()`.

- [x] **Step 2: Add TT behind explicit flag**

Added per-`choose_move()` table only; no cross-move state is kept.

Track minimal stats and exactness:

```text
last_search_stats.nodes
last_search_stats.tt_hits
last_search_stats.tt_stores
last_search_stats.timed_out
TT entries store only completed exact values
```

- [x] **Step 3: Verify**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
```

Observed:

```text
tests/test_expectimax_v2.py: 11 passed in 0.96s
tests/test_expectimax_v2.py + expectimax_v2 signature test: 12 passed in 0.92s
full pytest: 893 passed in 71.66s
```

### Task 3: Move Ordering Without Result Changes

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`

- [x] **Step 1: Write ordering-only tests**

Covered direct win, enemy capture, progress toward target, stable equal-score ordering, deterministic tie fallback, and full-search equivalence.

- [x] **Step 2: Use ordering inside search**

Applied ordering behind explicit `move_ordering=True` at root and recursive turn nodes. Ordering changes traversal order only; tied root recommendations are restored to original legal-move order before fallback.

- [x] **Step 3: Verify equivalence**

Run deterministic equivalence tests against `move_ordering=False` for fixed positions.

Observed:

```text
tests/test_expectimax_v2.py: 18 passed in 1.21s
tests/test_expectimax_v2.py + expectimax_v2 signature test: 19 passed in 1.18s
full pytest: 900 passed in 73.16s
```

### Task 4: Iterative Deepening And Time Budget

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`

- [x] **Step 1: Add fake-clock tests**

Tests must prove:

```text
returns last completed depth result when time expires
falls back to legal move if no depth completes
records completed_depth
does not mutate GameState
```

- [x] **Step 2: Implement explicit iterative mode**

Implemented behind explicit `iterative_deepening=True`. Plain fixed-depth behavior remains the default path and uses the same root-search helper for regression comparison.

- [x] **Step 3: Verify**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
```

Observed:

```text
tests/test_expectimax_v2.py + expectimax_v2 signature test: 23 passed in 1.49s
full pytest: 904 passed in 71.94s
```

### Task 5: Star1/Star2 Entry Gate

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`
- Report: `reports/rp2a_star_pruning_entry_YYYYMMDD.md`

- [x] **Step 1: Prove bounds first**

Implemented explicit score-bound enforcement in `ai/expectimax_v2.py` and documented the entry gate in `reports/rp2a_star_pruning_entry_20260613.md`. Chance-node pruning remains unimplemented.

Observed:

```text
tests/test_expectimax_v2.py: 25 passed in 1.52s
full pytest: 907 passed in 73.66s
```

- [x] **Step 2: Small-depth exact equivalence**

For small positions, compare pruned and unpruned chance values at depth 1-2.
Implemented a default-off `chance_pruning` parameter with modes `none` and `star1`.
`star1` currently uses a separate conservative exact chance-node path and records
`chance_prunes=0`; this is an equivalence gate, not an implemented Star pruning
claim.

Observed:

```text
tests/test_expectimax_v2.py + expectimax_v2 signature test: 30 passed in 2.11s
full pytest: 911 passed in 76.03s
```

- [x] **Step 3: Root-level Star1 upper-bound pruning**

At root candidate evaluation, `chance_pruning="star1"` now passes the incumbent
root score into the chance node as an upper-bound cutoff. After each dice outcome,
the chance node computes the best possible remaining average using
`EXPECTIMAX_V2_MAX_SCORE`; if that upper bound is strictly below the incumbent,
it skips the remaining dice outcomes and increments `chance_prunes`. The cutoff
uses strict `<` so equal-score candidates are still fully evaluated and tie
fallback semantics are preserved. Pruned chance values are treated as bounds, not
exact TT values.

Observed:

```text
tests/test_expectimax_v2.py + expectimax_v2 signature test: 32 passed in 2.00s
full pytest: 913 passed in 73.30s
```

- [x] **Step 4: Bench-only, no promotion**

Use `scripts/perf_probe.py` and `scripts/ladder.py` for evidence. Any strength claim must compare against P14 release default rollout kwargs, not bare `build_ai("rollout")`.

Observed 2026-06-14:

```text
ladder smoke: E:/computergame-data/ladder/rp2a_expectimax_v2_star1_smoke_20260614/report.json
perf probe: reports/rp2a_expectimax_v2_star1_perf_probe_20260614.json
report: reports/rp2a_expectimax_v2_star1_bench_smoke_20260614.md
scope: 1 ladder game + 1 perf game, no strength claim, no promotion
```

- [x] **Step 5: Complete recursive Star1/Star2 chance pruning**

Recursive Star1 now carries symmetric upper/lower incumbent bounds. The
frontier-only `star2` mode and all-depth `star2_recursive` mode have independent
AI signatures so both reports remain reproducible. Recursive Star2 uses exact
one-child probe subtrees, exact-only TT reuse, strict tie comparisons, and
timeout-safe incomplete propagation. Reports:
`reports/rp2a_minimizing_star1_20260731.md`,
`reports/rp2a_star2_frontier_20260731.md`, and
`reports/rp2a_recursive_star2_20260731.md`.

Observed 2026-07-31:

```text
ExpectimaxV2 target group: 61 passed in 2.68s
full pytest: 970 passed in 75.41s
scope: correctness + wiring probes only, no promotion
```

- [x] **Step 6: Exact endgame solver**

Added standalone `ExactEndgameSolver` / `ExactEndgameAI` under the explicit
`endgame_exact` kind. The solver uses a strictly decreasing Manhattan progress
measure, untruncated chance/turn recursion, canonical RED win-probability TT,
and a small-piece/near-terminal gate with explicit failure outside the gate.
Retrograde databases remain out of scope. Report:
`reports/rp2a_exact_endgame_20260731.md`.

Observed 2026-07-31:

```text
E3 target group: 21 passed in 0.81s
full pytest: 991 passed in 72.85s
hand oracle: P(RED)=1/3, P(BLUE)=2/3, 25 nodes, 3 TT hits, 14 TT stores
scope: exact primitive + endgame-only AI, no promotion
```

### Task 6: Status And Evidence Sync

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`
- Create/Modify: `reports/rp2a_*.md`

- [x] **Step 1: Record each completed slice**

Only record verified facts: changed files, exact tests, perf/ladder outputs, and explicit non-goals.

- [x] **Step 2: Keep R-P0 boundary visible**

Historical boundary updated 2026-06-14: R-P0 migration to `E:\computergame`, `.venv` rebuild, E-drive cache directories, and dependency install are already complete per `docs/E_DRIVE_HANDOFF_20260614.md`. This R-P2A plan does not repeat migration, dependency install, commit, push, or old-directory cleanup; any future commit/push or destructive cleanup still requires explicit user confirmation.
