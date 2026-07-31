"""Resumable CEM tuning for evaluator weights with ladder Elo objectives."""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.evaluator import (
    DISTANCE_WEIGHT as EVALUATOR_DISTANCE_WEIGHT,
    EXPECTED_RISK_WEIGHT as EVALUATOR_EXPECTED_RISK_WEIGHT,
    EXPECTED_WIN_RISK_WEIGHT as EVALUATOR_EXPECTED_WIN_RISK_WEIGHT,
    MATERIAL_WEIGHT as EVALUATOR_MATERIAL_WEIGHT,
)
from ai.zweistein import (
    CAPTURE_RISK_WEIGHT as ZWEISTEIN_CAPTURE_RISK_WEIGHT,
    MATERIAL_WEIGHT as ZWEISTEIN_MATERIAL_WEIGHT,
    MOBILITY_WEIGHT as ZWEISTEIN_MOBILITY_WEIGHT,
    PROGRESS_WEIGHT as ZWEISTEIN_PROGRESS_WEIGHT,
    TARGET_WIN_RISK_WEIGHT as ZWEISTEIN_TARGET_WIN_RISK_WEIGHT,
)
from ai.match import (
    STARTING_LAYOUT_ID,
    ai_version_signature,
    build_ai,
    play_one_game,
    starting_state_for,
)
from core.types import Player
from scripts.ladder import estimate_rating_uncertainty, update_ratings


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WeightSpec:
    name: str
    lower: float
    upper: float
    initial: float

    def __post_init__(self) -> None:
        values = (float(self.lower), float(self.upper), float(self.initial))
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError("weight bounds and initial value must be finite and positive")
        if not self.lower < self.upper:
            raise ValueError("weight lower bound must be less than upper bound")
        if not self.lower <= self.initial <= self.upper:
            raise ValueError("weight initial value must be inside bounds")
        if not self.name:
            raise ValueError("weight name must not be empty")


@dataclass(frozen=True)
class CEMDistribution:
    log_means: dict[str, float]
    log_stds: dict[str, float]


_PROFILE_SPECS: dict[str, tuple[WeightSpec, ...]] = {
    "greedy_risk": (
        WeightSpec(
            "distance_weight",
            lower=0.25,
            upper=4.0,
            initial=EVALUATOR_DISTANCE_WEIGHT,
        ),
        WeightSpec(
            "material_weight",
            lower=2.5,
            upper=40.0,
            initial=EVALUATOR_MATERIAL_WEIGHT,
        ),
        WeightSpec(
            "expected_risk_weight",
            lower=0.5,
            upper=24.0,
            initial=EVALUATOR_EXPECTED_RISK_WEIGHT,
        ),
        WeightSpec(
            "expected_win_risk_weight",
            lower=50.0,
            upper=2000.0,
            initial=EVALUATOR_EXPECTED_WIN_RISK_WEIGHT,
        ),
    ),
    "greedy_zweistein": (
        WeightSpec(
            "progress_weight",
            lower=3.0,
            upper=48.0,
            initial=ZWEISTEIN_PROGRESS_WEIGHT,
        ),
        WeightSpec(
            "material_weight",
            lower=20.0,
            upper=360.0,
            initial=ZWEISTEIN_MATERIAL_WEIGHT,
        ),
        WeightSpec(
            "mobility_weight",
            lower=1.0,
            upper=24.0,
            initial=ZWEISTEIN_MOBILITY_WEIGHT,
        ),
        WeightSpec(
            "capture_risk_weight",
            lower=30.0,
            upper=480.0,
            initial=ZWEISTEIN_CAPTURE_RISK_WEIGHT,
        ),
        WeightSpec(
            "target_win_risk_weight",
            lower=150.0,
            upper=2400.0,
            initial=ZWEISTEIN_TARGET_WIN_RISK_WEIGHT,
        ),
    ),
}


@dataclass(frozen=True)
class TuningConfig:
    profile: str
    generations: int
    population_size: int
    elite_count: int
    initial_log_std: float
    smoothing: float
    min_log_std: float
    games_per_side: int
    seed: int
    layout_id: str
    max_turns: int
    k_factor: float

    def __post_init__(self) -> None:
        if self.profile not in _PROFILE_SPECS:
            raise ValueError(f"unknown tuning profile: {self.profile!r}")
        for field_name in (
            "generations",
            "population_size",
            "elite_count",
            "games_per_side",
            "max_turns",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if self.elite_count > self.population_size:
            raise ValueError("elite_count must not exceed population_size")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not isinstance(self.layout_id, str) or not self.layout_id.strip():
            raise ValueError("layout_id must not be empty")

        for field_name in ("initial_log_std", "min_log_std", "k_factor"):
            value = getattr(self, field_name)
            if isinstance(value, bool):
                raise ValueError(f"{field_name} must be finite and positive")
            numeric = float(value)
            if not math.isfinite(numeric) or numeric <= 0.0:
                raise ValueError(f"{field_name} must be finite and positive")
        if isinstance(self.smoothing, bool):
            raise ValueError("smoothing must be finite and in (0, 1]")
        smoothing = float(self.smoothing)
        if not math.isfinite(smoothing) or not 0.0 < smoothing <= 1.0:
            raise ValueError("smoothing must be finite and in (0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "generations": self.generations,
            "population_size": self.population_size,
            "elite_count": self.elite_count,
            "initial_log_std": self.initial_log_std,
            "smoothing": self.smoothing,
            "min_log_std": self.min_log_std,
            "games_per_side": self.games_per_side,
            "seed": self.seed,
            "layout_id": self.layout_id,
            "max_turns": self.max_turns,
            "k_factor": self.k_factor,
        }


def profile_specs(profile: str) -> tuple[WeightSpec, ...]:
    try:
        return _PROFILE_SPECS[str(profile)]
    except KeyError as exc:
        raise ValueError(f"unknown tuning profile: {profile!r}") from exc


def default_run_id(config: TuningConfig | None = None) -> str:
    if config is None:
        return "cem"
    return f"{config.profile}-seed-{config.seed}"


def _validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run-id must not be empty")
    normalized = run_id.strip()
    if normalized in {".", ".."} or Path(normalized).name != normalized:
        raise ValueError("run-id must be a single path component")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("run-id must be a single path component")
    return normalized


def resolve_output_dir(
    *,
    output_dir: str | Path | None,
    run_id: str | None,
    config: TuningConfig | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    if output_dir is not None:
        if not str(output_dir).strip():
            raise ValueError("output-dir must not be empty")
        return Path(output_dir)

    environment = os.environ if environ is None else environ
    research_root = environment.get("CG_RESEARCH_DATA_DIR", "").strip()
    if not research_root:
        raise ValueError(
            "--output-dir is required unless CG_RESEARCH_DATA_DIR is set"
        )
    selected_run_id = _validate_run_id(
        run_id if run_id is not None else default_run_id(config)
    )
    return Path(research_root) / "tuning" / selected_run_id


def _validate_distribution(
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
) -> None:
    names = {spec.name for spec in specs}
    if set(distribution.log_means) != names or set(distribution.log_stds) != names:
        raise ValueError("distribution keys must exactly match weight specs")
    for name in names:
        mean = float(distribution.log_means[name])
        std = float(distribution.log_stds[name])
        if not math.isfinite(mean):
            raise ValueError(f"non-finite log mean for {name}")
        if not math.isfinite(std) or std <= 0.0:
            raise ValueError(f"log std for {name} must be finite and positive")


def _require_positive_int(value: object, *, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def initial_distribution(
    specs: tuple[WeightSpec, ...],
    *,
    initial_log_std: float,
) -> CEMDistribution:
    std = float(initial_log_std)
    if not math.isfinite(std) or std <= 0.0:
        raise ValueError("initial_log_std must be finite and positive")
    if not specs:
        raise ValueError("at least one weight spec is required")
    return CEMDistribution(
        log_means={spec.name: math.log(spec.initial) for spec in specs},
        log_stds={spec.name: std for spec in specs},
    )


def sample_population(
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
    *,
    population_size: int,
    rng: random.Random,
) -> list[dict[str, float]]:
    size = _require_positive_int(population_size, name="population_size")
    _validate_distribution(specs, distribution)

    population: list[dict[str, float]] = []
    for _index in range(size):
        params: dict[str, float] = {}
        for spec in specs:
            lower_log = math.log(spec.lower)
            upper_log = math.log(spec.upper)
            sampled_log = rng.gauss(
                distribution.log_means[spec.name],
                distribution.log_stds[spec.name],
            )
            sampled_log = min(upper_log, max(lower_log, sampled_log))
            sampled = math.exp(sampled_log)
            params[spec.name] = min(spec.upper, max(spec.lower, sampled))
        population.append(params)
    return population


def select_elites(rows: list[dict], *, elite_count: int) -> list[dict]:
    count = _require_positive_int(elite_count, name="elite_count")
    valid_rows = [row for row in rows if bool(row.get("valid", False))]
    scored_rows: list[tuple[float, str, dict]] = []
    for row in valid_rows:
        try:
            objective_elo = float(row["objective_elo"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("objective_elo must be finite for valid candidates") from exc
        if not math.isfinite(objective_elo):
            raise ValueError("objective_elo must be finite for valid candidates")
        scored_rows.append((objective_elo, str(row["candidate_id"]), row))
    if len(scored_rows) < count:
        raise ValueError("not enough valid candidates to select elites")
    scored_rows.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored_rows[:count]]


def update_distribution(
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
    *,
    elite_params: list[dict[str, float]],
    smoothing: float,
    min_log_std: float,
) -> CEMDistribution:
    alpha = float(smoothing)
    minimum_std = float(min_log_std)
    if not 0.0 < alpha <= 1.0:
        raise ValueError("smoothing must be in (0, 1]")
    if not math.isfinite(minimum_std) or minimum_std <= 0.0:
        raise ValueError("min_log_std must be finite and positive")
    if not elite_params:
        raise ValueError("elite_params must not be empty")
    _validate_distribution(specs, distribution)

    updated_means: dict[str, float] = {}
    updated_stds: dict[str, float] = {}
    for spec in specs:
        logs = []
        for params in elite_params:
            value = float(params[spec.name])
            if not math.isfinite(value) or not spec.lower <= value <= spec.upper:
                raise ValueError(f"elite {spec.name} outside declared bounds")
            logs.append(math.log(value))
        elite_mean = math.fsum(logs) / len(logs)
        elite_variance = math.fsum(
            (value - elite_mean) ** 2 for value in logs
        ) / len(logs)
        elite_std = math.sqrt(elite_variance)

        old_mean = distribution.log_means[spec.name]
        old_std = distribution.log_stds[spec.name]
        updated_means[spec.name] = (1.0 - alpha) * old_mean + alpha * elite_mean
        updated_stds[spec.name] = max(
            minimum_std,
            (1.0 - alpha) * old_std + alpha * elite_std,
        )

    return CEMDistribution(log_means=updated_means, log_stds=updated_stds)


def _validated_candidate_params(
    profile: str,
    params: Mapping[str, Any],
) -> dict[str, float]:
    specs = profile_specs(profile)
    expected_names = {spec.name for spec in specs}
    if set(params) != expected_names:
        raise ValueError("candidate params must exactly match profile weight specs")

    validated: dict[str, float] = {}
    for spec in specs:
        value = float(params[spec.name])
        if not math.isfinite(value) or not spec.lower <= value <= spec.upper:
            raise ValueError(f"candidate {spec.name} outside declared bounds")
        validated[spec.name] = value
    return validated


def _red_score(winner: Player | None) -> float:
    if winner is Player.RED:
        return 1.0
    if winner is Player.BLUE:
        return 0.0
    return 0.5


def evaluate_candidate(
    *,
    profile: str,
    params: Mapping[str, Any],
    games_per_side: int,
    match_seed: int,
    layout_id: str = STARTING_LAYOUT_ID,
    max_turns: int = 200,
    k_factor: float = 32.0,
) -> dict[str, Any]:
    """Evaluate one profile candidate against its same-kind default anchor."""
    games_each_side = _require_positive_int(
        games_per_side,
        name="games_per_side",
    )
    turn_limit = _require_positive_int(max_turns, name="max_turns")
    if type(match_seed) is not int or match_seed < 0:
        raise ValueError("match_seed must be a non-negative integer")
    factor = float(k_factor)
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValueError("k_factor must be finite and positive")

    candidate_params = _validated_candidate_params(profile, params)
    candidate_rating = 1500.0
    anchor_rating = 1500.0
    wins = 0
    losses = 0
    draws = 0
    illegal_moves = 0
    crashes = 0
    timeouts = 0
    turns: list[int] = []
    step_times_ms: list[float] = []
    termination_reasons: list[str] = []
    game_seed_manifest: list[dict[str, Any]] = []
    candidate_signature: dict[str, Any] | None = None
    anchor_signature: dict[str, Any] | None = None

    for pair_index in range(games_each_side):
        pair_seed = match_seed * 1_000_003 + pair_index
        dice_seed = pair_seed * 3
        candidate_ai_seed = pair_seed * 3 + 1
        anchor_ai_seed = pair_seed * 3 + 2

        for orientation in ("candidate_red", "candidate_blue"):
            candidate_ai = build_ai(
                profile,
                seed=candidate_ai_seed,
                **candidate_params,
                randomize_ties=False,
            )
            anchor_ai = build_ai(
                profile,
                seed=anchor_ai_seed,
                randomize_ties=False,
            )
            if candidate_signature is None:
                candidate_signature = ai_version_signature(candidate_ai)
                anchor_signature = ai_version_signature(anchor_ai)

            if orientation == "candidate_red":
                red_ai = candidate_ai
                blue_ai = anchor_ai
                red_ai_seed = candidate_ai_seed
                blue_ai_seed = anchor_ai_seed
                candidate_color = Player.RED
            else:
                red_ai = anchor_ai
                blue_ai = candidate_ai
                red_ai_seed = anchor_ai_seed
                blue_ai_seed = candidate_ai_seed
                candidate_color = Player.BLUE

            result = play_one_game(
                red_ai=red_ai,
                blue_ai=blue_ai,
                dice_rng=random.Random(dice_seed),
                max_turns=turn_limit,
                starting_state=starting_state_for(layout_id),
            )
            red_score = _red_score(result.winner)
            if orientation == "candidate_red":
                candidate_rating, anchor_rating = update_ratings(
                    candidate_rating,
                    anchor_rating,
                    red_score=red_score,
                    k_factor=factor,
                )
            else:
                anchor_rating, candidate_rating = update_ratings(
                    anchor_rating,
                    candidate_rating,
                    red_score=red_score,
                    k_factor=factor,
                )

            if result.winner is None:
                draws += 1
            elif result.winner is candidate_color:
                wins += 1
            else:
                losses += 1
            illegal_moves += int(result.illegal_moves)
            crashes += int(result.crashes)
            timeouts += int(result.timeouts)
            turns.append(int(result.turns))
            step_times_ms.extend(float(value) for value in result.step_times_ms)
            termination_reasons.append(str(result.termination_reason))
            game_seed_manifest.append(
                {
                    "pair_index": pair_index,
                    "orientation": orientation,
                    "match_seed": match_seed,
                    "dice_seed": dice_seed,
                    "candidate_ai_seed": candidate_ai_seed,
                    "anchor_ai_seed": anchor_ai_seed,
                    "red_ai_seed": red_ai_seed,
                    "blue_ai_seed": blue_ai_seed,
                }
            )

    games = games_each_side * 2
    candidate_uncertainty = estimate_rating_uncertainty(games)
    anchor_uncertainty = estimate_rating_uncertainty(games)
    reason_counts = dict(Counter(termination_reasons))
    return {
        "profile": profile,
        "anchor_profile": profile,
        "params": candidate_params,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "valid": illegal_moves == crashes == timeouts == 0,
        "turns": turns,
        "total_turns": sum(turns),
        "average_turns": math.fsum(turns) / len(turns) if turns else 0.0,
        "step_times_ms": step_times_ms,
        "average_step_time_ms": (
            math.fsum(step_times_ms) / len(step_times_ms)
            if step_times_ms
            else 0.0
        ),
        "max_step_time_ms": max(step_times_ms, default=0.0),
        "termination_reasons": termination_reasons,
        "termination_reason_counts": reason_counts,
        "candidate_ai_signature": candidate_signature,
        "anchor_ai_signature": anchor_signature,
        "game_seed_manifest": game_seed_manifest,
        "candidate_rating": candidate_rating,
        "anchor_rating": anchor_rating,
        "candidate_rating_uncertainty": candidate_uncertainty,
        "anchor_rating_uncertainty": anchor_uncertainty,
        "objective_elo": candidate_rating,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _specs_payload(specs: tuple[WeightSpec, ...]) -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "lower": spec.lower,
            "upper": spec.upper,
            "initial": spec.initial,
        }
        for spec in specs
    ]


def _distribution_payload(distribution: CEMDistribution) -> dict[str, Any]:
    return {
        "log_means": dict(distribution.log_means),
        "log_stds": dict(distribution.log_stds),
    }


def _generation_seeds(config: TuningConfig, generation: int) -> dict[str, int]:
    base_seed = config.seed * 1_000_003 + generation * 2
    return {
        "generation": generation,
        "sample_seed": base_seed,
        "match_seed": base_seed + 1,
    }


def _generation_seed_manifest(config: TuningConfig) -> list[dict[str, int]]:
    return [
        _generation_seeds(config, generation)
        for generation in range(config.generations)
    ]


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _candidate_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "generation": row["generation"],
        "index": row["index"],
        "params": dict(row["params"]),
        "objective_elo": float(row["objective_elo"]),
        "valid": bool(row["valid"]),
    }


def _best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid_rows = []
    for row in rows:
        if not bool(row.get("valid", False)):
            continue
        try:
            objective = float(row["objective_elo"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("objective_elo must be finite for valid candidates") from exc
        if not math.isfinite(objective):
            raise ValueError("objective_elo must be finite for valid candidates")
        valid_rows.append((objective, str(row["candidate_id"]), row))
    if not valid_rows:
        return None
    valid_rows.sort(key=lambda item: (-item[0], item[1]))
    return _candidate_summary(valid_rows[0][2])


def _new_state(
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "updated_at": now,
        "config": config.to_dict(),
        "profile": config.profile,
        "specs": _specs_payload(specs),
        "distribution": _distribution_payload(distribution),
        "next_generation": 0,
        "best_candidate": None,
        "completed_candidates": 0,
        "generation_seed_manifest": _generation_seed_manifest(config),
    }


def _render_markdown_report(report: Mapping[str, Any]) -> str:
    best = report.get("best_candidate")
    best_id = best["candidate_id"] if isinstance(best, Mapping) else "none"
    return "\n".join(
        (
            "# CEM Evaluator Tuning Report",
            "",
            f"- profile: {report['profile']}",
            f"- completed_generations: {report['completed_generations']}",
            f"- candidate_count: {report['candidate_count']}",
            f"- best_candidate: {best_id}",
            "",
            "optimizer/harness evidence only; no default promotion/strength claim",
            "",
        )
    )


def _write_reports(
    *,
    output_dir: Path,
    state: Mapping[str, Any],
    candidate_count: int,
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": state["generated_at"],
        "updated_at": _utc_now(),
        "config": state["config"],
        "profile": state["profile"],
        "specs": state["specs"],
        "distribution": state["distribution"],
        "completed_generations": state["next_generation"],
        "candidate_count": candidate_count,
        "best_candidate": state["best_candidate"],
        "generation_seed_manifest": state["generation_seed_manifest"],
        "candidates_jsonl": str(output_dir / "candidates.jsonl"),
        "evidence_note": (
            "optimizer/harness evidence only; no default promotion/strength claim"
        ),
    }
    _atomic_write_json(output_dir / "report.json", report)
    (output_dir / "report.md").write_text(
        _render_markdown_report(report),
        encoding="utf-8",
    )
    return report


def _distribution_from_payload(
    payload: Any,
    specs: tuple[WeightSpec, ...],
) -> CEMDistribution:
    if not isinstance(payload, Mapping):
        raise ValueError("state distribution must be an object")
    try:
        distribution = CEMDistribution(
            log_means={
                str(name): float(value)
                for name, value in payload["log_means"].items()
            },
            log_stds={
                str(name): float(value)
                for name, value in payload["log_stds"].items()
            },
        )
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("state distribution is invalid") from exc
    _validate_distribution(specs, distribution)
    return distribution


def _load_resume_state(
    path: Path,
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("non-empty resume directory requires state.json")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("could not parse state.json") from exc
    if not isinstance(state, dict):
        raise ValueError("state.json must contain a JSON object")

    expected_fields = {
        "schema_version": SCHEMA_VERSION,
        "profile": config.profile,
        "config": config.to_dict(),
        "specs": _specs_payload(specs),
        "generation_seed_manifest": _generation_seed_manifest(config),
    }
    for field_name, expected in expected_fields.items():
        if state.get(field_name) != expected:
            raise ValueError(f"resume state {field_name} mismatch")
    next_generation = state.get("next_generation")
    if (
        type(next_generation) is not int
        or next_generation < 0
        or next_generation > config.generations
    ):
        raise ValueError("resume state next_generation is invalid")
    _distribution_from_payload(state.get("distribution"), specs)
    return state


def _load_candidate_rows(
    path: Path,
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not path.exists():
        return [], {}
    rows: list[dict[str, Any]] = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    expected_common = {
        "schema_version": SCHEMA_VERSION,
        "config": config.to_dict(),
        "profile": config.profile,
        "specs": _specs_payload(specs),
    }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("could not read candidates.jsonl") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"could not parse candidates.jsonl line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(
                f"candidates.jsonl line {line_number} must be an object"
            )
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError(
                f"candidates.jsonl line {line_number} has invalid candidate_id"
            )
        if candidate_id in rows_by_id:
            raise ValueError(f"duplicate candidate_id in candidates.jsonl: {candidate_id}")
        for field_name, expected in expected_common.items():
            if row.get(field_name) != expected:
                raise ValueError(
                    f"candidate {candidate_id} {field_name} mismatch"
                )
        generation = row.get("generation")
        index = row.get("index")
        if (
            type(generation) is not int
            or not 0 <= generation < config.generations
            or type(index) is not int
            or not 0 <= index < config.population_size
        ):
            raise ValueError(f"candidate {candidate_id} generation/index mismatch")
        expected_id = f"g{generation:04d}-c{index:04d}"
        if candidate_id != expected_id:
            raise ValueError(f"candidate {candidate_id} generation/index mismatch")
        rows.append(row)
        rows_by_id[candidate_id] = row
    return rows, rows_by_id


def _population_for_generation(
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
    generation: int,
) -> tuple[list[dict[str, float]], dict[str, int]]:
    seeds = _generation_seeds(config, generation)
    population = sample_population(
        specs,
        distribution,
        population_size=config.population_size,
        rng=random.Random(seeds["sample_seed"]),
    )
    return population, seeds


def _validate_existing_candidate(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    generation: int,
    index: int,
    params: Mapping[str, float],
    seeds: Mapping[str, int],
) -> None:
    expected_fields = {
        "candidate_id": candidate_id,
        "generation": generation,
        "index": index,
        "params": dict(params),
        "generation_sample_seed": seeds["sample_seed"],
        "generation_match_seed": seeds["match_seed"],
    }
    for field_name, expected in expected_fields.items():
        if row.get(field_name) != expected:
            raise ValueError(f"candidate {candidate_id} {field_name} mismatch")


def _advance_distribution(
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
    distribution: CEMDistribution,
    generation_rows: list[dict[str, Any]],
) -> CEMDistribution:
    elites = select_elites(generation_rows, elite_count=config.elite_count)
    return update_distribution(
        specs,
        distribution,
        elite_params=[row["params"] for row in elites],
        smoothing=config.smoothing,
        min_log_std=config.min_log_std,
    )


def _replay_completed_generations(
    *,
    config: TuningConfig,
    specs: tuple[WeightSpec, ...],
    state: Mapping[str, Any],
    rows_by_id: Mapping[str, dict[str, Any]],
) -> CEMDistribution:
    distribution = initial_distribution(
        specs,
        initial_log_std=config.initial_log_std,
    )
    for generation in range(int(state["next_generation"])):
        population, seeds = _population_for_generation(
            config=config,
            specs=specs,
            distribution=distribution,
            generation=generation,
        )
        generation_rows: list[dict[str, Any]] = []
        for index, params in enumerate(population):
            candidate_id = f"g{generation:04d}-c{index:04d}"
            row = rows_by_id.get(candidate_id)
            if row is None:
                raise ValueError(
                    f"resume state completed generation is missing {candidate_id}"
                )
            _validate_existing_candidate(
                row,
                candidate_id=candidate_id,
                generation=generation,
                index=index,
                params=params,
                seeds=seeds,
            )
            generation_rows.append(row)
        distribution = _advance_distribution(
            config=config,
            specs=specs,
            distribution=distribution,
            generation_rows=generation_rows,
        )
    if _distribution_payload(distribution) != state.get("distribution"):
        raise ValueError("resume state distribution mismatch")
    return distribution


def run_tuning(
    *,
    config: TuningConfig,
    output_dir: str | Path,
    resume: bool = False,
    evaluator: Callable[..., Mapping[str, Any]] = evaluate_candidate,
) -> dict[str, Any]:
    output = Path(output_dir)
    if output.exists() and not output.is_dir():
        raise ValueError("output directory path exists and is not a directory")
    is_nonempty = output.exists() and any(output.iterdir())
    if is_nonempty and not resume:
        raise ValueError("output directory is non-empty; pass --resume to continue")
    output.mkdir(parents=True, exist_ok=True)

    specs = profile_specs(config.profile)
    state_path = output / "state.json"
    candidates_path = output / "candidates.jsonl"
    if is_nonempty:
        state = _load_resume_state(state_path, config=config, specs=specs)
        rows, rows_by_id = _load_candidate_rows(
            candidates_path,
            config=config,
            specs=specs,
        )
        distribution = _replay_completed_generations(
            config=config,
            specs=specs,
            state=state,
            rows_by_id=rows_by_id,
        )
        state["best_candidate"] = _best_candidate(rows)
        state["completed_candidates"] = len(rows)
    else:
        distribution = initial_distribution(
            specs,
            initial_log_std=config.initial_log_std,
        )
        state = _new_state(config=config, specs=specs, distribution=distribution)
        rows = []
        rows_by_id = {}
        _atomic_write_json(state_path, state)

    for generation in range(int(state["next_generation"]), config.generations):
        population, seeds = _population_for_generation(
            config=config,
            specs=specs,
            distribution=distribution,
            generation=generation,
        )
        generation_rows: list[dict[str, Any]] = []
        for index, params in enumerate(population):
            candidate_id = f"g{generation:04d}-c{index:04d}"
            existing = rows_by_id.get(candidate_id)
            if existing is not None:
                _validate_existing_candidate(
                    existing,
                    candidate_id=candidate_id,
                    generation=generation,
                    index=index,
                    params=params,
                    seeds=seeds,
                )
                generation_rows.append(existing)
                continue

            evaluation = dict(
                evaluator(
                    profile=config.profile,
                    params=dict(params),
                    games_per_side=config.games_per_side,
                    match_seed=seeds["match_seed"],
                    layout_id=config.layout_id,
                    max_turns=config.max_turns,
                    k_factor=config.k_factor,
                )
            )
            row = {
                **evaluation,
                "schema_version": SCHEMA_VERSION,
                "config": config.to_dict(),
                "profile": config.profile,
                "specs": _specs_payload(specs),
                "generation": generation,
                "index": index,
                "candidate_id": candidate_id,
                "params": dict(params),
                "generation_sample_seed": seeds["sample_seed"],
                "generation_match_seed": seeds["match_seed"],
                "evaluated_at": _utc_now(),
            }
            _append_jsonl(candidates_path, row)
            rows.append(row)
            rows_by_id[candidate_id] = row
            generation_rows.append(row)
            state["best_candidate"] = _best_candidate(rows)
            state["completed_candidates"] = len(rows)
            state["updated_at"] = _utc_now()
            _atomic_write_json(state_path, state)

        distribution = _advance_distribution(
            config=config,
            specs=specs,
            distribution=distribution,
            generation_rows=generation_rows,
        )
        state["distribution"] = _distribution_payload(distribution)
        state["next_generation"] = generation + 1
        state["best_candidate"] = _best_candidate(rows)
        state["completed_candidates"] = len(rows)
        state["updated_at"] = _utc_now()
        _atomic_write_json(state_path, state)

    return _write_reports(
        output_dir=output,
        state=state,
        candidate_count=len(rows),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tune greedy evaluator weights with resumable CEM."
    )
    parser.add_argument(
        "--profile",
        choices=tuple(_PROFILE_SPECS),
        default="greedy_risk",
    )
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--population-size", type=int, default=12)
    parser.add_argument("--elite-count", type=int, default=4)
    parser.add_argument("--initial-log-std", type=float, default=0.5)
    parser.add_argument("--smoothing", type=float, default=0.7)
    parser.add_argument("--min-log-std", type=float, default=0.05)
    parser.add_argument("--games-per-side", type=int, default=4)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--layout-id", default=STARTING_LAYOUT_ID)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--k-factor", type=float, default=32.0)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = TuningConfig(
            profile=args.profile,
            generations=args.generations,
            population_size=args.population_size,
            elite_count=args.elite_count,
            initial_log_std=args.initial_log_std,
            smoothing=args.smoothing,
            min_log_std=args.min_log_std,
            games_per_side=args.games_per_side,
            seed=args.seed,
            layout_id=args.layout_id,
            max_turns=args.max_turns,
            k_factor=args.k_factor,
        )
        output_dir = resolve_output_dir(
            output_dir=args.output_dir,
            run_id=args.run_id,
            config=config,
        )
    except ValueError as exc:
        parser.error(str(exc))

    report = run_tuning(
        config=config,
        output_dir=output_dir,
        resume=args.resume,
    )
    best = report.get("best_candidate")
    best_candidate_id = (
        best.get("candidate_id") if isinstance(best, Mapping) else None
    )
    summary = {
        "schema_version": report.get("schema_version", SCHEMA_VERSION),
        "output_dir": str(output_dir),
        "completed_generations": report.get("completed_generations", 0),
        "candidate_count": report.get("candidate_count", 0),
        "best_candidate_id": best_candidate_id,
    }
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
