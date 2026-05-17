# R-4 GUI Dice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional GUI "程序掷骰" button beside the existing dice Spinbox, while preserving manual dice entry and existing legal-move refresh behavior.

**Architecture:** `core/dice.py` owns fair dice generation via `secrets.randbelow`. `gui/control_panel.py` exposes a button callback and enable-state setter. `gui/main_window.py` enforces phase/winner/awaiting-dice guards, then updates existing state fields and calls `_refresh()`.

**Tech Stack:** Python 3.11, Tkinter, pytest, existing project virtualenv commands.

---

### Task 1: Core Dice Helper

**Files:**
- Create: `core/dice.py`
- Create: `tests/test_dice.py`

- [x] **Step 1: Write failing dice tests**

```python
import pytest

from core.dice import roll_die


def test_roll_die_maps_zero_to_one() -> None:
    assert roll_die(lambda n: 0) == 1


def test_roll_die_maps_five_to_six() -> None:
    assert roll_die(lambda n: 5) == 6


def test_roll_die_rejects_out_of_range_randbelow_result() -> None:
    with pytest.raises(ValueError, match=r"\[0, 6\)"):
        roll_die(lambda n: 6)
```

- [x] **Step 2: Run test to verify it fails**

Run: `& ".venv/Scripts/python.exe" -m pytest tests/test_dice.py -q`

Expected: FAIL because `core.dice` does not exist.

- [x] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import secrets
from collections.abc import Callable

DICE_SIDES = 6


def roll_die(randbelow: Callable[[int], int] = secrets.randbelow) -> int:
    """Return one fair EWN dice value in [1, 6]."""
    value = int(randbelow(DICE_SIDES))
    if not 0 <= value < DICE_SIDES:
        raise ValueError("randbelow must return a value in [0, 6)")
    return value + 1
```

- [x] **Step 4: Run test to verify it passes**

Run: `& ".venv/Scripts/python.exe" -m pytest tests/test_dice.py -q`

Expected: PASS.

### Task 2: GUI Button Wiring

**Files:**
- Modify: `gui/control_panel.py`
- Modify: `gui/main_window.py`
- Modify: `tests/test_main_window.py`

- [x] **Step 1: Write failing GUI tests**

Add tests that monkeypatch `gui.main_window.roll_die`, call `window.controls.roll_dice_button.invoke()`, and assert:

```python
assert window.current_dice == 4
assert window._awaiting_dice is False
assert "程序掷骰：4" in window.status_message
assert str(window.controls.roll_dice_button["state"]) == "disabled"
```

Also assert the button is disabled in setup, enabled in playing/awaiting dice, disabled after dice is recorded, and enabled again after applying a move.

- [x] **Step 2: Run targeted GUI tests to verify they fail**

Run: `& ".venv/Scripts/python.exe" -m pytest tests/test_main_window.py -q`

Expected: FAIL because `roll_dice_button` / `_roll_dice_from_gui` do not exist.

- [x] **Step 3: Add ControlPanel button**

Add `on_roll_dice: Callable[[], None]` to `ControlPanel.__init__`, create `self.roll_dice_button` beside the Spinbox, and add:

```python
def set_can_roll_dice(self, enabled: bool) -> None:
    self.roll_dice_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
```

- [x] **Step 4: Add MainWindow roll handler**

Import `roll_die`, pass `on_roll_dice=self._roll_dice_from_gui`, add `_roll_dice_from_gui()` with the same guards as manual dice entry, and update `_refresh()`:

```python
self.controls.set_can_roll_dice(
    self._phase == "playing"
    and winner is None
    and self._awaiting_dice
    and not self._match_is_finished()
)
```

- [x] **Step 5: Run targeted GUI tests to verify they pass**

Run: `& ".venv/Scripts/python.exe" -m pytest tests/test_dice.py tests/test_main_window.py -q`

Expected: PASS.

### Task 3: Documentation Sync

**Files:**
- Modify: `docs/MATCH_CHECKLIST.md`
- Modify: `docs/RULE_ASSUMPTIONS.md`
- Modify: `docs/PROJECT_BRIEF.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Document dice-source assumptions**

State that dice source is decided by both sides or referee requirements, and the GUI supports both in-program rolling and manual input.

- [x] **Step 2: Document match checklist discipline**

Add per-turn guidance: use "程序掷骰" only when both sides agree, manually input external dice results, and do not reroll after seeing recommendations.

- [x] **Step 3: Mark R-4 complete in project status**

Record that R-4 GUI program dice is complete and does not change default AI, default layout, or core rules.

### Task 4: Final Verification

**Files:**
- No code edits.

- [x] **Step 1: Run full pytest**

Run: `& ".venv/Scripts/python.exe" -m pytest`

Expected: PASS.

- [x] **Step 2: Run smoke**

Run: `& ".venv/Scripts/python.exe" "scripts/smoke_test.py"`

Expected: PASS.

- [x] **Step 3: Run S2 rehearsal**

Run: `& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"`

Expected: PASS.

- [x] **Step 4: Run preflight**

Run: `& ".venv/Scripts/python.exe" "scripts/preflight_check.py"`

Expected: output includes `READY FOR MATCH`.

## Self-Review

- Spec coverage: covers core dice generation, GUI button, enable/disable guard, manual input preservation, AI recommendation refresh, and documentation sync.
- Placeholder scan: no TBD/TODO/implement-later placeholders.
- Type consistency: `roll_die()`, `ControlPanel.set_can_roll_dice()`, and `MainWindow._roll_dice_from_gui()` names are consistent across tasks.
- Code review follow-up: fixed the Spinbox `FocusOut` vs. "程序掷骰" click ordering bug, and added regression coverage for the default `secrets.randbelow(6)` path.
