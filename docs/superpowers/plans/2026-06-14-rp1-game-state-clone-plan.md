# R-P1 GameState Clone Fast Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rollout hot-loop `GameState.serialize()` / `GameState.deserialize()` cloning with a behavior-equivalent in-memory `GameState.clone()` path.

**Architecture:** Public serialization remains unchanged for record/replay compatibility. `GameState.clone()` becomes a normal in-process deep copy API using existing `Piece.copy()` and `Move.copy()`. Rollout code uses `clone(include_history=False)` because playout simulations do not call `undo_move()` or inspect historical moves; fixed-seed characterization tests guard move choice, root stats, caller-state immutability, and RNG progression.

**Tech Stack:** Python 3.11, pytest, existing `GameState`, `Piece.copy()`, `Move.copy()`, `RolloutAI`, `RolloutPairedAI`, and `scripts/perf_probe.py`.

---

### Task 1: Exact `GameState.clone()` API

**Files:**
- Modify: `core/game_state.py`
- Test: `tests/test_game_state.py`

- [x] **Step 1: Write failing clone equivalence tests**

Add tests that prove:

```text
clone(include_history=True).serialize() == state.serialize()
clone(include_history=False).serialize(include_history=False) == state.serialize(include_history=False)
clone(include_history=False).history == []
mutating clone does not mutate original
```

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py::test_clone_matches_serialize_round_trip_and_is_independent" "tests/test_game_state.py::test_clone_can_omit_history_for_rollout_simulations" -q
```

Expected before implementation: fail with `AttributeError: 'GameState' object has no attribute 'clone'`.

- [x] **Step 2: Implement minimal clone**

Add this method to `GameState`:

```python
def clone(self, *, include_history: bool = True) -> "GameState":
    pieces = {
        player: {
            piece_id: piece.copy()
            for piece_id, piece in player_pieces.items()
        }
        for player, player_pieces in self.pieces.items()
    }
    history = [move.copy() for move in self.history] if include_history else []
    return GameState(
        pieces=pieces,
        current_player=self.current_player,
        history=history,
    )
```

- [x] **Step 3: Verify clone tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py::test_clone_matches_serialize_round_trip_and_is_independent" "tests/test_game_state.py::test_clone_can_omit_history_for_rollout_simulations" -q
```

Expected: pass.

### Task 2: Rollout Hot Path Uses Clone

**Files:**
- Modify: `ai/rollout_ai.py`
- Test: `tests/test_rollout_ai.py`

- [x] **Step 1: Strengthen fixed-seed characterization**

Use the existing `test_rollout_ai_fixed_seed_behavior_characterization` and add an equivalent `RolloutPairedAI` fixed-seed characterization if missing. The assertions must cover selected move, caller-state serialization, root visits/scores, and RNG progression.

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_fixed_seed_behavior_characterization" "tests/test_rollout_paired.py" -q
```

Expected before implementation: pass. This is a characterization baseline.

- [x] **Step 2: Replace serialize/deserialize clones in rollout hot loops**

Change only clone sites that immediately apply an already legal root move:

```python
sim = state.clone(include_history=False)
sim._apply_known_legal_move(score.move)
```

Apply in:

```text
RolloutAI._sample_move_score()
RolloutPairedAI.choose_move()
```

Do not change RNG construction, playout policy construction, scoring, tie handling, or public defaults.

- [x] **Step 3: Verify rollout behavior**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py" "tests/test_rollout_paired.py" -q
```

Expected: pass.

### Task 3: Perf Evidence And Review

**Files:**
- Modify/Create: `reports/rp1_game_state_clone_fastpath_20260614.md`
- Modify/Create: `reports/rp1_game_state_clone_fastpath_probe_20260614.json`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Run targeted and full verification**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py" "tests/test_rollout_ai.py" "tests/test_rollout_paired.py" "tests/test_perf_probe.py" -q
& ".venv/Scripts/python.exe" -m pytest -q
git diff --check
```

- [x] **Step 2: Run perf probe**

Run:

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 1 --samples 8 --seed 62014 --output "reports/rp1_game_state_clone_fastpath_probe_20260614.json"
```

Expected: JSON report with rollout decision instrumentation. Do not claim a speedup unless a same-parameter pre-change baseline is preserved in this plan.

- [x] **Step 3: Document and request Superpowers review**

Record:

```text
scope
files changed
verification output
perf probe output
explicit non-goals: no default AI/release/core rule semantic changes
```

Use `superpowers:requesting-code-review` after this task is complete. Fix Critical/Important findings before moving to another design item.
