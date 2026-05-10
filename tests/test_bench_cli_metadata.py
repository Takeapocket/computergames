from __future__ import annotations

from pathlib import Path

import pytest

from scripts import quick_bench, run_match
from scripts._bench_meta import build_provenance


ROOT = Path(__file__).resolve().parents[1]


def test_build_provenance_marks_whether_worktree_is_dirty() -> None:
    metadata = build_provenance(
        repo_root=ROOT,
        script_name="quick_bench.py",
        argv=["--red", "random", "--blue", "random"],
        starting_layout_id="default_no_stuck_corner_v1",
    )

    assert "git_dirty" in metadata
    assert isinstance(metadata["git_dirty"], bool)


def test_quick_bench_rejects_red_stuck_penalty_for_non_greedy_ai() -> None:
    with pytest.raises(SystemExit) as exc_info:
        quick_bench.main([
            "--red", "random",
            "--blue", "random",
            "--red-stuck-penalty", "0",
            "--games", "1",
            "--no-save-report",
        ])

    assert exc_info.value.code == 2


def test_quick_bench_rejects_blue_stuck_penalty_for_non_greedy_ai() -> None:
    with pytest.raises(SystemExit) as exc_info:
        quick_bench.main([
            "--red", "random",
            "--blue", "random",
            "--blue-stuck-penalty", "0",
            "--games", "1",
            "--no-save-report",
        ])

    assert exc_info.value.code == 2


def test_run_match_rejects_stuck_penalty_for_non_greedy_ai() -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_match.main([
            "--red", "random",
            "--blue", "random",
            "--red-stuck-penalty", "0",
            "--no-save-replay",
        ])

    assert exc_info.value.code == 2
