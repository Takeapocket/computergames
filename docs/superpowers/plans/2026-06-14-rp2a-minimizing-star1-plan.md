# R-P2A Minimizing Star1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ExpectimaxV2(chance_pruning="star1")` from perspective/maximizing turn pruning to opponent/minimizing turn pruning without changing default search behavior.

**Architecture:** Keep the pruning entry in `_turn_value_with_status()`, because that method knows whether the turn node maximizes or minimizes from `perspective`. Extend `_chance_value_with_status()` / `_chance_value_star1()` with an optional lower-bound cutoff, and keep pruned chance results incomplete so they are never stored as exact TT values.

**Tech Stack:** Python, pytest, existing `ai/expectimax_v2.py` search internals.

---

### Task 1: Characterize Opponent/Minimizing Pruning

**Files:**
- Modify: `tests/test_expectimax_v2.py`

- [x] **Step 1: Write the failing test**

Add this test after `test_expectimax_v2_star1_prunes_recursive_perspective_turn_candidates`:

```python
def test_expectimax_v2_star1_prunes_recursive_opponent_turn_candidates():
    class ScriptedOpponentStar1Expectimax(ExpectimaxV2):
        def __init__(self, *, chance_pruning):
            super().__init__(
                depth=2,
                time_limit_ms=1000,
                randomize_ties=False,
                chance_pruning=chance_pruning,
            )
            self.dice_seen_by_to = {}
            self.preferred_to = None

        def _scripted_chance_value(
            self,
            state,
            *,
            cutoff_upper_bound=None,
            cutoff_lower_bound=None,
        ):
            assert cutoff_upper_bound is None
            root_to = state.history[-1].to_pos
            self.dice_seen_by_to.setdefault(root_to, [])
            total = 0.0
            for index, dice in enumerate(range(1, 7), start=1):
                self.dice_seen_by_to[root_to].append(dice)
                value = (
                    EXPECTIMAX_V2_MIN_SCORE
                    if root_to == self.preferred_to
                    else EXPECTIMAX_V2_MAX_SCORE
                )
                total += value
                remaining = 6 - index
                if cutoff_lower_bound is not None and remaining > 0:
                    min_possible = (total + remaining * EXPECTIMAX_V2_MIN_SCORE) / 6.0
                    if min_possible > cutoff_lower_bound:
                        self.last_search_stats.chance_prunes += remaining
                        return min_possible, False
            return total / 6.0, True

        def _chance_value_exact(self, state, *, perspective, depth, deadline, table):
            del perspective, depth, deadline, table
            return self._scripted_chance_value(state)

        def _chance_value_star1(
            self,
            state,
            *,
            perspective,
            depth,
            deadline,
            table,
            cutoff_upper_bound,
            cutoff_lower_bound,
        ):
            del perspective, depth, deadline, table
            return self._scripted_chance_value(
                state,
                cutoff_upper_bound=cutoff_upper_bound,
                cutoff_lower_bound=cutoff_lower_bound,
            )

    plain_state = _make_state(
        red={1: Position(2, 2)},
        blue={1: Position(2, 4)},
        current_player=Player.BLUE,
    )
    star1_state = _make_state(
        red={1: Position(2, 2)},
        blue={1: Position(2, 4)},
        current_player=Player.BLUE,
    )
    plain_before = plain_state.serialize()
    star1_before = star1_state.serialize()
    preferred_to = plain_state.legal_moves(Player.BLUE, 1)[0].to_pos
    plain = ScriptedOpponentStar1Expectimax(chance_pruning="none")
    star1 = ScriptedOpponentStar1Expectimax(chance_pruning="star1")
    plain.preferred_to = preferred_to
    star1.preferred_to = preferred_to

    plain_value, plain_complete = plain._turn_value_with_status(
        plain_state,
        dice=1,
        perspective=Player.RED,
        depth=2,
        deadline=10_000_000.0,
        table=None,
    )
    star1_value, star1_complete = star1._turn_value_with_status(
        star1_state,
        dice=1,
        perspective=Player.RED,
        depth=2,
        deadline=10_000_000.0,
        table=None,
    )

    assert plain_value == star1_value == EXPECTIMAX_V2_MIN_SCORE
    assert plain_complete is True
    assert star1_complete is False
    assert plain_state.serialize() == plain_before
    assert star1_state.serialize() == star1_before
    assert plain.last_search_stats.chance_prunes == 0
    assert star1.last_search_stats.chance_prunes > 0
    assert plain.dice_seen_by_to[preferred_to] == [1, 2, 3, 4, 5, 6]
    losing_to_positions = [to_pos for to_pos in plain.dice_seen_by_to if to_pos != preferred_to]
    assert losing_to_positions
    assert all(plain.dice_seen_by_to[to_pos] == [1, 2, 3, 4, 5, 6] for to_pos in losing_to_positions)
    assert any(star1.dice_seen_by_to[to_pos] == [1] for to_pos in losing_to_positions)
    assert star1.last_search_stats.timed_out is False
```

- [x] **Step 2: Run the targeted test to verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_opponent_turn_candidates" -q
```

Expected: fail because `_chance_value_star1()` does not pass `cutoff_lower_bound` and `_turn_value_with_status()` never supplies a lower-bound cutoff for opponent turn candidates.

### Task 2: Implement Lower-Bound Cutoff

**Files:**
- Modify: `ai/expectimax_v2.py`

- [x] **Step 1: Extend chance method signatures**

Update `_chance_value_with_status()` to accept `cutoff_lower_bound: float | None = None` beside `cutoff_upper_bound`.

Update `_chance_value_star1()` to require `cutoff_lower_bound: float | None`.

- [x] **Step 2: Pass minimizing incumbent from turn nodes**

In `_turn_value_with_status()`, keep the existing maximizing branch:

```python
if self.chance_pruning == "star1" and whose_turn is perspective and scores:
    chance_kwargs["cutoff_upper_bound"] = max(scores)
```

Add the minimizing branch:

```python
if self.chance_pruning == "star1" and whose_turn is not perspective and scores:
    chance_kwargs["cutoff_lower_bound"] = min(scores)
```

- [x] **Step 3: Add lower-bound pruning in `_chance_value_star1()`**

Inside the dice loop, after the existing upper-bound check, add:

```python
if (
    cutoff_lower_bound is not None
    and remaining > 0
    and not self.last_search_stats.timed_out
):
    min_possible = (total + remaining * EXPECTIMAX_V2_MIN_SCORE) / 6.0
    if min_possible > cutoff_lower_bound:
        self.last_search_stats.chance_prunes += remaining
        return (
            expectimax_v2_require_score_in_bounds(
                min_possible,
                context="chance-pruned-lower-bound",
            ),
            False,
        )
```

Keep the strict `>` comparison so equal values are not pruned.

- [x] **Step 4: Run the targeted test to verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_opponent_turn_candidates" -q
```

Expected: pass.

### Task 3: Regression Coverage and Documentation

**Files:**
- Modify: `tests/test_expectimax_v2.py`
- Create: `reports/rp2a_minimizing_star1_20260614.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Run existing Star1 regression group**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields" -q
```

Expected: all tests pass.

- [x] **Step 2: Run full test suite**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Expected: full suite passes.

- [x] **Step 3: Write the report**

Create `reports/rp2a_minimizing_star1_20260731.md` with:

```markdown
# R-P2A Minimizing Star1 Lower-Bound Pruning

Date: 2026-07-31

## Scope

`ExpectimaxV2(chance_pruning="star1")` now prunes recursive opponent/minimizing turn candidates using a lower-bound chance cutoff. The default remains `chance_pruning="none"`.

## Implementation

- Perspective/maximizing turn nodes keep the existing upper-bound cutoff.
- Opponent/minimizing turn nodes pass `min(scores)` as a lower-bound incumbent after at least one candidate has been evaluated.
- Chance nodes compute `min_possible = (observed_total + remaining * EXPECTIMAX_V2_MIN_SCORE) / 6.0` and prune only when `min_possible > cutoff_lower_bound`.
- Pruned chance values remain incomplete and are not stored as exact transposition-table entries.

## Verification

- `tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_opponent_turn_candidates`: PASS
- `tests/test_expectimax_v2.py` + signature test: PASS
- Full `pytest -q`: PASS

## Boundaries

No default AI, GUI, release/v1.0, P14 rollout parameter, or core rule behavior changed. Star2 interval pruning and terminal exact solver remain future work.
```

- [x] **Step 4: Update project status docs**

Append concise 2026-06-14 status bullets to `PROJECT_MEMORY.md` and `PROJECT_PHASES.md` noting:

- R-P2A minimizing Star1 lower-bound pruning completed.
- Default behavior unchanged.
- Targeted and full pytest results.
- Star2 / exact endgame solver still pending.

- [x] **Step 5: Check diff whitespace**

Run:

```powershell
git diff --check
```

Expected: no new whitespace errors. Existing LF/CRLF warnings are acceptable if unchanged.

### Task 4: Superpowers Code Review

**Files:**
- Review all changed files for this plan.

- [x] **Step 1: Request code review**

Use `superpowers:requesting-code-review` with a reviewer subagent. Provide:

- Description: R-P2A minimizing Star1 lower-bound pruning.
- Requirements: this plan file and the approved design doc.
- Diff scope: `ai/expectimax_v2.py`, `tests/test_expectimax_v2.py`, report/status docs.

- [x] **Step 2: Apply Critical/Important feedback**

Use `superpowers:receiving-code-review` before changing code. Fix Critical and Important issues before moving to the next design item. Minor documentation/test-intent suggestions may be fixed immediately if low-risk.

- [x] **Step 3: Re-run verification after fixes**

Run targeted tests touched by feedback, then full `pytest -q` if production code changed.
