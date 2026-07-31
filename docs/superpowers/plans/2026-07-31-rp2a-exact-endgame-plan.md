# R-P2A Exact Endgame Solver Implementation Plan

**Goal:** Add a standalone, opt-in exact endgame solver and `endgame_exact` AI
for small-piece or near-terminal positions. The solver performs untruncated
expectimax to a real winner, caches exact values in a transposition table, and
never changes the default ExpectimaxV2, GUI, release/v1.0, or P14 rollout path.

**Finite-Game Invariant:** Define progress as the sum, over all living pieces,
of Manhattan distance to that piece's target corner. Every legal RED move
increases row and/or column toward `(4, 4)`; every legal BLUE move decreases row
and/or column toward `(0, 0)`. An orthogonal move lowers the moved piece's
distance by one and a diagonal move lowers it by two; a capture removes an
additional nonnegative distance. Therefore every move strictly decreases
progress and the reachable game graph is a finite DAG.

**Value Semantics:** Cache canonical RED win probability in `[0, 1]`. A terminal
RED win is `1.0`, a terminal BLUE win is `0.0`; chance nodes average six fair dice
outcomes; RED turn nodes maximize and BLUE turn nodes minimize. “Exact” means no
depth/evaluator cutoff under these game rules, represented with deterministic
floating-point averages rather than symbolic rational arithmetic.

**Architecture:** Create `ai/endgame_solver.py` with stable history-independent
state/TT keys, `endgame_progress_measure()`, an eligibility gate, exact chance and
known-dice turn recursion, per-search TT/stats, and `ExactEndgameAI`. Public solve
and choose entry points accept terminal states or states satisfying
`alive_pieces <= max_total_pieces OR progress <= max_total_distance`; defaults are
3 pieces and distance 6. An ineligible nonterminal raises a clear `ValueError`;
there is no hidden heuristic fallback. Recursive moves use the core known-legal
fast path, verify strict progress, and always undo.

**Stop Conditions:** Stop or revert if the hand-computed race oracle is wrong,
RED/BLUE probabilities are not complementary, a move fails the strict-progress
check, caller state/history changes, an ineligible state silently runs/falls
back, TT changes a value, dice outcomes are not equally averaged, or default AI
and release behavior changes.

---

### Task 1: Lock The Mathematical Contract With RED Tests

**Files:**
- Create: `tests/test_endgame_solver.py`

- [x] Add progress-measure tests proving every legal move in representative RED,
  BLUE, self-capture, and opponent-capture positions strictly decreases it.
- [x] Add eligibility boundary tests for piece-count, near-terminal distance,
  terminal bypass, and rejected midgame states.
- [x] Add a hand-computed oracle: RED pieces 1/6 on the bottom row and BLUE's
  sole piece one step from its target yield RED win probability `3/6` when RED
  is to roll.
- [x] Add terminal and perspective-complement tests.
- [x] Run tests and verify RED because the solver module does not exist.

### Task 2: Implement Untruncated Exact Expectimax And TT

**Files:**
- Create: `ai/endgame_solver.py`
- Modify: `tests/test_endgame_solver.py`

- [x] Implement stable chance/turn TT keys with canonical RED probability.
- [x] Implement exact chance recursion over dice 1-6 and exact turn recursion
  using RED max / BLUE min.
- [x] Handle terminal and defensive no-move states without an evaluator.
- [x] Use `_apply_known_legal_move()`, verify progress decreases, and always undo.
- [x] Cache only fully computed exact values and expose nodes/hits/stores plus
  chance/turn counts in per-search stats.
- [x] Prove TT on/off value equivalence, actual TT hits, deterministic repeated
  solves, and caller-state/history restoration.
- [x] Run Task 1-2 tests and verify GREEN.

### Task 3: Add The Experimental AI And Reproducible Signature

**Files:**
- Modify: `ai/endgame_solver.py`
- Modify: `ai/match.py`
- Modify: `ai/__init__.py`
- Modify: `tests/test_endgame_solver.py`
- Modify: `tests/test_ai_basic.py`

- [x] Add `ExactEndgameAI.choose_move()` with first-legal deterministic ties by
  default and optional seeded random tie breaking.
- [x] Prove it selects a direct exact win, restores caller state, and rejects an
  ineligible nonterminal before search.
- [x] Register `build_ai("endgame_exact")`, export the class, and record
  `max_total_pieces`, `max_total_distance`, `randomize_ties`, and TT mode in
  `ai_version_signature()`.
- [x] Add a small endgame `play_one_game()` smoke with 0 illegal/crash outcomes.
- [x] Run focused solver/AI tests and full `pytest -q`; check diagnostics.

### Task 4: Evidence And Status Sync

**Files:**
- Create: `reports/rp2a_exact_endgame_20260731.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`
- Modify: `docs/superpowers/plans/2026-06-13-rp2a-expectimax-v2-plan.md`

- [x] Record the finite-DAG proof, value semantics, gate, exact oracle, TT stats,
  match smoke, exact commands, and absence of a speed/strength claim.
- [x] Mark R-P2A E3 complete while keeping retrograde databases explicitly out
  of scope and preserving all defaults.
- [x] Run `git diff --check`.

### Task 5: Independent Code Review

- [x] Request a read-only reviewer focused on the finite-progress proof, dice and
  min/max semantics, canonical perspective conversion, TT key completeness,
  state restoration, eligibility/failure behavior, and oracle independence.
- [x] Fix every Critical/Important finding and rerun affected tests plus full
  pytest whenever production code changes.
- [x] Obtain review confirmation that all blockers are closed.
