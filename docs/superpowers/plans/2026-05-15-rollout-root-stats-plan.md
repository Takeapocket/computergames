# Rollout Root Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical `RootMoveStats` diagnostics surface for `RolloutAI` so GUI and scripts can explain every root candidate without changing default AI parameters.

**Architecture:** Keep rollout behavior unchanged and only normalize the telemetry produced after sampling. `RootMoveStats` becomes the formal interface; `last_diagnostics` remains a compatibility alias derived from the same stats. GUI reads `last_root_stats` first and falls back to `last_diagnostics` for older recommenders.

**Tech Stack:** Python 3.11, dataclasses, pytest, Tkinter GUI logic tests.

---

## Files

- Modify: `ai/rollout_ai.py`
  - Add `RootMoveStats`.
  - Add `RolloutAI.last_root_stats`.
  - Derive `last_diagnostics` from the same stats for compatibility.
- Modify: `gui/main_window.py`
  - Format `wins`, `losses`, `draws/cutoffs`, `score`, `winrate`, `avg`.
  - Prefer `last_root_stats`; fallback to `last_diagnostics`.
- Modify: `tests/test_rollout_ai.py`
  - Assert canonical stats length, formulas, no state mutation, and empty stats with no legal moves.
- Modify: `tests/test_gui_logic.py`
  - Assert GUI uses `last_root_stats` when present.
- No release default config changes.
- No branch, commit, push, dependency, or core rule changes in this execution.

---

### Task 1: RolloutAI Canonical Root Stats

**Files:**
- Modify: `tests/test_rollout_ai.py`
- Modify: `ai/rollout_ai.py`

- [x] **Step 1: Write the failing canonical stats test**

Add assertions to `test_rollout_ai_records_candidate_diagnostics`:

```python
assert [stats.move for stats in ai.last_root_stats] == legal
assert ai.last_diagnostics == ai.last_root_stats
assert all(stats.visits == 3 for stats in ai.last_root_stats)
assert all(0.0 <= stats.winrate <= 1.0 for stats in ai.last_root_stats)
assert all(0.0 <= stats.score <= 1.0 for stats in ai.last_root_stats)
assert all(stats.avg == 2 * stats.score - 1 for stats in ai.last_root_stats)
assert all(stats.draws == stats.cutoffs for stats in ai.last_root_stats)
assert all(
    stats.visits == stats.wins + stats.losses + stats.draws
    for stats in ai.last_root_stats
)
```

- [x] **Step 2: Write the failing no-legal-moves reset test**

Add assertions to `test_rollout_ai_returns_none_when_no_legal_moves`:

```python
assert ai.last_root_stats == []
assert ai.last_diagnostics == []
```

- [x] **Step 3: Run RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_records_candidate_diagnostics" "tests/test_rollout_ai.py::test_rollout_ai_returns_none_when_no_legal_moves" -q
```

Expected: FAIL because `RolloutAI` has no `last_root_stats` attribute.

- [x] **Step 4: Implement minimal stats surface**

In `ai/rollout_ai.py`, replace the compatibility-only dataclass with:

```python
@dataclass(frozen=True)
class RootMoveStats:
    move: Move
    visits: int
    wins: float
    losses: float
    draws: float
    score: float
    winrate: float
    avg: float
    low_confidence: bool = False

    @property
    def cutoffs(self) -> float:
        return self.draws


RolloutMoveDiagnostic = RootMoveStats
```

Update `_RolloutMoveScore.to_diagnostic()` to return `RootMoveStats(draws=self.cutoffs, ...)`.

Initialize and reset both fields:

```python
self.last_root_stats: list[RootMoveStats] = []
self.last_diagnostics: list[RolloutMoveDiagnostic] = []
```

```python
self.last_root_stats = []
self.last_diagnostics = []
```

Update `_record_diagnostics()`:

```python
def _record_diagnostics(self, scores: list[_RolloutMoveScore]) -> None:
    self.last_root_stats = [
        score.to_diagnostic()
        for score in scores
        if score.visits > 0
    ]
    self.last_diagnostics = self.last_root_stats
```

- [x] **Step 5: Run GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py::test_rollout_ai_records_candidate_diagnostics" "tests/test_rollout_ai.py::test_rollout_ai_returns_none_when_no_legal_moves" -q
```

Expected: PASS.

---

### Task 2: GUI Root Stats Display

**Files:**
- Modify: `tests/test_gui_logic.py`
- Modify: `gui/main_window.py`

- [x] **Step 1: Write the failing GUI priority test**

Add a test that creates a fake recommender with both `last_root_stats` and stale `last_diagnostics`:

```python
def test_recommendation_text_prefers_root_stats_over_legacy_diagnostics():
    move = Move(
        player=Player.RED,
        piece_id=5,
        from_pos=Position(2, 1),
        to_pos=Position(3, 1),
        is_capture=False,
    )
    stale = Move(
        player=Player.RED,
        piece_id=6,
        from_pos=Position(2, 0),
        to_pos=Position(3, 0),
        is_capture=False,
    )

    class FakeStats:
        move = move
        visits = 8
        wins = 3.0
        losses = 4.0
        draws = 1.0
        cutoffs = 1.0
        score = 0.4375
        winrate = 0.375
        avg = -0.125

    class StaleStats:
        move = stale
        visits = 1
        wins = 1.0
        losses = 0.0
        draws = 0.0
        cutoffs = 0.0
        score = 1.0
        winrate = 1.0
        avg = 1.0

    class FakeRecommender:
        last_root_stats = [FakeStats()]
        last_diagnostics = [StaleStats()]
        last_low_confidence = False
        last_timed_out = False

    class FakeWindow:
        _awaiting_dice = False
        _recommender = FakeRecommender()

        def _recommended_move(self):
            return move

    text = MainWindow._recommendation_text(FakeWindow(), None)

    assert "红方 5: (2,1) -> (3,1)" in text
    assert "红方 6: (2,0) -> (3,0)" not in text
    assert "wins=3" in text
    assert "losses=4" in text
    assert "draws=1" in text
```

- [x] **Step 2: Run RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_gui_logic.py::test_recommendation_text_prefers_root_stats_over_legacy_diagnostics" -q
```

Expected: FAIL because GUI still reads only `last_diagnostics` and does not show wins/losses/draws.

- [x] **Step 3: Implement GUI priority and formatter**

Update `_format_rollout_diagnostic()` to read `wins`, `losses`, and `draws` with a legacy `cutoffs` fallback:

```python
draws = float(getattr(diagnostic, "draws", getattr(diagnostic, "cutoffs", 0.0)))
```

Return text containing:

```text
visits=..., score=..., winrate=..., wins=..., losses=..., draws=..., avg=...
```

Update `_recommendation_text()`:

```python
diagnostics = getattr(self._recommender, "last_root_stats", None)
if diagnostics is None:
    diagnostics = getattr(self._recommender, "last_diagnostics", [])
```

- [x] **Step 4: Run GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_gui_logic.py::test_recommendation_text_prefers_root_stats_over_legacy_diagnostics" "tests/test_gui_logic.py::test_recommendation_text_marks_low_confidence" -q
```

Expected: PASS.

---

### Task 3: Regression Verification And Documentation Status

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Run targeted tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py" "tests/test_gui_logic.py" "tests/test_rollout_stability.py" -q
```

Expected: PASS.

- [x] **Step 2: Run smoke test**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected: exit code 0.

- [x] **Step 3: Run full pytest because AI and GUI public behavior changed**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

Expected: PASS.

- [x] **Step 4: Sync status docs**

Update `PROJECT_MEMORY.md` and `PROJECT_PHASES.md` to record:

```text
2026-05-15 P1 Rollout 根节点诊断收敛已完成：新增 RootMoveStats / last_root_stats，last_diagnostics 保持兼容，GUI 优先显示 canonical root stats，默认 rollout 参数和 release/v1.0/default_params.json 未变更。验证：pytest 全量与 smoke_test.py。
```

- [x] **Step 5: Final self-check**

Confirm:

```text
No core rule changes.
No release default AI parameter changes.
No branch/commit/push.
Root stats formulas are covered by tests.
GUI fallback remains compatible with legacy diagnostics.
```
