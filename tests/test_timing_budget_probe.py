from __future__ import annotations

import json

import pytest

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


def test_write_reports_marks_preflight_probe_as_quick_check(tmp_path) -> None:
    payload = {
        "ai_kind": "rollout",
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "default_layout": "balanced_v1",
        "sample_count": 16,
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
        "command": "python scripts/timing_budget_probe.py --samples 16",
    }

    md_path = tmp_path / "preflight_timing_budget_probe.md"
    json_path = tmp_path / "preflight_timing_budget_probe.json"
    timing_budget_probe.write_reports(payload, md_path, json_path)

    markdown = md_path.read_text(encoding="utf-8")
    assert "Preflight Timing Budget Probe" in markdown
    assert "16 样本赛前快速核对" in markdown
    assert "不替代历史 P6 120 样本 timing probe 证据" in markdown


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
    assert "rollout_timed_out_count 是 RolloutAI 内部 deadline 信号" in markdown
    assert "preflight 硬失败条件" in markdown
    assert "## Flagged Samples" in markdown
    assert "index=7" in markdown
    assert "fallback=True" in markdown


def _probe_payload(*, illegal_recommendations: int = 0, exceptions: int = 0) -> dict:
    return {
        "sample_count": 1,
        "avg_ms": 10.0,
        "p50_ms": 10.0,
        "p95_ms": 10.0,
        "p99_ms": 10.0,
        "max_ms": 10.0,
        "rollout_timed_out_count": 0,
        "rollout_used_fallback_count": 0,
        "illegal_recommendations": illegal_recommendations,
        "exceptions": exceptions,
        "samples": [],
    }


@pytest.mark.parametrize(
    "field",
    ["exceptions", "illegal_recommendations"],
)
def test_main_returns_nonzero_when_hard_timing_gate_fails(monkeypatch, tmp_path, field) -> None:
    payload = _probe_payload(**{field: 1})
    written: list[dict] = []

    monkeypatch.setattr(timing_budget_probe, "load_release_default_ai_config", lambda: ("rollout", {}))
    monkeypatch.setattr(timing_budget_probe, "collect_samples", lambda **kwargs: payload)
    monkeypatch.setattr(timing_budget_probe, "write_reports", lambda payload, output, json_output: written.append(payload))

    exit_code = timing_budget_probe.main(
        [
            "--samples",
            "1",
            "--output",
            str(tmp_path / "probe.md"),
            "--json-output",
            str(tmp_path / "probe.json"),
        ]
    )

    assert exit_code == 1
    assert written[0][field] == 1


def test_main_allows_timeout_and_fallback_samples_by_default(monkeypatch, tmp_path) -> None:
    payload = {
        **_probe_payload(),
        "rollout_timed_out_count": 1,
        "rollout_used_fallback_count": 1,
    }

    monkeypatch.setattr(timing_budget_probe, "load_release_default_ai_config", lambda: ("rollout", {}))
    monkeypatch.setattr(timing_budget_probe, "collect_samples", lambda **kwargs: payload)
    monkeypatch.setattr(timing_budget_probe, "write_reports", lambda payload, output, json_output: None)

    exit_code = timing_budget_probe.main(
        [
            "--samples",
            "1",
            "--output",
            str(tmp_path / "probe.md"),
            "--json-output",
            str(tmp_path / "probe.json"),
        ]
    )

    assert exit_code == 0
