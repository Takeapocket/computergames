# R-P2A Recursive Star1 Upper-Bound Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ExpectimaxV2(chance_pruning="star1")` from root-only upper-bound pruning to recursive perspective-turn pruning without changing default behavior.

**Architecture:** Keep `chance_pruning="none"` as the default exact path. Reuse the existing `_chance_value_star1(..., cutoff_upper_bound=...)` implementation only when the current turn node belongs to `perspective` and already has an incumbent best score. Opponent/minimizing lower-bound pruning is deliberately out of scope for this slice because it needs a separate lower-bound cutoff API and equivalence tests.

**Tech Stack:** Python 3.11, pytest, existing `ExpectimaxV2`, `GameState.apply_move()/undo_move()`, and current score bounds.

---

### Task 1: Recursive Perspective-Turn Star1

**Files:**
- Modify: `ai/expectimax_v2.py`
- Test: `tests/test_expectimax_v2.py`

- [x] **Step 1: Write failing recursive pruning test**

Add a scripted test that calls `_turn_value_with_status()` on a perspective-owned turn node with multiple legal moves. The subclass should make the first candidate return `EXPECTIMAX_V2_MAX_SCORE` and later candidates return `EXPECTIMAX_V2_MIN_SCORE`, while recording how many dice outcomes each candidate evaluated.

Expected before implementation:

```text
chance_pruning="star1" evaluates all six dice outcomes for the losing recursive candidate, so the test fails.
```

Assertions:

```text
plain and star1 return the same value
plain.last_search_stats.chance_prunes == 0
star1.last_search_stats.chance_prunes > 0
at least one losing recursive candidate only evaluates dice [1]
state serialization is unchanged after the call
```

- [x] **Step 2: Pass incumbent upper bound inside perspective turn nodes**

Inside `ExpectimaxV2._turn_value_with_status()`:

```python
cutoff_upper_bound = None
if self.chance_pruning == "star1" and whose_turn is perspective and scores:
    cutoff_upper_bound = max(scores)
...
chance_kwargs = {...}
if cutoff_upper_bound is not None:
    chance_kwargs["cutoff_upper_bound"] = cutoff_upper_bound
value, child_complete = self._chance_value_with_status(state, **chance_kwargs)
```

Do not pass a cutoff for opponent/minimizing nodes.

- [x] **Step 3: Verify recursive test and existing Star1 tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py::test_expectimax_v2_star1_prunes_recursive_perspective_turn_candidates" "tests/test_expectimax_v2.py::test_expectimax_v2_star1_root_pruning_preserves_choice_and_skips_losing_candidate_dice" -q
```

Expected: pass.

### Task 2: Equivalence And Evidence

**Files:**
- Modify: `tests/test_expectimax_v2.py`
- Create/Modify: `reports/rp2a_recursive_star1_20260614.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Run R-P2A verification**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" -q
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax_v2.py" "tests/test_ai_basic.py::test_build_ai_expectimax_v2_registers_signature_fields" -q
```

- [x] **Step 2: Run full regression**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
git diff --check
```

- [x] **Step 3: Record scope and request Superpowers review**

Document:

```text
recursive perspective-turn Star1 only
opponent lower-bound pruning / Star2 not implemented
default chance_pruning remains none
verification outputs
no default AI / GUI / release / core semantic changes
```

Use `superpowers:requesting-code-review` after implementation. Fix Critical/Important findings before moving on.
