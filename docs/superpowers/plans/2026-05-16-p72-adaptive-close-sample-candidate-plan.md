# P7.2 Adaptive Close-Sample Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Conditionally register an experimental `rollout_adaptive_close_sample` profile that keeps current release rollout kwargs and only tightens close-sample parameters.

**Architecture:** Do not add a new AI class. Register a factory branch in `build_ai()` that constructs `RolloutAI` with release default kwargs plus three explicit close-sample overrides. Register a bench profile using current release default rollout kwargs as opponent. The candidate remains report-only and cannot become GUI/release default without a separate user-approved phase.

**Tech Stack:** Python 3.11, pytest, existing `RolloutAI`, existing `ai.match.build_ai`, existing `scripts/bench_ai.py`, existing P6.4 timing probe report.

---

## Execution Gate

Execute this plan only when both conditions are true:

1. `reports/p7_rollout_failure_analysis_*.json` shows failures concentrated in `low_confidence_loss` or close root score examples.
2. `reports/p6_timing_budget_probe_*.json` shows `p99_ms <= 1000.0` and `max_ms <= 5000.0`.

If either condition fails, stop this plan and record that P7.2 is not supported by current evidence.

## File Structure

- Modify: `ai/match.py`
  - Add `build_ai("rollout_adaptive_close_sample")`.
- Modify: `scripts/bench_ai.py`
  - Add candidate and promotion profile entries for `rollout_adaptive_close_sample`.
- Modify: `tests/test_ai_match.py`
  - Add build/signature tests.
- Modify: `tests/test_bench_ai.py`
  - Add profile tests.

## Task 1: Evidence Gate Check

**Files:**
- Read: `reports/p6_timing_budget_probe_20260516.json`
- Read: `reports/p7_rollout_failure_analysis_20260516.json`

- [ ] **Step 1: Check timing budget**

Run:

```powershell
& ".venv/Scripts/python.exe" -c "import json; p=json.load(open('reports/p6_timing_budget_probe_20260516.json', encoding='utf-8')); print(p['p99_ms'], p['max_ms'])"
```

Expected to proceed: first value `<= 1000.0`, second value `<= 5000.0`.

- [ ] **Step 2: Check low-confidence signal**

Run:

```powershell
& ".venv/Scripts/python.exe" -c "import json; p=json.load(open('reports/p7_rollout_failure_analysis_20260516.json', encoding='utf-8')); print(p['failure_buckets'].get('low_confidence_loss', 0))"
```

Expected to proceed: output is an integer greater than `0`.

## Task 2: Factory and Signature Tests

**Files:**
- Modify: `tests/test_ai_match.py`
- Modify later: `ai/match.py`

- [ ] **Step 1: Add failing factory tests**

Append to `tests/test_ai_match.py`:

```python
def test_build_ai_rollout_adaptive_close_sample_overrides_only_close_sampling() -> None:
    ai = build_ai("rollout_adaptive_close_sample", seed=2026)

    assert ai.name == "rollout_adaptive_close_sample"
    assert ai.rollouts_per_move == 32
    assert ai.max_rollout_turns == 80
    assert ai.max_step_time_ms == 750.0
    assert ai.epsilon == 0.1
    assert ai.playout_policy == "greedy_risk"
    assert ai.cutoff_eval == "zweistein"
    assert ai.deadline_safety_ms == 30.0
    assert ai.close_sample_margin == 0.06
    assert ai.close_sample_rollouts_per_move == 64
    assert ai.low_confidence_margin == 0.06


def test_ai_version_signature_records_rollout_adaptive_close_sample() -> None:
    ai = build_ai("rollout_adaptive_close_sample", seed=2026)

    signature = ai_version_signature(ai)

    assert signature["name"] == "rollout_adaptive_close_sample"
    assert signature["close_sample_margin"] == 0.06
    assert signature["close_sample_rollouts_per_move"] == 64
    assert signature["low_confidence_margin"] == 0.06
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py::test_build_ai_rollout_adaptive_close_sample_overrides_only_close_sampling tests/test_ai_match.py::test_ai_version_signature_records_rollout_adaptive_close_sample
```

Expected: FAIL because the factory branch is not registered.

## Task 3: Register Adaptive Close-Sample Factory Branch

**Files:**
- Modify: `ai/match.py`

- [ ] **Step 1: Add factory branch**

In `ai/match.py`, in `build_ai()` before `expectimax`, add:

```python
    if kind == "rollout_adaptive_close_sample":
        from ai.rollout_ai import RolloutAI
        from scripts.bench_ai import RELEASE_DEFAULT_ROLLOUT_KWARGS

        return RolloutAI(
            rng=rng,
            name="rollout_adaptive_close_sample",
            **_merged(
                {
                    **RELEASE_DEFAULT_ROLLOUT_KWARGS,
                    "close_sample_margin": 0.06,
                    "close_sample_rollouts_per_move": 64,
                    "low_confidence_margin": 0.06,
                }
            ),
        )
```

- [ ] **Step 2: Run factory tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py::test_build_ai_rollout_adaptive_close_sample_overrides_only_close_sampling tests/test_ai_match.py::test_ai_version_signature_records_rollout_adaptive_close_sample
```

Expected: PASS.

## Task 4: Register Bench Profile

**Files:**
- Modify: `scripts/bench_ai.py`
- Modify: `tests/test_bench_ai.py`

- [ ] **Step 1: Add bench profile test**

Append to `tests/test_bench_ai.py`:

```python
def test_rollout_adaptive_close_sample_profile_uses_release_default_opponent() -> None:
    profile = CANDIDATE_PROFILES["rollout_adaptive_close_sample"]["candidate"]

    assert profile["opponent"] == "rollout"
    assert profile["opponent_kwargs"] == RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert profile["games_per_side"] == 100
```

- [ ] **Step 2: Add profile entry**

In `scripts/bench_ai.py`, add to `CANDIDATE_PROFILES`:

```python
    "rollout_adaptive_close_sample": {
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
& ".venv/Scripts/python.exe" -m pytest -q tests/test_bench_ai.py::test_rollout_adaptive_close_sample_profile_uses_release_default_opponent
```

Expected: PASS.

## Task 5: Candidate Robustness Smoke

**Files:**
- Verify: `ai/match.py`

- [ ] **Step 1: Verify small deadline still returns legal move or fallback**

Append to `tests/test_ai_match.py`:

```python
def test_rollout_adaptive_close_sample_small_deadline_returns_legal_move() -> None:
    state = default_starting_state()
    ai = build_ai("rollout_adaptive_close_sample", seed=2026, max_step_time_ms=1.0)

    move = ai.choose_move(state, 6)

    assert move is None or move in state.legal_moves(state.current_player, 6)
```

- [ ] **Step 2: Run smoke test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py::test_rollout_adaptive_close_sample_small_deadline_returns_legal_move
```

Expected: PASS.

## Task 6: Candidate Bench Report

**Files:**
- Generate: `reports/p72_candidate_rollout_adaptive_close_sample_20260516.json`
- Generate: `reports/p72_candidate_rollout_adaptive_close_sample_20260516.md`

- [ ] **Step 1: Run candidate bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_adaptive_close_sample --opponent rollout --stage candidate --games-per-side 100 --report-name p72_candidate_rollout_adaptive_close_sample_20260516
```

Expected: report files written. Candidate may pass or fail gates; either result is report-only.

## Task 7: P7.2 Verification

**Files:**
- Verify: `ai/match.py`
- Verify: `scripts/bench_ai.py`
- Verify: `tests/test_ai_match.py`
- Verify: `tests/test_bench_ai.py`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_ai_match.py tests/test_bench_ai.py
```

Expected: PASS.

- [ ] **Step 2: Run release consistency**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py
```

Expected: PASS, proving GUI/release default did not change.

## Self-Review

- Spec coverage: Covers P7.2 evidence gates, adaptive close-sample profile, factory registration, signature metadata, and report-only candidate bench.
- Placeholder scan: No placeholder tokens or omitted code blocks.
- Boundary check: Does not alter GUI default recommender, release default params, release config, core rules, or MCTS.
