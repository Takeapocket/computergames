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
    """工作树是否有源码层面的未提交改动。

    会跳过 ``reports/*.json`` 与 ``replays/*.json``，因为它们是 bench/match 脚本的输出
    产物，自身就会被脚本覆写——如果不跳过，串行重跑多份 bench 时 git_dirty 会永远是 True
    （第一份 bench 写完后，下一份 bench 启动时就把前一份当成"脏"），无法反映源码状态。
    """
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
    for raw in out.decode("ascii", errors="replace").splitlines():
        if len(raw) < 4:
            continue
        path = raw[3:].strip().strip('"')
        # 处理 rename：旧路径 -> 新路径，新路径才是当前文件
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip().strip('"')
        if not path:
            continue
        if _is_generated_artifact(path):
            continue
        return True
    return False


def _is_generated_artifact(path: str) -> bool:
    return (
        (path.startswith("reports/") and path.endswith(".json"))
        or (path.startswith("replays/") and path.endswith(".json"))
    )


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
