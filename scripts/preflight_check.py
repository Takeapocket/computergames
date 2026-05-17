from __future__ import annotations

import json
import subprocess
import sys
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
    ("pytest -q", (sys.executable, "-m", "pytest", "-q")),
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
            print(f"[FAIL] {label}: exit code {code}", flush=True)
            return code
        print(f"[OK] {label}", flush=True)
    return 0


def main() -> int:
    try:
        validate_project_root(PROJECT_ROOT)
        validate_release_files(PROJECT_ROOT)
        validate_gui_defaults()
    except PreflightError as exc:
        print(f"[FAIL] release defaults locked: {exc}", flush=True)
        return 1

    print("[OK] release defaults locked", flush=True)
    code = run_external_checks(PROJECT_ROOT)
    if code != 0:
        return code

    print("READY FOR MATCH", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
