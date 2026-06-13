# R-P2A Star1/Star2 Entry Gate

Date: 2026-06-13

## Scope

This report records the current Star1/Star2 entry-gate status for `ExpectimaxV2`.
It adds a default-off experimental entry point and a narrow root-level upper-bound
pruning slice. It does not implement full Star1/Star2 recursive pruning and does
not claim any playing-strength improvement.

## Completed Gate

Search value bounds are now explicit and mechanically enforced in `ai/expectimax_v2.py`:

```text
EXPECTIMAX_V2_MIN_SCORE = -WIN_SCORE
EXPECTIMAX_V2_MAX_SCORE = WIN_SCORE
expectimax_v2_require_score_in_bounds(...)
```

The checker is applied to the values used by the unpruned search path:

```text
leaf evaluator values
terminal win/loss values
no-move win/loss values
chance-node averages
turn-node min/max values
transposition-table cache hits
```

This makes any future evaluator change that escapes the declared range fail loudly instead of silently invalidating Star1/Star2 assumptions.

## Completed Equivalence Entry

`ExpectimaxV2` now exposes an explicit chance-node optimization mode:

```text
chance_pruning="none"   # default
chance_pruning="star1"  # conservative exact entry path
```

Without a cutoff, the `star1` path enumerates all six dice outcomes exactly and
records `last_search_stats.chance_prunes == 0`. This keeps the future Star1 work
behind a traceable flag while preserving default behavior.

## Completed Root-Level Pruning Slice

When `choose_move()` evaluates root candidate moves with `chance_pruning="star1"`,
the current best root score is passed into the chance node as a cutoff. After each
dice outcome, the chance node computes the best possible remaining average:

```text
(partial_total + remaining_dice * EXPECTIMAX_V2_MAX_SCORE) / 6
```

If that upper bound is strictly below the incumbent root score, the remaining
dice outcomes are skipped and `last_search_stats.chance_prunes` is incremented.
The comparison is strict `<`, so equal-score candidates are still fully evaluated
and normal tie fallback semantics are preserved. A pruned value is a safe bound,
not an exact chance-node value, so it is not stored as an exact TT entry.

## Verification

Targeted tests:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
```

Observed:

```text
31 passed in 1.93s
```

Targeted tests plus the `expectimax_v2` version-signature test:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields" -q
```

Observed:

```text
32 passed in 2.00s
```

Full regression:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Observed:

```text
913 passed in 73.30s
```

The new tests cover:

```text
explicit bounds checker accepts in-range values and rejects out-of-range values
leaf evaluator out-of-range values raise ValueError
small-depth unpruned expectimax values stay inside declared bounds
chance_pruning is explicit and disabled by default
unknown chance_pruning modes fail loudly
star1 chance path matches unpruned values at small depth
star1 choice matches unpruned choice on a fixed position and preserves caller state
star1 chance path actually prunes remaining dice when the upper bound cannot reach cutoff
star1 root pruning preserves the unpruned choice and caller state on a scripted position
ai_version_signature records chance_pruning
```

## Remaining Gate

Full Star1/Star2 pruning remains blocked until a future slice adds:

```text
recursive interval pruning beyond the root candidate chance node
tests that prove equality on positions where recursive pruning actually occurs
bench/perf evidence against the current P14 release default rollout kwargs
```

No `core/`, GUI, `release/v1.0/`, P14 rollout defaults, or default AI behavior changed in this slice.
