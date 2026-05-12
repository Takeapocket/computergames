from types import SimpleNamespace

import scripts.param_sweep as param_sweep
from core.types import Player
from scripts.param_sweep import iter_param_grid, summarize_candidate


def test_iter_param_grid_contains_expected_keys():
    params = next(iter(iter_param_grid(limit=1, seed=1)))

    assert set(params) >= {
        "distance_weight",
        "material_weight",
        "expected_risk_weight",
        "expected_win_risk_weight",
    }


def test_iter_param_grid_limit_truncates():
    samples = list(iter_param_grid(limit=3, seed=1))

    assert len(samples) == 3


def test_iter_param_grid_seed_makes_samples_reproducible():
    a = list(iter_param_grid(limit=5, seed=42))
    b = list(iter_param_grid(limit=5, seed=42))

    assert a == b


def test_summarize_candidate_formats_win_rate():
    row = summarize_candidate(
        params={"distance_weight": 1.0},
        wins=12,
        games=20,
        illegal_moves=0,
        crashes=0,
        max_step_time_ms=3.0,
    )

    assert "60.0%" in row
    assert "distance_weight=1.0" in row


def test_summarize_candidate_marks_illegal_or_crashes():
    row = summarize_candidate(
        params={"distance_weight": 1.0},
        wins=10,
        games=20,
        illegal_moves=1,
        crashes=0,
        max_step_time_ms=3.0,
    )

    assert "illegal=1" in row


def test_run_candidate_can_score_candidate_as_blue(monkeypatch):
    params = {"distance_weight": 2.0}
    built: list[tuple[str, dict]] = []

    def fake_build_ai(name, seed, **kwargs):
        built.append((name, kwargs))
        return {"name": name, "params": kwargs}

    def fake_play_one_game(**kwargs):
        assert kwargs["red_ai"]["params"] == {}
        assert kwargs["blue_ai"]["params"] == params
        return SimpleNamespace(
            winner=Player.BLUE,
            illegal_moves=0,
            crashes=0,
            step_times_ms=[1.0, 3.0],
        )

    monkeypatch.setattr(param_sweep, "build_ai", fake_build_ai)
    monkeypatch.setattr(param_sweep, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(param_sweep, "starting_state_for", lambda layout_id: object())

    stats = param_sweep._run_candidate(
        params,
        games=1,
        master_seed=2026,
        layout_id="balanced_v1",
        max_turns=200,
        candidate_player=Player.BLUE,
    )

    assert built == [("greedy_risk", {}), ("greedy_risk", params)]
    assert stats["wins"] == 1
    assert stats["games"] == 1
    assert stats["avg_step_time_ms"] == 2.0


def test_run_bilateral_candidate_combines_red_and_blue_orientations(monkeypatch):
    calls: list[Player] = []

    def fake_run_candidate(params, *, games, master_seed, layout_id, max_turns, candidate_player):
        calls.append(candidate_player)
        return {
            "wins": 1 if candidate_player is Player.RED else 2,
            "games": games,
            "illegal_moves": 0,
            "crashes": 0,
            "max_step_time_ms": 4.0 if candidate_player is Player.RED else 5.0,
            "avg_step_time_ms": 2.0,
            "total_step_time_ms": 4.0,
            "step_time_count": 2,
        }

    monkeypatch.setattr(param_sweep, "_run_candidate", fake_run_candidate)

    stats = param_sweep._run_bilateral_candidate(
        {"distance_weight": 2.0},
        games_per_side=3,
        master_seed=2026,
        layout_id="balanced_v1",
        max_turns=200,
    )

    assert calls == [Player.RED, Player.BLUE]
    assert stats["wins"] == 3
    assert stats["games"] == 6
    assert stats["max_step_time_ms"] == 5.0
