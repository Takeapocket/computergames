"""启动器和预检共享的项目内临时目录与子进程运行支持。"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Sequence


PYTEST_BASETEMP_TOKEN = "{PYTEST_BASETEMP}"


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
