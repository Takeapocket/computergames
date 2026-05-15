# Rollout Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register P2 rollout candidates (`rollout_32`, `rollout_risk_playout`, `rollout_cutoff_eval`) as stable benchable AI kinds, with playout-policy and cutoff-evaluator metadata captured in reports.

**Architecture:** Keep `rollout` release defaults unchanged. Extend `RolloutAI` with two explicit knobs: `playout_policy` (`greedy` or `greedy_risk`) and `cutoff_eval` (`draw` or `current`). Register named candidates in `build_ai()` and `bench_ai.py` profiles so candidate/promotion runs are reproducible without ad hoc kwargs.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing `ai.match`, `ai.rollout_ai`, and `scripts.bench_ai` harness.

---

## Files

- Modify: `ai/rollout_ai.py`
  - Add `playout_policy` and `cutoff_eval` constructor args.
  - Use `greedy_risk` policy in playout when requested.
  - Use current evaluator for non-terminal cutoff scoring when requested.
- Modify: `ai/match.py`
  - Register `rollout_32`, `rollout_risk_playout`, `rollout_cutoff_eval`.
  - Include `playout_policy` and `cutoff_eval` in `ai_version_signature()`.
- Modify: `scripts/bench_ai.py`
  - Add candidate/promotion profiles for the three rollout candidates.
- Modify: `tests/test_ai_basic.py`
  - Cover candidate factory defaults and signature metadata.
- Modify: `tests/test_rollout_ai.py`
  - Cover risk playout policy and cutoff evaluator behavior.
- Modify: `tests/test_bench_ai.py`
  - Cover default bench profiles.
- Modify docs after implementation:
  - `PROJECT_MEMORY.md`
  - `PROJECT_PHASES.md`
  - `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md`
- No changes to `core/`.
- No changes to `release/v1.0/default_params.json`.
- No `git commit`, `git push`, or branch operations.

---

### Task 1: Factory And Signature Registration

**Files:**
- Modify: `tests/test_ai_basic.py`
- Modify: `ai/match.py`

- [x] **Step 1: Write failing build_ai tests**

Add tests asserting:

```python
def test_build_ai_rollout_candidates_register_expected_defaults():
    cases = {
        "rollout_32": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.15,
            "playout_policy": "greedy",
            "cutoff_eval": "draw",
        },
        "rollout_risk_playout": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.10,
            "playout_policy": "greedy_risk",
            "cutoff_eval": "draw",
        },
        "rollout_cutoff_eval": {
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.10,
            "playout_policy": "greedy_risk",
            "cutoff_eval": "current",
        },
    }
    for kind, expected in cases.items():
        ai = build_ai(kind, seed=1)
        sig = ai_version_signature(ai)

        assert ai.name == kind
        for key, value in expected.items():
            assert getattr(ai, key) == value
            assert sig[key] == value


def test_build_ai_rollout_candidate_kwargs_can_override_defaults():
    ai = build_ai("rollout_32", seed=1, rollouts_per_move=2, max_step_time_ms=20)

    assert ai.rollouts_per_move == 2
    assert ai.max_step_time_ms == 20.0
```

- [x] **Step 2: Run RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_ai_basic.py::test_build_ai_rollout_candidates_register_expected_defaults" "tests/test_ai_basic.py::test_build_ai_rollout_candidate_kwargs_can_override_defaults" -q
```

Expected: FAIL with `ValueError: unknown AI`.

- [x] **Step 3: Implement factory defaults and signature fields**

In `ai/match.py`, add a small local helper inside `build_ai()`:

```python
def _merged(defaults: dict[str, Any]) -> dict[str, Any]:
    return {**defaults, **ai_kwargs}
```

Add candidate branches before `expectimax`:

```python
if kind == "rollout_32":
    from ai.rollout_ai import RolloutAI
    return RolloutAI(
        rng=rng,
        name="rollout_32",
        **_merged({
            "rollouts_per_move": 32,
            "max_rollout_turns": 80,
            "max_step_time_ms": 750.0,
            "epsilon": 0.15,
            "playout_policy": "greedy",
            "cutoff_eval": "draw",
        }),
    )
```

Repeat for `rollout_risk_playout` and `rollout_cutoff_eval` with spec defaults.

In `ai_version_signature()`, add:

```python
"playout_policy",
"cutoff_eval",
```

- [x] **Step 4: Run GREEN**

Run the same two tests. Expected: PASS.

---

### Task 2: RolloutAI Playout Policy And Cutoff Eval

**Files:**
- Modify: `tests/test_rollout_ai.py`
- Modify: `ai/rollout_ai.py`

- [x] **Step 1: Write failing playout policy test**

Add a test that monkeypatches `ai.rollout_ai.GreedyAI` and directly calls `_playout()`:

```python
def test_rollout_ai_risk_playout_policy_uses_greedy_risk_weights(monkeypatch):
    captured = []

    class FakeGreedy:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def choose_move(self, state, dice):
            legal = state.legal_moves(state.current_player, dice)
            return legal[0] if legal else None

    monkeypatch.setattr("ai.rollout_ai.GreedyAI", FakeGreedy)
    state = default_starting_state()
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=1,
        max_step_time_ms=1000,
        epsilon=0.0,
        playout_policy="greedy_risk",
        rng=random.Random(1),
    )

    ai._playout(state, deadline=10**9)

    assert captured
    assert captured[0]["expected_risk_weight"] > 0
    assert captured[0]["expected_win_risk_weight"] > captured[0]["expected_risk_weight"]
```

- [x] **Step 2: Write failing cutoff evaluator test**

Add a test proving non-terminal cutoffs use `evaluate()` instead of fixed 0.5:

```python
def test_rollout_ai_current_cutoff_eval_scores_non_terminal_leaf(monkeypatch):
    state = GameState.from_layout(
        red={1: Position(0, 0), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )

    def fake_evaluate(sim, perspective):
        red_five = sim.pieces[Player.RED][5].position
        return 10.0 if red_five == Position(3, 1) else -10.0

    monkeypatch.setattr("ai.rollout_ai.evaluate", fake_evaluate)
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        cutoff_eval="current",
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 5)

    assert move.to_pos == Position(3, 1)
    assert any(stats.cutoffs == 1 for stats in ai.last_root_stats)
    assert any(stats.score == 1.0 for stats in ai.last_root_stats)
```

- [x] **Step 3: Run RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_risk_playout_policy_uses_greedy_risk_weights" "tests/test_rollout_ai.py::test_rollout_ai_current_cutoff_eval_scores_non_terminal_leaf" -q
```

Expected: FAIL because `RolloutAI` does not accept `playout_policy` or `cutoff_eval`.

- [x] **Step 4: Implement minimal RolloutAI extension**

In `ai/rollout_ai.py`:

```python
from ai.evaluator import (
    EXPECTED_RISK_WEIGHT,
    EXPECTED_WIN_RISK_WEIGHT,
    evaluate,
)
```

Add constructor args:

```python
playout_policy: str = "greedy",
cutoff_eval: str = "draw",
```

Validate:

```python
if playout_policy not in {"greedy", "greedy_risk"}:
    raise ValueError(f"unknown playout_policy: {playout_policy!r}")
if cutoff_eval not in {"draw", "current"}:
    raise ValueError(f"unknown cutoff_eval: {cutoff_eval!r}")
self.playout_policy = playout_policy
self.cutoff_eval = cutoff_eval
```

Change `_playout()` policy construction:

```python
policy_kwargs = {"rng": random.Random(self._rng.randrange(2**31)), "name": "rollout_policy"}
if self.playout_policy == "greedy_risk":
    policy_kwargs["expected_risk_weight"] = EXPECTED_RISK_WEIGHT
    policy_kwargs["expected_win_risk_weight"] = EXPECTED_WIN_RISK_WEIGHT
policy = GreedyAI(**policy_kwargs)
```

Change `_sample_move_score()` when `winner is None`:

```python
elif winner is None:
    score.record_cutoff(self._cutoff_score(sim, perspective))
```

Add `_cutoff_score()`:

```python
def _cutoff_score(self, state: GameState, perspective: Player) -> float:
    if self.cutoff_eval == "draw":
        return 0.5
    value = evaluate(state, perspective)
    if value > 0:
        return 1.0
    if value < 0:
        return 0.0
    return 0.5
```

Update `_RolloutMoveScore` to store explicit `losses`, `draws`, and `cutoffs` so `visits == wins + losses + draws` remains true while `cutoffs` reports non-terminal leaf count.

- [x] **Step 5: Run GREEN**

Run the two new rollout tests. Expected: PASS.

---

### Task 3: Bench Profiles

**Files:**
- Modify: `tests/test_bench_ai.py`
- Modify: `scripts/bench_ai.py`

- [x] **Step 1: Write failing profile tests**

Add:

```python
def test_resolve_profile_returns_defaults_for_p2_rollout_candidates():
    for kind in ("rollout_32", "rollout_risk_playout", "rollout_cutoff_eval"):
        candidate = bench_ai._resolve_profile(kind, "candidate")
        promotion = bench_ai._resolve_profile(kind, "promotion")

        assert candidate["opponent"] == "rollout"
        assert candidate["games_per_side"] == 100
        assert promotion["opponent"] == "rollout"
        assert promotion["games_per_side"] == 400
```

- [x] **Step 2: Run RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_bench_ai.py::test_resolve_profile_returns_defaults_for_p2_rollout_candidates" -q
```

Expected: FAIL because profiles are absent.

- [x] **Step 3: Implement profiles**

In `scripts/bench_ai.py`, add the three candidates:

```python
"rollout_32": {
    "candidate": {"opponent": "rollout", "games_per_side": 100},
    "promotion": {"opponent": "rollout", "games_per_side": 400},
},
```

Repeat for `rollout_risk_playout` and `rollout_cutoff_eval`.

- [x] **Step 4: Run GREEN**

Run the profile test. Expected: PASS.

---

### Task 4: Verification, Smoke Bench, And Docs

**Files:**
- Modify docs listed above.

- [x] **Step 1: Run targeted tests**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_ai_basic.py" "tests/test_rollout_ai.py" "tests/test_bench_ai.py" -q
```

- [x] **Step 2: Run no-save smoke bench for each candidate**

Use tiny smoke settings to validate construction and report metadata without writing reports:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_32 --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_risk_playout --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_cutoff_eval --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
```

- [x] **Step 3: Run full pytest**

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

- [x] **Step 4: Optional P2 candidate reports**

Only after tests and smoke pass, run candidate reports if runtime is acceptable:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_32 --opponent rollout --games-per-side 100 --stage candidate
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_risk_playout --opponent rollout --games-per-side 100 --stage candidate
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_cutoff_eval --opponent rollout --games-per-side 100 --stage candidate
```

If runtime is too high for the current turn, record that implementation is ready and candidate reports remain the next action.

- [x] **Step 5: Sync docs**

Record:

```text
P2 implementation registered rollout_32 / rollout_risk_playout / rollout_cutoff_eval as benchable kinds. Default rollout and release/v1.0/default_params.json unchanged. Candidate reports either generated under reports/ or explicitly left as next action.
```

Update `PROJECT_MEMORY.md`, `PROJECT_PHASES.md`, and the P2 section in the roadmap spec.

- [x] **Step 6: Final self-check**

Confirm:

```text
No core rule changes.
No release default parameter changes.
No GUI default AI change.
No git commit/push.
ai_version_signature includes playout_policy and cutoff_eval.
bench_ai profiles provide candidate=100/side and promotion=400/side.
```
