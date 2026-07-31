# R-P2A Minimizing Star1 Lower-Bound Pruning

Date: 2026-07-31

## Hypothesis And Stop Conditions

The existing Star1 upper-bound cutoff only pruned candidates at perspective/maximizing turn nodes. The symmetric lower-bound cutoff should skip dominated candidates at opponent/minimizing turn nodes without changing completed expectimax values or storing an incomplete bound as an exact transposition-table value.

Stop this change if Star1 disagrees with exact enumeration, mutates caller state, writes a pruned bound to the transposition table, or changes the default `chance_pruning="none"` behavior.

## Implementation

- `_turn_value_with_status()` passes `max(scores)` as the existing upper cutoff at perspective turns and `min(scores)` as a lower cutoff at opponent turns.
- `_chance_value_star1()` computes `min_possible = (observed_total + remaining * EXPECTIMAX_V2_MIN_SCORE) / 6.0`.
- It prunes only when `min_possible > cutoff_lower_bound`; strict comparison preserves equal-score candidates.
- Pruned results return `complete=False`, so neither the chance node nor its incomplete parent turn node is stored as an exact TT entry.

## Verification

- TDD RED: the new opponent-turn test failed because the Star1 chance path did not accept `cutoff_lower_bound`.
- Star1 upper/lower and TT targeted tests: `4 passed in 0.87s`.
- Code-review follow-up added a direct production `_chance_value_star1()` test for the lower-bound formula, strict equality behavior, prune count, and `complete=False` result.
- `tests/test_expectimax_v2.py` plus AI signature test after review: `37 passed in 2.05s`.
- Full `pytest -q` after review: `946 passed in 74.21s`.

## Boundaries

`chance_pruning="none"` remains the default. No default AI, GUI, release/v1.0, P14 rollout parameter, or core rule behavior changed. Star2 interval pruning and the exact endgame solver remain future R-P2A work.
