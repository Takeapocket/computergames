from types import SimpleNamespace

from core.types import Player
from scripts import tournament
from scripts.tournament import format_markdown_matrix, parse_ai_list


def test_parse_ai_list_strips_spaces():
    assert parse_ai_list("random, greedy,greedy_risk") == ["random", "greedy", "greedy_risk"]


def test_parse_ai_list_rejects_empty_entry():
    import pytest

    with pytest.raises(ValueError):
        parse_ai_list("random,,greedy")


def test_format_markdown_matrix_contains_headers_and_diagonal():
    ais = ["random", "greedy"]
    matrix = {
        "random": {"greedy": 25.0},
        "greedy": {"random": 75.0},
    }

    output = format_markdown_matrix(ais, matrix)

    assert "| AI | random | greedy |" in output
    assert "| random | - | 25.0% |" in output
    assert "| greedy | 75.0% | - |" in output


def test_format_markdown_matrix_handles_missing_cell_as_dash():
    ais = ["random", "greedy", "greedy_risk"]
    matrix = {
        "random": {"greedy": 12.0, "greedy_risk": 8.0},
        "greedy": {"random": 88.0, "greedy_risk": 42.0},
        "greedy_risk": {"random": 92.0, "greedy": 58.0},
    }

    output = format_markdown_matrix(ais, matrix)

    assert "| greedy_risk | 92.0% | 58.0% | - |" in output


def test_run_pair_aggregates_timeouts(monkeypatch):
    monkeypatch.setattr(tournament, "build_ai", lambda kind, seed: {"kind": kind, "seed": seed})
    monkeypatch.setattr(tournament, "starting_state_for", lambda layout_id: object())

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=Player.RED,
            illegal_moves=0,
            crashes=0,
            timeouts=2,
            step_times_ms=[1.0, 3.0],
        )

    monkeypatch.setattr(tournament, "play_one_game", fake_play_one_game)

    stats = tournament._run_pair(
        red_kind="greedy",
        blue_kind="random",
        games=1,
        master_seed=2026,
        layout_id="balanced_v1",
        max_turns=200,
    )

    assert stats["timeouts"] == 2


def test_run_tournament_metadata_sums_timeouts(monkeypatch):
    def fake_run_pair(red_kind, blue_kind, games, master_seed, layout_id, max_turns):
        return {
            "games": games,
            "red_wins": 1,
            "blue_wins": 0,
            "draws": 0,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 3 if red_kind == "greedy" else 4,
            "average_step_time_ms": 1.0,
            "max_step_time_ms": 2.0,
        }

    monkeypatch.setattr(tournament, "_run_pair", fake_run_pair)

    _matrix, metadata = tournament.run_tournament(
        ["greedy", "random"],
        games_per_orientation=1,
        seed=2026,
        layout_id="balanced_v1",
        max_turns=200,
    )

    assert metadata["timeouts_total"] == 7
    assert metadata["pairs"][0]["timeouts"] == 3
