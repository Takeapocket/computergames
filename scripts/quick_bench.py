from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import (
    LAYOUTS,
    STARTING_LAYOUT_ID,
    ai_version_signature,
    build_ai,
    play_one_game,
    starting_state_for,
)
from core.types import Player
from scripts._bench_meta import build_provenance, greedy_kwargs


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


def _per_game_payload(
    *,
    index: int,
    per_game_seed: int,
    red_seed: int,
    blue_seed: int,
    dice_seed: int,
    result,
) -> dict:
    final_state = (
        result.record.restore_state().serialize(include_history=False)
        if result.record is not None
        else None
    )
    return {
        "index": index,
        "per_game_seed": per_game_seed,
        "seeds": {"red": red_seed, "blue": blue_seed, "dice": dice_seed},
        "winner": result.winner.value if result.winner else None,
        "turns": result.turns,
        "termination_reason": result.termination_reason,
        "illegal_moves": result.illegal_moves,
        "crashes": result.crashes,
        "final_state": final_state,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run N AI vs AI games and emit a JSON benchmark report (schema v2).")
    parser.add_argument("--red", required=True, help="Red AI kind")
    parser.add_argument("--blue", required=True, help="Blue AI kind")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed; per-game seed = master*100000 + i")
    parser.add_argument("--max-turns", type=int, default=200, help="Per-game half-move cap; reaching it = draw")
    parser.add_argument(
        "--red-stuck-penalty",
        type=float,
        default=None,
        help="Override GreedyAI stuck_penalty for red (use 0 to reproduce 4.1 baseline).",
    )
    parser.add_argument(
        "--blue-stuck-penalty",
        type=float,
        default=None,
        help="Override GreedyAI stuck_penalty for blue (use 0 to reproduce 4.1 baseline).",
    )
    parser.add_argument(
        "--starting-layout",
        default=STARTING_LAYOUT_ID,
        choices=sorted(LAYOUTS),
        help="Starting layout id (default: %(default)s).",
    )
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
    parser.add_argument(
        "--report-name",
        default=None,
        help="Override the report filename stem (without timestamp/extension).",
    )
    parser.add_argument(
        "--include-per-game",
        action="store_true",
        help=(
            "Include per_game array (with seeds, winner, termination_reason, final_state) "
            "in the JSON report. Default off — only summary aggregates are saved, keeping "
            "report files small (<2KB instead of ~600KB). Per-game state is reproducible "
            "from per_game_seed = master_seed * 100_000 + i."
        ),
    )
    args = parser.parse_args(argv)

    if args.red != "greedy" and args.red_stuck_penalty is not None:
        parser.error("--red-stuck-penalty requires --red greedy")
    if args.blue != "greedy" and args.blue_stuck_penalty is not None:
        parser.error("--blue-stuck-penalty requires --blue greedy")

    red_kwargs = greedy_kwargs(args.red_stuck_penalty) if args.red == "greedy" else {}
    blue_kwargs = greedy_kwargs(args.blue_stuck_penalty) if args.blue == "greedy" else {}

    start = time.perf_counter()
    results = []
    per_game: list[dict] = []
    red_signature: dict | None = None
    blue_signature: dict | None = None

    for i in range(args.games):
        per_game_seed = args.seed * 100_000 + i
        red_seed = per_game_seed * 3 + 1
        blue_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3
        red_ai = build_ai(args.red, seed=red_seed, **red_kwargs)
        blue_ai = build_ai(args.blue, seed=blue_seed, **blue_kwargs)
        if i == 0:
            red_signature = ai_version_signature(red_ai)
            blue_signature = ai_version_signature(blue_ai)
        dice_rng = random.Random(dice_seed)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=args.max_turns,
            starting_state=starting_state_for(args.starting_layout),
        )
        results.append(result)
        if args.include_per_game:
            per_game.append(
                _per_game_payload(
                    index=i,
                    per_game_seed=per_game_seed,
                    red_seed=red_seed,
                    blue_seed=blue_seed,
                    dice_seed=dice_seed,
                    result=result,
                )
            )
    elapsed = time.perf_counter() - start

    summary = _aggregate(results)
    summary.update(build_provenance(
        repo_root=ROOT,
        script_name="quick_bench.py",
        argv=argv,
        starting_layout_id=args.starting_layout,
    ))
    summary.update({
        "red_ai": args.red,
        "blue_ai": args.blue,
        "ai_versions": {"red": red_signature or {"name": args.red}, "blue": blue_signature or {"name": args.blue}},
        "seed": args.seed,
        "max_turns": args.max_turns,
        "wall_seconds": round(elapsed, 3),
    })
    if args.include_per_game:
        summary["per_game"] = per_game

    report_path: str | None = None
    if not args.no_save_report:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = args.report_name or f"bench_{timestamp}_{args.red}_vs_{args.blue}"
        report_path = str(report_dir / f"{stem}.json")
        Path(report_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["report_path"] = report_path

    # 打印到 stdout 时去掉 per_game（避免覆盖终端），保留聚合摘要
    stdout_summary = {k: v for k, v in summary.items() if k != "per_game"}
    print(json.dumps(stdout_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
