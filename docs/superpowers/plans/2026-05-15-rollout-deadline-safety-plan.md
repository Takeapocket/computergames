# Rollout Deadline Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable rollout deadline safety margin so P2 positive candidates stop crossing `max_step_time_ms` by sub-millisecond boundary overhead.

**Architecture:** `RolloutAI.deadline_safety_ms` defaults to `0.0`, preserving existing default `rollout` behavior. `choose_move()` computes an internal sampling budget of `max_step_time_ms - deadline_safety_ms`; `bench_ai.CANDIDATE_PROFILES` injects `deadline_safety_ms=30.0` only for `rollout_risk_playout` and `rollout_cutoff_eval` candidate/promotion runs.

**Tech Stack:** Python 3.11, pytest, existing `RolloutAI`, `ai.match.ai_version_signature`, and `scripts.bench_ai` profiles.

**Execution status:** Completed 2026-05-15. `rollout_cutoff_eval` met P2.5 survival criteria (`200` games, win rate `57.0%`, `timeouts=0`); `rollout_risk_playout` did not meet total timeout gate (`200` games, win rate `58.5%`, `timeouts=1`). No GUI/release default change.

---

## Files

- Modify: `ai/rollout_ai.py`
  - Add `deadline_safety_ms: float = 0.0`.
  - Compute internal deadline with `max(0.0, max_step_time_ms - deadline_safety_ms)`.
- Modify: `ai/match.py`
  - Include `deadline_safety_ms` in `ai_version_signature()`.
- Modify: `scripts/bench_ai.py`
  - Support profile-level `candidate_kwargs`.
  - Set `deadline_safety_ms=30.0` for `rollout_risk_playout` and `rollout_cutoff_eval` candidate/promotion profiles.
- Modify: `tests/test_rollout_ai.py`
  - Cover deadline safety budget.
- Modify: `tests/test_ai_basic.py`
  - Cover default signature and candidate profile behavior.
- Modify: `tests/test_bench_ai.py`
  - Cover profile default kwargs and CLI override merge.
- Modify docs after verification:
  - `PROJECT_MEMORY.md`
  - `PROJECT_PHASES.md`
  - `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md`

---

### Task 1: RolloutAI Safety Budget

**Files:**
- Modify: `tests/test_rollout_ai.py`
- Modify: `ai/rollout_ai.py`
- Modify: `ai/match.py`

- [x] **Step 1: Write failing tests**

Add:

```python
def test_rollout_ai_deadline_safety_ms_reduces_internal_deadline(monkeypatch):
    state = default_starting_state()
    seen_deadlines = []

    def fake_sample(score, **kwargs):
        seen_deadlines.append(kwargs["deadline"])
        score.record_cutoff(0.5)
        return False

    monkeypatch.setattr("ai.rollout_ai.time.perf_counter", lambda: 100.0)
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=100.0,
        deadline_safety_ms=30.0,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    ai.choose_move(state, 6)

    assert seen_deadlines
    assert all(deadline == 100.07 for deadline in seen_deadlines)
```

Add or extend an existing signature test:

```python
ai = build_ai("rollout", seed=1)
signature = ai_version_signature(ai)
assert ai.deadline_safety_ms == 0.0
assert signature["deadline_safety_ms"] == 0.0
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_deadline_safety_ms_reduces_internal_deadline" "tests/test_ai_basic.py::test_build_ai_rollout_default_keeps_flat_release_baseline" -q
```

Expected: FAIL because `deadline_safety_ms` is not accepted / not signed.

- [x] **Step 3: Implement minimal code**

In `RolloutAI.__init__()`:

```python
deadline_safety_ms: float = 0.0,
...
self.deadline_safety_ms = max(0.0, float(deadline_safety_ms))
```

In `choose_move()`:

```python
step_budget_ms = max(0.0, self.max_step_time_ms - self.deadline_safety_ms)
deadline = time.perf_counter() + step_budget_ms / 1000.0
```

In `ai_version_signature()` attr list:

```python
"deadline_safety_ms",
```

- [x] **Step 4: Run GREEN**

Run the same tests. Expected: PASS.

---

### Task 2: bench_ai Profile kwargs

**Files:**
- Modify: `tests/test_bench_ai.py`
- Modify: `scripts/bench_ai.py`

- [x] **Step 1: Write failing profile kwargs tests**

Add:

```python
def test_resolve_profile_sets_deadline_safety_for_p25_candidates():
    for kind in ("rollout_risk_playout", "rollout_cutoff_eval"):
        profile = bench_ai._resolve_profile(kind, "candidate")

        assert profile["candidate_kwargs"]["deadline_safety_ms"] == 30.0


def test_merge_profile_kwargs_keeps_cli_override():
    profile = {"candidate_kwargs": {"deadline_safety_ms": 30.0, "rollouts_per_move": 32}}
    explicit = {"deadline_safety_ms": 5.0}

    assert bench_ai._merge_profile_kwargs(profile, explicit) == {
        "deadline_safety_ms": 5.0,
        "rollouts_per_move": 32,
    }
```

- [x] **Step 2: Run RED**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_bench_ai.py::test_resolve_profile_sets_deadline_safety_for_p25_candidates" "tests/test_bench_ai.py::test_merge_profile_kwargs_keeps_cli_override" -q
```

Expected: FAIL because profile kwargs and merge helper are absent.

- [x] **Step 3: Implement profile kwargs**

In `scripts/bench_ai.py` add:

```python
def _merge_profile_kwargs(profile: dict, explicit_kwargs: dict) -> dict:
    return {**profile.get("candidate_kwargs", {}), **explicit_kwargs}
```

In `main()` after parsing candidate args:

```python
candidate_kwargs = _merge_profile_kwargs(profile, candidate_kwargs)
```

Set only these profiles:

```python
"rollout_risk_playout": {
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

Repeat for `rollout_cutoff_eval`. Do not add safety to `rollout_32`.

- [x] **Step 4: Run GREEN**

Run the two profile tests. Expected: PASS.

---

### Task 3: Verification And P2.5 Reports

**Files:**
- Reports:
  - `reports/p25_candidate_rollout_risk_playout_20260515.json`
  - `reports/p25_candidate_rollout_risk_playout_20260515.md`
  - `reports/p25_candidate_rollout_cutoff_eval_20260515.json`
  - `reports/p25_candidate_rollout_cutoff_eval_20260515.md`
- Docs listed above.

- [x] **Step 1: Run targeted tests**

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py" "tests/test_ai_basic.py" "tests/test_bench_ai.py" -q
```

- [x] **Step 2: Run no-save smoke bench for the two P2.5 candidates**

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_risk_playout --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_cutoff_eval --stage smoke --opponent greedy --games-per-side 1 --candidate-arg rollouts_per_move=1 --candidate-arg max_rollout_turns=1 --candidate-arg max_step_time_ms=50 --no-save-report
```

- [x] **Step 3: Run full pytest**

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

- [x] **Step 4: Run P2.5 candidate reports**

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_risk_playout --stage candidate --report-name p25_candidate_rollout_risk_playout_20260515
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_cutoff_eval --stage candidate --report-name p25_candidate_rollout_cutoff_eval_20260515
```

Survival condition:

```text
timeouts = 0
candidate_win_rate >= 55%
illegal_moves = 0
crashes = 0
```

- [x] **Step 5: Sync docs**

Record P2.5 result:

```text
P2.5 deadline safety added with default 0.0; P2.5 candidate profiles pass deadline_safety_ms=30.0 for risk/cutoff candidates only. No GUI/release default change. Survives only if timeout=0 and win rate >=55%.
```

- [x] **Step 6: Final self-check**

Confirm:

```text
No core rule changes.
No GUI default change.
No release/v1.0/default_params.json change.
rollout_32 not rerun.
P3 not started.
```
