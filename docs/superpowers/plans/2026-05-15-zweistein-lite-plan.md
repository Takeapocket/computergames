# Zweistein-Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested, zero-sum-ish Zweistein-lite evaluator and register safe experimental AI kinds that can enter harness evaluation without changing GUI/release defaults.

**Architecture:** Keep the evaluator in a new `ai/zweistein.py` module so the existing `ai.evaluator.evaluate()` contract remains stable. Add thin AI integrations: a dedicated greedy wrapper, a `RolloutAI` cutoff mode, and an `ExpectimaxAI` leaf-evaluator mode. Register bench profiles only for `rollout_zweistein_cutoff`.

**Tech Stack:** Python 3.11, pytest, existing `GameState`, `GreedyAI`-style one-ply selection, `RolloutAI`, `ExpectimaxAI`, `bench_ai.py`.

**Execution status:** Completed 2026-05-15. `rollout_zweistein_cutoff` candidate report passed (`200` games, win rate `58.0%`, `timeouts=0`). No GUI/release default change and no promotion/default claim.

---

## Files

- Create: `ai/zweistein.py`
  - Export `zweistein_lite_score(state, perspective)`.
  - Keep helper functions private: alive pieces, distance total, expected mobility.
- Create: `ai/zweistein_ai.py`
  - Export `ZweisteinGreedyAI` using `zweistein_lite_score`.
- Create: `tests/test_zweistein.py`
  - Cover terminal, progress, material, mobility, mirror, and sparse states.
- Modify: `ai/rollout_ai.py`
  - Allow `cutoff_eval="zweistein"`.
  - Map positive/negative/zero Zweistein scores to cutoff outcomes `1.0/0.0/0.5`.
- Modify: `ai/expectimax_ai.py`
  - Add `leaf_evaluator="current"|"zweistein"` and route leaf scoring through a helper.
- Modify: `ai/match.py`
  - Register `greedy_zweistein`, `rollout_zweistein_cutoff`, `expectimax_zweistein_d1`.
  - Include `leaf_evaluator` in `ai_version_signature()`.
- Modify: `scripts/bench_ai.py`
  - Add candidate/promotion profile for `rollout_zweistein_cutoff` with `deadline_safety_ms=30.0`.
- Modify: tests:
  - `tests/test_ai_basic.py`
  - `tests/test_rollout_ai.py`
  - `tests/test_expectimax.py`
  - `tests/test_bench_ai.py`
- Modify docs after verification:
  - `PROJECT_MEMORY.md`
  - `PROJECT_PHASES.md`
  - `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md`

---

### Task 1: Zweistein-Lite Evaluator

**Files:**
- Create: `tests/test_zweistein.py`
- Create: `ai/zweistein.py`

- [x] **Step 1: Write failing evaluator tests**

Add:

```python
import pytest

from ai.evaluator import WIN_SCORE
from ai.zweistein import zweistein_lite_score
from core.game_state import GameState
from core.types import Player, Position


def make_state(red=None, blue=None, current_player=Player.RED):
    return GameState.from_layout(red=red or {}, blue=blue or {}, current_player=current_player)


def mirror_state(state: GameState) -> GameState:
    red = {
        piece_id: Position(4 - piece.position.row, 4 - piece.position.col)
        for piece_id, piece in state.pieces[Player.BLUE].items()
        if piece.alive
    }
    blue = {
        piece_id: Position(4 - piece.position.row, 4 - piece.position.col)
        for piece_id, piece in state.pieces[Player.RED].items()
        if piece.alive
    }
    return GameState.from_layout(red=red, blue=blue, current_player=state.current_player.opponent)


def test_zweistein_terminal_scores_match_win_score():
    state = make_state(red={1: Position(4, 4)}, blue={1: Position(0, 0)})

    assert zweistein_lite_score(state, Player.RED) == WIN_SCORE
    assert zweistein_lite_score(state, Player.BLUE) == -WIN_SCORE


def test_zweistein_prefers_piece_closer_to_target():
    far = make_state(red={1: Position(0, 0)}, blue={1: Position(0, 4)})
    close = make_state(red={1: Position(3, 3)}, blue={1: Position(0, 4)})

    assert zweistein_lite_score(close, Player.RED) > zweistein_lite_score(far, Player.RED)


def test_zweistein_prefers_more_material():
    down_piece = make_state(red={1: Position(1, 1)}, blue={1: Position(3, 3), 2: Position(4, 2)})
    even_material = make_state(red={1: Position(1, 1), 2: Position(2, 1)}, blue={1: Position(3, 3), 2: Position(4, 2)})

    assert zweistein_lite_score(even_material, Player.RED) > zweistein_lite_score(down_piece, Player.RED)


def test_zweistein_mobility_breaks_distance_and_material_tie():
    blocked = make_state(
        red={1: Position(0, 0), 2: Position(0, 1), 3: Position(1, 0), 4: Position(1, 1)},
        blue={1: Position(4, 4), 2: Position(4, 3), 3: Position(3, 4), 4: Position(3, 3)},
    )
    mobile = make_state(
        red={1: Position(0, 0), 2: Position(0, 2), 3: Position(2, 0), 4: Position(2, 2)},
        blue={1: Position(4, 4), 2: Position(4, 2), 3: Position(2, 4), 4: Position(2, 2)},
    )

    assert zweistein_lite_score(mobile, Player.RED) > zweistein_lite_score(blocked, Player.RED)


def test_zweistein_red_blue_mirror_is_opposite():
    state = make_state(
        red={1: Position(1, 0), 2: Position(2, 1)},
        blue={1: Position(3, 4), 2: Position(2, 3)},
    )
    mirrored = mirror_state(state)

    assert zweistein_lite_score(state, Player.RED) == pytest.approx(
        -zweistein_lite_score(mirrored, Player.BLUE)
    )


def test_zweistein_sparse_states_do_not_crash():
    empty = make_state()
    single = make_state(red={1: Position(2, 2)})

    assert isinstance(zweistein_lite_score(empty, Player.RED), float)
    assert isinstance(zweistein_lite_score(single, Player.RED), float)
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein.py" -q
```

Expected: FAIL because `ai.zweistein` does not exist.

- [x] **Step 3: Implement minimal evaluator**

Create `ai/zweistein.py`:

```python
from __future__ import annotations

from ai.evaluator import WIN_SCORE
from ai.risk import distance_weighted_capture_risk, expected_target_win_risk
from core.game_state import GameState
from core.rules import target_corner
from core.types import Player, chebyshev_distance


PROGRESS_WEIGHT = 12.0
MATERIAL_WEIGHT = 90.0
MOBILITY_WEIGHT = 6.0
CAPTURE_RISK_WEIGHT = 120.0
TARGET_WIN_RISK_WEIGHT = 600.0


def zweistein_lite_score(state: GameState, perspective: Player) -> float:
    perspective = Player.from_value(perspective)
    winner = state.get_winner()
    if winner is perspective:
        return WIN_SCORE
    if winner is perspective.opponent:
        return -WIN_SCORE

    opponent = perspective.opponent
    return float(
        PROGRESS_WEIGHT * (_distance_total(state, opponent) - _distance_total(state, perspective))
        + MATERIAL_WEIGHT * (_alive_count(state, perspective) - _alive_count(state, opponent))
        + MOBILITY_WEIGHT * (_expected_mobility(state, perspective) - _expected_mobility(state, opponent))
        + CAPTURE_RISK_WEIGHT * (
            distance_weighted_capture_risk(state, opponent)
            - distance_weighted_capture_risk(state, perspective)
        )
        + TARGET_WIN_RISK_WEIGHT * (
            expected_target_win_risk(state, opponent)
            - expected_target_win_risk(state, perspective)
        )
    )


def _alive_count(state: GameState, player: Player) -> int:
    return sum(1 for piece in state.pieces[player].values() if piece.alive)


def _distance_total(state: GameState, player: Player) -> int:
    target = target_corner(player)
    return sum(
        chebyshev_distance(piece.position, target)
        for piece in state.pieces[player].values()
        if piece.alive
    )


def _expected_mobility(state: GameState, player: Player) -> float:
    return sum(len(state.legal_moves(player, dice)) for dice in range(1, 7)) / 6.0
```

- [x] **Step 4: Run GREEN**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein.py" -q
```

Expected: PASS.

---

### Task 2: Greedy And Factory Registration

**Files:**
- Create: `ai/zweistein_ai.py`
- Modify: `ai/match.py`
- Modify: `ai/__init__.py`
- Modify: `tests/test_ai_basic.py`

- [x] **Step 1: Write failing factory tests**

Add to `tests/test_ai_basic.py`:

```python
def test_build_ai_supports_zweistein_experimental_kinds():
    for kind in ("greedy_zweistein", "rollout_zweistein_cutoff", "expectimax_zweistein_d1"):
        ai = build_ai(kind, seed=2026)

        assert ai.name == kind
        assert hasattr(ai, "choose_move")


def test_build_ai_rollout_zweistein_cutoff_defaults_are_experimental():
    ai = build_ai("rollout_zweistein_cutoff", seed=1)
    signature = ai_version_signature(ai)

    assert ai.cutoff_eval == "zweistein"
    assert ai.playout_policy == "greedy_risk"
    assert ai.deadline_safety_ms == 0.0
    assert signature["cutoff_eval"] == "zweistein"


def test_build_ai_expectimax_zweistein_signature_records_leaf_evaluator():
    ai = build_ai("expectimax_zweistein_d1", seed=1)
    signature = ai_version_signature(ai)

    assert ai.depth == 1
    assert ai.leaf_evaluator == "zweistein"
    assert signature["leaf_evaluator"] == "zweistein"
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_ai_basic.py::test_build_ai_supports_zweistein_experimental_kinds" "tests/test_ai_basic.py::test_build_ai_rollout_zweistein_cutoff_defaults_are_experimental" "tests/test_ai_basic.py::test_build_ai_expectimax_zweistein_signature_records_leaf_evaluator" -q
```

Expected: FAIL because the kinds are not registered.

- [x] **Step 3: Add `ZweisteinGreedyAI`**

Create `ai/zweistein_ai.py`:

```python
from __future__ import annotations

import random

from ai.zweistein import zweistein_lite_score
from core.game_state import GameState
from core.move import Move


class ZweisteinGreedyAI:
    """One-ply greedy AI backed by the Zweistein-lite evaluator."""

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        name: str = "greedy_zweistein",
        randomize_ties: bool = True,
    ) -> None:
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = randomize_ties

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal_moves = state.legal_moves(state.current_player, dice)
        if not legal_moves:
            return None

        perspective = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []

        for move in legal_moves:
            applied = state.apply_move(move, dice=dice)
            try:
                score = zweistein_lite_score(state, perspective)
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        if self.randomize_ties:
            return self._rng.choice(best_moves)
        return best_moves[0]
```

In `ai/__init__.py`, import/export `ZweisteinGreedyAI`.

In `ai/match.py`, register:

```python
if kind == "greedy_zweistein":
    from ai.zweistein_ai import ZweisteinGreedyAI
    return ZweisteinGreedyAI(rng=rng, name="greedy_zweistein", **ai_kwargs)
```

Also add `rollout_zweistein_cutoff` and `expectimax_zweistein_d1` stubs after Task 3 and Task 4 implementation.

- [x] **Step 4: Run partial GREEN for greedy kind**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_ai_basic.py::test_build_ai_supports_zweistein_experimental_kinds" -q
```

Expected: still FAIL until rollout/expectimax registrations are implemented in later tasks.

---

### Task 3: Rollout Zweistein Cutoff

**Files:**
- Modify: `ai/rollout_ai.py`
- Modify: `ai/match.py`
- Modify: `scripts/bench_ai.py`
- Modify: `tests/test_rollout_ai.py`
- Modify: `tests/test_bench_ai.py`

- [x] **Step 1: Write failing rollout cutoff tests**

Add to `tests/test_rollout_ai.py`:

```python
def test_rollout_ai_cutoff_eval_zweistein_uses_zweistein_score(monkeypatch):
    state = default_starting_state()
    ai = RolloutAI(cutoff_eval="zweistein", rng=random.Random(1))

    monkeypatch.setattr("ai.rollout_ai.zweistein_lite_score", lambda state, perspective: 12.0)
    assert ai._cutoff_score(state, Player.RED) == 1.0

    monkeypatch.setattr("ai.rollout_ai.zweistein_lite_score", lambda state, perspective: -12.0)
    assert ai._cutoff_score(state, Player.RED) == 0.0

    monkeypatch.setattr("ai.rollout_ai.zweistein_lite_score", lambda state, perspective: 0.0)
    assert ai._cutoff_score(state, Player.RED) == 0.5
```

Add to `tests/test_bench_ai.py`:

```python
def test_resolve_profile_sets_deadline_safety_for_rollout_zweistein_cutoff():
    profile = bench_ai._resolve_profile("rollout_zweistein_cutoff", "candidate")

    assert profile["opponent"] == "rollout"
    assert profile["games_per_side"] == 100
    assert profile["candidate_kwargs"]["deadline_safety_ms"] == 30.0
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_cutoff_eval_zweistein_uses_zweistein_score" "tests/test_bench_ai.py::test_resolve_profile_sets_deadline_safety_for_rollout_zweistein_cutoff" -q
```

Expected: FAIL because `cutoff_eval="zweistein"` and profile are missing.

- [x] **Step 3: Implement rollout integration**

In `ai/rollout_ai.py`:

```python
from ai.zweistein import zweistein_lite_score
...
if cutoff_eval not in {"draw", "current", "zweistein"}:
    raise ValueError(...)
...
if self.cutoff_eval == "zweistein":
    value = zweistein_lite_score(state, perspective)
else:
    value = evaluate(state, perspective)
```

In `ai/match.py`:

```python
if kind == "rollout_zweistein_cutoff":
    from ai.rollout_ai import RolloutAI
    return RolloutAI(
        rng=rng,
        name="rollout_zweistein_cutoff",
        **_merged({
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.10,
            "playout_policy": "greedy_risk",
            "cutoff_eval": "zweistein",
        }),
    )
```

In `scripts/bench_ai.py`, add candidate/promotion profile:

```python
"rollout_zweistein_cutoff": {
    "candidate": {
        "opponent": "rollout",
        "games_per_side": 100,
        "candidate_kwargs": {"deadline_safety_ms": 30.0},
    },
    "promotion": {
        "opponent": "rollout",
        "games_per_side": 400,
        "candidate_kwargs": {"deadline_safety_ms": 30.0},
    },
},
```

- [x] **Step 4: Run GREEN**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_cutoff_eval_zweistein_uses_zweistein_score" "tests/test_bench_ai.py::test_resolve_profile_sets_deadline_safety_for_rollout_zweistein_cutoff" "tests/test_ai_basic.py::test_build_ai_rollout_zweistein_cutoff_defaults_are_experimental" -q
```

Expected: PASS for rollout-related tests.

---

### Task 4: Expectimax Zweistein Leaf

**Files:**
- Modify: `ai/expectimax_ai.py`
- Modify: `ai/match.py`
- Modify: `tests/test_expectimax.py`
- Modify: `tests/test_ai_basic.py`

- [x] **Step 1: Write failing Expectimax tests**

Add to `tests/test_expectimax.py`:

```python
def test_expectimax_leaf_evaluator_zweistein_uses_zweistein_score(monkeypatch):
    state = GameState.from_layout(
        red={1: Position(1, 1)},
        blue={1: Position(3, 3)},
        current_player=Player.RED,
    )
    ai = ExpectimaxAI(depth=0, leaf_evaluator="zweistein", rng=random.Random(1))

    monkeypatch.setattr("ai.expectimax_ai.zweistein_lite_score", lambda state, perspective: 123.0)

    assert ai._leaf_score(state, Player.RED) == 123.0
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax.py::test_expectimax_leaf_evaluator_zweistein_uses_zweistein_score" "tests/test_ai_basic.py::test_build_ai_expectimax_zweistein_signature_records_leaf_evaluator" -q
```

Expected: FAIL because `leaf_evaluator` and `_leaf_score` are missing.

- [x] **Step 3: Implement leaf evaluator routing**

In `ai/expectimax_ai.py`:

```python
from ai.zweistein import zweistein_lite_score
...
leaf_evaluator: str = "current",
...
if leaf_evaluator not in {"current", "zweistein"}:
    raise ValueError(f"unknown leaf_evaluator: {leaf_evaluator!r}")
self.leaf_evaluator = leaf_evaluator
...
def _leaf_score(self, state: GameState, perspective: Player) -> float:
    if self.leaf_evaluator == "zweistein":
        return zweistein_lite_score(state, perspective)
    return evaluate(state, perspective, **self._eval_kwargs)
```

Replace leaf `evaluate(...)` calls in `_expectimin()` and `_expectimax()` with `self._leaf_score(...)`.

In `ai/match.py`, register:

```python
if kind == "expectimax_zweistein_d1":
    from ai.expectimax_ai import ExpectimaxAI
    return ExpectimaxAI(
        rng=rng,
        name="expectimax_zweistein_d1",
        depth=1,
        leaf_evaluator="zweistein",
        **ai_kwargs,
    )
```

Add `"leaf_evaluator"` to `ai_version_signature()` attrs.

- [x] **Step 4: Run GREEN**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_expectimax.py::test_expectimax_leaf_evaluator_zweistein_uses_zweistein_score" "tests/test_ai_basic.py::test_build_ai_expectimax_zweistein_signature_records_leaf_evaluator" -q
```

Expected: PASS.

---

### Task 5: Integration Verification

**Files:**
- Modify docs listed above.
- Reports generated by smoke bench only unless candidate run is explicitly requested later.

- [x] **Step 1: Run P3 targeted tests**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein.py" "tests/test_ai_basic.py" "tests/test_rollout_ai.py" "tests/test_expectimax.py" "tests/test_bench_ai.py" -q
```

- [x] **Step 2: Run smoke bench for rollout_zweistein_cutoff**

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_zweistein_cutoff --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
```

- [x] **Step 3: Run full pytest**

- [x] **Step 3b: Run candidate bench for rollout_zweistein_cutoff**

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_zweistein_cutoff --stage candidate --report-name p3_candidate_rollout_zweistein_cutoff_20260515
```

Result: PASS, `candidate_win_rate=0.58`, `timeouts=0`.

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

- [x] **Step 4: Sync docs**

Record:

```text
P3 Zweistein-lite evaluator implemented as experimental AI infrastructure. No candidate/promotion/default change yet. `rollout_zweistein_cutoff` is registered for later candidate bench with deadline_safety_ms=30.0 in profile.
```

- [x] **Step 5: Final self-check**

Confirm:

```text
No core rule changes.
No GUI default change.
No release/v1.0/default_params.json change.
No P3 candidate report claimed unless candidate bench actually ran.
```
