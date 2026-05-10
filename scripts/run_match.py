from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

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
from scripts._bench_meta import build_provenance, greedy_kwargs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a single AI vs AI Einstein chess game and dump JSON + replay (schema v2).")
    parser.add_argument("--red", required=True, help="Red AI kind (e.g. random / greedy)")
    parser.add_argument("--blue", required=True, help="Blue AI kind (e.g. random / greedy)")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed for dice and AI RNGs")
    parser.add_argument("--max-turns", type=int, default=200, help="Hard cap on total half-moves; reaching it = draw")
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
        "--replay-dir",
        default=str(ROOT / "replays"),
        help="Directory to write the replay JSON file",
    )
    parser.add_argument(
        "--no-save-replay",
        action="store_true",
        help="Skip writing the replay file (useful when calling from other scripts)",
    )
    parser.add_argument(
        "--replay-name",
        default=None,
        help="Override the replay filename stem (without timestamp/extension).",
    )
    args = parser.parse_args(argv)

    if args.red != "greedy" and args.red_stuck_penalty is not None:
        parser.error("--red-stuck-penalty requires --red greedy")
    if args.blue != "greedy" and args.blue_stuck_penalty is not None:
        parser.error("--blue-stuck-penalty requires --blue greedy")

    red_kwargs = greedy_kwargs(args.red_stuck_penalty) if args.red == "greedy" else {}
    blue_kwargs = greedy_kwargs(args.blue_stuck_penalty) if args.blue == "greedy" else {}

    red_ai = build_ai(args.red, seed=args.seed * 3 + 1, **red_kwargs)
    blue_ai = build_ai(args.blue, seed=args.seed * 3 + 2, **blue_kwargs)
    dice_rng = random.Random(args.seed * 3)

    result = play_one_game(
        red_ai=red_ai,
        blue_ai=blue_ai,
        dice_rng=dice_rng,
        max_turns=args.max_turns,
        starting_state=starting_state_for(args.starting_layout),
    )

    metadata = {
        **build_provenance(
            repo_root=ROOT,
            script_name="run_match.py",
            argv=argv,
            starting_layout_id=args.starting_layout,
        ),
        "ai_versions": {
            "red": ai_version_signature(red_ai),
            "blue": ai_version_signature(blue_ai),
        },
        "seed": args.seed,
        "max_turns": args.max_turns,
    }
    result_meta = {
        "winner": result.winner.value if result.winner else None,
        "termination_reason": result.termination_reason,
        "turns": result.turns,
        "illegal_moves": result.illegal_moves,
        "crashes": result.crashes,
    }

    replay_path: str | None = None
    if not args.no_save_replay and result.record is not None:
        result.record.metadata = metadata
        result.record.result = result_meta
        replay_dir = Path(args.replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = args.replay_name or f"match_{timestamp}_{args.red}_vs_{args.blue}_seed{args.seed}"
        replay_path = str(replay_dir / f"{stem}.json")
        result.record.save(replay_path)

    summary = {
        "red_ai": red_ai.name,
        "blue_ai": blue_ai.name,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "winner": result.winner.value if result.winner else None,
        "termination_reason": result.termination_reason,
        "turns": result.turns,
        "illegal_moves": result.illegal_moves,
        "crashes": result.crashes,
        "avg_step_time_ms": round(result.avg_step_time_ms, 3),
        "max_step_time_ms": round(result.max_step_time_ms, 3),
        "replay_path": replay_path,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
