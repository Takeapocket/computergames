from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gui import main_window

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

EXPECTED_RELEASE_CONFIG = {
    "version": "1.0",
    "default_ai": "rollout",
    "default_layout": "balanced_v1",
    "board_size": 5,
    "time_limit_seconds": 240,
    "max_games_per_match": 7,
    "games_to_win_match": 4,
    "offline_required": True,
}

DEFAULT_COMMANDS = (
    (
        "pytest -q",
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "--maxfail=1",
            "--basetemp",
            "{PYTEST_BASETEMP}",
        ),
    ),
    ("scripts/smoke_test.py", (sys.executable, "scripts/smoke_test.py")),
    ("scripts/s2_rehearsal.py", (sys.executable, "scripts/s2_rehearsal.py")),
    (
        "scripts/timing_budget_probe.py --samples 16",
        (
            sys.executable,
            "scripts/timing_budget_probe.py",
            "--samples",
            "16",
            "--output",
            "reports/preflight_timing_budget_probe.md",
            "--json-output",
            "reports/preflight_timing_budget_probe.json",
        ),
    ),
)

REQUIRED_FILES = (
    "PROJECT_MEMORY.md",
    "PROJECT_PHASES.md",
    "README.md",
    "docs/RULE_ASSUMPTIONS.md",
    "docs/PROJECT_BRIEF.md",
    "release/v1.0/README.md",
    "release/v1.0/default_params.json",
    "release/v1.0/config.json",
    "release/v1.0/test_report.md",
    "release/v1.0/known_limitations.md",
    "scripts/smoke_test.py",
    "scripts/s2_rehearsal.py",
    "scripts/launcher.py",
    "启动项目.cmd",
)

Runner = Callable[[Sequence[str], Path], int]
PYTEST_BASETEMP_TOKEN = "{PYTEST_BASETEMP}"


class PreflightError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreflightError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"invalid json: {path}: {exc}") from exc


def validate_project_root(
    project_root: Path = PROJECT_ROOT,
    current_dir: Path | None = None,
) -> None:
    actual_cwd = (current_dir or Path.cwd()).resolve()
    expected_cwd = project_root.resolve()
    if actual_cwd != expected_cwd:
        raise PreflightError(f"current working directory must be project root: {expected_cwd}")

    missing = [relative_path for relative_path in REQUIRED_FILES if not (project_root / relative_path).exists()]
    if missing:
        raise PreflightError(f"missing required files: {', '.join(missing)}")


def validate_release_files(project_root: Path = PROJECT_ROOT) -> None:
    default_params = _read_json(project_root / "release" / "v1.0" / "default_params.json")
    if default_params != EXPECTED_DEFAULT_PARAMS:
        raise PreflightError("default_params.json drifted from locked P3 rollout defaults")

    config = _read_json(project_root / "release" / "v1.0" / "config.json")
    for key, expected in EXPECTED_RELEASE_CONFIG.items():
        if config.get(key) != expected:
            raise PreflightError(f"config.json {key} must be {expected!r}")


def validate_gui_defaults() -> None:
    if main_window.DEFAULT_RECOMMENDER_KIND != "rollout":
        raise PreflightError("GUI default recommender kind must be rollout")
    if main_window.DEFAULT_RECOMMENDER_KWARGS != EXPECTED_RECOMMENDER_KWARGS:
        raise PreflightError("GUI default recommender kwargs drifted from locked P3 rollout defaults")


def validate_runtime_environment(project_root: Path = PROJECT_ROOT) -> None:
    if not sys.executable.lower().startswith(str(project_root / ".venv" / "Scripts").lower()):
        raise PreflightError(f"preflight must use project venv python, got: {sys.executable}")
    _configure_tk_library_paths()
    try:
        import tkinter as tk
    except ImportError as exc:
        raise PreflightError(
            "Tk 初始化失败。常见原因是把 .venv 从另一台电脑直接拷过来，"
            "或新电脑 Python 安装缺少 Tcl/Tk；请在当前电脑重建 .venv。"
        ) from exc

    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except tk.TclError as exc:
        raise PreflightError(
            "Tk 初始化失败。常见原因是把 .venv 从另一台电脑直接拷过来，"
            "或新电脑 Python 安装缺少 Tcl/Tk；请在当前电脑重建 .venv。"
        ) from exc


def _configure_tk_library_paths() -> None:
    _set_library_path_if_present("TCL_LIBRARY", "tcl8.6", "init.tcl")
    _set_library_path_if_present("TK_LIBRARY", "tk8.6", "tk.tcl")


def _set_library_path_if_present(env_var: str, directory_name: str, marker_file: str) -> None:
    if os.environ.get(env_var):
        return
    candidate = Path(sys.base_prefix) / "tcl" / directory_name
    if (candidate / marker_file).is_file():
        os.environ[env_var] = str(candidate)


def print_runtime_summary(project_root: Path = PROJECT_ROOT) -> None:
    print(f"[INFO] python: {sys.executable}", flush=True)
    print(f"[INFO] version: {sys.version.split()[0]}", flush=True)
    print(f"[INFO] project: {project_root}", flush=True)
    print(f"[INFO] temp: {os.environ.get('TEMP', '')}", flush=True)


def _project_temp_dir(project_root: Path) -> Path:
    temp_dir = project_root / ".local-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _pytest_basetemp(project_root: Path) -> Path:
    return _project_temp_dir(project_root) / f"pytest-{os.getpid()}-{time.monotonic_ns()}"


def _expand_runtime_args(args: Sequence[str], project_root: Path) -> tuple[str, ...]:
    basetemp = None
    expanded: list[str] = []
    for arg in args:
        if arg == PYTEST_BASETEMP_TOKEN:
            if basetemp is None:
                basetemp = _pytest_basetemp(project_root)
            expanded.append(str(basetemp))
        else:
            expanded.append(str(arg))
    return tuple(expanded)


def _subprocess_runner(args: Sequence[str], cwd: Path) -> int:
    temp_dir = _project_temp_dir(cwd)
    env = os.environ.copy()
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    return subprocess.run(args, cwd=cwd, check=False, env=env).returncode


def run_external_checks(
    project_root: Path = PROJECT_ROOT,
    *,
    runner: Runner = _subprocess_runner,
    commands: Sequence[tuple[str, Sequence[str]]] = DEFAULT_COMMANDS,
) -> int:
    for label, args in commands:
        code = runner(_expand_runtime_args(args, project_root), project_root)
        if code != 0:
            print(f"[FAIL] {label}: exit code {code}", flush=True)
            return code
        print(f"[OK] {label}", flush=True)
    return 0


def main() -> int:
    try:
        validate_project_root(PROJECT_ROOT)
        validate_release_files(PROJECT_ROOT)
        validate_gui_defaults()
        validate_runtime_environment(PROJECT_ROOT)
    except PreflightError as exc:
        print(f"[FAIL] release defaults locked: {exc}", flush=True)
        return 1

    print("[OK] release defaults locked", flush=True)
    print_runtime_summary(PROJECT_ROOT)
    code = run_external_checks(PROJECT_ROOT)
    if code != 0:
        return code

    print("READY FOR MATCH", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
