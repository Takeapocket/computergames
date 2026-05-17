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


def test_validate_project_root_rejects_wrong_working_directory(tmp_path) -> None:
    project_root = tmp_path / "project"
    wrong_cwd = tmp_path / "elsewhere"
    project_root.mkdir()
    wrong_cwd.mkdir()

    with pytest.raises(preflight_check.PreflightError, match="project root"):
        preflight_check.validate_project_root(project_root, wrong_cwd)


def test_validate_release_files_rejects_layout_drift(tmp_path) -> None:
    _write_release_files(tmp_path, default_layout="aggressive_v1")

    with pytest.raises(preflight_check.PreflightError, match="default_layout"):
        preflight_check.validate_release_files(tmp_path)


def test_run_external_checks_reports_ok_lines(tmp_path, capsys) -> None:
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
