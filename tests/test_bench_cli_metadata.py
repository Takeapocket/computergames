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

    from core.rules import RULES_VERSION

    assert metadata["rules_version"] == RULES_VERSION
    assert "git_dirty" in metadata
    assert isinstance(metadata["git_dirty"], bool)


def test_run_match_preserves_record_metadata_and_rules_version(tmp_path, monkeypatch, capsys):
    import json

    from core.rules import RULES_VERSION
    from scripts import run_match

    play_one_game = run_match.play_one_game

    def play_with_source_metadata(**kwargs):
        result = play_one_game(**kwargs)
        result.record.metadata["source_note"] = "retained"
        return result

    monkeypatch.setattr(run_match, "play_one_game", play_with_source_metadata)
    assert run_match.main([
        "--red", "random", "--blue", "random", "--max-turns", "0",
        "--replay-dir", str(tmp_path), "--replay-name", "rules-boundary",
    ]) == 0
    capsys.readouterr()
    saved = json.loads((tmp_path / "rules-boundary.json").read_text(encoding="utf-8"))
    assert saved["metadata"]["source_note"] == "retained"
    assert saved["metadata"]["rules_version"] == RULES_VERSION
    assert saved["metadata"]["ai_versions"]["red"]["rules_version"] == RULES_VERSION
