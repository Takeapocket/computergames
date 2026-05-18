from __future__ import annotations

from pathlib import Path

import pytest

from scripts import launcher


def _fake_project(tmp_path: Path) -> Path:
    root = _fake_release_project(tmp_path)
    python_exe = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_exe.parent.mkdir(parents=True)
    python_exe.write_text("", encoding="utf-8")
    return root


def _fake_release_project(tmp_path: Path) -> Path:
    release_dir = tmp_path / "release" / "v1.0"
    release_dir.mkdir(parents=True)
    (release_dir / "config.json").write_text(
        '{"default_ai":"rollout","default_layout":"balanced_v1","time_limit_seconds":240}',
        encoding="utf-8",
    )
    (release_dir / "default_params.json").write_text(
        '{"ai":"rollout","fallback_ai":"greedy_risk"}',
        encoding="utf-8",
    )
    return tmp_path


def test_build_commands_cover_match_day_actions(tmp_path) -> None:
    root = _fake_project(tmp_path)

    commands = launcher.build_commands(root)
    labels = {command.key: command.label for command in commands}

    assert labels["1"] == "启动 GUI"
    assert labels["2"] == "一键赛前总检查"
    assert labels["3"] == "完整 pytest"
    assert labels["4"] == "smoke 测试"
    assert labels["5"] == "S2 全流程演练"
    assert labels["6"] == "timing budget probe"
    assert labels["7"] == "显示 release/default 状态"


def test_subprocess_commands_use_project_venv_python(tmp_path) -> None:
    root = _fake_project(tmp_path)
    python_exe = root / ".venv" / "Scripts" / "python.exe"

    commands = launcher.build_commands(root)
    subprocess_commands = [command for command in commands if command.kind == "subprocess"]

    assert subprocess_commands
    assert all(command.args[0] == str(python_exe) for command in subprocess_commands)


def test_pytest_command_uses_project_local_basetemp(tmp_path) -> None:
    root = _fake_project(tmp_path)
    command = launcher.resolve_command(launcher.build_commands(root), "pytest")

    assert "-p" in command.args
    assert "no:cacheprovider" in command.args
    assert "--basetemp" in command.args
    assert command.args[-1] == launcher.PYTEST_BASETEMP_TOKEN


def test_resolve_command_accepts_number_and_label(tmp_path) -> None:
    root = _fake_project(tmp_path)
    commands = launcher.build_commands(root)

    assert launcher.resolve_command(commands, "1").label == "启动 GUI"
    assert launcher.resolve_command(commands, "pytest").label == "完整 pytest"


def test_missing_venv_python_is_reported(tmp_path) -> None:
    with pytest.raises(launcher.LauncherError, match=r"\.venv"):
        launcher.ensure_venv_python(tmp_path)


def test_run_subprocess_command_uses_project_root(tmp_path) -> None:
    root = _fake_project(tmp_path)
    command = launcher.resolve_command(launcher.build_commands(root), "4")
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_runner(args, cwd):
        calls.append((tuple(args), cwd))
        return 0

    assert launcher.run_command(command, root, runner=fake_runner) == 0
    assert calls == [(tuple(command.args), root)]


def test_run_pytest_command_expands_runtime_basetemp(tmp_path) -> None:
    root = _fake_project(tmp_path)
    command = launcher.resolve_command(launcher.build_commands(root), "pytest")
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_runner(args, cwd):
        calls.append((tuple(args), cwd))
        return 0

    assert launcher.run_command(command, root, runner=fake_runner) == 0

    args, cwd = calls[0]
    assert cwd == root
    basetemp = Path(args[args.index("--basetemp") + 1])
    assert basetemp.parent == root / ".local-temp"
    assert basetemp.name.startswith("pytest-")
    assert launcher.PYTEST_BASETEMP_TOKEN not in args


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

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    assert launcher._subprocess_runner(("python", "-V"), tmp_path) == 0
    assert captured["cwd"] == tmp_path
    assert captured["check"] is False
    assert captured["env"]["TEMP"] == str(tmp_path / ".local-temp")
    assert captured["env"]["TMP"] == str(tmp_path / ".local-temp")
    assert (tmp_path / ".local-temp").is_dir()


def test_main_dry_run_prints_command_without_running(tmp_path, capsys) -> None:
    root = _fake_project(tmp_path)

    assert launcher.main(["--project-root", str(root), "--dry-run", "4"]) == 0

    output = capsys.readouterr().out
    assert "smoke 测试" in output
    assert "scripts/smoke_test.py" in output


def test_cmd_launcher_uses_crlf_line_endings() -> None:
    content = (launcher.PROJECT_ROOT / "启动项目.cmd").read_bytes()

    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")


def test_gitattributes_locks_cmd_launcher_to_crlf() -> None:
    attributes = (launcher.PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "启动项目.cmd text eol=crlf" in attributes


def test_main_dry_run_does_not_require_venv_python(tmp_path, capsys) -> None:
    root = _fake_release_project(tmp_path)

    assert launcher.main(["--project-root", str(root), "--dry-run", "4"]) == 0

    output = capsys.readouterr().out
    assert "smoke 测试" in output
    assert "scripts/smoke_test.py" in output


def test_main_status_does_not_require_venv_python(tmp_path, capsys) -> None:
    root = _fake_release_project(tmp_path)

    assert launcher.main(["--project-root", str(root), "--run", "status"]) == 0

    output = capsys.readouterr().out
    assert "当前 release/default 状态" in output
    assert "默认 AI：rollout" in output
