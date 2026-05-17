from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

from gui import main_window
from gui.opening_panel import OpeningPanel
from tests.tk_support import make_hidden_tk_root


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RECOMMENDER_KWARGS = {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0,
}

EXPECTED_DEFAULT_PARAMS = {
    "ai": "rollout",
    **EXPECTED_RECOMMENDER_KWARGS,
    "fallback_ai": "greedy_risk",
    "promotion_report": "reports/ai_promotion_decision.md",
}


def _read_json(relative_path: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def test_gui_default_recommender_is_locked_to_p3_rollout() -> None:
    assert main_window.DEFAULT_RECOMMENDER_KIND == "rollout"
    assert main_window.DEFAULT_RECOMMENDER_KWARGS == EXPECTED_RECOMMENDER_KWARGS


def test_release_default_params_match_gui_defaults() -> None:
    assert _read_json("release/v1.0/default_params.json") == EXPECTED_DEFAULT_PARAMS


def test_release_config_locks_balanced_v1_layout() -> None:
    config = _read_json("release/v1.0/config.json")
    assert config["default_ai"] == "rollout"
    assert config["default_layout"] == "balanced_v1"
    assert config["board_size"] == 5
    assert config["time_limit_seconds"] == 240
    assert config["max_games_per_match"] == 7
    assert config["games_to_win_match"] == 4
    assert config["offline_required"] is True


def test_opening_panel_initial_layout_is_balanced_v1(tmp_path) -> None:
    root = make_hidden_tk_root()
    panel = OpeningPanel(root, on_confirm=lambda selection: None, layout_directory=tmp_path)
    try:
        assert panel.layout_var.get() == "balanced_v1"
    finally:
        panel.destroy()


def test_release_readme_documents_default_ai_and_layout() -> None:
    readme = (PROJECT_ROOT / "release/v1.0/README.md").read_text(encoding="utf-8")
    assert "我方推荐 AI = `rollout` kind + P3 promotion 显式参数" in readme
    assert "默认 `balanced_v1`" in readme


def test_release_docs_promote_preflight_as_match_gate() -> None:
    release_readme = (PROJECT_ROOT / "release/v1.0/README.md").read_text(encoding="utf-8")
    checklist = (PROJECT_ROOT / "docs/MATCH_CHECKLIST.md").read_text(encoding="utf-8")

    for text in (release_readme, checklist):
        assert "scripts/preflight_check.py" in text
        assert "READY FOR MATCH" in text


def test_release_report_records_current_p6_to_p9_preflight_state() -> None:
    text = (PROJECT_ROOT / "release/v1.0/test_report.md").read_text(encoding="utf-8")

    assert "614 passed" in text
    for phase in ("P6", "P7", "P8", "P9"):
        assert phase in text
    assert "READY FOR MATCH" in text


def test_release_readme_uses_controlled_rollback_language() -> None:
    text = (PROJECT_ROOT / "release/v1.0/README.md").read_text(encoding="utf-8")

    assert "不要在比赛中直接编辑 `gui/main_window.py` 默认常量" in text
    assert "临时把 `DEFAULT_RECOMMENDER_KIND`" not in text


def test_root_readme_does_not_use_bare_rollout_as_release_baseline_example() -> None:
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "--red rollout --blue greedy_risk" not in text
    assert "--blue rollout --games" not in text


def test_r2_smoke_imports_from_repo_root_when_cwd_differs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry not in {"", ".", str(PROJECT_ROOT)}])
    old_auto_save_path = main_window.AUTO_SAVE_PATH
    old_auto_save_match_path = main_window.AUTO_SAVE_MATCH_PATH

    try:
        module = runpy.run_path(str(PROJECT_ROOT / "scripts/r2_smoke.py"), run_name="__r2_smoke_import_test__")
    finally:
        main_window.AUTO_SAVE_PATH = old_auto_save_path
        main_window.AUTO_SAVE_MATCH_PATH = old_auto_save_match_path

    assert module["ROOT"] == PROJECT_ROOT
    assert str(PROJECT_ROOT) in sys.path
