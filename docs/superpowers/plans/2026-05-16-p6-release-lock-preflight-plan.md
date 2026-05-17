# P6 Release Lock and Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Lock the current release defaults in tests and add a one-command preflight check that prints `READY FOR MATCH` only after required checks pass.

**Architecture:** Keep default AI and default layout as data assertions, not behavior changes. `tests/test_release_consistency.py` verifies GUI/release/docs consistency; `scripts/preflight_check.py` reuses the same locked constants and runs the existing verification commands without writing release files.

**Tech Stack:** Python 3.11, pytest, Tkinter test helper, standard-library `json`, `pathlib`, `subprocess`.

---

### Task 1: P6.0 Release Consistency Test

**Files:**
- Create: `tests/test_release_consistency.py`
- Read: `gui/main_window.py`
- Read: `gui/opening_panel.py`
- Read: `release/v1.0/default_params.json`
- Read: `release/v1.0/config.json`
- Read: `release/v1.0/README.md`

- [ ] **Step 1: Add the release consistency tests**

Create `tests/test_release_consistency.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from gui import main_window
from gui.opening_panel import OpeningPanel
from tests.tk_support import make_hidden_tk_root


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RECOMMENDER_KWARGS = {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0,
}

EXPECTED_DEFAULT_PARAMS = {
    "ai": "rollout",
    **EXPECTED_RECOMMENDER_KWARGS,
    "fallback_ai": "greedy_risk",
    "promotion_report": "reports/ai_promotion_decision.md",
}


def _read_json(relative_path: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def test_gui_default_recommender_is_locked_to_p3_rollout() -> None:
    assert main_window.DEFAULT_RECOMMENDER_KIND == "rollout"
    assert main_window.DEFAULT_RECOMMENDER_KWARGS == EXPECTED_RECOMMENDER_KWARGS


def test_release_default_params_match_gui_defaults() -> None:
    assert _read_json("release/v1.0/default_params.json") == EXPECTED_DEFAULT_PARAMS


def test_release_config_locks_balanced_v1_layout() -> None:
    config = _read_json("release/v1.0/config.json")
    assert config["default_ai"] == "rollout"
    assert config["default_layout"] == "balanced_v1"


def test_opening_panel_initial_layout_is_balanced_v1(tmp_path) -> None:
    root = make_hidden_tk_root()
    panel = OpeningPanel(root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    try:
        assert panel.layout_var.get() == "balanced_v1"
    finally:
        panel.destroy()


def test_release_readme_documents_default_ai_and_layout() -> None:
    readme = (PROJECT_ROOT / "release/v1.0/README.md").read_text(encoding="utf-8")
    assert "我方推荐 AI = `rollout` kind + P3 promotion 显式参数" in readme
    assert "默认 `balanced_v1`" in readme
```

- [ ] **Step 2: Run the P6.0 test file**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py
```

Expected: PASS. This task is a lock test over existing behavior, so it may pass immediately.

### Task 2: P6.1 Preflight Check, Test First

**Files:**
- Create: `tests/test_preflight_check.py`
- Create: `scripts/preflight_check.py`

- [ ] **Step 1: Add failing tests for the preflight helper API**

Create `tests/test_preflight_check.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import preflight_check


def _write_release_files(root: Path, *, default_layout: str = "balanced_v1") -> None:
    release_dir = root / "release" / "v1.0"
    release_dir.mkdir(parents=True)
    (release_dir / "default_params.json").write_text(
        json.dumps(preflight_check.EXPECTED_DEFAULT_PARAMS),
        encoding="utf-8",
    )
    (release_dir / "config.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "default_ai": "rollout",
                "default_layout": default_layout,
                "board_size": 5,
                "time_limit_seconds": 240,
                "max_games_per_match": 7,
                "games_to_win_match": 4,
                "offline_required": True,
            }
        ),
        encoding="utf-8",
    )


def test_validate_release_files_accepts_locked_defaults(tmp_path) -> None:
    _write_release_files(tmp_path)

    preflight_check.validate_release_files(tmp_path)


def test_validate_release_files_rejects_layout_drift(tmp_path) -> None:
    _write_release_files(tmp_path, default_layout="aggressive_v1")

    with pytest.raises(preflight_check.PreflightError, match="default_layout"):
        preflight_check.validate_release_files(tmp_path)


def test_run_external_checks_reports_ok_lines(monkeypatch, tmp_path, capsys) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(args, cwd):
        calls.append(tuple(args))
        return 0

    result = preflight_check.run_external_checks(
        tmp_path,
        runner=fake_run,
        commands=(("unit", ("python", "-m", "pytest", "-q")),),
    )

    assert result == 0
    assert calls == [("python", "-m", "pytest", "-q")]
    assert "[OK] unit" in capsys.readouterr().out
```

- [ ] **Step 2: Run the new preflight tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_preflight_check.py
```

Expected: FAIL because `scripts/preflight_check.py` does not exist yet.

- [ ] **Step 3: Implement `scripts/preflight_check.py` minimally**

Create `scripts/preflight_check.py` with:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

from gui import main_window


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RECOMMENDER_KWARGS = {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0,
}

EXPECTED_DEFAULT_PARAMS = {
    "ai": "rollout",
    **EXPECTED_RECOMMENDER_KWARGS,
    "fallback_ai": "greedy_risk",
    "promotion_report": "reports/ai_promotion_decision.md",
}

DEFAULT_COMMANDS = (
    ("pytest -q", (sys.executable, "-m", "pytest", "-q")),
    ("scripts/smoke_test.py", (sys.executable, "scripts/smoke_test.py")),
    ("scripts/s2_rehearsal.py", (sys.executable, "scripts/s2_rehearsal.py")),
)

Runner = Callable[[Sequence[str], Path], int]


class PreflightError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreflightError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"invalid json: {path}: {exc}") from exc


def validate_release_files(project_root: Path = PROJECT_ROOT) -> None:
    default_params = _read_json(project_root / "release" / "v1.0" / "default_params.json")
    if default_params != EXPECTED_DEFAULT_PARAMS:
        raise PreflightError("default_params.json drifted from locked P3 rollout defaults")

    config = _read_json(project_root / "release" / "v1.0" / "config.json")
    if config.get("default_ai") != "rollout":
        raise PreflightError("config.json default_ai must be rollout")
    if config.get("default_layout") != "balanced_v1":
        raise PreflightError("config.json default_layout must be balanced_v1")


def validate_gui_defaults() -> None:
    if main_window.DEFAULT_RECOMMENDER_KIND != "rollout":
        raise PreflightError("GUI default recommender kind must be rollout")
    if main_window.DEFAULT_RECOMMENDER_KWARGS != EXPECTED_RECOMMENDER_KWARGS:
        raise PreflightError("GUI default recommender kwargs drifted from locked P3 rollout defaults")


def _subprocess_runner(args: Sequence[str], cwd: Path) -> int:
    return subprocess.run(args, cwd=cwd, check=False).returncode


def run_external_checks(
    project_root: Path = PROJECT_ROOT,
    *,
    runner: Runner = _subprocess_runner,
    commands: Sequence[tuple[str, Sequence[str]]] = DEFAULT_COMMANDS,
) -> int:
    for label, args in commands:
        code = runner(args, project_root)
        if code != 0:
            print(f"[FAIL] {label}: exit code {code}")
            return code
        print(f"[OK] {label}")
    return 0


def main() -> int:
    try:
        validate_release_files(PROJECT_ROOT)
        validate_gui_defaults()
    except PreflightError as exc:
        print(f"[FAIL] release defaults locked: {exc}")
        return 1

    print("[OK] release defaults locked")
    code = run_external_checks(PROJECT_ROOT)
    if code != 0:
        return code

    print("READY FOR MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the preflight tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_preflight_check.py
```

Expected: PASS.

### Task 3: Slice Verification

**Files:**
- Verify: `tests/test_release_consistency.py`
- Verify: `tests/test_preflight_check.py`
- Verify: `scripts/preflight_check.py`

- [ ] **Step 1: Run focused P6.0/P6.1 tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py tests/test_preflight_check.py
```

Expected: PASS.

- [ ] **Step 2: Run project smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected: exit code 0.

- [ ] **Step 3: Run preflight**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

Expected: output includes `[OK] release defaults locked`, `[OK] pytest -q`, `[OK] scripts/smoke_test.py`, `[OK] scripts/s2_rehearsal.py`, and final line `READY FOR MATCH`.

## Self-Review

- Spec coverage: This plan implements P6.0 and P6.1 only. P6.2-P7.2 remain pending and should be planned/executed after this slice verifies.
- Placeholder scan: No `TBD`, no vague "add tests" steps; each code-producing step includes concrete content.
- Type consistency: `EXPECTED_RECOMMENDER_KWARGS`, `EXPECTED_DEFAULT_PARAMS`, `PreflightError`, `validate_release_files`, and `run_external_checks` names are consistent across tests and implementation.
