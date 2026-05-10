"""quick_bench.py 与 run_match.py 共享的 schema v2 元数据工具。

两个 CLI 都生成同一组 provenance 字段（schema_version、git_revision、command、
python_version、starting_layout_id）。集中在此处避免两边代码漂移。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


def git_revision(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "<not-a-git-repo>"
    return out.decode("ascii", errors="replace").strip()


def git_dirty(repo_root: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
    return bool(out.strip())


def greedy_kwargs(stuck_penalty: float | None) -> dict[str, float]:
    if stuck_penalty is None:
        return {}
    return {"stuck_penalty": stuck_penalty}


def build_command(script_name: str, argv: list[str] | None) -> str:
    """Reconstruct the user-visible CLI for `python scripts/<script_name>`."""
    args = argv if argv is not None else sys.argv[1:]
    return " ".join(["python", f"scripts/{script_name}", *args])


def build_provenance(
    *,
    repo_root: Path,
    script_name: str,
    argv: list[str] | None,
    starting_layout_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_revision": git_revision(repo_root),
        "git_dirty": git_dirty(repo_root),
        "command": build_command(script_name, argv),
        "python_version": sys.version.split()[0],
        "starting_layout_id": starting_layout_id,
    }
