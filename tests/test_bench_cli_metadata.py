from __future__ import annotations

from pathlib import Path

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
