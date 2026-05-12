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
