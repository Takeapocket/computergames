import importlib
import json
import math
import random
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

import ai.evaluator as evaluator
import ai.zweistein as zweistein
import scripts.tune_eval_weights as tuning
from core.types import Player
from scripts.tune_eval_weights import (
    CEMDistribution,
    WeightSpec,
    initial_distribution,
    profile_specs,
    sample_population,
    select_elites,
    update_distribution,
)


def test_cem_profiles_cover_greedy_risk_and_zweistein_weights():
    greedy_risk = profile_specs("greedy_risk")
    zweistein = profile_specs("greedy_zweistein")

    assert {spec.name for spec in greedy_risk} == {
        "distance_weight",
        "material_weight",
        "expected_risk_weight",
        "expected_win_risk_weight",
    }
    assert {spec.name for spec in zweistein} == {
        "progress_weight",
        "material_weight",
        "mobility_weight",
        "capture_risk_weight",
        "target_win_risk_weight",
    }


def test_cem_profiles_source_initial_values_from_evaluator_defaults(monkeypatch):
    evaluator_defaults = {
        "DISTANCE_WEIGHT": 1.25,
        "MATERIAL_WEIGHT": 11.0,
        "EXPECTED_RISK_WEIGHT": 3.5,
        "EXPECTED_WIN_RISK_WEIGHT": 550.0,
    }
    zweistein_defaults = {
        "PROGRESS_WEIGHT": 13.0,
        "MATERIAL_WEIGHT": 91.0,
        "MOBILITY_WEIGHT": 7.0,
        "CAPTURE_RISK_WEIGHT": 121.0,
        "TARGET_WIN_RISK_WEIGHT": 601.0,
    }

    try:
        with monkeypatch.context() as patch:
            for name, value in evaluator_defaults.items():
                patch.setattr(evaluator, name, value)
            for name, value in zweistein_defaults.items():
                patch.setattr(zweistein, name, value)

            importlib.reload(tuning)

            assert {
                spec.name: spec.initial for spec in tuning.profile_specs("greedy_risk")
            } == {
                "distance_weight": 1.25,
                "material_weight": 11.0,
                "expected_risk_weight": 3.5,
                "expected_win_risk_weight": 550.0,
            }
            assert {
                spec.name: spec.initial
                for spec in tuning.profile_specs("greedy_zweistein")
            } == {
                "progress_weight": 13.0,
                "material_weight": 91.0,
                "mobility_weight": 7.0,
                "capture_risk_weight": 121.0,
                "target_win_risk_weight": 601.0,
            }
    finally:
        importlib.reload(tuning)


@pytest.mark.parametrize(
    ("lower", "upper", "initial"),
    [
        (0.0, 2.0, 1.0),
        (1.0, 1.0, 1.0),
        (1.0, 2.0, 3.0),
        (math.nan, 2.0, 1.0),
    ],
)
def test_weight_spec_rejects_invalid_positive_finite_bounds(lower, upper, initial):
    with pytest.raises(ValueError):
        WeightSpec("weight", lower=lower, upper=upper, initial=initial)


def test_cem_log_space_sampling_is_seeded_and_bounded():
    specs = profile_specs("greedy_risk")
    distribution = initial_distribution(specs, initial_log_std=0.8)

    first = sample_population(
        specs,
        distribution,
        population_size=8,
        rng=random.Random(17),
    )
    second = sample_population(
        specs,
        distribution,
        population_size=8,
        rng=random.Random(17),
    )

    assert first == second
    assert len(first) == 8
    for params in first:
        for spec in specs:
            assert spec.lower <= params[spec.name] <= spec.upper


def test_cem_sampling_clamps_extreme_finite_logs_before_exp():
    class ExtremeGaussian:
        def __init__(self):
            self.values = iter((sys.float_info.max, -sys.float_info.max))

        def gauss(self, _mean, _std):
            return next(self.values)

    specs = (WeightSpec("weight", lower=0.5, upper=2.0, initial=1.0),)
    distribution = CEMDistribution(
        log_means={"weight": 0.0},
        log_stds={"weight": sys.float_info.max},
    )

    population = sample_population(
        specs,
        distribution,
        population_size=2,
        rng=ExtremeGaussian(),
    )

    assert population == [{"weight": 2.0}, {"weight": 0.5}]


def test_cem_population_size_requires_a_positive_builtin_integer():
    specs = (WeightSpec("weight", lower=0.5, upper=2.0, initial=1.0),)
    distribution = initial_distribution(specs, initial_log_std=0.5)

    for invalid_size in (True, 1.0, 1.5, "1"):
        with pytest.raises(ValueError, match="population_size.*positive integer"):
            sample_population(
                specs,
                distribution,
                population_size=invalid_size,
                rng=random.Random(17),
            )


def test_cem_select_elites_orders_by_valid_objective_then_candidate_id():
    rows = [
        {"candidate_id": "g0-c2", "objective_elo": 1510.0, "valid": True},
        {"candidate_id": "g0-c1", "objective_elo": 1510.0, "valid": True},
        {"candidate_id": "g0-c0", "objective_elo": 1900.0, "valid": False},
        {"candidate_id": "g0-c3", "objective_elo": 1490.0, "valid": True},
    ]

    elites = select_elites(rows, elite_count=2)

    assert [row["candidate_id"] for row in elites] == ["g0-c1", "g0-c2"]


def test_cem_select_elites_rejects_non_finite_valid_objective():
    for invalid_objective in (math.nan, math.inf, -math.inf):
        rows = [
            {
                "candidate_id": "g0-c0",
                "objective_elo": invalid_objective,
                "valid": True,
            }
        ]

        with pytest.raises(ValueError, match="objective_elo.*finite"):
            select_elites(rows, elite_count=1)


def test_cem_elite_count_requires_a_positive_builtin_integer():
    rows = [
        {"candidate_id": "g0-c0", "objective_elo": 1500.0, "valid": True}
    ]

    for invalid_count in (True, 1.0, 1.5, "1"):
        with pytest.raises(ValueError, match="elite_count.*positive integer"):
            select_elites(rows, elite_count=invalid_count)


def test_cem_update_moves_log_mean_toward_synthetic_better_weights():
    specs = (WeightSpec("weight", lower=0.5, upper=8.0, initial=1.0),)
    distribution = initial_distribution(specs, initial_log_std=1.0)
    rows = [
        {
            "candidate_id": "g0-c0",
            "objective_elo": 1400.0,
            "valid": True,
            "params": {"weight": 1.0},
        },
        {
            "candidate_id": "g0-c1",
            "objective_elo": 1500.0,
            "valid": True,
            "params": {"weight": 2.0},
        },
        {
            "candidate_id": "g0-c2",
            "objective_elo": 1600.0,
            "valid": True,
            "params": {"weight": 4.0},
        },
    ]
    elites = select_elites(rows, elite_count=2)

    updated = update_distribution(
        specs,
        distribution,
        elite_params=[row["params"] for row in elites],
        smoothing=1.0,
        min_log_std=0.05,
    )

    assert updated.log_means["weight"] > distribution.log_means["weight"]
    assert math.exp(updated.log_means["weight"]) == pytest.approx(math.sqrt(8.0))
    assert updated.log_stds["weight"] >= 0.05


def test_cem_update_applies_smoothing_and_minimum_std():
    specs = (WeightSpec("weight", lower=0.5, upper=8.0, initial=1.0),)
    distribution = CEMDistribution(
        log_means={"weight": 0.0},
        log_stds={"weight": 0.4},
    )

    updated = update_distribution(
        specs,
        distribution,
        elite_params=[{"weight": 4.0}, {"weight": 4.0}],
        smoothing=0.5,
        min_log_std=0.1,
    )

    assert updated.log_means["weight"] == pytest.approx(math.log(4.0) * 0.5)
    assert updated.log_stds["weight"] == pytest.approx(0.2)


def _match_result(
    winner,
    *,
    turns=5,
    illegal_moves=0,
    crashes=0,
    timeouts=0,
    step_times_ms=(),
    termination_reason="draw_max_turns",
):
    return SimpleNamespace(
        winner=winner,
        turns=turns,
        illegal_moves=illegal_moves,
        crashes=crashes,
        timeouts=timeouts,
        step_times_ms=list(step_times_ms),
        termination_reason=termination_reason,
    )


def test_evaluate_candidate_uses_bilateral_common_seeds_and_same_profile_anchor(
    monkeypatch,
):
    build_calls = []
    play_calls = []

    def fake_build_ai(kind, *, seed=None, **kwargs):
        ai = SimpleNamespace(kind=kind, seed=seed, kwargs=dict(kwargs), name=kind)
        build_calls.append(ai)
        return ai

    def fake_play_one_game(**kwargs):
        play_calls.append(
            {
                **kwargs,
                "dice_sample": kwargs["dice_rng"].random(),
            }
        )
        orientation = len(play_calls) % 2
        winner = Player.RED if orientation == 1 else Player.BLUE
        return _match_result(winner, termination_reason="winner_target_corner")

    monkeypatch.setattr(tuning, "build_ai", fake_build_ai)
    monkeypatch.setattr(tuning, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(tuning, "starting_state_for", lambda layout_id: ("state", layout_id))
    monkeypatch.setattr(
        tuning,
        "ai_version_signature",
        lambda ai: {"kind": ai.kind, "kwargs": ai.kwargs},
    )

    params = {
        spec.name: spec.initial for spec in profile_specs("greedy_zweistein")
    }
    row = tuning.evaluate_candidate(
        profile="greedy_zweistein",
        params=params,
        games_per_side=2,
        match_seed=73,
        layout_id="balanced_v1",
        max_turns=40,
        k_factor=24.0,
    )

    assert len(build_calls) == 8
    assert len(play_calls) == 4
    for pair_index in range(2):
        candidate_red = play_calls[pair_index * 2]
        candidate_blue = play_calls[pair_index * 2 + 1]

        assert candidate_red["red_ai"].kind == "greedy_zweistein"
        assert candidate_red["red_ai"].kwargs == {
            **params,
            "randomize_ties": False,
        }
        assert candidate_red["blue_ai"].kwargs == {"randomize_ties": False}
        assert candidate_blue["red_ai"].kwargs == {"randomize_ties": False}
        assert candidate_blue["blue_ai"].kwargs == {
            **params,
            "randomize_ties": False,
        }
        assert candidate_red["red_ai"].seed == candidate_blue["blue_ai"].seed
        assert candidate_red["blue_ai"].seed == candidate_blue["red_ai"].seed
        assert candidate_red["dice_sample"] == candidate_blue["dice_sample"]
        assert candidate_red["max_turns"] == candidate_blue["max_turns"] == 40
        assert candidate_red["starting_state"] == candidate_blue["starting_state"] == (
            "state",
            "balanced_v1",
        )

    assert row["profile"] == row["anchor_profile"] == "greedy_zweistein"
    assert row["games"] == 4
    assert row["wins"] == 4
    assert row["losses"] == row["draws"] == 0
    assert len(row["game_seed_manifest"]) == 4
    for pair_index in range(2):
        red_manifest = row["game_seed_manifest"][pair_index * 2]
        blue_manifest = row["game_seed_manifest"][pair_index * 2 + 1]
        assert red_manifest["orientation"] == "candidate_red"
        assert blue_manifest["orientation"] == "candidate_blue"
        assert red_manifest["dice_seed"] == blue_manifest["dice_seed"]
        assert red_manifest["candidate_ai_seed"] == blue_manifest["candidate_ai_seed"]
        assert red_manifest["anchor_ai_seed"] == blue_manifest["anchor_ai_seed"]


def test_evaluate_candidate_routes_every_game_through_ladder_elo_and_telemetry(
    monkeypatch,
):
    results = iter(
        (
            _match_result(
                None,
                turns=4,
                step_times_ms=(1.0, 3.0),
                termination_reason="draw_max_turns",
            ),
            _match_result(
                Player.BLUE,
                turns=6,
                illegal_moves=1,
                crashes=2,
                timeouts=3,
                step_times_ms=(2.0,),
                termination_reason="illegal_move",
            ),
        )
    )
    rating_calls = []
    uncertainty_calls = []

    def fake_update_ratings(red_rating, blue_rating, *, red_score, k_factor):
        rating_calls.append((red_rating, blue_rating, red_score, k_factor))
        if len(rating_calls) == 1:
            return 1510.0, 1490.0
        return 1495.0, 1505.0

    def fake_uncertainty(games):
        uncertainty_calls.append(games)
        return 42.0

    monkeypatch.setattr(
        tuning,
        "build_ai",
        lambda kind, *, seed=None, **kwargs: SimpleNamespace(
            name=kind,
            seed=seed,
            kwargs=kwargs,
        ),
    )
    monkeypatch.setattr(tuning, "play_one_game", lambda **_kwargs: next(results))
    monkeypatch.setattr(tuning, "starting_state_for", lambda _layout_id: object())
    monkeypatch.setattr(tuning, "ai_version_signature", lambda ai: {"name": ai.name})
    monkeypatch.setattr(tuning, "update_ratings", fake_update_ratings)
    monkeypatch.setattr(tuning, "estimate_rating_uncertainty", fake_uncertainty)

    params = {spec.name: spec.initial for spec in profile_specs("greedy_risk")}
    row = tuning.evaluate_candidate(
        profile="greedy_risk",
        params=params,
        games_per_side=1,
        match_seed=91,
        layout_id="balanced_v1",
        max_turns=20,
        k_factor=16.0,
    )

    assert rating_calls == [
        (1500.0, 1500.0, 0.5, 16.0),
        (1490.0, 1510.0, 0.0, 16.0),
    ]
    assert uncertainty_calls == [2, 2]
    assert row["candidate_rating"] == row["objective_elo"] == 1505.0
    assert row["anchor_rating"] == 1495.0
    assert row["candidate_rating_uncertainty"] == 42.0
    assert row["anchor_rating_uncertainty"] == 42.0
    assert row["wins"] == 1
    assert row["losses"] == 0
    assert row["draws"] == 1
    assert row["games"] == 2
    assert row["illegal_moves"] == 1
    assert row["crashes"] == 2
    assert row["timeouts"] == 3
    assert row["valid"] is False
    assert row["turns"] == [4, 6]
    assert row["step_times_ms"] == [1.0, 3.0, 2.0]
    assert row["average_step_time_ms"] == pytest.approx(2.0)
    assert row["max_step_time_ms"] == 3.0
    assert row["termination_reasons"] == ["draw_max_turns", "illegal_move"]
    assert row["termination_reason_counts"] == {
        "draw_max_turns": 1,
        "illegal_move": 1,
    }
    assert row["candidate_ai_signature"] == {"name": "greedy_risk"}
    assert row["anchor_ai_signature"] == {"name": "greedy_risk"}


def _tuning_config(**overrides):
    values = {
        "profile": "greedy_risk",
        "generations": 2,
        "population_size": 4,
        "elite_count": 2,
        "initial_log_std": 0.5,
        "smoothing": 0.7,
        "min_log_std": 0.05,
        "games_per_side": 1,
        "seed": 2026,
        "layout_id": "balanced_v1",
        "max_turns": 40,
        "k_factor": 24.0,
    }
    values.update(overrides)
    return tuning.TuningConfig(**values)


def test_tuning_config_is_frozen_and_has_explicit_schema():
    config = _tuning_config()

    assert tuning.SCHEMA_VERSION == 1
    assert config.to_dict() == {
        "profile": "greedy_risk",
        "generations": 2,
        "population_size": 4,
        "elite_count": 2,
        "initial_log_std": 0.5,
        "smoothing": 0.7,
        "min_log_std": 0.05,
        "games_per_side": 1,
        "seed": 2026,
        "layout_id": "balanced_v1",
        "max_turns": 40,
        "k_factor": 24.0,
    }
    with pytest.raises(FrozenInstanceError):
        config.generations = 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"profile": "rollout"},
        {"generations": 0},
        {"generations": 1.0},
        {"population_size": True},
        {"population_size": 0},
        {"elite_count": 5},
        {"initial_log_std": 0.0},
        {"initial_log_std": math.inf},
        {"smoothing": 0.0},
        {"smoothing": 1.01},
        {"smoothing": math.nan},
        {"min_log_std": 0.0},
        {"games_per_side": 0},
        {"seed": -1},
        {"seed": 1.0},
        {"layout_id": ""},
        {"max_turns": 0},
        {"k_factor": 0.0},
        {"k_factor": math.inf},
    ],
)
def test_tuning_config_strictly_rejects_invalid_values(overrides):
    with pytest.raises(ValueError):
        _tuning_config(**overrides)


def test_resolve_output_dir_prefers_explicit_then_research_environment(tmp_path):
    explicit = tmp_path / "explicit"
    data_root = tmp_path / "research"

    assert tuning.resolve_output_dir(
        output_dir=explicit,
        run_id="ignored",
        environ={"CG_RESEARCH_DATA_DIR": str(data_root)},
    ) == explicit
    assert tuning.resolve_output_dir(
        output_dir=None,
        run_id="run-17",
        environ={"CG_RESEARCH_DATA_DIR": str(data_root)},
    ) == data_root / "tuning" / "run-17"


def test_resolve_output_dir_default_run_id_is_stable_and_nonempty(tmp_path):
    config = _tuning_config(profile="greedy_zweistein", seed=81)
    environ = {"CG_RESEARCH_DATA_DIR": str(tmp_path)}

    first = tuning.resolve_output_dir(
        output_dir=None,
        run_id=None,
        config=config,
        environ=environ,
    )
    second = tuning.resolve_output_dir(
        output_dir=None,
        run_id=None,
        config=config,
        environ=environ,
    )

    assert first == second
    assert first == tmp_path / "tuning" / "greedy_zweistein-seed-81"
    assert first.name


def test_resolve_output_dir_rejects_missing_source_and_invalid_run_id(tmp_path):
    with pytest.raises(ValueError, match="output-dir.*CG_RESEARCH_DATA_DIR"):
        tuning.resolve_output_dir(output_dir=None, run_id="run-1", environ={})
    with pytest.raises(ValueError, match="run-id"):
        tuning.resolve_output_dir(
            output_dir=None,
            run_id=" ",
            environ={"CG_RESEARCH_DATA_DIR": str(tmp_path)},
        )


def _synthetic_evaluator(calls, *, fail_on_call=None):
    def evaluate(**kwargs):
        captured = {**kwargs, "params": dict(kwargs["params"])}
        calls.append(captured)
        if fail_on_call is not None and len(calls) == fail_on_call:
            raise RuntimeError("synthetic interruption")

        objective = 1500.0 + math.fsum(kwargs["params"].values()) / 1000.0
        games = kwargs["games_per_side"] * 2
        return {
            "games": games,
            "wins": games,
            "losses": 0,
            "draws": 0,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "turns": [3] * games,
            "step_times_ms": [0.25] * games,
            "termination_reasons": ["winner_target_corner"] * games,
            "candidate_ai_signature": {"name": kwargs["profile"]},
            "anchor_ai_signature": {"name": kwargs["profile"]},
            "game_seed_manifest": [{"match_seed": kwargs["match_seed"]}],
            "candidate_rating": objective,
            "anchor_rating": 3000.0 - objective,
            "candidate_rating_uncertainty": 10.0,
            "anchor_rating_uncertainty": 10.0,
            "valid": True,
            "objective_elo": objective,
        }

    return evaluate


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_run_tuning_persists_two_generation_synthetic_run(tmp_path):
    output_dir = tmp_path / "run"
    config = _tuning_config(
        generations=2,
        population_size=3,
        elite_count=1,
    )
    calls = []

    report = tuning.run_tuning(
        config=config,
        output_dir=output_dir,
        evaluator=_synthetic_evaluator(calls),
    )

    candidates_path = output_dir / "candidates.jsonl"
    state_path = output_dir / "state.json"
    report_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    assert candidates_path.is_file()
    assert state_path.is_file()
    assert report_path.is_file()
    assert markdown_path.is_file()

    rows = _read_jsonl(candidates_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    persisted_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(rows) == len(calls) == 6
    assert len({row["candidate_id"] for row in rows}) == 6
    assert [row["candidate_id"] for row in rows] == [
        "g0000-c0000",
        "g0000-c0001",
        "g0000-c0002",
        "g0001-c0000",
        "g0001-c0001",
        "g0001-c0002",
    ]
    assert {call["match_seed"] for call in calls[:3]} == {
        rows[0]["generation_match_seed"]
    }
    assert {call["match_seed"] for call in calls[3:]} == {
        rows[3]["generation_match_seed"]
    }
    assert rows[0]["generation_match_seed"] != rows[3]["generation_match_seed"]

    expected_specs = [
        {
            "name": spec.name,
            "lower": spec.lower,
            "upper": spec.upper,
            "initial": spec.initial,
        }
        for spec in profile_specs(config.profile)
    ]
    for row in rows:
        assert row["schema_version"] == tuning.SCHEMA_VERSION
        assert row["config"] == config.to_dict()
        assert row["profile"] == config.profile
        assert row["specs"] == expected_specs
        assert row["params"]
        assert row["games"] == 2
        assert row["valid"] is True
        assert row["evaluated_at"]

    assert state["schema_version"] == tuning.SCHEMA_VERSION
    assert state["config"] == config.to_dict()
    assert state["profile"] == config.profile
    assert state["specs"] == expected_specs
    assert state["next_generation"] == 2
    assert state["completed_candidates"] == 6
    assert state["distribution"] == report["distribution"]
    assert state["best_candidate"]["candidate_id"] in {
        row["candidate_id"] for row in rows
    }
    assert len(state["generation_seed_manifest"]) == 2

    assert persisted_report == report
    assert report["completed_generations"] == 2
    assert report["candidate_count"] == 6
    assert report["best_candidate"] == state["best_candidate"]
    assert (
        "optimizer/harness evidence only; no default promotion/strength claim"
        in markdown_path.read_text(encoding="utf-8")
    )


def test_run_tuning_rejects_nonempty_new_run_without_resume(tmp_path):
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    (output_dir / "foreign.txt").write_text("occupied", encoding="utf-8")
    calls = []

    with pytest.raises(ValueError, match="non-empty.*--resume"):
        tuning.run_tuning(
            config=_tuning_config(generations=1, population_size=2, elite_count=1),
            output_dir=output_dir,
            evaluator=_synthetic_evaluator(calls),
        )

    assert calls == []


def test_run_tuning_resume_after_interruption_only_evaluates_missing_candidates(
    tmp_path,
):
    config = _tuning_config(
        generations=2,
        population_size=3,
        elite_count=1,
    )
    output_dir = tmp_path / "interrupted"
    interrupted_calls = []

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        tuning.run_tuning(
            config=config,
            output_dir=output_dir,
            evaluator=_synthetic_evaluator(interrupted_calls, fail_on_call=3),
        )

    rows_before_resume = _read_jsonl(output_dir / "candidates.jsonl")
    state_before_resume = json.loads(
        (output_dir / "state.json").read_text(encoding="utf-8")
    )
    assert len(interrupted_calls) == 3
    assert len(rows_before_resume) == 2
    assert state_before_resume["next_generation"] == 0

    resumed_calls = []
    tuning.run_tuning(
        config=config,
        output_dir=output_dir,
        resume=True,
        evaluator=_synthetic_evaluator(resumed_calls),
    )

    rows_after_resume = _read_jsonl(output_dir / "candidates.jsonl")
    assert len(resumed_calls) == 4
    assert resumed_calls[0]["params"] == interrupted_calls[2]["params"]
    assert resumed_calls[0]["match_seed"] == interrupted_calls[2]["match_seed"]
    assert rows_after_resume[:2] == rows_before_resume
    assert len(rows_after_resume) == 6
    assert len({row["candidate_id"] for row in rows_after_resume}) == 6

    fresh_calls = []
    fresh_dir = tmp_path / "fresh"
    tuning.run_tuning(
        config=config,
        output_dir=fresh_dir,
        evaluator=_synthetic_evaluator(fresh_calls),
    )
    fresh_rows = _read_jsonl(fresh_dir / "candidates.jsonl")
    reproducible_fields = lambda row: (
        row["candidate_id"],
        row["params"],
        row["generation_sample_seed"],
        row["generation_match_seed"],
    )
    assert [reproducible_fields(row) for row in rows_after_resume] == [
        reproducible_fields(row) for row in fresh_rows
    ]


def test_resume_replays_fully_appended_generation_when_state_did_not_advance(
    tmp_path,
):
    config = _tuning_config(generations=1, population_size=3, elite_count=1)
    output_dir = tmp_path / "stale-state"
    tuning.run_tuning(
        config=config,
        output_dir=output_dir,
        evaluator=_synthetic_evaluator([]),
    )
    candidates_path = output_dir / "candidates.jsonl"
    rows_before = _read_jsonl(candidates_path)
    state_path = output_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    initial = initial_distribution(
        profile_specs(config.profile),
        initial_log_std=config.initial_log_std,
    )
    state["distribution"] = {
        "log_means": dict(initial.log_means),
        "log_stds": dict(initial.log_stds),
    }
    state["next_generation"] = 0
    state["best_candidate"] = None
    state["completed_candidates"] = 0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    calls = []

    tuning.run_tuning(
        config=config,
        output_dir=output_dir,
        resume=True,
        evaluator=_synthetic_evaluator(calls),
    )

    assert calls == []
    assert _read_jsonl(candidates_path) == rows_before
    resumed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert resumed_state["next_generation"] == 1
    assert resumed_state["completed_candidates"] == 3


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("schema_version", 999, "schema_version"),
        ("profile", "greedy_zweistein", "profile"),
        ("config", {"incompatible": True}, "config"),
        ("specs", [{"incompatible": True}], "specs"),
    ],
)
def test_resume_rejects_incompatible_state_metadata(
    tmp_path,
    field,
    replacement,
    message,
):
    config = _tuning_config(generations=1, population_size=2, elite_count=1)
    output_dir = tmp_path / field
    tuning.run_tuning(
        config=config,
        output_dir=output_dir,
        evaluator=_synthetic_evaluator([]),
    )
    state_path = output_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state[field] = replacement
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        tuning.run_tuning(
            config=config,
            output_dir=output_dir,
            resume=True,
            evaluator=_synthetic_evaluator([]),
        )


def test_resume_rejects_candidate_params_mismatch_and_duplicate_id(tmp_path):
    config = _tuning_config(generations=1, population_size=2, elite_count=1)

    params_dir = tmp_path / "params-mismatch"
    tuning.run_tuning(
        config=config,
        output_dir=params_dir,
        evaluator=_synthetic_evaluator([]),
    )
    params_path = params_dir / "candidates.jsonl"
    params_rows = _read_jsonl(params_path)
    first_name = next(iter(params_rows[0]["params"]))
    params_rows[0]["params"][first_name] += 0.001
    params_path.write_text(
        "\n".join(json.dumps(row) for row in params_rows) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="params"):
        tuning.run_tuning(
            config=config,
            output_dir=params_dir,
            resume=True,
            evaluator=_synthetic_evaluator([]),
        )

    duplicate_dir = tmp_path / "duplicate"
    tuning.run_tuning(
        config=config,
        output_dir=duplicate_dir,
        evaluator=_synthetic_evaluator([]),
    )
    duplicate_path = duplicate_dir / "candidates.jsonl"
    duplicate_rows = _read_jsonl(duplicate_path)
    with duplicate_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(duplicate_rows[0]) + "\n")
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        tuning.run_tuning(
            config=config,
            output_dir=duplicate_dir,
            resume=True,
            evaluator=_synthetic_evaluator([]),
        )


def test_resume_requires_parseable_state_in_nonempty_directory(tmp_path):
    missing_dir = tmp_path / "missing-state"
    missing_dir.mkdir()
    (missing_dir / "candidates.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="state.json"):
        tuning.run_tuning(
            config=_tuning_config(),
            output_dir=missing_dir,
            resume=True,
            evaluator=_synthetic_evaluator([]),
        )

    invalid_dir = tmp_path / "invalid-state"
    invalid_dir.mkdir()
    (invalid_dir / "state.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="parse state.json"):
        tuning.run_tuning(
            config=_tuning_config(),
            output_dir=invalid_dir,
            resume=True,
            evaluator=_synthetic_evaluator([]),
        )


def test_main_cli_calls_run_tuning_and_prints_compact_summary(
    tmp_path,
    monkeypatch,
    capsys,
):
    captured = {}

    def fake_run_tuning(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": tuning.SCHEMA_VERSION,
            "completed_generations": 3,
            "candidate_count": 12,
            "best_candidate": {"candidate_id": "g0002-c0001"},
            "distribution": {"log_means": {}, "log_stds": {}},
        }

    monkeypatch.setattr(tuning, "run_tuning", fake_run_tuning)
    output_dir = tmp_path / "cli-run"
    result = tuning.main(
        [
            "--profile",
            "greedy_zweistein",
            "--generations",
            "3",
            "--population-size",
            "4",
            "--elite-count",
            "2",
            "--initial-log-std",
            "0.6",
            "--smoothing",
            "0.8",
            "--min-log-std",
            "0.04",
            "--games-per-side",
            "2",
            "--seed",
            "88",
            "--layout-id",
            "balanced_v1",
            "--max-turns",
            "55",
            "--k-factor",
            "20",
            "--output-dir",
            str(output_dir),
            "--run-id",
            "ignored-for-explicit-output",
            "--resume",
        ]
    )

    assert result == 0
    assert captured == {
        "config": tuning.TuningConfig(
            profile="greedy_zweistein",
            generations=3,
            population_size=4,
            elite_count=2,
            initial_log_std=0.6,
            smoothing=0.8,
            min_log_std=0.04,
            games_per_side=2,
            seed=88,
            layout_id="balanced_v1",
            max_turns=55,
            k_factor=20.0,
        ),
        "output_dir": output_dir,
        "resume": True,
    }
    stdout = capsys.readouterr().out.strip()
    assert "\n" not in stdout
    assert json.loads(stdout) == {
        "schema_version": tuning.SCHEMA_VERSION,
        "output_dir": str(output_dir),
        "completed_generations": 3,
        "candidate_count": 12,
        "best_candidate_id": "g0002-c0001",
    }


def test_main_cli_missing_output_source_is_system_exit(monkeypatch, capsys):
    monkeypatch.delenv("CG_RESEARCH_DATA_DIR", raising=False)
    monkeypatch.setattr(
        tuning,
        "run_tuning",
        lambda **_kwargs: pytest.fail("run_tuning must not be called"),
    )

    with pytest.raises(SystemExit):
        tuning.main(["--generations", "1", "--population-size", "2", "--elite-count", "1"])

    assert "--output-dir is required unless CG_RESEARCH_DATA_DIR is set" in (
        capsys.readouterr().err
    )
