from scripts.rollout_stability import build_audit_state, run_stability


def test_rollout_stability_audit_state_matches_self_capture_case():
    state = build_audit_state("self_capture_audit")

    moves = state.legal_moves(state.current_player, 5)

    assert len(moves) == 3
    assert {(move.to_pos.row, move.to_pos.col) for move in moves} == {
        (3, 1),
        (2, 2),
        (3, 2),
    }


def test_rollout_stability_records_runs_and_candidate_stats():
    result = run_stability(
        scenario="self_capture_audit",
        runs=3,
        seed=0,
        rollouts_per_move=1,
        close_sample_margin=1.0,
        close_sample_rollouts_per_move=2,
        low_confidence_margin=0.08,
        max_rollout_turns=0,
        max_step_time_ms=1000.0,
        epsilon=0.15,
    )

    assert len(result["runs"]) == 3
    assert sum(result["recommendation_counts"].values()) == 3
    assert all(len(row["candidates"]) == 3 for row in result["runs"])
    assert all(
        {"move", "visits", "score", "winrate", "cutoffs", "avg"} <= set(candidate)
        for row in result["runs"]
        for candidate in row["candidates"]
    )
