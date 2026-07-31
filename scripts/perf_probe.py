from __future__ import annotations

import argparse
import json
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai.rollout_ai as rollout_module
from ai.match import build_ai, play_one_game, starting_state_for
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from ai.rollout_ai import RolloutAI
from core.game_state import GameState


def _new_instrumentation_counts() -> dict[str, int]:
    return {
        "game_state_serialize_calls": 0,
        "game_state_deserialize_calls": 0,
        "game_state_clone_calls": 0,
        "legal_moves_calls": 0,
        "greedy_ai_constructs": 0,
        "rng_constructs": 0,
    }


@contextmanager
def _instrument_rollout_hotspots():
    counters = _new_instrumentation_counts()
    original_serialize = GameState.__dict__["serialize"]
    original_deserialize_descriptor = GameState.__dict__["deserialize"]
    original_deserialize = original_deserialize_descriptor.__func__
    original_clone = GameState.__dict__["clone"]
    original_legal_moves = GameState.__dict__["legal_moves"]
    original_greedy_ai = rollout_module.GreedyAI
    original_random = rollout_module.random.Random

    def counted_serialize(self, *args, **kwargs):
        counters["game_state_serialize_calls"] += 1
        return original_serialize(self, *args, **kwargs)

    def counted_deserialize(cls, data):
        counters["game_state_deserialize_calls"] += 1
        return original_deserialize(cls, data)

    def counted_clone(self, *args, **kwargs):
        counters["game_state_clone_calls"] += 1
        return original_clone(self, *args, **kwargs)

    def counted_legal_moves(self, *args, **kwargs):
        counters["legal_moves_calls"] += 1
        return original_legal_moves(self, *args, **kwargs)

    def counted_greedy_ai(*args, **kwargs):
        counters["greedy_ai_constructs"] += 1
        return original_greedy_ai(*args, **kwargs)

    def counted_random(*args, **kwargs):
        counters["rng_constructs"] += 1
        return original_random(*args, **kwargs)

    GameState.serialize = counted_serialize
    GameState.deserialize = classmethod(counted_deserialize)
    GameState.clone = counted_clone
    GameState.legal_moves = counted_legal_moves
    rollout_module.GreedyAI = counted_greedy_ai
    rollout_module.random.Random = counted_random
    try:
        yield counters
    finally:
        GameState.serialize = original_serialize
        GameState.deserialize = original_deserialize_descriptor
        GameState.clone = original_clone
        GameState.legal_moves = original_legal_moves
        rollout_module.GreedyAI = original_greedy_ai
        rollout_module.random.Random = original_random


def run_probe(
    *,
    red_kind: str = "rollout",
    blue_kind: str = "random",
    games: int = 2,
    seed: int = 2026,
    layout_id: str = "balanced_v1",
    max_turns: int = 200,
    red_kwargs: dict[str, Any] | None = None,
    blue_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    red_kwargs = dict(red_kwargs or {})
    blue_kwargs = dict(blue_kwargs or {})
    turns = 0
    step_times: list[float] = []
    illegal_moves = 0
    crashes = 0
    timeouts = 0
    start = time.perf_counter()
    for index in range(games):
        game_seed = seed * 100_000 + index
        result = play_one_game(
            red_ai=build_ai(red_kind, seed=game_seed * 3 + 1, **red_kwargs),
            blue_ai=build_ai(blue_kind, seed=game_seed * 3 + 2, **blue_kwargs),
            dice_rng=random.Random(game_seed * 3),
            max_turns=max_turns,
            starting_state=starting_state_for(layout_id),
        )
        turns += result.turns
        step_times.extend(result.step_times_ms)
        illegal_moves += result.illegal_moves
        crashes += result.crashes
        timeouts += result.timeouts
    wall_seconds = max(time.perf_counter() - start, 1e-9)
    steps = len(step_times)
    return {
        "red": {"kind": red_kind, "kwargs": red_kwargs},
        "blue": {"kind": blue_kind, "kwargs": blue_kwargs},
        "seed": seed,
        "layout_id": layout_id,
        "max_turns": max_turns,
        "games": games,
        "turns": turns,
        "steps": steps,
        "wall_seconds": wall_seconds,
        "steps_per_second": steps / wall_seconds,
        "average_step_time_ms": sum(step_times) / steps if steps else 0.0,
        "max_step_time_ms": max(step_times) if step_times else 0.0,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "instrumentation_note": (
            "match_probe reports match timing; rollout_decision_probe.instrumentation reports "
            "clone/legal-generation/object-construction counters."
        ),
    }


def run_rollout_decision_probe(
    *,
    samples: int = 16,
    seed: int = 2026,
    layout_id: str = "balanced_v1",
    rollout_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kwargs = dict(RELEASE_DEFAULT_ROLLOUT_KWARGS)
    kwargs.update(rollout_kwargs or {})
    total_visits = 0
    decisions = 0
    start = time.perf_counter()
    with _instrument_rollout_hotspots() as instrumentation:
        rng = random.Random(seed)
        for index in range(samples):
            state = starting_state_for(layout_id)
            ai = RolloutAI(rng=random.Random(seed * 100_000 + index), **kwargs)
            dice = rng.randint(1, 6)
            move = ai.choose_move(state, dice)
            if move is not None:
                decisions += 1
            total_visits += sum(int(getattr(stats, "visits", 0)) for stats in ai.last_root_stats)
    wall_seconds = max(time.perf_counter() - start, 1e-9)
    return {
        "samples": samples,
        "decisions": decisions,
        "wall_seconds": wall_seconds,
        "root_visits": total_visits,
        "root_visits_per_second": total_visits / wall_seconds,
        "average_root_visits": total_visits / samples if samples else 0.0,
        "instrumentation": dict(instrumentation),
    }


def _json_kwargs_arg(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON object: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect research performance baseline metrics.")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--red", default="rollout")
    parser.add_argument("--blue", default="random")
    parser.add_argument("--red-kwargs", type=_json_kwargs_arg, default=None)
    parser.add_argument("--blue-kwargs", type=_json_kwargs_arg, default=None)
    parser.add_argument("--layout-id", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    payload = {
        "match_probe": run_probe(
            red_kind=args.red,
            blue_kind=args.blue,
            games=args.games,
            seed=args.seed,
            layout_id=args.layout_id,
            max_turns=args.max_turns,
            red_kwargs=args.red_kwargs or {},
            blue_kwargs=args.blue_kwargs or {},
        ),
        "rollout_decision_probe": run_rollout_decision_probe(
            samples=args.samples,
            seed=args.seed,
            layout_id=args.layout_id,
        ),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
