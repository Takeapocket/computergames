from __future__ import annotations

import json
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
