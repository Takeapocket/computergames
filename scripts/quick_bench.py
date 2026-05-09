from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game
from core.types import Player


def _aggregate(results) -> dict:
    games = len(results)
    if games == 0:
        return {}

    winners = {Player.RED: 0, Player.BLUE: 0, None: 0}
    total_turns = 0
    total_illegal = 0
    total_crashes = 0
    all_step_times: list[float] = []

    for r in results:
        winners[r.winner] = winners.get(r.winner, 0) + 1
        total_turns += r.turns
        total_illegal += r.illegal_moves
        total_crashes += r.crashes
        all_step_times.extend(r.step_times_ms)

    avg_step = sum(all_step_times) / len(all_step_times) if all_step_times else 0.0
    max_step = max(all_step_times) if all_step_times else 0.0

    return {
        "games": games,
        "red_wins": winners[Player.RED],
        "blue_wins": winners[Player.BLUE],
        "draws": winners[None],
        "red_win_rate": winners[Player.RED] / games,
        "blue_win_rate": winners[Player.BLUE] / games,
        "draw_rate": winners[None] / games,
        "average_turns": total_turns / games,
        "illegal_moves": total_illegal,
        "crashes": total_crashes,
        "timeouts": 0,  # 阶段 4 还没引入单步时限
        "average_step_time_ms": avg_step,
        "max_step_time_ms": max_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run N AI vs AI games and emit a JSON benchmark report.")
    parser.add_argument("--red", required=True, help="Red AI kind")
    parser.add_argument("--blue", required=True, help="Blue AI kind")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed; per-game seed = master*100000 + i")
    parser.add_argument("--max-turns", type=int, default=200, help="Per-game half-move cap; reaching it = draw")
    parser.add_argument(
        "--report-dir",
        default=str(ROOT / "reports"),
        help="Directory to write the JSON report file",
    )
    parser.add_argument(
        "--no-save-report",
        action="store_true",
        help="Skip writing the report file (only print summary to stdout)",
    )
    args = parser.parse_args(argv)

    start = time.perf_counter()
    results = []
    for i in range(args.games):
        per_game_seed = args.seed * 100_000 + i
        red_ai = build_ai(args.red, seed=per_game_seed * 3 + 1)
        blue_ai = build_ai(args.blue, seed=per_game_seed * 3 + 2)
        dice_rng = random.Random(per_game_seed * 3)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=args.max_turns,
        )
        results.append(result)
    elapsed = time.perf_counter() - start

    summary = _aggregate(results)
    summary.update({
        "red_ai": args.red,
        "blue_ai": args.blue,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "wall_seconds": round(elapsed, 3),
    })

    report_path: str | None = None
    if not args.no_save_report:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = str(report_dir / f"bench_{timestamp}_{args.red}_vs_{args.blue}.json")
        Path(report_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["report_path"] = report_path

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
