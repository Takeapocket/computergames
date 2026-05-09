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

from ai.match import build_ai, play_one_game


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a single AI vs AI Einstein chess game and dump JSON + replay.")
    parser.add_argument("--red", required=True, help="Red AI kind (e.g. random / greedy)")
    parser.add_argument("--blue", required=True, help="Blue AI kind (e.g. random / greedy)")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed for dice and AI RNGs")
    parser.add_argument("--max-turns", type=int, default=200, help="Hard cap on total half-moves; reaching it = draw")
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
    args = parser.parse_args(argv)

    red_ai = build_ai(args.red, seed=args.seed * 3 + 1)
    blue_ai = build_ai(args.blue, seed=args.seed * 3 + 2)
    dice_rng = random.Random(args.seed * 3)

    result = play_one_game(
        red_ai=red_ai,
        blue_ai=blue_ai,
        dice_rng=dice_rng,
        max_turns=args.max_turns,
    )

    replay_path: str | None = None
    if not args.no_save_replay and result.record is not None:
        replay_dir = Path(args.replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        replay_path = str(replay_dir / f"match_{timestamp}_{args.red}_vs_{args.blue}_seed{args.seed}.json")
        result.record.save(replay_path)

    summary = {
        "red_ai": red_ai.name,
        "blue_ai": blue_ai.name,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "winner": result.winner.value if result.winner else None,
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
