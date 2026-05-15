import argparse
from types import SimpleNamespace

from core.types import Player
from scripts.quick_bench import _aggregate, wilson_ci


def test_wilson_ci_bounds_are_inside_zero_one():
    lower, upper = wilson_ci(58, 100)
    assert 0.0 <= lower <= upper <= 1.0


def test_wilson_ci_gets_narrower_with_more_games():
    low_small, high_small = wilson_ci(5, 10)
    low_large, high_large = wilson_ci(500, 1000)
    assert (high_large - low_large) < (high_small - low_small)


def test_wilson_ci_zero_games_returns_zero_zero():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_percentile_uses_nearest_rank():
    from scripts.quick_bench import _percentile

    values = [1, 2, 3, 4, 5, 100]

    assert _percentile(values, 0.50) == 3
    assert _percentile(values, 0.95) == 100
    assert _percentile(values, 0.99) == 100


def test_aggregate_includes_step_time_percentiles():
    results = [
        SimpleNamespace(winner=Player.RED, turns=1, illegal_moves=0, crashes=0, timeouts=1, step_times_ms=[1.0, 2.0, 3.0]),
        SimpleNamespace(winner=Player.BLUE, turns=1, illegal_moves=0, crashes=0, timeouts=2, step_times_ms=[4.0, 5.0, 100.0]),
    ]

    summary = _aggregate(results)

    assert summary["p95_step_time_ms"] == 100.0
    assert summary["p99_step_time_ms"] == 100.0
    assert summary["timeouts"] == 3


def test_aggregate_includes_red_and_blue_ci():
    results = [
        SimpleNamespace(winner=Player.RED, turns=10, illegal_moves=0, crashes=0, step_times_ms=[1.0, 2.0]),
        SimpleNamespace(winner=Player.BLUE, turns=12, illegal_moves=0, crashes=0, step_times_ms=[3.0]),
    ]

    summary = _aggregate(results)

    assert "red_win_ci95" in summary
    assert "blue_win_ci95" in summary
    assert len(summary["red_win_ci95"]) == 2
    assert len(summary["blue_win_ci95"]) == 2
    assert 0.0 <= summary["red_win_ci95"][0] <= summary["red_win_ci95"][1] <= 1.0


def test_parse_ai_kwargs_accepts_json_object():
    from scripts.quick_bench import _parse_ai_kwargs

    assert _parse_ai_kwargs('{"rollouts_per_move": 32, "epsilon": 0.15}') == {
        "rollouts_per_move": 32,
        "epsilon": 0.15,
    }


def test_parse_ai_kwargs_rejects_non_object_json():
    from scripts.quick_bench import _parse_ai_kwargs

    try:
        _parse_ai_kwargs('[1, 2, 3]')
    except argparse.ArgumentTypeError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("expected argparse.ArgumentTypeError")
