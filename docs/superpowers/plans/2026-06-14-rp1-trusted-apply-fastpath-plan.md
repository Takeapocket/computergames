# R-P1 Trusted Apply Fast Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a private `GameState` fast path for applying already-validated legal moves and use it in `RolloutAI` hot loops without changing public `apply_move()` validation semantics.

**Architecture:** Public `GameState.apply_move()` remains the only externally safe API and continues to validate dice, player, legality, and terminal state. A private `_apply_known_legal_move()` handles the shared mutation/undo bookkeeping for callers that already hold a legal `Move` from `legal_moves()`. `RolloutAI` uses the private path only after it has just cloned the state and already owns a root legal move or playout legal move.

**Tech Stack:** Python 3.11, pytest, existing `GameState`, `Move`, and `RolloutAI`.

---

### Task 1: Private Fast Path With State Equivalence

**Files:**
- Modify: `core/game_state.py`
- Test: `tests/test_game_state.py`

- [x] **Step 1: Write failing equivalence test**

Add this test to `tests/test_game_state.py`:

```python
def test_apply_known_legal_move_matches_public_apply_for_legal_capture():
    public_state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    trusted_state = make_state(red={1: Position(2, 2)}, blue={2: Position(3, 3)})
    public_move = next(
        move
        for move in public_state.legal_moves(Player.RED, 1)
        if move.to_pos == Position(3, 3)
    )
    trusted_move = next(
        move
        for move in trusted_state.legal_moves(Player.RED, 1)
        if move.to_pos == Position(3, 3)
    )

    public_applied = public_state.apply_move(public_move, dice=1)
    trusted_applied = trusted_state._apply_known_legal_move(trusted_move)

    assert trusted_state.serialize() == public_state.serialize()
    assert trusted_applied.to_dict() == public_applied.to_dict()
    public_state.undo_move()
    trusted_state.undo_move()
    assert trusted_state.serialize() == public_state.serialize()
```

- [x] **Step 2: Run red test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py::test_apply_known_legal_move_matches_public_apply_for_legal_capture" -q
```

Expected: fail with `AttributeError: 'GameState' object has no attribute '_apply_known_legal_move'`.

- [x] **Step 3: Implement shared mutation helper**

In `core/game_state.py`, move the mutation part of `apply_move()` into a private helper:

```python
def apply_move(self, move: Move, dice: int) -> Move:
    if self.get_winner() is not None:
        raise ValueError("game is already finished")
    if move.player is not self.current_player:
        raise ValueError("move player must match current player")

    matching_move = self._find_matching_legal_move(move, dice)
    return self._apply_known_legal_move(matching_move)

def _apply_known_legal_move(self, move: Move) -> Move:
    if self.get_winner() is not None:
        raise ValueError("game is already finished")
    if move.player is not self.current_player:
        raise ValueError("move player must match current player")

    piece = self.pieces[move.player][move.piece_id]

    if move.captured_piece is not None:
        captured = self.pieces[move.captured_piece.player][move.captured_piece.piece_id]
        captured.alive = False

    piece.position = move.to_pos
    self.history.append(move.copy())
    self.current_player = self.current_player.opponent
    return move.copy()
```

- [x] **Step 4: Run target test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py::test_apply_known_legal_move_matches_public_apply_for_legal_capture" -q
```

Expected: pass.

### Task 2: Rollout Uses Trusted Apply Only After Legal Enumeration

**Files:**
- Modify: `ai/rollout_ai.py`
- Test: `tests/test_rollout_ai.py`

- [x] **Step 1: Write fixed-seed behavior equivalence test**

Add this test to `tests/test_rollout_ai.py`:

```python
def test_rollout_ai_fixed_seed_behavior_characterization():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(0, 1), 3: Position(0, 2), 4: Position(1, 0), 5: Position(2, 0), 6: Position(3, 1)},
        blue={1: Position(4, 4), 2: Position(4, 3), 3: Position(4, 2), 4: Position(3, 4), 5: Position(2, 4), 6: Position(1, 3)},
        current_player=Player.RED,
    )
    before = state.serialize()
    ai = RolloutAI(
        rollouts_per_move=4,
        max_rollout_turns=8,
        max_step_time_ms=10_000.0,
        epsilon=0.15,
        playout_policy="greedy_risk",
        cutoff_eval="zweistein",
        rng=random.Random(2026),
    )

    move = ai.choose_move(state, 3)

    assert state.serialize() == before
    assert move.to_dict() == {
        "player": "red",
        "piece_id": 3,
        "from_pos": {"row": 0, "col": 2},
        "to_pos": {"row": 1, "col": 3},
        "is_capture": True,
        "captured_piece": {
            "player": "blue",
            "piece_id": 6,
            "position": {"row": 1, "col": 3},
            "alive": True,
        },
    }
    assert [stats.visits for stats in ai.last_root_stats] == [4, 4, 4]
    assert [stats.score for stats in ai.last_root_stats] == [0.5, 0.25, 1.0]
    assert abs(ai._rng.random() - 0.21872353393889177) < 1e-15
```

- [x] **Step 2: Run test before implementation**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_fixed_seed_behavior_characterization" -q
```

Expected: pass before implementation; this is a characterization test locking current fixed-seed behavior.

- [x] **Step 3: Replace trusted internal applications**

In `ai/rollout_ai.py`, replace only calls immediately following legal enumeration:

```python
sim._apply_known_legal_move(score.move)
...
state._apply_known_legal_move(move)
```

Do this in `RolloutAI._sample_move_score()`, `RolloutAI._playout()`, `RolloutPairedAI.choose_move()`, `RolloutPairedAI._playout_with_rng()`, and inherited helper paths that clone a state then apply an already-legal root move.

- [x] **Step 4: Run target tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py" "tests/test_rollout_ai.py" -q
```

Expected: all tests pass.

### Task 3: Measure and Document

**Files:**
- Modify: `reports/rp1_trusted_apply_fastpath_20260614.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Run perf probe before/after if no pre-change baseline exists in this session**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 1 --samples 8 --seed 62014 --output "reports/rp1_trusted_apply_fastpath_probe_20260614.json"
```

Expected: JSON report with `rollout_decision_probe.instrumentation.legal_moves_calls`, clone counts, and root visits/sec.

- [x] **Step 2: Run verification**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py" "tests/test_rollout_ai.py" -q
& ".venv/Scripts/python.exe" -m pytest -q
git diff --check
```

Expected: all tests pass; `git diff --check` reports no whitespace errors except existing line-ending warnings.

- [x] **Step 3: Request Superpowers code review**

Use `superpowers:requesting-code-review` after this task is complete. Fix Critical/Important findings before moving to another design item.
