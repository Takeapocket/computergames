from __future__ import annotations

import json

from scripts import timing_budget_probe


def test_summarize_timings_computes_percentiles() -> None:
    summary = timing_budget_probe.summarize_timings([10.0, 20.0, 30.0, 40.0])

    assert summary["avg_ms"] == 25.0
    assert summary["p50_ms"] == 25.0
    assert summary["max_ms"] == 40.0


def test_load_release_default_ai_config_strips_metadata(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(
        json.dumps(
            {
                "ai": "rollout",
                "rollouts_per_move": 32,
                "max_rollout_turns": 80,
                "fallback_ai": "greedy_risk",
                "promotion_report": "reports/ai_promotion_decision.md",
            }
        ),
        encoding="utf-8",
    )

    kind, kwargs = timing_budget_probe.load_release_default_ai_config(path)

    assert kind == "rollout"
    assert kwargs == {"rollouts_per_move": 32, "max_rollout_turns": 80}


def test_write_reports_writes_json_and_markdown(tmp_path) -> None:
    payload = {
        "ai_kind": "rollout",
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "default_layout": "balanced_v1",
        "sample_count": 1,
        "avg_ms": 10.0,
        "p50_ms": 10.0,
        "p95_ms": 10.0,
        "p99_ms": 10.0,
        "max_ms": 10.0,
        "rollout_timed_out_count": 0,
        "rollout_used_fallback_count": 0,
        "illegal_recommendations": 0,
        "exceptions": 0,
        "samples": [],
        "command": "python scripts/timing_budget_probe.py --samples 1",
    }

    md_path = tmp_path / "probe.md"
    json_path = tmp_path / "probe.json"
    timing_budget_probe.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["sample_count"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "P6 Timing Budget Probe" in markdown
    assert "默认 AI、默认布局、release 配置未变" in markdown


def test_write_reports_lists_fallback_samples(tmp_path) -> None:
    payload = {
        "ai_kind": "rollout",
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "default_layout": "balanced_v1",
        "sample_count": 1,
        "avg_ms": 10.0,
        "p50_ms": 10.0,
        "p95_ms": 10.0,
        "p99_ms": 10.0,
        "max_ms": 10.0,
        "rollout_timed_out_count": 1,
        "rollout_used_fallback_count": 1,
        "illegal_recommendations": 0,
        "exceptions": 0,
        "samples": [
            {
                "index": 7,
                "player": "red",
                "dice": 6,
                "legal_moves": 2,
                "elapsed_ms": 720.0,
                "timed_out": True,
                "used_fallback": True,
                "illegal": False,
                "board": "board-key",
            }
        ],
        "command": "python scripts/timing_budget_probe.py --samples 1",
    }

    md_path = tmp_path / "probe.md"
    json_path = tmp_path / "probe.json"
    timing_budget_probe.write_reports(payload, md_path, json_path)

    markdown = md_path.read_text(encoding="utf-8")
    assert "## Flagged Samples" in markdown
    assert "index=7" in markdown
    assert "fallback=True" in markdown
