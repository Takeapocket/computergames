from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import preflight_check


def _write_release_files(root: Path, *, default_layout: str = "balanced_v1", config_overrides: dict | None = None) -> None:
    release_dir = root / "release" / "v1.0"
    release_dir.mkdir(parents=True)
    config = {
        "version": "1.0",
        "default_ai": "rollout",
        "default_layout": default_layout,
        "board_size": 5,
        "time_limit_seconds": 240,
        "max_games_per_match": 7,
        "games_to_win_match": 4,
        "offline_required": True,
    }
    if config_overrides:
        config.update(config_overrides)
    (release_dir / "default_params.json").write_text(
        json.dumps(preflight_check.EXPECTED_DEFAULT_PARAMS),
        encoding="utf-8",
    )
    (release_dir / "config.json").write_text(
        json.dumps(config),
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


@pytest.mark.parametrize(
    ("key", "bad_value"),
    [
        ("board_size", 6),
        ("time_limit_seconds", 180),
        ("max_games_per_match", 5),
        ("games_to_win_match", 3),
        ("offline_required", False),
    ],
)
def test_validate_release_files_rejects_competition_config_drift(tmp_path, key, bad_value) -> None:
    _write_release_files(tmp_path, config_overrides={key: bad_value})

    with pytest.raises(preflight_check.PreflightError, match=key):
        preflight_check.validate_release_files(tmp_path)


def test_required_files_include_release_signoff_docs() -> None:
    assert "release/v1.0/README.md" in preflight_check.REQUIRED_FILES
    assert "release/v1.0/test_report.md" in preflight_check.REQUIRED_FILES
    assert "release/v1.0/known_limitations.md" in preflight_check.REQUIRED_FILES


def test_required_files_include_one_click_launcher() -> None:
    assert "启动项目.cmd" in preflight_check.REQUIRED_FILES
    assert "scripts/launcher.py" in preflight_check.REQUIRED_FILES


def test_default_commands_include_small_timing_probe_gate() -> None:
    timing_commands = [
        tuple(args)
        for _label, args in preflight_check.DEFAULT_COMMANDS
        if "scripts/timing_budget_probe.py" in args
    ]

    assert len(timing_commands) == 1
    timing_command = timing_commands[0]
    samples_index = timing_command.index("--samples")
    assert int(timing_command[samples_index + 1]) <= 24
    assert "--output" in timing_command
    assert "--json-output" in timing_command


def test_default_pytest_command_uses_project_local_basetemp() -> None:
    pytest_commands = [
        tuple(args)
        for _label, args in preflight_check.DEFAULT_COMMANDS
        if "-m" in args and "pytest" in args
    ]

    assert len(pytest_commands) == 1
    pytest_command = pytest_commands[0]
    assert "-p" in pytest_command
    assert "no:cacheprovider" in pytest_command
    assert "--tb=short" in pytest_command
    assert "--maxfail=1" in pytest_command
    assert "--basetemp" in pytest_command
    assert pytest_command[-1] == preflight_check.PYTEST_BASETEMP_TOKEN


def test_validate_runtime_environment_rejects_non_venv_python(tmp_path) -> None:
    with pytest.raises(preflight_check.PreflightError, match="project venv"):
        preflight_check.validate_runtime_environment(tmp_path)


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


def test_run_external_checks_expands_runtime_basetemp(tmp_path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(args, cwd):
        calls.append(tuple(args))
        return 0

    result = preflight_check.run_external_checks(
        tmp_path,
        runner=fake_run,
        commands=(("pytest", ("python", "-m", "pytest", "--basetemp", preflight_check.PYTEST_BASETEMP_TOKEN)),),
    )

    assert result == 0
    args = calls[0]
    basetemp = Path(args[args.index("--basetemp") + 1])
    assert basetemp.parent == tmp_path / ".local-temp"
    assert basetemp.name.startswith("pytest-")
    assert preflight_check.PYTEST_BASETEMP_TOKEN not in args


def test_subprocess_runner_uses_project_local_temp(tmp_path, monkeypatch) -> None:
    captured = {}

    def fake_run(args, cwd, check, env):
        captured["args"] = tuple(args)
        captured["cwd"] = cwd
        captured["check"] = check
        captured["env"] = env

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(preflight_check.subprocess, "run", fake_run)

    assert preflight_check._subprocess_runner(("python", "-V"), tmp_path) == 0
    assert captured["cwd"] == tmp_path
    assert captured["check"] is False
    assert captured["env"]["TEMP"] == str(tmp_path / ".local-temp")
    assert captured["env"]["TMP"] == str(tmp_path / ".local-temp")
    assert (tmp_path / ".local-temp").is_dir()


def test_main_success_output_includes_ready_for_match(monkeypatch, capsys) -> None:
    monkeypatch.setattr(preflight_check, "validate_project_root", lambda project_root: None)
    monkeypatch.setattr(preflight_check, "validate_release_files", lambda project_root: None)
    monkeypatch.setattr(preflight_check, "validate_gui_defaults", lambda: None)
    monkeypatch.setattr(preflight_check, "run_external_checks", lambda project_root: 0)

    assert preflight_check.main() == 0

    output = capsys.readouterr().out
    assert "[OK] release defaults locked" in output
    assert "READY FOR MATCH" in output


def test_main_failure_output_omits_ready_for_match(monkeypatch, capsys) -> None:
    def fail_release_files(project_root):
        raise preflight_check.PreflightError("time_limit_seconds drifted")

    monkeypatch.setattr(preflight_check, "validate_project_root", lambda project_root: None)
    monkeypatch.setattr(preflight_check, "validate_release_files", fail_release_files)
    monkeypatch.setattr(preflight_check, "validate_gui_defaults", lambda: None)

    assert preflight_check.main() == 1

    output = capsys.readouterr().out
    assert "[FAIL] release defaults locked: time_limit_seconds drifted" in output
    assert "READY FOR MATCH" not in output
