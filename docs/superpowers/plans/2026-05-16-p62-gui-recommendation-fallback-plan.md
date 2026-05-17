# P6.2 GUI Recommendation Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Make the GUI recommendation area always try a safe fallback chain: current default `rollout` -> `greedy_risk` -> first legal move -> `None`.

**Architecture:** Keep the default recommender as the current release `rollout` instance and add a separate GUI-level fallback recommender. `MainWindow._recommended_move()` becomes the only place that catches default AI failures, rejects illegal recommendations, and records the source label used by `_recommendation_text()`.

**Tech Stack:** Python 3.11, Tkinter GUI code, pytest, existing `ai.match.build_ai`, existing `GameState.legal_moves()`.

---

## File Structure

- Modify: `gui/main_window.py`
  - Add one cached fallback recommender instance: `build_ai("greedy_risk", seed=0)`.
  - Add recommendation source state: `"rollout"`, `"greedy_risk"`, `"rules"`, `"none"`.
  - Add two private helpers: `_is_legal_recommendation()` and `_choose_fallback_recommendation()`.
  - Replace `_recommended_move()` with the fallback chain.
  - Update `_recommendation_text()` to display source-specific labels.
- Modify: `tests/test_gui_logic.py`
  - Add logic-level tests for fallback paths without starting a full Tk window.
- Modify: `tests/test_main_window.py`
  - Add one real-window smoke assertion that fallback source appears in the recommendation panel.

## Task 1: Logic Tests for Fallback Chain

**Files:**
- Modify: `tests/test_gui_logic.py`
- Read: `gui/main_window.py`
- Read: `ai/match.py`

- [ ] **Step 1: Add failing tests for fallback behavior**

Append these tests to `tests/test_gui_logic.py`:

```python
def test_recommended_move_uses_greedy_risk_fallback_when_rollout_raises() -> None:
    from ai.match import default_starting_state

    state = default_starting_state()
    legal = state.legal_moves(state.current_player, 6)
    fallback_move = legal[-1]

    class BrokenRollout:
        def choose_move(self, state, dice):
            raise RuntimeError("rollout exploded")

    class FallbackAI:
        def choose_move(self, state, dice):
            return fallback_move

    class FakeWindow:
        current_dice = 6
        state = state
        _recommender = BrokenRollout()
        _fallback_recommender = FallbackAI()
        _recommendation_cache_key = None
        _recommendation_cache_move = None
        _recommendation_cache_source = "none"

        def _recommendation_key(self):
            return (self.current_dice, repr(self.state.serialize(include_history=False)))

    window = FakeWindow()

    assert MainWindow._recommended_move(window) == fallback_move
    assert window._recommendation_cache_source == "greedy_risk"


def test_recommended_move_rejects_illegal_rollout_move_and_uses_fallback() -> None:
    from ai.match import default_starting_state

    state = default_starting_state()
    legal = state.legal_moves(state.current_player, 6)
    illegal_move = legal[0]
    illegal_move = Move(
        player=illegal_move.player,
        piece_id=illegal_move.piece_id,
        from_pos=illegal_move.from_pos,
        to_pos=Position(4, 4),
        is_capture=False,
    )
    fallback_move = legal[-1]

    class IllegalRollout:
        def choose_move(self, state, dice):
            return illegal_move

    class FallbackAI:
        def choose_move(self, state, dice):
            return fallback_move

    class FakeWindow:
        current_dice = 6
        state = state
        _recommender = IllegalRollout()
        _fallback_recommender = FallbackAI()
        _recommendation_cache_key = None
        _recommendation_cache_move = None
        _recommendation_cache_source = "none"

        def _recommendation_key(self):
            return (self.current_dice, repr(self.state.serialize(include_history=False)))

    window = FakeWindow()

    assert MainWindow._recommended_move(window) == fallback_move
    assert window._recommendation_cache_source == "greedy_risk"


def test_recommended_move_uses_first_legal_when_fallback_fails() -> None:
    from ai.match import default_starting_state

    state = default_starting_state()
    legal = state.legal_moves(state.current_player, 6)

    class BrokenAI:
        def choose_move(self, state, dice):
            raise RuntimeError("no recommendation")

    class FakeWindow:
        current_dice = 6
        state = state
        _recommender = BrokenAI()
        _fallback_recommender = BrokenAI()
        _recommendation_cache_key = None
        _recommendation_cache_move = None
        _recommendation_cache_source = "none"

        def _recommendation_key(self):
            return (self.current_dice, repr(self.state.serialize(include_history=False)))

    window = FakeWindow()

    assert MainWindow._recommended_move(window) == legal[0]
    assert window._recommendation_cache_source == "rules"


def test_recommendation_text_names_greedy_risk_fallback_source() -> None:
    from ai.match import default_starting_state

    state = default_starting_state()
    move = state.legal_moves(state.current_player, 6)[0]

    class FakeRecommender:
        last_diagnostics = []
        last_root_stats = []
        last_low_confidence = False
        last_timed_out = False

    class FakeWindow:
        _awaiting_dice = False
        _recommender = FakeRecommender()
        _recommendation_cache_source = "greedy_risk"

        def _recommended_move(self):
            return move

    text = MainWindow._recommendation_text(FakeWindow(), None)

    assert "greedy_risk 回退：" in text
    assert "rollout：" not in text


def test_recommendation_text_names_rules_fallback_source() -> None:
    from ai.match import default_starting_state

    state = default_starting_state()
    move = state.legal_moves(state.current_player, 6)[0]

    class FakeRecommender:
        last_diagnostics = []
        last_root_stats = []
        last_low_confidence = False
        last_timed_out = False

    class FakeWindow:
        _awaiting_dice = False
        _recommender = FakeRecommender()
        _recommendation_cache_source = "rules"

        def _recommended_move(self):
            return move

    text = MainWindow._recommendation_text(FakeWindow(), None)

    assert "规则兜底：" in text
    assert "rollout：" not in text
```

- [ ] **Step 2: Run the new logic tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_gui_logic.py
```

Expected: FAIL because `MainWindow._recommended_move()` does not catch exceptions, does not reject illegal moves, and does not set `_recommendation_cache_source`.

## Task 2: Implement Fallback Chain in `MainWindow`

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Add cached fallback state in `__init__`**

In `MainWindow.__init__`, immediately after constructing `self._recommender`, add:

```python
        self._fallback_recommender = build_ai("greedy_risk", seed=0)
```

Then replace the recommendation cache fields with:

```python
        self._recommendation_cache_key: tuple[int, str] | None = None
        self._recommendation_cache_move: Move | None = None
        self._recommendation_cache_source: Literal["rollout", "greedy_risk", "rules", "none"] = "none"
```

- [ ] **Step 2: Add private legality and fallback helpers**

Insert these methods immediately before `_recommended_move()`:

```python
    def _is_legal_recommendation(self, move: Move | None, legal_moves: list[Move]) -> bool:
        return move is not None and move in legal_moves

    def _choose_fallback_recommendation(self, legal_moves: list[Move]) -> tuple[Move | None, Literal["greedy_risk", "rules", "none"]]:
        try:
            fallback_move = self._fallback_recommender.choose_move(self.state, self.current_dice)
        except Exception:  # noqa: BLE001 - GUI fallback must survive AI failures
            fallback_move = None

        if self._is_legal_recommendation(fallback_move, legal_moves):
            return fallback_move, "greedy_risk"
        if legal_moves:
            return legal_moves[0], "rules"
        return None, "none"
```

- [ ] **Step 3: Replace `_recommended_move()`**

Replace the body of `MainWindow._recommended_move()` with:

```python
    def _recommended_move(self) -> Move | None:
        key = self._recommendation_key()
        if self._recommendation_cache_key == key:
            return self._recommendation_cache_move

        self._recommendation_cache_key = key
        legal_moves = self.state.legal_moves(self.state.current_player, self.current_dice)
        if not legal_moves:
            self._recommendation_cache_move = None
            self._recommendation_cache_source = "none"
            return None

        try:
            rollout_move = self._recommender.choose_move(self.state, self.current_dice)
        except Exception:  # noqa: BLE001 - GUI must keep producing a safe recommendation
            rollout_move = None

        if self._is_legal_recommendation(rollout_move, legal_moves):
            self._recommendation_cache_move = rollout_move
            self._recommendation_cache_source = "rollout"
            return rollout_move

        fallback_move, source = self._choose_fallback_recommendation(legal_moves)
        self._recommendation_cache_move = fallback_move
        self._recommendation_cache_source = source
        return fallback_move
```

- [ ] **Step 4: Update `_recommendation_text()` source label**

Replace the current first `lines = [f"{DEFAULT_RECOMMENDER_KIND}：{format_move_label(move, distinguish_self_capture=True)}"]` assignment in `_recommendation_text()` with:

```python
        source_label = {
            "rollout": DEFAULT_RECOMMENDER_KIND,
            "greedy_risk": "greedy_risk 回退",
            "rules": "规则兜底",
            "none": DEFAULT_RECOMMENDER_KIND,
        }.get(getattr(self, "_recommendation_cache_source", "rollout"), DEFAULT_RECOMMENDER_KIND)
        lines = [f"{source_label}：{format_move_label(move, distinguish_self_capture=True)}"]
```

Then guard rollout diagnostics so they only display for real rollout recommendations:

```python
        if getattr(self, "_recommendation_cache_source", "rollout") == "rollout":
            diagnostics = getattr(self._recommender, "last_root_stats", None)
            if diagnostics is None:
                diagnostics = getattr(self._recommender, "last_diagnostics", [])
            if diagnostics:
                lines.append("rollout 候选：")
                lines.extend(_format_rollout_diagnostic(diagnostic) for diagnostic in diagnostics)
```

- [ ] **Step 5: Run logic tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_gui_logic.py
```

Expected: PASS.

## Task 3: Real Window Smoke Test for Fallback Source

**Files:**
- Modify: `tests/test_main_window.py`

- [ ] **Step 1: Add a real-window fallback display test**

Append this test to `tests/test_main_window.py`:

```python
def test_match_mode_panel_displays_greedy_risk_fallback_source(tk_root, monkeypatch):
    from ai.match import default_starting_state

    state = default_starting_state()
    fallback_move = state.legal_moves(state.current_player, 6)[0]

    class BrokenRollout:
        name = "rollout"

        def choose_move(self, state, dice):
            raise RuntimeError("rollout failed")

    class FallbackAI:
        name = "greedy_risk"

        def choose_move(self, state, dice):
            return fallback_move

    def fake_build_ai(kind, *, seed=None, **kwargs):
        if kind == "rollout":
            return BrokenRollout()
        if kind == "greedy_risk":
            return FallbackAI()
        raise AssertionError(kind)

    monkeypatch.setattr("gui.main_window.build_ai", fake_build_ai)

    window = MainWindow(tk_root)
    window.pack()
    window.state = state
    window.record = GameRecord.from_state(state)
    window._phase = "playing"
    window._awaiting_dice = False
    window.current_dice = 6
    window._refresh()

    assert "greedy_risk 回退：" in window.controls.recommendation_var.get()
```

- [ ] **Step 2: Run the real-window test and verify RED/GREEN**

Run before implementation if Task 2 was not executed:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_main_window.py::test_match_mode_panel_displays_greedy_risk_fallback_source
```

Expected before Task 2: FAIL with uncaught `RuntimeError` or missing fallback label.

Run after Task 2:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_main_window.py::test_match_mode_panel_displays_greedy_risk_fallback_source
```

Expected after Task 2: PASS.

## Task 4: P6.2 Verification

**Files:**
- Verify: `gui/main_window.py`
- Verify: `tests/test_gui_logic.py`
- Verify: `tests/test_main_window.py`

- [ ] **Step 1: Run focused GUI logic and window tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_gui_logic.py tests/test_main_window.py
```

Expected: PASS.

- [ ] **Step 2: Run release consistency and preflight helper tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py tests/test_preflight_check.py
```

Expected: PASS. This confirms P6.2 did not change release defaults.

## Self-Review

- Spec coverage: Covers P6.2 fallback chain, source labels, illegal recommendation rejection, and no-legal-move behavior.
- Placeholder scan: No placeholder tokens or deferred steps.
- Boundary check: Does not modify `DEFAULT_RECOMMENDER_KIND`, `DEFAULT_RECOMMENDER_KWARGS`, release configs, or core rules.
