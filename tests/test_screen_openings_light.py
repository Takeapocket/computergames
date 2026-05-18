from __future__ import annotations

from dataclasses import dataclass

from ai.opening_layouts import mirror_layout, validate_layout
from core.types import Player

import json

import pytest

from scripts import screen_openings_light as sol


@dataclass
class FakeResult:
    winner: Player | None
    turns: int
    illegal_moves: int = 0
    crashes: int = 0
    timeouts: int = 0
    step_times_ms: list[float] | None = None


def _layout_key(candidate: sol.OpeningCandidate) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (piece_id, candidate.red_layout[piece_id].row, candidate.red_layout[piece_id].col)
        for piece_id in sorted(candidate.red_layout)
    )


def test_generate_candidates_is_deterministic() -> None:
    first = sol.generate_candidates(mode="curated", max_candidates=12, seed=2026)
    second = sol.generate_candidates(mode="curated", max_candidates=12, seed=2026)

    assert [candidate.candidate_id for candidate in first] == [candidate.candidate_id for candidate in second]
    assert [_layout_key(candidate) for candidate in first] == [_layout_key(candidate) for candidate in second]


def test_make_game_seeds_uses_role_offset() -> None:
    red_seed = sol.make_game_seeds(master_seed=2026, candidate_index=3, role="candidate_as_red", local_game_index=1, games_per_side=2)
    blue_seed = sol.make_game_seeds(master_seed=2026, candidate_index=3, role="candidate_as_blue", local_game_index=0, games_per_side=2)

    assert red_seed.base_seed == 2026 * 100000 + 3 * 1000 + 1
    assert blue_seed.base_seed == 2026 * 100000 + 3 * 1000 + 2
    assert red_seed.dice_seed == red_seed.base_seed * 3
    assert blue_seed.red_seed == blue_seed.base_seed * 3 + 1
    assert blue_seed.blue_seed == blue_seed.base_seed * 3 + 2


def test_make_game_seeds_rejects_out_of_range_local_game_index() -> None:
    with pytest.raises(ValueError, match="local_game_index"):
        sol.make_game_seeds(
            master_seed=2026,
            candidate_index=3,
            role="candidate_as_red",
            local_game_index=2,
            games_per_side=2,
        )

    with pytest.raises(ValueError, match="local_game_index"):
        sol.make_game_seeds(
            master_seed=2026,
            candidate_index=3,
            role="candidate_as_red",
            local_game_index=-1,
            games_per_side=2,
        )


def test_aggregate_candidate_results_calculates_combined_fields() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]
    red_results = [
        (FakeResult(Player.RED, 10, step_times_ms=[1.0, 3.0]), sol.GameSeeds("candidate_as_red", 0, 1, 3, 4, 5)),
        (FakeResult(Player.BLUE, 12, illegal_moves=1, step_times_ms=[5.0]), sol.GameSeeds("candidate_as_red", 1, 2, 6, 7, 8)),
    ]
    blue_results = [
        (FakeResult(Player.BLUE, 14, crashes=1, timeouts=1, step_times_ms=[2.0, 10.0]), sol.GameSeeds("candidate_as_blue", 0, 3, 9, 10, 11)),
        (FakeResult(None, 20, step_times_ms=[]), sol.GameSeeds("candidate_as_blue", 1, 4, 12, 13, 14)),
    ]

    result = sol.aggregate_candidate_result(
        candidate=candidate,
        games_per_side=2,
        red_results=red_results,
        blue_results=blue_results,
    )

    assert result["candidate_wins_as_red"] == 1
    assert result["candidate_wins_as_blue"] == 1
    assert result["combined_candidate_wins"] == 2
    assert result["combined_games"] == 4
    assert result["combined_win_rate"] == 0.5
    assert result["candidate_id"] == candidate.candidate_id
    assert result["source"] == candidate.source
    assert result["red_layout"] == sol.layout_to_json(candidate.red_layout)
    assert result["blue_layout"] == sol.layout_to_json(candidate.blue_layout)
    assert result["games_per_side"] == 2
    assert result["candidate_as_red"]["wins"] == 1
    assert result["candidate_as_red"]["games"] == 2
    assert result["candidate_as_blue"]["wins"] == 1
    assert result["candidate_as_blue"]["games"] == 2
    assert "candidate_wins" not in result["candidate_as_red"]
    assert "candidate_wins" not in result["candidate_as_blue"]
    assert "total_step_time_ms" not in result["candidate_as_red"]
    assert "step_time_count" not in result["candidate_as_red"]
    assert "total_step_time_ms" not in result["candidate_as_blue"]
    assert "step_time_count" not in result["candidate_as_blue"]
    assert result["illegal_moves"] == 1
    assert result["crashes"] == 1
    assert result["timeouts"] == 1
    assert result["average_turns"] == 14.0
    assert result["average_step_time_ms"] == 4.2
    assert result["max_step_time_ms"] == 10.0
    assert len(result["seeds_used"]) == 4


def test_layout_to_json_uses_list_coordinates() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]
    raw = sol.layout_to_json(candidate.red_layout)

    assert raw["1"] == [candidate.red_layout[1].row, candidate.red_layout[1].col]
    assert not isinstance(raw["1"], dict)


def test_layout_from_json_round_trips_candidate_red_layout() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]

    restored = sol.layout_from_json(sol.layout_to_json(candidate.red_layout))

    assert restored == candidate.red_layout


def test_generate_candidates_respects_max_candidates() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=8, seed=2026)

    assert len(candidates) == 8
    assert candidates[0].candidate_id == "curated_000"
    assert candidates[-1].candidate_id == "curated_007"


def test_generate_candidates_rejects_zero_max_candidates() -> None:
    try:
        sol.generate_candidates(mode="curated", max_candidates=0, seed=2026)
    except ValueError as exc:
        assert str(exc) == "max_candidates must be >= 1"
    else:
        raise AssertionError("expected ValueError")


def test_generate_candidates_are_valid_and_blue_is_mirror() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=20, seed=2026)

    assert candidates
    for candidate in candidates:
        assert validate_layout(candidate.red_layout, candidate.blue_layout) == []
        assert candidate.blue_layout == mirror_layout(candidate.red_layout)


def test_generate_candidates_has_unique_ids_and_layouts() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=32, seed=2026)

    ids = [candidate.candidate_id for candidate in candidates]
    layouts = [_layout_key(candidate) for candidate in candidates]
    assert len(ids) == len(set(ids))
    assert len(layouts) == len(set(layouts))


def test_curated_sources_start_with_required_seed_layouts() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=11, seed=2026)

    assert [candidate.source for candidate in candidates] == [
        "preset:balanced_v1",
        "preset:aggressive_v1",
        "preset:defensive_v1",
        "heuristic:low_ids_forward",
        "heuristic:high_ids_forward",
        "heuristic:low_ids_center",
        "heuristic:high_ids_center",
        "swap:balanced_1_6",
        "swap:balanced_2_5",
        "swap:balanced_3_4",
        "heuristic:balanced_reverse",
    ]


def test_full_mode_can_generate_all_layouts() -> None:
    candidates = sol.generate_candidates(mode="full", max_candidates=720, seed=2026)

    assert len(candidates) == 720


def test_full_mode_can_be_limited_without_running_all_games() -> None:
    candidates = sol.generate_candidates(mode="full", max_candidates=5, seed=2026)

    assert [candidate.candidate_id for candidate in candidates] == [
        "full_000",
        "full_001",
        "full_002",
        "full_003",
        "full_004",
    ]


def test_load_release_default_ai_config_strips_metadata(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(
        json.dumps(
            {
                "ai": "rollout",
                "rollouts_per_move": 32,
                "fallback_ai": "greedy_risk",
                "promotion_report": "reports/ai_promotion_decision.md",
            }
        ),
        encoding="utf-8",
    )

    kind, kwargs = sol.load_release_default_ai_config(path)

    assert kind == "rollout"
    assert kwargs == {"rollouts_per_move": 32}


def test_load_release_default_ai_config_rejects_non_rollout(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(json.dumps({"ai": "greedy_risk"}), encoding="utf-8")

    with pytest.raises(ValueError, match="must use ai='rollout'"):
        sol.load_release_default_ai_config(path)


def test_validate_run_limits_rejects_large_non_dry_run() -> None:
    with pytest.raises(ValueError, match="planned games"):
        sol.validate_run_limits(candidate_count=81, games_per_side=1, dry_run=False)


def test_validate_run_limits_allows_large_dry_run() -> None:
    sol.validate_run_limits(candidate_count=720, games_per_side=1, dry_run=True)


def test_validate_run_limits_rejects_invalid_games_per_side() -> None:
    with pytest.raises(ValueError, match="games_per_side"):
        sol.validate_run_limits(candidate_count=4, games_per_side=0, dry_run=False)


def test_validate_run_limits_rejects_too_large_games_per_side() -> None:
    with pytest.raises(ValueError, match="games_per_side must be <= 500"):
        sol.validate_run_limits(candidate_count=1, games_per_side=501, dry_run=False)


def test_is_result_complete_requires_matching_layout_and_game_count() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]
    result = {
        "candidate_id": candidate.candidate_id,
        "red_layout": sol.layout_to_json(candidate.red_layout),
        "combined_games": 4,
    }

    assert sol.is_result_complete(result, candidate, expected_games=4) is True
    assert sol.is_result_complete({**result, "combined_games": 2}, candidate, expected_games=4) is False
    assert sol.is_result_complete({**result, "red_layout": {"1": [9, 9]}}, candidate, expected_games=4) is False


def test_load_resume_state_rejects_incompatible_parameters(tmp_path) -> None:
    output = tmp_path / "screen.json"
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps({**payload, "seed": 9999}), encoding="utf-8")

    with pytest.raises(ValueError, match="incompatible resume output"):
        sol.load_resume_payload(
            output,
            expected=payload,
            no_resume=False,
        )


def test_load_resume_state_allows_larger_current_max_candidates(tmp_path) -> None:
    output = tmp_path / "screen.json"
    old_payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps(old_payload), encoding="utf-8")
    current_payload = {**old_payload, "max_candidates": 8, "candidate_count": 8}

    loaded = sol.load_resume_payload(output, expected=current_payload, no_resume=False)

    assert loaded["max_candidates"] == 4
    assert loaded["results"] == []


def test_load_resume_state_rejects_schema_version_mismatch(tmp_path) -> None:
    output = tmp_path / "screen.json"
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps({**payload, "schema_version": 999}), encoding="utf-8")

    with pytest.raises(ValueError, match="incompatible resume output"):
        sol.load_resume_payload(
            output,
            expected=payload,
            no_resume=False,
        )


def test_load_resume_state_no_resume_returns_expected_for_incompatible_file(tmp_path) -> None:
    output = tmp_path / "screen.json"
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps({**payload, "seed": 9999}), encoding="utf-8")

    loaded = sol.load_resume_payload(output, expected=payload, no_resume=True)

    assert loaded == payload


def test_atomic_write_json_writes_readable_json_with_trailing_newline(tmp_path) -> None:
    output = tmp_path / "nested" / "screen.json"
    payload = {
        "schema_version": sol.SCHEMA_VERSION,
        "name": "布局筛选",
        "results": [{"candidate_id": "curated_001", "combined_games": 2}],
    }

    sol.atomic_write_json(output, payload)

    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == payload
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_run_screening_resumes_completed_candidate_and_writes_summary(tmp_path, monkeypatch) -> None:
    output = tmp_path / "screen.json"
    summary = tmp_path / "screen.md"
    candidates = sol.generate_candidates(mode="curated", max_candidates=2, seed=2026)
    existing_result = {
        "candidate_id": candidates[0].candidate_id,
        "source": candidates[0].source,
        "red_layout": sol.layout_to_json(candidates[0].red_layout),
        "blue_layout": sol.layout_to_json(candidates[0].blue_layout),
        "games_per_side": 1,
        "candidate_wins_as_red": 1,
        "candidate_wins_as_blue": 0,
        "combined_candidate_wins": 1,
        "combined_games": 2,
        "combined_win_rate": 0.5,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "average_turns": 10.0,
        "average_step_time_ms": 1.0,
        "max_step_time_ms": 2.0,
        "seeds_used": [],
        "candidate_as_red": {},
        "candidate_as_blue": {},
    }
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=2,
        candidate_count=2,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    payload["results"] = [existing_result]
    output.write_text(json.dumps(payload), encoding="utf-8")
    calls: list[str] = []

    def fake_run_candidate(**kwargs):
        candidate = kwargs["candidate"]
        calls.append(candidate.candidate_id)
        return {
            **existing_result,
            "candidate_id": candidate.candidate_id,
            "source": candidate.source,
            "red_layout": sol.layout_to_json(candidate.red_layout),
            "blue_layout": sol.layout_to_json(candidate.blue_layout),
            "combined_candidate_wins": 2,
            "combined_games": 2,
            "combined_win_rate": 1.0,
        }

    monkeypatch.setattr(sol, "run_candidate", fake_run_candidate)
    monkeypatch.setattr(sol, "load_release_default_ai_config", lambda: ("rollout", {"rollouts_per_move": 32}))

    exit_code = sol.main(
        [
            "--max-candidates",
            "2",
            "--games-per-side",
            "1",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    assert exit_code == 0
    assert calls == ["curated_001"]
    written = json.loads(output.read_text(encoding="utf-8"))
    assert len(written["results"]) == 2
    assert summary.exists()
    assert "这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。" in summary.read_text(encoding="utf-8")


def test_run_screening_refreshes_metadata_when_resume_expands_candidates(tmp_path, monkeypatch) -> None:
    output = tmp_path / "screen.json"
    summary = tmp_path / "screen.md"
    candidates = sol.generate_candidates(mode="curated", max_candidates=2, seed=2026)
    existing_result = {
        "candidate_id": candidates[0].candidate_id,
        "source": candidates[0].source,
        "red_layout": sol.layout_to_json(candidates[0].red_layout),
        "blue_layout": sol.layout_to_json(candidates[0].blue_layout),
        "games_per_side": 1,
        "candidate_wins_as_red": 1,
        "candidate_wins_as_blue": 0,
        "combined_candidate_wins": 1,
        "combined_games": 2,
        "combined_win_rate": 0.5,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "average_turns": 10.0,
        "average_step_time_ms": 1.0,
        "max_step_time_ms": 2.0,
        "seeds_used": [],
        "candidate_as_red": {},
        "candidate_as_blue": {},
    }
    old_payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=1,
        candidate_count=1,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    old_payload["results"] = [existing_result]
    output.write_text(json.dumps(old_payload), encoding="utf-8")
    calls: list[str] = []

    def fake_run_candidate(**kwargs):
        candidate = kwargs["candidate"]
        calls.append(candidate.candidate_id)
        return {
            **existing_result,
            "candidate_id": candidate.candidate_id,
            "source": candidate.source,
            "red_layout": sol.layout_to_json(candidate.red_layout),
            "blue_layout": sol.layout_to_json(candidate.blue_layout),
            "combined_candidate_wins": 2,
            "combined_games": 2,
            "combined_win_rate": 1.0,
        }

    monkeypatch.setattr(sol, "run_candidate", fake_run_candidate)
    monkeypatch.setattr(sol, "load_release_default_ai_config", lambda: ("rollout", {"rollouts_per_move": 32}))

    exit_code = sol.main(
        [
            "--max-candidates",
            "2",
            "--games-per-side",
            "1",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    assert exit_code == 0
    assert calls == ["curated_001"]
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["max_candidates"] == 2
    assert written["candidate_count"] == 2
    assert len(written["results"]) == 2
    assert "candidate_count: 2" in summary.read_text(encoding="utf-8")


def test_main_passes_selected_baseline_layout_to_run_candidate(tmp_path, monkeypatch) -> None:
    output = tmp_path / "screen.json"
    summary = tmp_path / "screen.md"
    expected_baseline = sol.PRESETS["aggressive_v1"]
    seen_baselines = []

    def fake_run_candidate(**kwargs):
        baseline = kwargs["baseline"]
        seen_baselines.append(baseline)
        candidate = kwargs["candidate"]
        return {
            "candidate_id": candidate.candidate_id,
            "source": candidate.source,
            "red_layout": sol.layout_to_json(candidate.red_layout),
            "blue_layout": sol.layout_to_json(candidate.blue_layout),
            "games_per_side": 1,
            "candidate_wins_as_red": 1,
            "candidate_wins_as_blue": 1,
            "combined_candidate_wins": 2,
            "combined_games": 2,
            "combined_win_rate": 1.0,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_turns": 10.0,
            "average_step_time_ms": 1.0,
            "max_step_time_ms": 2.0,
            "seeds_used": [],
            "candidate_as_red": {},
            "candidate_as_blue": {},
        }

    monkeypatch.setattr(sol, "run_candidate", fake_run_candidate)
    monkeypatch.setattr(sol, "load_release_default_ai_config", lambda: ("rollout", {"rollouts_per_move": 32}))

    exit_code = sol.main(
        [
            "--max-candidates",
            "1",
            "--games-per-side",
            "1",
            "--baseline-layout",
            "aggressive_v1",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    assert exit_code == 0
    assert seen_baselines == [expected_baseline]


def test_write_summary_sorts_top_candidates(tmp_path) -> None:
    summary = tmp_path / "summary.md"
    payload = sol.new_run_payload(
        argv=["--max-candidates", "2"],
        mode="curated",
        max_candidates=2,
        candidate_count=2,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    assert payload["ai_kwargs_source"] == "release/v1.0/default_params.json"
    payload["results"] = [
        {
            "candidate_id": "curated_000",
            "red_layout": {"1": [0, 0]},
            "combined_win_rate": 0.25,
            "combined_candidate_wins": 1,
            "combined_games": 4,
            "candidate_wins_as_red": 1,
            "candidate_wins_as_blue": 0,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_turns": 10.0,
            "average_step_time_ms": 1.0,
            "max_step_time_ms": 2.0,
        },
        {
            "candidate_id": "curated_001",
            "red_layout": {"1": [1, 1]},
            "combined_win_rate": 0.75,
            "combined_candidate_wins": 3,
            "combined_games": 4,
            "candidate_wins_as_red": 1,
            "candidate_wins_as_blue": 2,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_turns": 12.0,
            "average_step_time_ms": 1.5,
            "max_step_time_ms": 3.0,
        },
    ]

    sol.write_summary(summary, payload)

    text = summary.read_text(encoding="utf-8")
    assert text.index("curated_001") < text.index("curated_000")
    assert "| rank | candidate_id | win_rate | wins/games |" in text
    assert "ai_kwargs_source: release/v1.0/default_params.json" in text


def test_dry_run_does_not_call_play_one_game_or_write_outputs(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "out.json"
    summary = tmp_path / "out.md"

    def fail_play_one_game(**kwargs):
        raise AssertionError("dry-run must not call play_one_game")

    monkeypatch.setattr(sol, "play_one_game", fail_play_one_game)

    exit_code = sol.main(
        [
            "--dry-run",
            "--max-candidates",
            "4",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "candidate_count: 4" in captured.out
    assert "curated_000" in captured.out
    assert not output.exists()
    assert not summary.exists()
