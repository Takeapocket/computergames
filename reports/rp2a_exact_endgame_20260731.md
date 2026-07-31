# R-P2A Exact Endgame Solver

Date: 2026-07-31

## Finite-Game Basis

The solver uses the sum of Manhattan distances from every living piece to that
piece's target corner as a progress measure. Every orthogonal legal move reduces
the moved piece's distance by one; every diagonal move reduces it by two. A
capture removes an additional nonnegative distance. Progress therefore strictly
decreases after every move, so the reachable game graph is a finite DAG.

The initial RED test intentionally used Chebyshev distance and failed because a
single-axis move can leave Chebyshev distance unchanged when both axis gaps are
equal. The production invariant and plan were corrected to Manhattan distance
before the recursive solver was accepted.

## Value And Gate

- TT values are canonical RED win probabilities in `[0, 1]`.
- RED terminal = `1.0`; BLUE terminal = `0.0`.
- A chance node averages all six fair dice outcomes.
- A known-dice RED turn maximizes; a BLUE turn minimizes.
- There is no depth cutoff and no evaluator fallback.
- A public nonterminal entry is accepted when total living pieces are at most 3
  or total Manhattan progress is at most 6. Terminal states bypass the gate.
- An ineligible nonterminal raises `ValueError`; it is not silently approximated.

“Exact” means game-theoretic expectimax to a real winner under the current rules,
represented by deterministic floating-point averages rather than symbolic
rational arithmetic.

## Implementation

- Added `ai/endgame_solver.py` with stable history-independent chance/turn TT
  keys, progress/gate helpers, exact recursion, stats, and `ExactEndgameAI`.
- Recursive moves use `GameState._apply_known_legal_move()`, check strict progress,
  and always undo in `finally`.
- The TT is per public solve/decision and stores only fully computed values. There
  is no timeout or partial-result path inside this solver.
- Added experimental `build_ai("endgame_exact")` registration and exports.
- AI signatures record `max_total_pieces`, `max_total_distance`,
  `use_transposition_table`, and `randomize_ties`.
- Deterministic ties use the first legal move; randomized ties use the supplied
  seeded RNG.

No default AI, GUI, release/v1.0, P14 rollout parameter, or core rule behavior
changed.

## Verification

- One hand oracle has RED pieces 1 and 6 on the bottom row and BLUE's only piece
  one move from `(0, 0)`, yielding `P(RED)=3/6=0.5`.
- The nondegenerate review oracle replaces piece 6 with piece 4. RED then wins
  only for dice 1-2 and loses for dice 3-6, yielding `P(RED)=1/3` and
  `P(BLUE)=2/3`; this locks equal six-face averaging and perspective conversion.
- Known-dice multi-move oracles independently lock RED child values
  `[0, 0, 1] -> max=1` and BLUE child RED-values `[1, 1, 0] -> min=0`.
- Tests cover representative RED/BLUE moves, self/opponent capture progress,
  piece/distance gates, terminal bypass, perspective complement, TT on/off value
  equivalence, TT hits, repeatability, existing-history and recursive-exception
  restoration, unique exact win, deterministic/seeded ties, ineligible failure,
  AI signature, and a full near-end match.
- Focused solver/AI group: `21 passed in 0.81s`.
- Full `pytest -q`: `991 passed in 72.85s`.
- Diagnostics for `ai/endgame_solver.py`, `ai/match.py`, and `ai/__init__.py`: no
  findings.

Hand-oracle solve:

```text
progress=6
red_probability=0.3333333333333333
elapsed_ms=0.3669
nodes=25
chance_nodes=13
turn_nodes=12
tt_hits=3
tt_stores=14
table_size=14
caller_state_unchanged=True
```

Near-end `play_one_game()` smoke:

```text
winner=red
turns=1
illegal_moves=0
crashes=0
timeouts=0
average_step_time_ms=0.0430
max_step_time_ms=0.0430
```

`ExactEndgameAI` has no deadline or `max_step_time_ms`; `timeouts=0` above means
the harness had no configured step-time gate for this AI. It is not evidence of
budget enforcement.

## Reproduction

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_endgame_solver.py" "tests/test_ai_basic.py::test_build_ai_registers_exact_endgame_signature" -q
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" -c "import random,time; from ai.endgame_solver import ExactEndgameAI,ExactEndgameSolver,endgame_progress_measure; from ai.match import play_one_game; from core.game_state import GameState; from core.types import Player,Position; state=GameState.from_layout(red={1:Position(4,3),4:Position(4,0)},blue={1:Position(0,1)},current_player=Player.RED); before=state.serialize(); solver=ExactEndgameSolver(); start=time.perf_counter(); probability=solver.solve_win_probability(state,perspective=Player.RED); elapsed=(time.perf_counter()-start)*1000.0; print({'progress':endgame_progress_measure(state),'red_probability':probability,'elapsed_ms':elapsed,'stats':solver.last_search_stats,'table_size':solver.last_table_size,'state_unchanged':state.serialize()==before}); result=play_one_game(red_ai=ExactEndgameAI(rng=random.Random(1)),blue_ai=ExactEndgameAI(rng=random.Random(2)),dice_rng=random.Random(3),max_turns=10,starting_state=state); print({'winner':None if result.winner is None else result.winner.value,'turns':result.turns,'illegal_moves':result.illegal_moves,'crashes':result.crashes,'timeouts':result.timeouts,'avg_step_time_ms':result.avg_step_time_ms,'max_step_time_ms':result.max_step_time_ms})"
```

## Code Review

The independent review found no Critical issue and one Important test-coverage
gap: the original `0.5` forced-line oracle could not distinguish perspective,
min/max, or averaging mistakes. The `1/3` oracle, RED/BLUE multi-move turn
oracles, and recursive-exception restoration test close that gap. Focused and
full suites pass after the additions.

## Boundaries

This slice establishes the exact solver primitive and endgame-only AI. It is not
a full-game hybrid and does not claim speed or strength from one tiny position.
Promotion still requires persistent-ladder evidence against the P14 anchor.
Retrograde endgame databases remain explicitly out of scope.
