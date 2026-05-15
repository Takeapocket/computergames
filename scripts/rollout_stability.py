from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.rollout_ai import RolloutAI
from core.game_state import GameState
from core.types import Player, Position
from gui.app import format_move_label


DEFAULT_SCENARIO = "self_capture_audit"
DEFAULT_DICE = 5


def build_audit_state(scenario: str = DEFAULT_SCENARIO) -> GameState:
    if scenario != DEFAULT_SCENARIO:
        raise ValueError(f"unknown rollout stability scenario: {scenario}")
    return GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(2, 2),
            3: Position(1, 4),
            4: Position(1, 0),
            5: Position(2, 1),
            6: Position(2, 0),
        },
        blue={
            4: Position(3, 3),
            5: Position(3, 2),
            6: Position(3, 1),
        },
        current_player=Player.RED,
    )


def _move_label(move: Any) -> str:
    if move is None:
        return "None"
    return format_move_label(move, distinguish_self_capture=True)


def _aggregate_candidate_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    winrates: dict[str, list[float]] = defaultdict(list)
    visits: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        for candidate in row["candidates"]:
            label = str(candidate["move"])
            winrates[label].append(float(candidate["winrate"]))
            visits[label].append(int(candidate["visits"]))

    aggregate: dict[str, dict[str, float | int]] = {}
    for label, values in winrates.items():
        aggregate[label] = {
            "samples": len(values),
            "mean_winrate": statistics.fmean(values),
            "stdev_winrate": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "mean_visits": statistics.fmean(visits[label]),
        }
    return aggregate


def run_stability(
    *,
    scenario: str = DEFAULT_SCENARIO,
    runs: int = 10,
    seed: int = 0,
    rollouts_per_move: int = 32,
    close_sample_margin: float = 0.08,
    close_sample_rollouts_per_move: int = 128,
    low_confidence_margin: float = 0.08,
    max_rollout_turns: int = 80,
    max_step_time_ms: float = 500.0,
    epsilon: float = 0.15,
) -> dict[str, Any]:
    state = build_audit_state(scenario)
    ai = RolloutAI(
        rollouts_per_move=rollouts_per_move,
        close_sample_margin=close_sample_margin,
        close_sample_rollouts_per_move=close_sample_rollouts_per_move,
        low_confidence_margin=low_confidence_margin,
        max_rollout_turns=max_rollout_turns,
        max_step_time_ms=max_step_time_ms,
        epsilon=epsilon,
        rng=random.Random(seed),
    )

    rows: list[dict[str, Any]] = []
    recommendation_counts: Counter[str] = Counter()
    for index in range(1, runs + 1):
        move = ai.choose_move(state, DEFAULT_DICE)
        label = _move_label(move)
        recommendation_counts[label] += 1
        rows.append(
            {
                "run": index,
                "recommendation": label,
                "low_confidence": ai.last_low_confidence,
                "score_margin": ai.last_score_margin,
                "candidates": [
                    {
                        "move": _move_label(diagnostic.move),
                        "visits": diagnostic.visits,
                        "score": diagnostic.score,
                        "winrate": diagnostic.winrate,
                        "cutoffs": diagnostic.cutoffs,
                        "avg": diagnostic.avg,
                    }
                    for diagnostic in ai.last_diagnostics
                ],
            }
        )

    return {
        "scenario": scenario,
        "dice": DEFAULT_DICE,
        "runs": rows,
        "recommendation_counts": dict(recommendation_counts),
        "candidate_stats": _aggregate_candidate_stats(rows),
        "config": {
            "seed": seed,
            "rollouts_per_move": rollouts_per_move,
            "close_sample_margin": close_sample_margin,
            "close_sample_rollouts_per_move": close_sample_rollouts_per_move,
            "low_confidence_margin": low_confidence_margin,
            "max_rollout_turns": max_rollout_turns,
            "max_step_time_ms": max_step_time_ms,
            "epsilon": epsilon,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit rollout recommendation stability on fixed positions.")
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rollouts-per-move", type=int, default=32)
    parser.add_argument("--close-sample-margin", type=float, default=0.08)
    parser.add_argument("--close-sample-rollouts-per-move", type=int, default=128)
    parser.add_argument("--low-confidence-margin", type=float, default=0.08)
    parser.add_argument("--max-rollout-turns", type=int, default=80)
    parser.add_argument("--max-step-time-ms", type=float, default=500.0)
    parser.add_argument("--epsilon", type=float, default=0.15)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    result = run_stability(
        scenario=args.scenario,
        runs=args.runs,
        seed=args.seed,
        rollouts_per_move=args.rollouts_per_move,
        close_sample_margin=args.close_sample_margin,
        close_sample_rollouts_per_move=args.close_sample_rollouts_per_move,
        low_confidence_margin=args.low_confidence_margin,
        max_rollout_turns=args.max_rollout_turns,
        max_step_time_ms=args.max_step_time_ms,
        epsilon=args.epsilon,
    )
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output_path)}, ensure_ascii=False, indent=2))
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
