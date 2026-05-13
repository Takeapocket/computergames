from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game, starting_state_for
from core.types import Player


class FailureBucket(StrEnum):
    LOST_BY_TARGET = "lost_by_target"
    LOST_BY_CAPTURE_ALL = "lost_by_capture_all"
    WON_BY_TARGET = "won_by_target"
    WON_BY_CAPTURE_ALL = "won_by_capture_all"
    DRAW_OR_LIMIT = "draw_or_limit"
    ILLEGAL_OR_CRASH = "illegal_or_crash"


BUCKET_ORDER = (
    FailureBucket.LOST_BY_TARGET,
    FailureBucket.LOST_BY_CAPTURE_ALL,
    FailureBucket.WON_BY_TARGET,
    FailureBucket.WON_BY_CAPTURE_ALL,
    FailureBucket.DRAW_OR_LIMIT,
    FailureBucket.ILLEGAL_OR_CRASH,
)

DEFAULT_STARTING_LAYOUT = "balanced_v1"


def _winner_value(winner: Any) -> str | None:
    if winner is None:
        return None
    if isinstance(winner, Player):
        return winner.value
    return str(winner)


def _loser_for(winner: str | None) -> str | None:
    if winner == Player.RED.value:
        return Player.BLUE.value
    if winner == Player.BLUE.value:
        return Player.RED.value
    return None


def _bucket_for_row(row: dict[str, Any], perspective: str) -> FailureBucket:
    reason = str(row.get("termination_reason") or "")
    winner = _winner_value(row.get("winner"))
    loser = row.get("loser") or _loser_for(winner)

    if reason in {"illegal_move", "no_move", "crash"}:
        return FailureBucket.ILLEGAL_OR_CRASH
    if int(row.get("illegal_moves") or 0) > 0 or int(row.get("crashes") or 0) > 0:
        return FailureBucket.ILLEGAL_OR_CRASH
    if winner is None or reason.startswith("draw"):
        return FailureBucket.DRAW_OR_LIMIT

    if reason not in {"winner_target_corner", "winner_capture_all"}:
        return FailureBucket.DRAW_OR_LIMIT

    if winner == perspective:
        if reason == "winner_capture_all":
            return FailureBucket.WON_BY_CAPTURE_ALL
        return FailureBucket.WON_BY_TARGET

    if loser == perspective:
        if reason == "winner_capture_all":
            return FailureBucket.LOST_BY_CAPTURE_ALL
        return FailureBucket.LOST_BY_TARGET

    return FailureBucket.DRAW_OR_LIMIT


def aggregate_buckets(rows: Iterable[dict[str, Any]], perspective: str) -> Counter[FailureBucket]:
    buckets: Counter[FailureBucket] = Counter()
    for row in rows:
        buckets[_bucket_for_row(row, perspective)] += 1
    return buckets


def format_bucket_table(buckets: dict[FailureBucket, int] | Counter[FailureBucket]) -> str:
    lines = [
        "| bucket | count |",
        "|---|---:|",
    ]
    for bucket in BUCKET_ORDER:
        lines.append(f"| {bucket.value} | {buckets.get(bucket, 0)} |")
    return "\n".join(lines)


def run_direction(
    red: str,
    blue: str,
    games: int,
    seed: int,
    starting_layout: str,
    perspective: str,
) -> tuple[list[dict[str, Any]], Counter[FailureBucket]]:
    rows: list[dict[str, Any]] = []
    for i in range(games):
        per_game_seed = seed * 100_000 + i
        red_seed = per_game_seed * 3 + 1
        blue_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3
        result = play_one_game(
            red_ai=build_ai(red, seed=red_seed),
            blue_ai=build_ai(blue, seed=blue_seed),
            dice_rng=random.Random(dice_seed),
            starting_state=starting_state_for(starting_layout),
        )
        winner = _winner_value(result.winner)
        row = {
            "game_index": i + 1,
            "winner": winner,
            "termination_reason": result.termination_reason,
            "turns": result.turns,
            "illegal_moves": result.illegal_moves,
            "crashes": result.crashes,
            "loser": _loser_for(winner),
        }
        rows.append(row)

    return rows, aggregate_buckets(rows, perspective=perspective)


def write_report(
    report_path: str | Path,
    red: str,
    blue: str,
    games: int,
    seed: int,
    starting_layout: str,
    rows: list[dict[str, Any]],
    buckets: Counter[FailureBucket],
) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "red": red,
        "blue": blue,
        "games": games,
        "seed": seed,
        "starting_layout": starting_layout,
    }
    content = "\n".join([
        "# AI Diagnostics",
        "",
        "## Metadata",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Buckets",
        "",
        format_bucket_table(buckets),
        "",
        "## First 20 Rows",
        "",
        "```json",
        json.dumps(rows[:20], ensure_ascii=False, indent=2),
        "```",
        "",
    ])
    path.write_text(content, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify AI self-play outcomes by failure bucket.")
    parser.add_argument("--red", default="greedy_risk")
    parser.add_argument("--blue", default="greedy")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--starting-layout", default=DEFAULT_STARTING_LAYOUT)
    parser.add_argument("--perspective", choices=[Player.RED.value, Player.BLUE.value], default=Player.RED.value)
    parser.add_argument("--output", default=str(ROOT / "reports" / "ai_diagnostics.md"))
    args = parser.parse_args(argv)

    rows, buckets = run_direction(
        red=args.red,
        blue=args.blue,
        games=args.games,
        seed=args.seed,
        starting_layout=args.starting_layout,
        perspective=args.perspective,
    )
    report_path = write_report(
        report_path=args.output,
        red=args.red,
        blue=args.blue,
        games=args.games,
        seed=args.seed,
        starting_layout=args.starting_layout,
        rows=rows,
        buckets=buckets,
    )
    print(json.dumps({
        "report_path": str(report_path),
        "buckets": {bucket.value: buckets.get(bucket, 0) for bucket in BUCKET_ORDER},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
