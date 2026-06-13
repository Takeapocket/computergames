from __future__ import annotations

from types import SimpleNamespace

from core.types import Player


def test_run_rollout_decision_probe_restores_instrumented_objects():
    import ai.rollout_ai as rollout_module
    from core.game_state import GameState
    from scripts import perf_probe

    original_serialize = GameState.__dict__["serialize"]
    original_deserialize = GameState.__dict__["deserialize"]
    original_legal_moves = GameState.__dict__["legal_moves"]
    original_greedy_ai = rollout_module.GreedyAI
    original_random = rollout_module.random.Random

    perf_probe.run_rollout_decision_probe(samples=0, seed=2026)

    assert GameState.__dict__["serialize"] is original_serialize
    assert GameState.__dict__["deserialize"] is original_deserialize
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

    metrics = perf_probe.run_probe(red_kind="random", blue_kind="random", games=2, seed=2026)

    assert metrics["games"] == 2
    assert metrics["turns"] == 8
    assert metrics["steps"] == 6
    assert metrics["average_step_time_ms"] == 2.0
    assert metrics["max_step_time_ms"] == 3.0
    assert metrics["steps_per_second"] > 0.0


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
        "legal_moves_calls",
        "greedy_ai_constructs",
        "rng_constructs",
    }
    assert expected_keys <= instrumentation.keys()
    assert all(isinstance(instrumentation[key], int) for key in expected_keys)
    assert instrumentation["game_state_serialize_calls"] > 0
    assert instrumentation["game_state_deserialize_calls"] > 0
    assert instrumentation["legal_moves_calls"] > 0
