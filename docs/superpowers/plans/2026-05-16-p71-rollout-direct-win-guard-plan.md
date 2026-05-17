# P7.1 Rollout Direct Win Guard Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Conditionally add an experimental `rollout_direct_win_guard` candidate that chooses an immediate winning move before delegating to the current release default rollout.

**Architecture:** Implement a wrapper AI in a new module. The wrapper owns a base rollout instance built from release default kwargs, uses existing `ai.tactical.find_winning_moves()` for the guard, and is only reachable through `build_ai("rollout_direct_win_guard")` and bench profiles. It must not affect GUI default recommender or release configuration.

**Tech Stack:** Python 3.11, pytest, existing `RolloutAI`, existing `ai.tactical.find_winning_moves`, existing `ai.match.build_ai`, existing `scripts/bench_ai.py`.

---

## Execution Gate

Execute this plan only when `reports/p7_rollout_failure_analysis_*.json` shows at least one clear `missed_direct_win` example and the example is reproducible with core legal moves. If the bucket is zero, stop this plan and record that P7.1 is not supported by P7.0 data.

## File Structure

- Create: `ai/direct_win_guard.py`
  - `DirectWinGuardAI` wrapper.
- Modify: `ai/match.py`
  - Add `build_ai("rollout_direct_win_guard")`.
  - Add signature support for `DirectWinGuardAI`.
- Modify: `scripts/bench_ai.py`
  - Add candidate and promotion profile entries for `rollout_direct_win_guard`.
- Create: `tests/test_direct_win_guard.py`
  - Unit tests for direct goal win, capture-all win, delegation, and legal move guarantee.
- Modify: `tests/test_ai_match.py`
  - Add build/signature tests.

## Task 1: Candidate Gate Check

**Files:**
- Read: `reports/p7_rollout_failure_analysis_20260516.json`

- [ ] **Step 1: Check whether P7.0 supports this candidate**

Run:

```powershell
& ".venv/Scripts/python.exe" -c "import json; p=json.load(open('reports/p7_rollout_failure_analysis_20260516.json', encoding='utf-8')); print(p['failure_buckets'].get('missed_direct_win', 0))"
```

Expected to proceed: output is an integer greater than `0`.

Expected to stop: output is `0`.

## Task 2: Wrapper Tests

**Files:**
- Create: `tests/test_direct_win_guard.py`
- Create later: `ai/direct_win_guard.py`

- [ ] **Step 1: Add failing wrapper tests**

Create `tests/test_direct_win_guard.py`:

```python
from __future__ import annotations

from core.game_state import GameState
from core.types import Player, Position


class DelegatingBase:
    name = "rollout"

    def __init__(self, move=None):
        self.move = move
        self.calls = 0

    def choose_move(self, state, dice):
        self.calls += 1
        return self.move or state.legal_moves(state.current_player, dice)[0]


def test_direct_win_guard_takes_goal_corner_win() -> None:
    from ai.direct_win_guard import DirectWinGuardAI

    state = GameState.from_layout(
        red={6: Position(3, 3)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    base = DelegatingBase()
    ai = DirectWinGuardAI(base=base)

    move = ai.choose_move(state, 6)

    state.apply_move(move, dice=6)
    assert state.get_winner() is Player.RED
    assert base.calls == 0


def test_direct_win_guard_takes_capture_all_win() -> None:
    from ai.direct_win_guard import DirectWinGuardAI

    state = GameState.from_layout(
        red={6: Position(2, 2)},
        blue={1: Position(3, 3)},
        current_player=Player.RED,
    )
    base = DelegatingBase()
    ai = DirectWinGuardAI(base=base)

    move = ai.choose_move(state, 6)

    assert move.captured_piece is not None
    state.apply_move(move, dice=6)
    assert state.get_winner() is Player.RED
    assert base.calls == 0


def test_direct_win_guard_delegates_without_direct_win() -> None:
    from ai.direct_win_guard import DirectWinGuardAI
    from ai.match import default_starting_state

    state = default_starting_state()
    expected = state.legal_moves(state.current_player, 6)[-1]
    base = DelegatingBase(move=expected)
    ai = DirectWinGuardAI(base=base)

    assert ai.choose_move(state, 6) == expected
    assert base.calls == 1


def test_direct_win_guard_returns_legal_move() -> None:
    from ai.direct_win_guard import DirectWinGuardAI
    from ai.match import default_starting_state

    state = default_starting_state()
    ai = DirectWinGuardAI(base=DelegatingBase())

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_direct_win_guard.py
```

Expected: FAIL because `ai.direct_win_guard` does not exist.

## Task 3: Implement Wrapper

**Files:**
- Create: `ai/direct_win_guard.py`

- [ ] **Step 1: Create `DirectWinGuardAI`**

Create `ai/direct_win_guard.py`:

```python
from __future__ import annotations

import random
from collections import Counter

from ai.tactical import find_winning_moves, pick_max_material


class DirectWinGuardAI:
    def __init__(self, *, base, rng=None, name: str = "rollout_direct_win_guard") -> None:
        self.base = base
        self.rng = rng if rng is not None else random.Random()
        self.name = name
        self.guard_name = "direct_win"
        self.fire_counts: Counter[str] = Counter()

    def choose_move(self, state, dice):
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None
        winning = find_winning_moves(state, dice, state.current_player)
        if winning:
            self.fire_counts["direct_win"] += 1
            return pick_max_material(winning, self.rng)
        self.fire_counts["delegate"] += 1
        move = self.base.choose_move(state, dice)
        if move in legal:
            return move
        self.fire_counts["base_illegal_fallback"] += 1
        return legal[0]
```

- [ ] **Step 2: Run wrapper tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_direct_win_guard.py
```

Expected: PASS.

## Task 4: Register Candidate in AI Factory and Signature

**Files:**
- Modify: `ai/match.py`
- Modify: `tests/test_ai_match.py`

- [ ] **Step 1: Add build/signature tests**

Append to `tests/test_ai_match.py`:

```python
def test_build_ai_rollout_direct_win_guard_wraps_release_rollout() -> None:
    ai = build_ai("rollout_direct_win_guard", seed=2026)

    assert ai.name == "rollout_direct_win_guard"
    assert ai.base.name == "rollout"


def test_ai_version_signature_records_direct_win_guard() -> None:
    ai = build_ai("rollout_direct_win_guard", seed=2026)

    signature = ai_version_signature(ai)

    assert signature["name"] == "rollout_direct_win_guard"
    assert signature["guard"] == "direct_win"
    assert signature["base"]["name"] == "rollout"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py::test_build_ai_rollout_direct_win_guard_wraps_release_rollout tests/test_ai_match.py::test_ai_version_signature_records_direct_win_guard
```

Expected: FAIL because the factory branch and signature branch are not registered.

- [ ] **Step 3: Add factory branch**

In `ai/match.py`, in `build_ai()` before `rollout_tactical`, add:

```python
    if kind == "rollout_direct_win_guard":
        from ai.direct_win_guard import DirectWinGuardAI
        from ai.rollout_ai import RolloutAI
        from scripts.bench_ai import RELEASE_DEFAULT_ROLLOUT_KWARGS

        base_rng = random.Random(seed)
        wrapper_seed = None if seed is None else (int(seed) ^ 0x9E3779B9)
        wrapper_rng = random.Random(wrapper_seed)
        base = RolloutAI(rng=base_rng, **_merged(RELEASE_DEFAULT_ROLLOUT_KWARGS))
        return DirectWinGuardAI(base=base, rng=wrapper_rng)
```

- [ ] **Step 4: Add signature branch**

In `ai_version_signature()`, import and handle `DirectWinGuardAI` before the generic signature:

```python
    from ai.direct_win_guard import DirectWinGuardAI
```

Add:

```python
    if isinstance(ai, DirectWinGuardAI):
        return {
            "name": ai.name,
            "guard": ai.guard_name,
            "base": ai_version_signature(ai.base),
        }
```

- [ ] **Step 5: Run build/signature tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py::test_build_ai_rollout_direct_win_guard_wraps_release_rollout tests/test_ai_match.py::test_ai_version_signature_records_direct_win_guard
```

Expected: PASS.

## Task 5: Register Bench Profile

**Files:**
- Modify: `scripts/bench_ai.py`
- Modify: `tests/test_bench_ai.py`

- [ ] **Step 1: Add bench profile test**

Append to `tests/test_bench_ai.py`:

```python
def test_rollout_direct_win_guard_candidate_profile_uses_release_default_opponent() -> None:
    profile = CANDIDATE_PROFILES["rollout_direct_win_guard"]["candidate"]

    assert profile["opponent"] == "rollout"
    assert profile["opponent_kwargs"] == RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert profile["games_per_side"] == 100
```

- [ ] **Step 2: Add profile entry**

In `scripts/bench_ai.py`, add to `CANDIDATE_PROFILES`:

```python
    "rollout_direct_win_guard": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
        },
    },
```

- [ ] **Step 3: Run bench profile test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_bench_ai.py::test_rollout_direct_win_guard_candidate_profile_uses_release_default_opponent
```

Expected: PASS.

## Task 6: Candidate Bench Report

**Files:**
- Generate: `reports/p71_candidate_rollout_direct_win_guard_20260516.json`
- Generate: `reports/p71_candidate_rollout_direct_win_guard_20260516.md`

- [ ] **Step 1: Run candidate bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_direct_win_guard --opponent rollout --stage candidate --games-per-side 100 --report-name p71_candidate_rollout_direct_win_guard_20260516
```

Expected: report files written. Candidate may pass or fail gates; either result is report-only.

## Task 7: P7.1 Verification

**Files:**
- Verify: `ai/direct_win_guard.py`
- Verify: `ai/match.py`
- Verify: `scripts/bench_ai.py`
- Verify: `tests/test_direct_win_guard.py`
- Verify: `tests/test_ai_match.py`
- Verify: `tests/test_bench_ai.py`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_direct_win_guard.py tests/test_ai_match.py tests/test_bench_ai.py
```

Expected: PASS.

- [ ] **Step 2: Run release consistency**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py
```

Expected: PASS, proving GUI/release default did not change.

## Self-Review

- Spec coverage: Covers P7.1 direct-win guard, wrapper signature, factory registration, bench profile, and report-only candidate bench.
- Placeholder scan: No placeholder tokens or deferred implementation points.
- Boundary check: Does not alter `DEFAULT_RECOMMENDER_KIND`, `DEFAULT_RECOMMENDER_KWARGS`, `release/v1.0/default_params.json`, or `release/v1.0/config.json`.
