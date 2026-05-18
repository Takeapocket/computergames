from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.match import ai_version_signature, build_ai, default_starting_state
from core.types import Player
from scripts import bench_ai


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS = {
    "rollouts_per_move": 64,
    "max_rollout_turns": 80,
    "max_step_time_ms": 2000.0,
    "epsilon": 0.05,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 96,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 80.0,
}

STRONG_ROLLOUT_EXPECTED = {
    "rollout_strong_48": {
        "rollouts_per_move": 48,
        "max_rollout_turns": 80,
        "max_step_time_ms": 1500.0,
        "epsilon": 0.08,
        "close_sample_margin": 0.08,
        "close_sample_rollouts_per_move": 64,
        "low_confidence_margin": 0.08,
        "playout_policy": "greedy_risk",
        "cutoff_eval": "zweistein",
        "deadline_safety_ms": 50.0,
    },
    "rollout_strong_64": {
        "rollouts_per_move": 64,
        "max_rollout_turns": 80,
        "max_step_time_ms": 2000.0,
        "epsilon": 0.08,
        "close_sample_margin": 0.08,
        "close_sample_rollouts_per_move": 96,
        "low_confidence_margin": 0.08,
        "playout_policy": "greedy_risk",
        "cutoff_eval": "zweistein",
        "deadline_safety_ms": 80.0,
    },
    "rollout_strong_64_loweps": {
        "rollouts_per_move": 64,
        "max_rollout_turns": 80,
        "max_step_time_ms": 2000.0,
        "epsilon": 0.05,
        "close_sample_margin": 0.08,
        "close_sample_rollouts_per_move": 96,
        "low_confidence_margin": 0.08,
        "playout_policy": "greedy_risk",
        "cutoff_eval": "zweistein",
        "deadline_safety_ms": 80.0,
    },
    "rollout_strong_96": {
        "rollouts_per_move": 96,
        "max_rollout_turns": 80,
        "max_step_time_ms": 3000.0,
        "epsilon": 0.08,
        "close_sample_margin": 0.08,
        "close_sample_rollouts_per_move": 128,
        "low_confidence_margin": 0.08,
        "playout_policy": "greedy_risk",
        "cutoff_eval": "zweistein",
        "deadline_safety_ms": 120.0,
    },
}


@pytest.mark.parametrize("kind, expected", STRONG_ROLLOUT_EXPECTED.items())
def test_build_ai_strong_rollout_profiles_have_expected_params(kind: str, expected: dict) -> None:
    ai = build_ai(kind, seed=2026)

    assert ai.name == kind
    for attr, value in expected.items():
        assert getattr(ai, attr) == value


@pytest.mark.parametrize("kind, expected", STRONG_ROLLOUT_EXPECTED.items())
def test_strong_rollout_profiles_record_signature(kind: str, expected: dict) -> None:
    signature = ai_version_signature(build_ai(kind, seed=2026))

    assert signature["name"] == kind
    for attr, value in expected.items():
        assert signature[attr] == value


def test_strong_rollout_profiles_allow_ai_kwargs_override_defaults() -> None:
    ai = build_ai(
        "rollout_strong_64",
        seed=2026,
        rollouts_per_move=3,
        max_step_time_ms=25.0,
        epsilon=0.01,
    )

    assert ai.rollouts_per_move == 3
    assert ai.max_step_time_ms == 25.0
    assert ai.epsilon == 0.01
    assert ai.close_sample_rollouts_per_move == 96


@pytest.mark.parametrize("kind", STRONG_ROLLOUT_EXPECTED)
def test_strong_rollout_profiles_choose_legal_move_with_small_override(kind: str) -> None:
    state = default_starting_state()
    ai = build_ai(
        kind,
        seed=2026,
        rollouts_per_move=1,
        close_sample_rollouts_per_move=1,
        max_step_time_ms=50.0,
    )

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)


def test_release_default_params_json_remains_unchanged() -> None:
    data = json.loads((PROJECT_ROOT / "release/v1.0/default_params.json").read_text(encoding="utf-8"))

    assert data == {
        "ai": "rollout",
        **EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS,
        "fallback_ai": "greedy_risk",
        "promotion_report": "reports/ai_promotion_decision.md",
    }


def test_gui_default_recommender_remains_unchanged() -> None:
    from gui import main_window

    assert main_window.DEFAULT_RECOMMENDER_KIND == "rollout"
    assert main_window.DEFAULT_RECOMMENDER_KWARGS == EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS


@pytest.mark.parametrize("kind", STRONG_ROLLOUT_EXPECTED)
def test_bench_ai_strong_rollout_profiles_use_release_default_opponent(kind: str) -> None:
    profile = bench_ai._resolve_profile(kind, "candidate")

    assert profile["opponent"] == "rollout"
    assert profile["opponent_kwargs"] == bench_ai.RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert profile["starting_layout"] == "balanced_v1"
    assert profile["games_per_side"] == 25

    candidate = build_ai(kind, seed=1, **profile.get("candidate_kwargs", {}))
    opponent = build_ai(profile["opponent"], seed=2, **profile["opponent_kwargs"])

    assert ai_version_signature(candidate)["name"] == kind
    assert ai_version_signature(opponent) == {
        "name": "rollout",
        **EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS,
    }


def _fake_result(*, winner: Player, players: list[Player], step_times_ms: list[float]):
    return SimpleNamespace(
        winner=winner,
        turns=len(players),
        illegal_moves=0,
        crashes=0,
        timeouts=0,
        step_times_ms=step_times_ms,
        record=SimpleNamespace(steps=[SimpleNamespace(player=player) for player in players]),
    )


def test_bench_ai_aggregate_estimates_per_side_thinking_time() -> None:
    summary = bench_ai._aggregate(
        [
            (
                _fake_result(
                    winner=Player.RED,
                    players=[Player.RED, Player.BLUE, Player.RED],
                    step_times_ms=[1000.0, 2000.0, 3000.0],
                ),
                {},
            ),
            (
                _fake_result(
                    winner=Player.BLUE,
                    players=[Player.BLUE],
                    step_times_ms=[5000.0],
                ),
                {},
            ),
        ],
        candidate_side=Player.RED,
    )

    assert summary["total_step_time_ms"] == 11000.0
    assert summary["average_turns"] == 2.0
    assert summary["max_red_thinking_seconds"] == 4.0
    assert summary["max_blue_thinking_seconds"] == 5.0
    assert summary["avg_red_thinking_seconds"] == 2.0
    assert summary["avg_blue_thinking_seconds"] == 3.5


def test_bench_ai_combine_preserves_per_side_thinking_time() -> None:
    red = bench_ai._aggregate(
        [
            (
                _fake_result(
                    winner=Player.RED,
                    players=[Player.RED, Player.BLUE],
                    step_times_ms=[1000.0, 2000.0],
                ),
                {},
            )
        ],
        candidate_side=Player.RED,
    )
    blue = bench_ai._aggregate(
        [
            (
                _fake_result(
                    winner=Player.BLUE,
                    players=[Player.RED, Player.BLUE],
                    step_times_ms=[3000.0, 4000.0],
                ),
                {},
            )
        ],
        candidate_side=Player.BLUE,
    )

    combined = bench_ai._combine(red, blue)

    assert combined["total_step_time_ms"] == 10000.0
    assert combined["average_turns"] == 2.0
    assert combined["max_red_thinking_seconds"] == 3.0
    assert combined["max_blue_thinking_seconds"] == 4.0
    assert combined["avg_red_thinking_seconds"] == 2.0
    assert combined["avg_blue_thinking_seconds"] == 3.0


def test_strong_rollout_decision_stops_below_52_percent() -> None:
    decision = bench_ai._strong_rollout_decision(
        "rollout_strong_48",
        "candidate",
        {
            "games": 50,
            "candidate_win_rate": 0.50,
            "candidate_win_ci95": [0.37, 0.63],
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "max_step_time_ms": 1234.0,
            "max_red_thinking_seconds": 12.0,
            "max_blue_thinking_seconds": 10.0,
        },
        gates_ok=False,
    )

    assert decision["status"] == "stop"
    assert decision["passed_52_gate"] is False
    assert decision["passed_55_gate"] is False
    assert decision["suggest_expansion"] is False
    assert decision["default_config_changed"] is False
    assert decision["core_rules_changed"] is False


def test_strong_rollout_decision_blocks_failed_candidate_gate() -> None:
    decision = bench_ai._strong_rollout_decision(
        "rollout_strong_64",
        "candidate",
        {
            "games": 50,
            "candidate_win_rate": 0.58,
            "candidate_win_ci95": [0.44, 0.70],
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_step_time_ms": 550.0,
            "p95_step_time_ms": 1700.0,
            "p99_step_time_ms": 1900.0,
            "max_step_time_ms": 1920.0,
            "max_red_thinking_seconds": 10.5,
            "max_blue_thinking_seconds": 8.4,
            "avg_red_thinking_seconds": 5.3,
            "avg_blue_thinking_seconds": 4.5,
        },
        gates_ok=False,
    )

    assert decision is not None
    assert decision["candidate_gate_pass"] is False
    assert decision["status"] == "blocked_by_candidate_gate"
    assert decision["suggest_expansion"] is False
    assert "candidate gate" in decision["recommendation"]


def test_strong_rollout_candidate_gates_use_timing_budget_gate() -> None:
    gates = bench_ai._resolve_gates("rollout_strong_64", "candidate")

    assert gates["candidate_win_rate"] == ("ge", 0.55)
    assert "average_step_time_ms" not in gates
    assert gates["max_step_time_ms"] == ("le", 5000.0)


def test_write_markdown_records_strong_rollout_decision_and_timing(tmp_path: Path) -> None:
    red = bench_ai._aggregate(
        [(_fake_result(winner=Player.RED, players=[Player.RED], step_times_ms=[1000.0]), {})],
        candidate_side=Player.RED,
    )
    blue = bench_ai._aggregate(
        [(_fake_result(winner=Player.RED, players=[Player.BLUE], step_times_ms=[2000.0]), {})],
        candidate_side=Player.BLUE,
    )
    combined = bench_ai._combine(red, blue)
    decision = bench_ai._strong_rollout_decision(
        "rollout_strong_48",
        "candidate",
        combined,
        gates_ok=False,
    )
    md_path = tmp_path / "report.md"

    bench_ai._write_markdown(
        md_path,
        candidate_kind="rollout_strong_48",
        stage="candidate",
        opponent_kind="rollout",
        args=SimpleNamespace(
            seed=2026,
            games_per_side=1,
            max_turns=12,
            starting_layout="balanced_v1",
            candidate_arg=[],
            opponent_arg=[],
        ),
        candidate_kwargs={},
        opponent_kwargs=EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS,
        candidate_signature={"name": "rollout_strong_48"},
        opponent_signature={"name": "rollout", **EXPECTED_RELEASE_DEFAULT_ROLLOUT_KWARGS},
        red_summary=red,
        blue_summary=blue,
        combined=combined,
        gates_ok=False,
        failures=["candidate_win_rate = 50.0%"],
        gates=bench_ai.STAGE_GATES["candidate"],
        elapsed_seconds=0.1,
        generated_at="2026-05-18T00:00:00+08:00",
        strong_rollout_decision=decision,
    )

    text = md_path.read_text(encoding="utf-8")
    assert "## P14 strong rollout 决策" in text
    assert "- 当前 release 默认配置：未修改" in text
    assert "- core 规则语义：未修改" in text
    assert "max_red_thinking_seconds" in text
    assert "不默认启用，不扩样" in text
