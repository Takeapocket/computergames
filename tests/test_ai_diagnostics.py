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
