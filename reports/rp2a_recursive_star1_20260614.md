# R-P2A Recursive Star1 Upper-Bound Pruning

Date: 2026-06-14

## Scope

This slice extends `ExpectimaxV2(chance_pruning="star1")` from root-only upper-bound pruning to recursive perspective-turn pruning.

Only maximizing turn nodes owned by the search `perspective` pass an incumbent upper-bound cutoff into child chance nodes. Opponent/minimizing lower-bound pruning and Star2 remain out of scope.

Default behavior is unchanged because `chance_pruning="none"` remains the default.

## Implementation

Changed files:

```text
ai/expectimax_v2.py
tests/test_expectimax_v2.py
docs/superpowers/plans/2026-06-14-rp2a-recursive-star1-plan.md
```

`ExpectimaxV2._turn_value_with_status()` now passes `cutoff_upper_bound=max(scores)` to `_chance_value_with_status()` only when:

```text
self.chance_pruning == "star1"
whose_turn is perspective
scores is non-empty
```

The opponent/minimizing branch deliberately receives no cutoff in this slice.

## Verification

TDD red check:

```text
tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_perspective_turn_candidates failed before implementation because recursive star1 completed all dice outcomes and returned complete=True.
```

Targeted verification:

```text
tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_perspective_turn_candidates
tests/test_expectimax_v2.py::test_expectimax_v2_star1_root_pruning_preserves_choice_and_skips_losing_candidate_dice
2 passed in 0.80s
```

R-P2A verification:

```text
tests/test_expectimax_v2.py tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields: 34 passed in 2.13s
```

Full regression:

```text
pytest -q: 943 passed in 74.38s
```

Whitespace check:

```text
git diff --check: no whitespace errors; only existing LF/CRLF working-copy warnings in documentation files
```

## Non-Goals

```text
No Star2 implementation.
No opponent/minimizing lower-bound pruning.
No release/v1.0, GUI, P14 rollout, or core rule semantic changes.
No strength claim or promotion claim.
```
