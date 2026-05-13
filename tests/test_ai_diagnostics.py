from scripts.ai_diagnostics import (
    FailureBucket,
    aggregate_buckets,
    format_bucket_table,
)


def test_aggregate_buckets_counts_known_reasons():
    rows = [
        {"winner": "blue", "termination_reason": "winner_target_corner", "loser": "red"},
        {"winner": "blue", "termination_reason": "winner_capture_all", "loser": "red"},
        {"winner": "red", "termination_reason": "winner_target_corner", "loser": "blue"},
    ]

    buckets = aggregate_buckets(rows, perspective="red")

    assert buckets[FailureBucket.LOST_BY_TARGET] == 1
    assert buckets[FailureBucket.LOST_BY_CAPTURE_ALL] == 1
    assert buckets[FailureBucket.WON_BY_TARGET] == 1

def test_failure_bucket_enum_is_complete():
    assert {bucket.value for bucket in FailureBucket} == {
        "lost_by_target",
        "lost_by_capture_all",
        "won_by_target",
        "won_by_capture_all",
        "draw_or_limit",
        "illegal_or_crash",
    }


def test_aggregate_buckets_counts_all_branches():
    rows = [
        {"winner": "red", "termination_reason": "winner_capture_all", "loser": "blue"},
        {"winner": None, "termination_reason": "draw_max_turns", "loser": None},
        {"winner": "blue", "termination_reason": "illegal_move", "loser": "red"},
        {"winner": "blue", "termination_reason": "crash", "loser": "red"},
        {"winner": "blue", "termination_reason": "no_move", "loser": "red"},
    ]

    buckets = aggregate_buckets(rows, perspective="red")

    assert buckets[FailureBucket.WON_BY_CAPTURE_ALL] == 1
    assert buckets[FailureBucket.DRAW_OR_LIMIT] == 1
    assert buckets[FailureBucket.ILLEGAL_OR_CRASH] == 3


def test_aggregate_buckets_counts_illegal_move_and_crash_counters_early():
    rows = [
        {"winner": "red", "termination_reason": "winner_target_corner", "loser": "blue", "illegal_moves": 1},
        {"winner": "red", "termination_reason": "winner_capture_all", "loser": "blue", "crashes": 1},
    ]

    buckets = aggregate_buckets(rows, perspective="red")

    assert buckets[FailureBucket.ILLEGAL_OR_CRASH] == 2
    assert buckets[FailureBucket.WON_BY_TARGET] == 0
    assert buckets[FailureBucket.WON_BY_CAPTURE_ALL] == 0


def test_aggregate_buckets_counts_unknown_winner_reason_as_draw_or_limit():
    rows = [
        {"winner": "red", "termination_reason": "unexpected_reason", "loser": "blue"},
    ]

    buckets = aggregate_buckets(rows, perspective="red")

    assert buckets[FailureBucket.DRAW_OR_LIMIT] == 1
    assert buckets[FailureBucket.WON_BY_TARGET] == 0


def test_run_direction_uses_one_based_game_index(monkeypatch):
    class _Result:
        winner = None
        termination_reason = "draw_max_turns"
        turns = 0
        illegal_moves = 0
        crashes = 0

    monkeypatch.setattr("scripts.ai_diagnostics.build_ai", lambda kind, seed: object())
    monkeypatch.setattr("scripts.ai_diagnostics.starting_state_for", lambda layout: object())
    monkeypatch.setattr("scripts.ai_diagnostics.play_one_game", lambda **kwargs: _Result())

    from scripts.ai_diagnostics import run_direction

    rows, _buckets = run_direction(
        red="greedy_risk",
        blue="greedy",
        games=1,
        seed=2026,
        starting_layout="balanced_v1",
        perspective="red",
    )

    assert rows[0]["game_index"] == 1


def test_main_defaults_to_balanced_v1_starting_layout(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_run_direction(red, blue, games, seed, starting_layout, perspective):
        captured["starting_layout"] = starting_layout
        return [], {}

    def fake_write_report(report_path, red, blue, games, seed, starting_layout, rows, buckets):
        return report_path

    monkeypatch.setattr("scripts.ai_diagnostics.run_direction", fake_run_direction)
    monkeypatch.setattr("scripts.ai_diagnostics.write_report", fake_write_report)

    from scripts.ai_diagnostics import main

    assert main(["--output", str(tmp_path / "diagnostics.md")]) == 0

    assert captured["starting_layout"] == "balanced_v1"
    assert "balanced_v1" not in capsys.readouterr().err


def test_format_bucket_table_contains_counts():
    table = format_bucket_table({
        FailureBucket.LOST_BY_TARGET: 2,
        FailureBucket.LOST_BY_CAPTURE_ALL: 1,
        FailureBucket.WON_BY_TARGET: 3,
    })

    assert "| bucket | count |" in table
    assert "| lost_by_target | 2 |" in table
    assert "| lost_by_capture_all | 1 |" in table
    assert "| won_by_target | 3 |" in table
