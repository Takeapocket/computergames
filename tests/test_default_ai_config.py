import json
from pathlib import Path

import gui.main_window as main_window


def test_gui_default_recommender_is_rollout():
    assert main_window.DEFAULT_RECOMMENDER_KIND == "rollout"
    assert main_window.DEFAULT_RECOMMENDER_KWARGS == {
        "rollouts_per_move": 16,
        "max_rollout_turns": 80,
        "max_step_time_ms": 500.0,
        "epsilon": 0.15,
    }


def test_release_default_params_match_gui_recommender():
    payload = json.loads(Path("release/v1.0/default_params.json").read_text(encoding="utf-8"))

    assert payload == {
        "ai": main_window.DEFAULT_RECOMMENDER_KIND,
        **main_window.DEFAULT_RECOMMENDER_KWARGS,
        "fallback_ai": "greedy_risk",
        "promotion_report": "reports/ai_promotion_decision.md",
    }
