from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.types import Player


def test_main_passes_ai_kwargs_to_match_probe(monkeypatch):
    from scripts import perf_probe

    captured = []

    def fake_run_probe(**kwargs):
        captured.append(kwargs)
        return {"games": kwargs["games"]}

    def fake_run_rollout_decision_probe(**kwargs):
        return {"samples": kwargs["samples"]}

    monkeypatch.setattr(perf_probe, "run_probe", fake_run_probe)
    monkeypatch.setattr(
        perf_probe,
        "run_rollout_decision_probe",
        fake_run_rollout_decision_probe,
    )

    assert (
        perf_probe.main(
            [
                "--games",
                "0",
                "--samples",
                "0",
                "--max-turns",
                "24",
                "--red",
                "expectimax_v2",
                "--red-kwargs",
                '{"depth": 2, "chance_pruning": "star1"}',
                "--blue",
                "rollout",
                "--blue-kwargs",
                '{"rollouts_per_move": 1}',
            ]
        )
        == 0
    )

    assert captured == [
        {
            "red_kind": "expectimax_v2",
            "blue_kind": "rollout",
            "games": 0,
            "seed": 2026,
            "layout_id": "balanced_v1",
            "max_turns": 24,
            "red_kwargs": {"depth": 2, "chance_pruning": "star1"},
            "blue_kwargs": {"rollouts_per_move": 1},
        }
    ]


def test_main_rejects_invalid_json_kwargs():
    from scripts import perf_probe

    with pytest.raises(SystemExit):
        perf_probe.main(["--red-kwargs", "{"])


@pytest.mark.parametrize("payload", ["[]", "42", '"depth"'])
def test_main_rejects_non_object_json_kwargs(payload):
    from scripts import perf_probe

    with pytest.raises(SystemExit):
        perf_probe.main(["--red-kwargs", payload])


def test_run_rollout_decision_probe_restores_instrumented_objects():
    import ai.rollout_ai as rollout_module
    from core.game_state import GameState
    from scripts import perf_probe

    original_serialize = GameState.__dict__["serialize"]
    original_deserialize = GameState.__dict__["deserialize"]
    original_clone = GameState.__dict__["clone"]
    original_legal_moves = GameState.__dict__["legal_moves"]
    original_greedy_ai = rollout_module.GreedyAI
    original_random = rollout_module.random.Random

    perf_probe.run_rollout_decision_probe(samples=0, seed=2026)

    assert GameState.__dict__["serialize"] is original_serialize
    assert GameState.__dict__["deserialize"] is original_deserialize
    assert GameState.__dict__["clone"] is original_clone
    assert GameState.__dict__["legal_moves"] is original_legal_moves
    assert rollout_module.GreedyAI is original_greedy_ai
    assert rollout_module.random.Random is original_random


def test_run_probe_aggregates_match_timing(monkeypatch):
    from scripts import perf_probe

    def fake_build_ai(kind, *, seed=None, **kwargs):
        return {"kind": kind, "seed": seed, "kwargs": kwargs}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=Player.RED,
            turns=4,
            illegal_moves=0,
            crashes=0,
            timeouts=0,
            step_times_ms=[1.0, 2.0, 3.0],
        )

    monkeypatch.setattr(perf_probe, "build_ai", fake_build_ai)
    monkeypatch.setattr(perf_probe, "play_one_game", fake_play_one_game)

    metrics = perf_probe.run_probe(
        red_kind="expectimax_v2",
        blue_kind="rollout",
        games=2,
        seed=2026,
        layout_id="balanced_v1",
        max_turns=24,
        red_kwargs={"depth": 2, "chance_pruning": "star1"},
        blue_kwargs={"rollouts_per_move": 1},
    )

    assert metrics["games"] == 2
    assert metrics["turns"] == 8
    assert metrics["steps"] == 6
    assert metrics["average_step_time_ms"] == 2.0
    assert metrics["max_step_time_ms"] == 3.0
    assert metrics["steps_per_second"] > 0.0
    assert metrics["red"] == {
        "kind": "expectimax_v2",
        "kwargs": {"depth": 2, "chance_pruning": "star1"},
    }
    assert metrics["blue"] == {"kind": "rollout", "kwargs": {"rollouts_per_move": 1}}
    assert metrics["seed"] == 2026
    assert metrics["layout_id"] == "balanced_v1"
    assert metrics["max_turns"] == 24


def test_run_rollout_decision_probe_reports_root_visits(monkeypatch):
    from scripts import perf_probe

    class FakeRolloutAI:
        def __init__(self, **kwargs):
            self.last_root_stats = []

        def choose_move(self, state, dice):
            self.last_root_stats = [
                SimpleNamespace(visits=3),
                SimpleNamespace(visits=4),
            ]
            return state.legal_moves(state.current_player, dice)[0]

    monkeypatch.setattr(perf_probe, "RolloutAI", FakeRolloutAI)

    metrics = perf_probe.run_rollout_decision_probe(samples=2, seed=2026)

    assert metrics["samples"] == 2
    assert metrics["root_visits"] == 14
    assert metrics["root_visits_per_second"] > 0.0


def test_run_rollout_decision_probe_reports_micro_counters():
    from scripts import perf_probe

    metrics = perf_probe.run_rollout_decision_probe(
        samples=1,
        seed=2026,
        rollout_kwargs={
            "rollouts_per_move": 1,
            "close_sample_rollouts_per_move": 1,
            "max_rollout_turns": 1,
            "max_step_time_ms": 100.0,
            "deadline_safety_ms": 0.0,
        },
    )

    instrumentation = metrics["instrumentation"]
    expected_keys = {
        "game_state_serialize_calls",
        "game_state_deserialize_calls",
        "game_state_clone_calls",
        "legal_moves_calls",
        "greedy_ai_constructs",
        "rng_constructs",
    }
    assert expected_keys <= instrumentation.keys()
    assert all(isinstance(instrumentation[key], int) for key in expected_keys)
    assert instrumentation["game_state_serialize_calls"] == 0
    assert instrumentation["game_state_deserialize_calls"] == 0
    assert instrumentation["game_state_clone_calls"] > 0
    assert instrumentation["legal_moves_calls"] > 0
    assert instrumentation["greedy_ai_constructs"] > 0
    assert instrumentation["rng_constructs"] > 0
