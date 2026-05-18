"""Lightweight resumable opening-layout screening.\n\nThe script generates deterministic opening candidates, compares them against a\nbaseline layout with current release rollout kwargs, and writes incremental JSON\nplus a small markdown summary. It never modifies GUI or release defaults.\n"""
from __future__ import annotations

import argparse
import json

import itertools
import random
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "opening_light_screen.json"
DEFAULT_SUMMARY = ROOT / "reports" / "opening_light_screen.md"
SCHEMA_VERSION = 1

METADATA_KEYS = {"ai", "fallback_ai", "promotion_report"}
MAX_DEFAULT_PLANNED_GAMES = 160
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game
from ai.opening_layouts import PRESETS, RED_ZONE, Layout, mirror_layout, validate_layout
from core.game_state import GameState
from core.types import Player, Position

Mode = Literal["curated", "full"]
GameRole = Literal["candidate_as_red", "candidate_as_blue"]

@dataclass(frozen=True)
class OpeningCandidate:
    candidate_id: str
    source: str
    red_layout: Layout
    blue_layout: Layout


@dataclass(frozen=True)
class GameSeeds:
    role: str
    game_index: int
    base_seed: int
    dice_seed: int
    red_seed: int
    blue_seed: int


def sorted_red_zone() -> tuple[Position, ...]:
    return tuple(sorted(RED_ZONE, key=lambda position: (position.row + position.col, position.row, position.col)))


def layout_signature(layout: Mapping[int, Position]) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (int(piece_id), position.row, position.col)
        for piece_id, position in sorted(layout.items())
    )


def copy_layout(layout: Mapping[int, Position]) -> Layout:
    return {int(piece_id): position for piece_id, position in layout.items()}


def layout_from_order(piece_order: Iterable[int]) -> Layout:
    positions = sorted_red_zone()
    order = tuple(int(piece_id) for piece_id in piece_order)
    if len(order) != len(positions) or set(order) != set(range(1, 7)):
        raise ValueError("piece_order must contain piece ids 1..6 exactly once")
    return {piece_id: position for piece_id, position in zip(order, positions)}


def swapped_layout(layout: Mapping[int, Position], first_piece_id: int, second_piece_id: int) -> Layout:
    copied = copy_layout(layout)
    copied[first_piece_id], copied[second_piece_id] = copied[second_piece_id], copied[first_piece_id]
    return copied


def reversed_layout(layout: Mapping[int, Position]) -> Layout:
    copied = copy_layout(layout)
    return {piece_id: copied[7 - piece_id] for piece_id in range(1, 7)}


def all_permutation_layouts() -> list[Layout]:
    positions = sorted_red_zone()
    return [
        {piece_id: position for piece_id, position in zip(range(1, 7), permutation)}
        for permutation in itertools.permutations(positions, 6)
    ]


def curated_layout_sources(seed: int) -> list[tuple[str, Layout]]:
    balanced = copy_layout(PRESETS["balanced_v1"].red)
    sources: list[tuple[str, Layout]] = [
        ("preset:balanced_v1", balanced),
        ("preset:aggressive_v1", copy_layout(PRESETS["aggressive_v1"].red)),
        ("preset:defensive_v1", copy_layout(PRESETS["defensive_v1"].red)),
        ("heuristic:low_ids_forward", layout_from_order((6, 5, 4, 3, 2, 1))),
        ("heuristic:high_ids_forward", layout_from_order((1, 2, 3, 5, 4, 6))),
        ("heuristic:low_ids_center", layout_from_order((6, 5, 1, 4, 2, 3))),
        ("heuristic:high_ids_center", layout_from_order((1, 2, 6, 3, 5, 4))),
        ("swap:balanced_1_6", swapped_layout(balanced, 1, 6)),
        ("swap:balanced_2_5", swapped_layout(balanced, 2, 5)),
        ("swap:balanced_3_4", swapped_layout(balanced, 3, 4)),
        ("heuristic:balanced_reverse", reversed_layout(balanced)),
    ]

    shuffled = all_permutation_layouts()
    random.Random(seed).shuffle(shuffled)
    sources.extend((f"shuffled_720:{index:03d}", layout) for index, layout in enumerate(shuffled))
    return sources


def generate_candidates(
    *,
    mode: Mode,
    max_candidates: int | None = None,
    seed: int = 2026,
) -> list[OpeningCandidate]:
    if max_candidates is not None and max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    if mode not in ("curated", "full"):
        raise ValueError("mode must be 'curated' or 'full'")

    raw_sources: Iterable[tuple[str, Layout]]
    if mode == "curated":
        raw_sources = curated_layout_sources(seed)
    else:
        raw_sources = (("full", layout) for layout in all_permutation_layouts())

    candidates: list[OpeningCandidate] = []
    seen_layouts: set[tuple[tuple[int, int, int], ...]] = set()
    for source, red_layout in raw_sources:
        signature = layout_signature(red_layout)
        if signature in seen_layouts:
            continue

        blue_layout = mirror_layout(red_layout)
        errors = validate_layout(red_layout, blue_layout)
        if errors:
            continue

        seen_layouts.add(signature)
        candidates.append(
            OpeningCandidate(
                candidate_id=f"{mode}_{len(candidates):03d}",
                source=source,
                red_layout=copy_layout(red_layout),
                blue_layout=blue_layout,
            )
        )
        if max_candidates is not None and len(candidates) >= max_candidates:
            break

    return candidates


def make_game_seeds(
    *,
    master_seed: int,
    candidate_index: int,
    role: GameRole,
    local_game_index: int,
    games_per_side: int,
) -> GameSeeds:
    if role not in ("candidate_as_red", "candidate_as_blue"):
        raise ValueError("role must be 'candidate_as_red' or 'candidate_as_blue'")
    if games_per_side < 1:
        raise ValueError("games_per_side must be >= 1")
    if local_game_index < 0 or local_game_index >= games_per_side:
        raise ValueError("local_game_index must satisfy 0 <= local_game_index < games_per_side")

    side_game_index = (
        local_game_index
        if role == "candidate_as_red"
        else games_per_side + local_game_index
    )
    base_seed = master_seed * 100000 + candidate_index * 1000 + side_game_index
    return GameSeeds(
        role=role,
        game_index=local_game_index,
        base_seed=base_seed,
        dice_seed=base_seed * 3,
        red_seed=base_seed * 3 + 1,
        blue_seed=base_seed * 3 + 2,
    )


def layout_to_json(layout: Mapping[int, Position]) -> dict[str, list[int]]:
    return {
        str(piece_id): [position.row, position.col]
        for piece_id, position in sorted(layout.items())
    }


def layout_from_json(data: Mapping[str | int, Any]) -> Layout:
    layout: Layout = {}
    for piece_id, position in data.items():
        if isinstance(position, Mapping):
            layout[int(piece_id)] = Position.from_dict(dict(position))
        else:
            row, col = position
            layout[int(piece_id)] = Position(row=int(row), col=int(col))
    return layout


def seeds_to_json(seeds: GameSeeds) -> dict[str, int | str]:
    return {
        "role": seeds.role,
        "game_index": seeds.game_index,
        "base_seed": seeds.base_seed,
        "dice_seed": seeds.dice_seed,
        "red_seed": seeds.red_seed,
        "blue_seed": seeds.blue_seed,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_run_payload(
    *,
    argv: list[str],
    mode: Mode,
    max_candidates: int,
    candidate_count: int,
    games_per_side: int,
    seed: int,
    baseline_layout: str,
    max_turns: int,
    ai_kind: str,
    ai_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "updated_at": now,
        "argv": argv,
        "mode": mode,
        "max_candidates": max_candidates,
        "candidate_count": candidate_count,
        "games_per_side": games_per_side,
        "seed": seed,
        "baseline_layout": baseline_layout,
        "max_turns": max_turns,
        "ai_kind": ai_kind,
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "ai_kwargs": dict(ai_kwargs),
        "results": [],
    }


def is_result_complete(
    result: Mapping[str, Any],
    candidate: OpeningCandidate,
    expected_games: int,
) -> bool:
    return (
        result.get("candidate_id") == candidate.candidate_id
        and result.get("combined_games") == expected_games
        and result.get("red_layout") == layout_to_json(candidate.red_layout)
    )


def validate_resume_compatible(
    existing: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    required_matches = (
        "schema_version",
        "mode",
        "seed",
        "baseline_layout",
        "games_per_side",
        "max_turns",
        "ai_kind",
        "ai_kwargs",
    )
    for key in required_matches:
        if existing.get(key) != expected.get(key):
            raise ValueError(f"incompatible resume output: {key} differs")

    if existing.get("max_candidates", 0) > expected.get("max_candidates", 0):
        raise ValueError("incompatible resume output: max_candidates exceeds current run")


def load_resume_payload(
    path: Path,
    *,
    expected: dict[str, Any],
    no_resume: bool,
) -> dict[str, Any]:
    if no_resume or not path.exists():
        return expected

    existing = json.loads(path.read_text(encoding="utf-8"))
    validate_resume_compatible(existing, expected)
    return existing


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def role_stats(
    *,
    results: Iterable[tuple[Any, GameSeeds]],
    candidate_winner: Player,
) -> dict[str, Any]:
    rows = list(results)
    wins = sum(1 for result, _seeds in rows if result.winner is candidate_winner)
    games = len(rows)
    return {
        "games": games,
        "wins": wins,
        "win_rate": wins / games if games else 0.0,
        "illegal_moves": sum(int(getattr(result, "illegal_moves", 0)) for result, _seeds in rows),
        "crashes": sum(int(getattr(result, "crashes", 0)) for result, _seeds in rows),
        "timeouts": sum(int(getattr(result, "timeouts", 0)) for result, _seeds in rows),
        "turns": [int(getattr(result, "turns", 0)) for result, _seeds in rows],
        "step_times_ms": [
            float(step_time)
            for result, _seeds in rows
            for step_time in (getattr(result, "step_times_ms", None) or [])
        ],
        "seeds_used": [seeds_to_json(seeds) for _result, seeds in rows],
    }


def aggregate_candidate_result(
    *,
    candidate: OpeningCandidate,
    games_per_side: int,
    red_results: Iterable[tuple[Any, GameSeeds]],
    blue_results: Iterable[tuple[Any, GameSeeds]],
) -> dict[str, Any]:
    red = role_stats(results=red_results, candidate_winner=Player.RED)
    blue = role_stats(results=blue_results, candidate_winner=Player.BLUE)
    combined_games = red["games"] + blue["games"]
    combined_wins = red["wins"] + blue["wins"]
    turns = [*red["turns"], *blue["turns"]]
    step_times = [*red["step_times_ms"], *blue["step_times_ms"]]

    return {
        "candidate_id": candidate.candidate_id,
        "source": candidate.source,
        "games_per_side": games_per_side,
        "red_layout": layout_to_json(candidate.red_layout),
        "blue_layout": layout_to_json(candidate.blue_layout),
        "candidate_wins_as_red": red["wins"],
        "candidate_wins_as_blue": blue["wins"],
        "combined_candidate_wins": combined_wins,
        "combined_games": combined_games,
        "combined_win_rate": combined_wins / combined_games if combined_games else 0.0,
        "illegal_moves": red["illegal_moves"] + blue["illegal_moves"],
        "crashes": red["crashes"] + blue["crashes"],
        "timeouts": red["timeouts"] + blue["timeouts"],
        "average_turns": sum(turns) / len(turns) if turns else 0.0,
        "average_step_time_ms": sum(step_times) / len(step_times) if step_times else 0.0,
        "max_step_time_ms": max(step_times) if step_times else 0.0,
        "seeds_used": [*red["seeds_used"], *blue["seeds_used"]],
        "candidate_as_red": red,
        "candidate_as_blue": blue,
    }


def run_one_direction(
    *,
    candidate: OpeningCandidate,
    candidate_index: int,
    role: GameRole,
    games_per_side: int,
    master_seed: int,
    ai_kind: str,
    baseline: Any,
    ai_kwargs: Mapping[str, Any] | None = None,
    max_turns: int = 200,
) -> list[tuple[Any, GameSeeds]]:
    if role == "candidate_as_red":
        red_layout = candidate.red_layout
        blue_layout = baseline.blue
    elif role == "candidate_as_blue":
        red_layout = baseline.red
        blue_layout = candidate.blue_layout
    else:
        raise ValueError("role must be 'candidate_as_red' or 'candidate_as_blue'")

    kwargs = dict(ai_kwargs or {})
    results: list[tuple[Any, GameSeeds]] = []
    for local_game_index in range(games_per_side):
        seeds = make_game_seeds(
            master_seed=master_seed,
            candidate_index=candidate_index,
            role=role,
            local_game_index=local_game_index,
            games_per_side=games_per_side,
        )
        state = GameState.from_layout(
            red=red_layout,
            blue=blue_layout,
            current_player=Player.RED,
        )
        result = play_one_game(
            red_ai=build_ai(ai_kind, seed=seeds.red_seed, **kwargs),
            blue_ai=build_ai(ai_kind, seed=seeds.blue_seed, **kwargs),
            dice_rng=random.Random(seeds.dice_seed),
            max_turns=max_turns,
            starting_state=state,
        )
        results.append((result, seeds))
    return results


def run_candidate(
    *,
    candidate: OpeningCandidate,
    candidate_index: int,
    games_per_side: int,
    master_seed: int,
    baseline: Any | None = None,
    ai_kind: str | None = None,
    ai_kwargs: Mapping[str, Any] | None = None,
    max_turns: int = 200,
) -> dict[str, Any]:
    if ai_kind is None or ai_kwargs is None:
        default_kind, default_kwargs = load_release_default_ai_config()
        ai_kind = ai_kind or default_kind
        ai_kwargs = ai_kwargs if ai_kwargs is not None else default_kwargs
    baseline = baseline or PRESETS["balanced_v1"]

    red_results = run_one_direction(
        candidate=candidate,
        candidate_index=candidate_index,
        role="candidate_as_red",
        games_per_side=games_per_side,
        master_seed=master_seed,
        ai_kind=ai_kind,
        baseline=baseline,
        ai_kwargs=ai_kwargs,
        max_turns=max_turns,
    )
    blue_results = run_one_direction(
        candidate=candidate,
        candidate_index=candidate_index,
        role="candidate_as_blue",
        games_per_side=games_per_side,
        master_seed=master_seed,
        ai_kind=ai_kind,
        baseline=baseline,
        ai_kwargs=ai_kwargs,
        max_turns=max_turns,
    )
    return aggregate_candidate_result(
        candidate=candidate,
        games_per_side=games_per_side,
        red_results=red_results,
        blue_results=blue_results,
    )


def load_release_default_ai_config(
    path=ROOT / "release" / "v1.0" / "default_params.json",
) -> tuple[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")

    kwargs = {key: value for key, value in data.items() if key not in METADATA_KEYS}
    return "rollout", kwargs


def validate_run_limits(candidate_count: int, games_per_side: int, dry_run: bool) -> None:
    if games_per_side < 1:
        raise ValueError("games_per_side must be >= 1")
    if games_per_side > 500:
        raise ValueError(
            "games_per_side must be <= 500 to keep deterministic seed ranges isolated"
        )

    planned_games = candidate_count * games_per_side * 2
    if not dry_run and planned_games > MAX_DEFAULT_PLANNED_GAMES:
        raise ValueError(
            f"planned games ({planned_games}) exceeds default limit "
            f"({MAX_DEFAULT_PLANNED_GAMES}); use dry-run or reduce candidates/games"
        )


def format_layout_label(layout: Mapping[int, Position]) -> str:
    return "/".join(
        f"{piece_id}:{layout[piece_id].row}{layout[piece_id].col}"
        for piece_id in sorted(layout)
    )


def json_layout_label(raw_layout: Mapping[str, Any]) -> str:
    def position_label(value: Any) -> str:
        if isinstance(value, Mapping):
            row = value["row"]
            col = value["col"]
        else:
            row, col = value
        return f"{int(row)}{int(col)}"

    return "/".join(
        f"{piece_id}:{position_label(raw_layout[piece_id])}"
        for piece_id in sorted(raw_layout, key=lambda item: int(item))
    )


def result_by_id(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(result["candidate_id"]): dict(result)
        for result in payload.get("results", [])
    }


def write_summary(path: Path, payload: Mapping[str, Any]) -> None:
    results = list(payload.get("results", []))
    sorted_results = sorted(
        results,
        key=lambda result: result.get("combined_win_rate", 0.0),
        reverse=True,
    )[:10]
    total_games = sum(int(result.get("combined_games", 0)) for result in results)
    total_illegal = sum(int(result.get("illegal_moves", 0)) for result in results)
    total_crashes = sum(int(result.get("crashes", 0)) for result in results)
    total_timeouts = sum(int(result.get("timeouts", 0)) for result in results)

    lines = [
        "# Opening Light Screen Summary",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- updated_at: {payload.get('updated_at', '')}",
        f"- argv: `{json.dumps(payload.get('argv', []), ensure_ascii=False)}`",
        f"- mode: {payload.get('mode', '')}",
        f"- candidate_count: {payload.get('candidate_count', 0)}",
        f"- games_per_side: {payload.get('games_per_side', 0)}",
        f"- seed: {payload.get('seed', '')}",
        f"- baseline_layout: {payload.get('baseline_layout', '')}",
        f"- max_turns: {payload.get('max_turns', '')}",
        f"- ai_kind: {payload.get('ai_kind', '')}",
        f"- ai_kwargs_source: {payload.get('ai_kwargs_source', '')}",
        f"- ai_kwargs: `{json.dumps(payload.get('ai_kwargs', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。",
        "",
        "## Stability Totals",
        "",
        f"- combined_games: {total_games}",
        f"- illegal_moves: {total_illegal}",
        f"- crashes: {total_crashes}",
        f"- timeouts: {total_timeouts}",
        "",
        "## Top Candidates",
        "",
        "| rank | candidate_id | win_rate | wins/games | red_wins | blue_wins | illegal | crashes | timeouts | avg_turns | avg_step_ms | max_step_ms | red_layout |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, result in enumerate(sorted_results, start=1):
        wins = int(result.get("combined_candidate_wins", 0))
        games = int(result.get("combined_games", 0))
        win_rate = float(result.get("combined_win_rate", 0.0))
        raw_layout = result.get("red_layout", {})
        layout_label = json_layout_label(raw_layout) if raw_layout else ""
        lines.append(
            f"| {rank} | {result.get('candidate_id', '')} | {win_rate:.3f} | "
            f"{wins}/{games} | {int(result.get('candidate_wins_as_red', 0))} | "
            f"{int(result.get('candidate_wins_as_blue', 0))} | "
            f"{int(result.get('illegal_moves', 0))} | {int(result.get('crashes', 0))} | "
            f"{int(result.get('timeouts', 0))} | {float(result.get('average_turns', 0.0)):.2f} | "
            f"{float(result.get('average_step_time_ms', 0.0)):.2f} | "
            f"{float(result.get('max_step_time_ms', 0.0)):.2f} | {layout_label} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_dry_run(
    mode: Mode,
    baseline_layout: str,
    candidates: list[OpeningCandidate],
    preview_count: int = 8,
) -> None:
    print(f"mode: {mode}")
    print(f"candidate_count: {len(candidates)}")
    print(f"baseline_layout: {baseline_layout}")
    for candidate in candidates[:preview_count]:
        print(
            f"candidate: {candidate.candidate_id} "
            f"source={candidate.source} "
            f"red={format_layout_label(candidate.red_layout)} "
            f"blue={format_layout_label(candidate.blue_layout)}"
        )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screen lightweight opening layouts with release default AI."
    )
    parser.add_argument("--mode", choices=("curated", "full"), default="curated")
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--games-per-side", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--baseline-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = generate_candidates(
        mode=args.mode,
        max_candidates=args.max_candidates,
        seed=args.seed,
    )
    validate_run_limits(
        candidate_count=len(candidates),
        games_per_side=args.games_per_side,
        dry_run=args.dry_run,
    )
    if args.baseline_layout not in PRESETS:
        raise ValueError(f"unknown baseline_layout: {args.baseline_layout}")

    if args.dry_run:
        print_dry_run(args.mode, args.baseline_layout, candidates)
        return 0

    ai_kind, ai_kwargs = load_release_default_ai_config()
    expected_payload = new_run_payload(
        argv=list(argv) if argv is not None else sys.argv[1:],
        mode=args.mode,
        max_candidates=args.max_candidates,
        candidate_count=len(candidates),
        games_per_side=args.games_per_side,
        seed=args.seed,
        baseline_layout=args.baseline_layout,
        max_turns=args.max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    resumed_payload = load_resume_payload(
        args.output,
        expected=expected_payload,
        no_resume=args.no_resume,
    )
    payload = dict(expected_payload)
    payload["generated_at"] = resumed_payload.get("generated_at", expected_payload["generated_at"])
    payload["results"] = list(resumed_payload.get("results", []))
    baseline = PRESETS[args.baseline_layout]
    results = result_by_id(payload)
    expected_games = args.games_per_side * 2

    for candidate_index, candidate in enumerate(candidates):
        existing = results.get(candidate.candidate_id)
        if existing is not None and is_result_complete(
            existing,
            candidate,
            expected_games=expected_games,
        ):
            continue

        results[candidate.candidate_id] = run_candidate(
            candidate=candidate,
            candidate_index=candidate_index,
            games_per_side=args.games_per_side,
            master_seed=args.seed,
            baseline=baseline,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
            max_turns=args.max_turns,
        )
        payload["results"] = [
            results[candidate.candidate_id]
            for candidate in candidates
            if candidate.candidate_id in results
        ]
        payload["updated_at"] = utc_now()
        atomic_write_json(args.output, payload)

    payload["results"] = [
        results[candidate.candidate_id]
        for candidate in candidates
        if candidate.candidate_id in results
    ]
    payload["updated_at"] = utc_now()
    atomic_write_json(args.output, payload)
    write_summary(args.summary, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
