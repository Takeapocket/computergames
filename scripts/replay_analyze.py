from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai
from ai.release_defaults import load_release_default_rollout_kwargs
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from record.game_record import GameRecord
from record.match_record import MatchRecord


RecommenderFactory = Callable[[int], Any]


def load_records(paths: Iterable[str | Path]) -> list[GameRecord]:
    records: list[GameRecord] = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "games" in data and "our_side" in data:
            records.extend(MatchRecord.from_dict(data).games)
        else:
            records.append(GameRecord.from_dict(data))
    return records


def classify_step(state_before: GameState, *, dice: int, move: Move) -> list[str]:
    labels: list[str] = []
    legal = state_before.legal_moves(move.player, dice)
    own_target = target_corner(move.player)
    if any(candidate.to_pos == own_target for candidate in legal):
        labels.append("mover_had_target_threat")
    if move.to_pos == own_target:
        labels.append("mover_hit_target")
    if move.captured_piece is not None:
        if move.captured_piece.player is move.player:
            labels.append("self_capture")
        else:
            labels.append("enemy_capture")
    return labels


def default_recommender_factory(step_index: int) -> Any:
    return build_ai(
        "rollout",
        seed=2026 * 100_000 + int(step_index),
        **load_release_default_rollout_kwargs(),
    )


def _move_identity(move: Move | None) -> tuple[Any, ...] | None:
    if move is None:
        return None
    return (
        move.player.value,
        move.piece_id,
        move.from_pos.row,
        move.from_pos.col,
        move.to_pos.row,
        move.to_pos.col,
    )


def _move_payload(move: Move | None) -> dict[str, Any] | None:
    return None if move is None else move.to_dict()


def _normalize_sources(sources: Iterable[str] | None) -> set[str] | None:
    if sources is None:
        return None
    return {str(source) for source in sources}


def compare_record_recommendations(
    record: GameRecord,
    *,
    recommender_factory: RecommenderFactory | None = None,
    sources: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    factory = recommender_factory or default_recommender_factory
    allowed_sources = _normalize_sources(sources)
    rows: list[dict[str, Any]] = []
    state = GameState.deserialize(record.initial_state)

    for step_index, step in enumerate(record.steps):
        if allowed_sources is None or step.source in allowed_sources:
            recommender = factory(step_index)
            recommended = recommender.choose_move(state, step.dice)
            rows.append(
                {
                    "turn": step.turn,
                    "player": step.player.value,
                    "source": step.source,
                    "dice": step.dice,
                    "recorded_move": _move_payload(step.move),
                    "recommended_move": _move_payload(recommended),
                    "matched_recommendation": (
                        _move_identity(recommended) == _move_identity(step.move)
                    ),
                    "labels": classify_step(state, dice=step.dice, move=step.move),
                    "recommender": getattr(recommender, "name", recommender.__class__.__name__),
                }
            )
        state.apply_move(step.move, dice=step.dice)
    return rows


def summarize_recommendation_comparison(
    records: Iterable[GameRecord],
    *,
    recommender_factory: RecommenderFactory | None = None,
    sources: Iterable[str] | None = None,
    include_rows: bool = False,
) -> dict[str, Any]:
    record_list = list(records)
    compared_steps = 0
    matches = 0
    mismatches = 0
    no_recommendation = 0
    by_source: dict[str, dict[str, int]] = {}
    rows: list[dict[str, Any]] = []

    for record in record_list:
        for row in compare_record_recommendations(
            record,
            recommender_factory=recommender_factory,
            sources=sources,
        ):
            if include_rows:
                rows.append(row)
            source = row["source"]
            source_stats = by_source.setdefault(
                source,
                {
                    "compared_steps": 0,
                    "matches": 0,
                    "mismatches": 0,
                    "no_recommendation": 0,
                },
            )
            compared_steps += 1
            source_stats["compared_steps"] += 1
            if row["recommended_move"] is None:
                no_recommendation += 1
                source_stats["no_recommendation"] += 1
            elif row["matched_recommendation"]:
                matches += 1
                source_stats["matches"] += 1
            else:
                mismatches += 1
                source_stats["mismatches"] += 1

    summary = {
        "records": len(record_list),
        "compared_steps": compared_steps,
        "matches": matches,
        "mismatches": mismatches,
        "no_recommendation": no_recommendation,
        "match_rate": matches / compared_steps if compared_steps else 0.0,
        "by_source": dict(sorted(by_source.items())),
    }
    if include_rows:
        summary["rows"] = rows
    return summary


def summarize_records(records: Iterable[GameRecord]) -> dict[str, Any]:
    record_list = list(records)
    source_counts: Counter[str] = Counter()
    dice_counts: Counter[str] = Counter()
    result_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    step_count = 0

    for record in record_list:
        state = GameState.deserialize(record.initial_state)
        winner = record.result.get("winner", "unknown")
        reason = record.result.get("reason", "unknown")
        if record.result:
            result_counts[f"{winner}:{reason}"] += 1
        for step in record.steps:
            step_count += 1
            source_counts[step.source] += 1
            dice_counts[str(step.dice)] += 1
            for label in classify_step(state, dice=step.dice, move=step.move):
                label_counts[label] += 1
            state.apply_move(step.move, dice=step.dice)

    return {
        "games": len(record_list),
        "steps": step_count,
        "sources": dict(sorted(source_counts.items())),
        "dice_counts": dict(sorted(dice_counts.items())),
        "results": dict(sorted(result_counts.items())),
        "labels": dict(sorted(label_counts.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze saved Einstein chess replay JSON files.")
    parser.add_argument("paths", nargs="+", help="GameRecord or MatchRecord JSON files")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--compare-recommendations",
        action="store_true",
        help="Compare recorded moves against the current P14 default recommender.",
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=["self", "opponent", "unknown"],
        help="Limit recommendation comparison to one or more move sources.",
    )
    parser.add_argument(
        "--include-recommendation-rows",
        action="store_true",
        help="Include per-step recommendation comparison rows in JSON output.",
    )
    args = parser.parse_args(argv)

    records = load_records(args.paths)
    summary = summarize_records(records)
    if args.compare_recommendations:
        summary["recommendations"] = summarize_recommendation_comparison(
            records,
            sources=args.source,
            include_rows=args.include_recommendation_rows,
        )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"games: {summary['games']}")
        print(f"steps: {summary['steps']}")
        print(f"sources: {summary['sources']}")
        print(f"dice_counts: {summary['dice_counts']}")
        print(f"results: {summary['results']}")
        print(f"labels: {summary['labels']}")
        if args.compare_recommendations:
            recommendations = summary["recommendations"]
            print(f"recommendation_compared_steps: {recommendations['compared_steps']}")
            print(f"recommendation_matches: {recommendations['matches']}")
            print(f"recommendation_mismatches: {recommendations['mismatches']}")
            print(f"recommendation_no_recommendation: {recommendations['no_recommendation']}")
            print(f"recommendation_match_rate: {recommendations['match_rate']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
