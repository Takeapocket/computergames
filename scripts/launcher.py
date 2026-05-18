from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTEST_BASETEMP_TOKEN = "{PYTEST_BASETEMP}"

CommandKind = Literal["subprocess", "status"]
Runner = Callable[[Sequence[str], Path], int]


class LauncherError(RuntimeError):
    pass


@dataclass(frozen=True)
class LauncherCommand:
    key: str
    aliases: tuple[str, ...]
    label: str
    description: str
    kind: CommandKind
    args: tuple[str, ...] = ()


def python_executable(project_root: Path) -> Path:
    return project_root / ".venv" / "Scripts" / "python.exe"


def ensure_venv_python(project_root: Path) -> Path:
    python_path = python_executable(project_root)
    if not python_path.exists():
        raise LauncherError(
            f"未找到项目虚拟环境 Python：{python_path}\n"
            '请先在项目根目录创建虚拟环境并安装 pytest：python -m venv .venv && '
            '& ".venv/Scripts/python.exe" -m pip install pytest'
        )
    return python_path


def build_commands(project_root: Path = PROJECT_ROOT) -> tuple[LauncherCommand, ...]:
    python_path = str(python_executable(project_root))
    return (
        LauncherCommand(
            key="1",
            aliases=("gui", "run_gui"),
            label="启动 GUI",
            description="打开离线比赛 GUI。",
            kind="subprocess",
            args=(python_path, "scripts/run_gui.py"),
        ),
        LauncherCommand(
            key="2",
            aliases=("preflight", "check"),
            label="一键赛前总检查",
            description="锁定 release 默认配置，运行 pytest、smoke、S2 rehearsal 和小样本 timing probe。",
            kind="subprocess",
            args=(python_path, "scripts/preflight_check.py"),
        ),
        LauncherCommand(
            key="3",
            aliases=("pytest", "test"),
            label="完整 pytest",
            description="运行全部自动测试。",
            kind="subprocess",
            args=(
                python_path,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                PYTEST_BASETEMP_TOKEN,
            ),
        ),
        LauncherCommand(
            key="4",
            aliases=("smoke",),
            label="smoke 测试",
            description="运行最小规则/悔棋 smoke 测试。",
            kind="subprocess",
            args=(python_path, "scripts/smoke_test.py"),
        ),
        LauncherCommand(
            key="5",
            aliases=("s2", "rehearsal"),
            label="S2 全流程演练",
            description="运行 headless GUI 比赛全流程 rehearsal。",
            kind="subprocess",
            args=(python_path, "scripts/s2_rehearsal.py"),
        ),
        LauncherCommand(
            key="6",
            aliases=("timing", "probe"),
            label="timing budget probe",
            description="运行 16 样本步时预算探针并刷新 preflight timing 报告。",
            kind="subprocess",
            args=(
                python_path,
                "scripts/timing_budget_probe.py",
                "--samples",
                "16",
                "--output",
                "reports/preflight_timing_budget_probe.md",
                "--json-output",
                "reports/preflight_timing_budget_probe.json",
            ),
        ),
        LauncherCommand(
            key="7",
            aliases=("status", "release"),
            label="显示 release/default 状态",
            description="显示当前 release 默认 AI、布局和比赛时限。",
            kind="status",
        ),
    )


def format_menu(commands: Sequence[LauncherCommand]) -> str:
    lines = [
        "爱恩斯坦棋比赛程序启动器",
        "",
        "请选择操作：",
    ]
    for command in commands:
        lines.append(f"  {command.key}. {command.label} - {command.description}")
    lines.append("  0. 退出")
    return "\n".join(lines)


def resolve_command(commands: Sequence[LauncherCommand], choice: str) -> LauncherCommand:
    normalized = choice.strip().lower()
    for command in commands:
        if normalized == command.key or normalized in command.aliases:
            return command
    raise LauncherError(f"未知选项：{choice}")


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


def _format_args(args: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(args))


def print_release_status(project_root: Path = PROJECT_ROOT) -> None:
    config_path = project_root / "release" / "v1.0" / "config.json"
    params_path = project_root / "release" / "v1.0" / "default_params.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        params = json.loads(params_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LauncherError(f"缺少 release 配置文件：{exc.filename}") from exc
    except json.JSONDecodeError as exc:
        raise LauncherError(f"release 配置 JSON 无效：{exc}") from exc

    print("当前 release/default 状态：")
    print(f"- 项目根目录：{project_root}")
    print(f"- 默认 AI：{config.get('default_ai')} / params.ai={params.get('ai')}")
    print(f"- fallback AI：{params.get('fallback_ai')}")
    print(f"- 默认布局：{config.get('default_layout')}")
    print(f"- 单方时限：{config.get('time_limit_seconds')} 秒")
    print(f"- rollout 数：{params.get('rollouts_per_move')}")
    print(f"- step deadline：{params.get('max_step_time_ms')} ms")
    print(f"- playout_policy：{params.get('playout_policy')}")
    print(f"- cutoff_eval：{params.get('cutoff_eval')}")


def run_command(
    command: LauncherCommand,
    project_root: Path = PROJECT_ROOT,
    *,
    runner: Runner = _subprocess_runner,
) -> int:
    if command.kind == "status":
        print_release_status(project_root)
        return 0
    return runner(_expand_runtime_args(command.args, project_root), project_root)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="爱恩斯坦棋比赛程序一键启动器")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="项目根目录；默认自动取脚本上级目录。",
    )
    parser.add_argument("--list", action="store_true", help="只显示菜单，不执行。")
    parser.add_argument("--dry-run", metavar="CHOICE", help="显示某个选项对应的命令，不执行。")
    parser.add_argument("--run", metavar="CHOICE", help="非交互执行某个选项，例如 --run 2。")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = args.project_root.resolve()
    commands = build_commands(project_root)

    if args.list:
        print(format_menu(commands))
        return 0

    try:
        if args.dry_run:
            command = resolve_command(commands, args.dry_run)
            print(f"{command.label}:")
            if command.kind == "subprocess":
                print(_format_args(_expand_runtime_args(command.args, project_root)))
            else:
                print("内置状态显示")
            return 0
        if args.run:
            command = resolve_command(commands, args.run)
            if command.kind == "subprocess":
                ensure_venv_python(project_root)
            return run_command(command, project_root)

        ensure_venv_python(project_root)
        return _interactive_loop(project_root, commands)
    except LauncherError as exc:
        print(f"[FAIL] {exc}", flush=True)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", flush=True)
        return 130


def _interactive_loop(project_root: Path, commands: Sequence[LauncherCommand]) -> int:
    while True:
        print()
        print(format_menu(commands))
        choice = input("\n输入编号后回车：").strip()
        if choice in {"0", "q", "quit", "exit"}:
            return 0
        try:
            command = resolve_command(commands, choice)
        except LauncherError as exc:
            print(f"[FAIL] {exc}")
            continue

        print(f"\n[RUN] {command.label}")
        if command.kind == "subprocess":
            runtime_args = _expand_runtime_args(command.args, project_root)
            print(_format_args(runtime_args))
            code = _subprocess_runner(runtime_args, project_root)
        else:
            code = run_command(command, project_root)
        if code == 0:
            print(f"[OK] {command.label}")
        else:
            print(f"[FAIL] {command.label}: exit code {code}")
        input("\n按 Enter 返回菜单...")


if __name__ == "__main__":
    raise SystemExit(main())
