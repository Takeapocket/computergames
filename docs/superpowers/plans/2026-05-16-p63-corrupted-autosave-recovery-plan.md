# P6.3 Corrupted Auto-Save Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Ensure corrupted `auto_save.json` and `auto_save_match.json` never block GUI startup or leave the GUI in a half-restored state.

**Architecture:** Keep JSON validity checks in `record.auto_save`, and let `MainWindow` clear invalid auto-save files before deciding whether to prompt for restoration. Valid match records still follow the existing restoration flow; corrupted single-game files are treated like missing single-game progress.

**Tech Stack:** Python 3.11, pytest, Tkinter tests, existing `record.auto_save` helpers, existing `MainWindow` restore flow.

---

## File Structure

- Modify: `record/auto_save.py`
  - Add `is_invalid_auto_save_file(path: str | Path = AUTO_SAVE_PATH) -> bool`.
  - Add `is_invalid_match_auto_save_file(path: str | Path = AUTO_SAVE_MATCH_PATH) -> bool`.
- Modify: `gui/main_window.py`
  - Import the two invalid-file helpers.
  - Add `_clear_invalid_auto_save_files()` and call it at the start of `_restore_auto_save_if_available()`.
- Modify: `tests/test_auto_save.py`
  - Add low-level invalid-file helper tests.
- Modify: `tests/test_main_window.py`
  - Add single-game corrupted auto-save GUI startup test.
- Modify: `tests/test_match_integration.py`
  - Add match corrupted auto-save and mixed valid/corrupt startup tests.

## Task 1: Low-Level Invalid Auto-Save Tests

**Files:**
- Modify: `tests/test_auto_save.py`
- Modify later: `record/auto_save.py`

- [ ] **Step 1: Add failing tests for invalid-file detection**

Append to `tests/test_auto_save.py`:

```python
def test_is_invalid_auto_save_file_detects_corrupt_json(tmp_path):
    from record.auto_save import is_invalid_auto_save_file

    path = tmp_path / "auto_save.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert is_invalid_auto_save_file(path=path) is True


def test_is_invalid_auto_save_file_is_false_for_missing_file(tmp_path):
    from record.auto_save import is_invalid_auto_save_file

    assert is_invalid_auto_save_file(path=tmp_path / "missing.json") is False


def test_is_invalid_match_auto_save_file_detects_corrupt_json(tmp_path):
    from record.auto_save import is_invalid_match_auto_save_file

    path = tmp_path / "auto_save_match.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert is_invalid_match_auto_save_file(path=path) is True
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_auto_save.py
```

Expected: FAIL because the two invalid-file helper functions are not defined.

- [ ] **Step 3: Implement invalid-file helpers**

In `record/auto_save.py`, add these functions immediately after `_is_valid_json_file()`:

```python
def _is_invalid_json_file(path: Path) -> bool:
    return path.is_file() and not _is_valid_json_file(path)


def is_invalid_auto_save_file(*, path: str | Path = AUTO_SAVE_PATH) -> bool:
    return _is_invalid_json_file(Path(path))


def is_invalid_match_auto_save_file(*, path: str | Path = AUTO_SAVE_MATCH_PATH) -> bool:
    return _is_invalid_json_file(Path(path))
```

- [ ] **Step 4: Run auto-save tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_auto_save.py
```

Expected: PASS.

## Task 2: Single-Game Corrupted Auto-Save Startup

**Files:**
- Modify: `tests/test_main_window.py`
- Modify later: `gui/main_window.py`

- [ ] **Step 1: Add failing GUI startup test**

Append to `tests/test_main_window.py`:

```python
def test_corrupt_single_game_auto_save_is_cleared_without_prompt(tk_root, monkeypatch, tmp_path):
    auto_save_path = tmp_path / "auto_save.json"
    auto_save_path.write_text("{not valid json", encoding="utf-8")

    prompts = []
    monkeypatch.setattr(
        "gui.main_window.messagebox.askyesno",
        lambda title, message, **kwargs: prompts.append(title) or True,
    )

    window = MainWindow(
        tk_root,
        auto_save_path=auto_save_path,
        auto_save_match_path=tmp_path / "auto_save_match.json",
    )
    window.pack()

    assert prompts == []
    assert window._mode == "debug"
    assert window._phase == "setup"
    assert not auto_save_path.exists()
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_main_window.py::test_corrupt_single_game_auto_save_is_cleared_without_prompt
```

Expected: FAIL because the corrupted file remains on disk.

## Task 3: Match Corrupted Auto-Save Startup Tests

**Files:**
- Modify: `tests/test_match_integration.py`
- Modify later: `gui/main_window.py`

- [ ] **Step 1: Add corrupted match auto-save test**

Append to `tests/test_match_integration.py`:

```python
def test_corrupt_match_auto_save_is_cleared_without_prompt(tk_root, monkeypatch, tmp_path):
    match_path = tmp_path / "auto_save_match.json"
    match_path.write_text("{not valid json", encoding="utf-8")

    prompts = []
    monkeypatch.setattr(
        "gui.main_window.messagebox.askyesno",
        lambda title, message, **kwargs: prompts.append(title) or True,
    )

    window = MainWindow(
        tk_root,
        auto_save_path=tmp_path / "auto_save.json",
        auto_save_match_path=match_path,
    )
    window.pack()

    assert prompts == []
    assert window._mode == "debug"
    assert window._match is None
    assert not match_path.exists()
```

- [ ] **Step 2: Add valid match plus corrupted single-game test**

Append to `tests/test_match_integration.py`:

```python
def test_match_playing_with_corrupt_single_game_prompts_missing_progress(tk_root, monkeypatch, tmp_path):
    from record.auto_save import auto_save_match, has_auto_save, has_auto_save_match
    from record.match_record import MatchRecord

    game_path = tmp_path / "auto_save.json"
    match_path = tmp_path / "auto_save_match.json"
    game_path.write_text("{not valid json", encoding="utf-8")
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=2,
        games_won_us=1,
        phase="playing",
        games=[_stub_game()],
    )
    auto_save_match(match, path=match_path)

    prompts = []

    def fake_askyesno(title, message, **kwargs):
        prompts.append(title)
        if title == "恢复未完成对局":
            return True
        if title == "本盘进度缺失":
            return False
        return False

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", fake_askyesno)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *args, **kwargs: None)

    window = MainWindow(tk_root, auto_save_path=game_path, auto_save_match_path=match_path)
    window.pack()

    assert "本盘进度缺失" in prompts
    assert window._mode == "debug"
    assert window._match is None
    assert not has_auto_save(path=game_path)
    assert not has_auto_save_match(path=match_path)
```

- [ ] **Step 3: Add finished match plus corrupted single-game test**

Append to `tests/test_match_integration.py`:

```python
def test_finished_match_with_corrupt_single_game_clears_both_files(tk_root, monkeypatch, tmp_path):
    from record.auto_save import auto_save_match, has_auto_save, has_auto_save_match
    from record.match_record import MatchRecord

    game_path = tmp_path / "auto_save.json"
    match_path = tmp_path / "auto_save_match.json"
    game_path.write_text("{not valid json", encoding="utf-8")
    match = MatchRecord(
        our_side=Player.RED,
        our_role="甲",
        current_game_index=4,
        games_won_us=4,
        games_won_them=0,
        phase="finished",
        games=[_stub_game(), _stub_game(), _stub_game(), _stub_game()],
    )
    auto_save_match(match, path=match_path)

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr("gui.main_window.messagebox.showinfo", lambda *args, **kwargs: None)

    window = MainWindow(tk_root, auto_save_path=game_path, auto_save_match_path=match_path)
    window.pack()

    assert window._mode == "debug"
    assert window._match is None
    assert not has_auto_save(path=game_path)
    assert not has_auto_save_match(path=match_path)
```

- [ ] **Step 4: Run match integration tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_match_integration.py
```

Expected: FAIL because corrupted files are not proactively cleared.

## Task 4: Clear Invalid Auto-Save Files on Startup

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Import invalid-file helpers**

Extend the `record.auto_save` import in `gui/main_window.py` with:

```python
    is_invalid_auto_save_file,
    is_invalid_match_auto_save_file,
```

- [ ] **Step 2: Add `_clear_invalid_auto_save_files()`**

Insert this method immediately before `_restore_auto_save_if_available()`:

```python
    def _clear_invalid_auto_save_files(self) -> None:
        if is_invalid_auto_save_file(path=self._auto_save_path):
            self._clear_auto_save()
        if is_invalid_match_auto_save_file(path=self._auto_save_match_path):
            clear_auto_save_match(path=self._auto_save_match_path)
```

- [ ] **Step 3: Call the helper at restore startup**

At the start of `_restore_auto_save_if_available()`, before `has_game = has_auto_save(path=self._auto_save_path)`, add:

```python
        self._clear_invalid_auto_save_files()
```

- [ ] **Step 4: Run corrupted auto-save tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_auto_save.py tests/test_main_window.py tests/test_match_integration.py
```

Expected: PASS.

## Task 5: P6.3 Verification

**Files:**
- Verify: `record/auto_save.py`
- Verify: `gui/main_window.py`
- Verify: `tests/test_auto_save.py`
- Verify: `tests/test_main_window.py`
- Verify: `tests/test_match_integration.py`

- [ ] **Step 1: Run focused restore suite**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_auto_save.py tests/test_main_window.py tests/test_match_integration.py
```

Expected: PASS.

- [ ] **Step 2: Run preflight**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

Expected: output ends with `READY FOR MATCH`.

## Self-Review

- Spec coverage: Covers P6.3-A through P6.3-D.
- Placeholder scan: No placeholder tokens or deferred test descriptions.
- Boundary check: Does not alter match rules, release defaults, or AI parameters.
