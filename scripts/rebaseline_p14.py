"""P14 versus frozen legacy Rollout, with paired seeds and immutable evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import ai_version_signature, build_ai, play_one_game, starting_state_for
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from core.rules import RULES_VERSION
from core.validation import require_int
from record.game_record import GameRecord
from scripts._release_config import reject_nonfinite_constant
from scripts.quick_bench import _percentile

SCHEMA_VERSION = 1
BASE_SEED = 2026101800000
P14 = "p14"
LEGACY = "legacy_p3_rollout"
LEGACY_KWARGS = {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0,
}
CONFIG_PATHS = ("release/v1.0/default_params.json", "release/v1.0/config.json")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_nonfinite_constant)


def _atomic_new(path: Path, content: bytes) -> None:
    """Publish a fully flushed file without replacing any existing destination."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic exclusive creation, including on Windows/NTFS.
    finally:
        temporary.unlink(missing_ok=True)


def source_hashes() -> dict[str, str]:
    paths = [path for folder in ("core", "ai", "record", "scripts", "gui")
             for path in (ROOT / folder).rglob("*.py")]
    paths.extend(ROOT / name for name in CONFIG_PATHS)
    return {path.relative_to(ROOT).as_posix(): _digest(path.read_bytes())
            for path in sorted(paths)}


def make_schedule(pairs: int, pair_start: int = 0) -> list[dict[str, Any]]:
    require_int(pairs, "pairs", minimum=1)
    require_int(pair_start, "pair_start", minimum=0)
    games = []
    for index in range(pair_start, pair_start + pairs):
        seed = BASE_SEED + index
        for p14_color in (("red", "blue") if index % 2 == 0 else ("blue", "red")):
            games.append({
                "game_id": f"pair_{index:06d}_p14_{p14_color}",
                "pair_index": index, "pair_seed": seed,
                "dice_seed": seed * 3,
                "actor_seeds": {P14: seed * 3 + 1, LEGACY: seed * 3 + 2},
                "red": P14 if p14_color == "red" else LEGACY,
                "blue": P14 if p14_color == "blue" else LEGACY,
            })
    return games


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
                                   cwd=ROOT, text=True, encoding="utf-8").strip()


def make_protocol(pairs: int, pair_start: int) -> dict[str, Any]:
    actors = {}
    for actor, kwargs in ((P14, RELEASE_DEFAULT_ROLLOUT_KWARGS), (LEGACY, LEGACY_KWARGS)):
        actors[actor] = {"actor_id": actor, "kind": "rollout", "kwargs": dict(kwargs),
                         "signature": ai_version_signature(build_ai("rollout", seed=0, **kwargs))}
    return {
        "schema_version": SCHEMA_VERSION, "rules_version": RULES_VERSION,
        "pairs": pairs, "pair_start": pair_start, "expected_games": pairs * 2,
        "layout": "balanced_v1", "first_player": "red", "max_turns": 200,
        "actors": actors, "schedule": make_schedule(pairs, pair_start),
        "source_sha256": source_hashes(),
        "config_raw_sha256": {name: _digest((ROOT / name).read_bytes()) for name in CONFIG_PATHS},
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "environment": {"python": sys.version, "executable": sys.executable,
                        "platform": platform.platform(), "machine": platform.machine(),
                        "processor": platform.processor(), "logical_cpus": os.cpu_count()},
        "limitations": [
            "Wall-clock deadlines can change search completion despite identical RNG seeds.",
            "Paired games reset dice and actor RNG streams; later paths may consume RNG differently.",
            "P14 and legacy retain different historical step budgets (2000ms vs 750ms).",
            "Harness step budget overruns are telemetry, not forfeits; no 240-second clock is enforced.",
            "Only balanced_v1 is sampled; this is not a tournament certification.",
        ],
    }


class ObservedAI:
    """Read diagnostics without changing AI parameters or its random stream."""

    def __init__(self, base: Any, actor_id: str, calls: list[dict[str, Any]]) -> None:
        self.base, self.actor_id, self.calls = base, actor_id, calls

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    def choose_move(self, state: Any, dice: int) -> Any:
        call = {"actor_id": self.actor_id, "color": state.current_player.value, "dice": dice,
                "error": None}
        self.calls.append(call)
        try:
            return self.base.choose_move(state, dice)
        except Exception as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            call.update({
                "internal_deadline_reached": bool(getattr(self.base, "last_timed_out", False)),
                "used_fallback": bool(getattr(self.base, "last_used_fallback", False)),
                "completed_root_visits": sum(stat.visits for stat in getattr(self.base, "last_root_stats", [])),
            })


def run_game(game: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    protocol = manifest["protocol"]
    calls: list[dict[str, Any]] = []
    actors = {}
    for actor_id, spec in protocol["actors"].items():
        base = build_ai(spec["kind"], seed=game["actor_seeds"][actor_id], **spec["kwargs"])
        if ai_version_signature(base) != spec["signature"]:
            raise ValueError(f"AI signature changed: {actor_id}")
        actors[actor_id] = ObservedAI(base, actor_id, calls)
    started = time.perf_counter()
    result = play_one_game(red_ai=actors[game["red"]], blue_ai=actors[game["blue"]],
                           dice_rng=random.Random(game["dice_seed"]), max_turns=protocol["max_turns"],
                           starting_state=starting_state_for(protocol["layout"]))
    wall_seconds = time.perf_counter() - started
    if len(calls) != len(result.step_times_ms):
        raise ValueError("harness timing count differs from observed calls")
    for call, elapsed in zip(calls, result.step_times_ms):
        call["elapsed_ms"] = elapsed
        limit = protocol["actors"][call["actor_id"]]["kwargs"]["max_step_time_ms"]
        call["harness_budget_exceeded"] = elapsed > limit
    by_actor = {}
    for actor_id in actors:
        own = [call for call in calls if call["actor_id"] == actor_id]
        by_actor[actor_id] = {
            "thinking_seconds": sum(call["elapsed_ms"] for call in own) / 1000,
            "step_count": len(own),
            **{key: sum(call[key] for call in own) for key in
               ("internal_deadline_reached", "used_fallback", "completed_root_visits", "harness_budget_exceeded")},
        }
    winner = result.winner.value if result.winner is not None else None
    errors = [call["error"] for call in calls if call["error"] is not None]
    if result.illegal_moves or result.crashes or result.termination_reason == "no_move":
        errors.append({"type": "HarnessFailure", "message": result.termination_reason})
    return {
        "schema_version": SCHEMA_VERSION, "run_id": manifest["run_id"],
        "protocol_sha256": manifest["protocol_sha256"], "input": game,
        "actors": protocol["actors"], "rules_version": protocol["rules_version"],
        "winner": winner, "winner_actor": game[winner] if winner is not None else None,
        "termination_reason": result.termination_reason, "errors": errors,
        "result": {"turns": result.turns, "illegal_moves": result.illegal_moves,
                   "crashes": result.crashes, "harness_step_budget_overruns": result.timeouts},
        "step_times_ms": result.step_times_ms, "observed_calls": calls,
        "by_actor": by_actor, "wall_seconds": wall_seconds,
        "record": result.record.to_dict() if result.record is not None else None,
    }


def _seal(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "content_sha256": _digest(_json_bytes(payload))}


def validate_game(payload: dict[str, Any], game: dict[str, Any], manifest: dict[str, Any]) -> None:
    unsealed = {key: value for key, value in payload.items() if key != "content_sha256"}
    if payload.get("content_sha256") != _digest(_json_bytes(unsealed)):
        raise ValueError(f"corrupt game content: {game['game_id']}")
    expected = {"schema_version": SCHEMA_VERSION, "run_id": manifest["run_id"],
                "protocol_sha256": manifest["protocol_sha256"], "input": game,
                "actors": manifest["protocol"]["actors"], "rules_version": RULES_VERSION}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError(f"game protocol mismatch: {game['game_id']}")
    required = {"winner", "winner_actor", "termination_reason", "errors", "result",
                "step_times_ms", "observed_calls", "by_actor", "wall_seconds", "record"}
    if not required <= payload.keys():
        raise ValueError(f"incomplete game: {game['game_id']}")
    if payload["record"] is not None:
        GameRecord.from_dict(payload["record"]).restore_state()
    elif not payload["errors"]:
        raise ValueError("successful game is missing its record")


def summarize(games: list[dict[str, Any]], manifest: dict[str, Any], source_unchanged: bool) -> dict[str, Any]:
    failures = sum(bool(game["errors"]) for game in games)
    expected = manifest["protocol"]["expected_games"]
    complete = len(games) == expected and source_unchanged and failures == 0
    times = [value for game in games for value in game["step_times_ms"]]
    return {
        "run_id": manifest["run_id"], "protocol_sha256": manifest["protocol_sha256"],
        "status": "complete" if complete else "failed", "expected_games": expected,
        "completed_games": len(games), "failed_games": failures, "source_unchanged": source_unchanged,
        "wins_by_actor": dict(Counter(game["winner_actor"] or "draw" for game in games)),
        "termination_reasons": dict(Counter(game["termination_reason"] for game in games)),
        "harness_step_budget_overruns": sum(game["result"]["harness_step_budget_overruns"] for game in games),
        "step_count": len(times), "max_step_ms": max(times, default=0.0),
        "p95_step_ms": _percentile(times, .95), "p99_step_ms": _percentile(times, .99),
        "game_content_sha256": {game["input"]["game_id"]: game["content_sha256"] for game in games},
    }


def run(output_dir: Path, *, pairs: int = 100, pair_start: int = 0, resume: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        raise ValueError("output-dir must be outside the repository")
    protocol = make_protocol(pairs, pair_start)
    manifest_path = output_dir / "manifest.json"
    if resume:
        manifest = _read_json(manifest_path)
        if manifest.get("protocol") != protocol or manifest.get("protocol_sha256") != _digest(_json_bytes(protocol)):
            raise ValueError("resume protocol/source/config/environment mismatch; no files written")
        for name, expected_hash in protocol["source_sha256"].items():
            if _digest((output_dir / "source_snapshot" / name).read_bytes()) != expected_hash:
                raise ValueError(f"source snapshot mismatch: {name}")
    else:
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError("output-dir is not empty; use a new directory or explicit --resume")
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, expected_hash in protocol["source_sha256"].items():
            content = (ROOT / name).read_bytes()
            if _digest(content) != expected_hash:
                raise ValueError(f"source changed during snapshot: {name}")
            destination = output_dir / "source_snapshot" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_new(destination, content)
        manifest = {"run_id": uuid.uuid4().hex, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "protocol": protocol, "protocol_sha256": _digest(_json_bytes(protocol))}
        _atomic_new(manifest_path, _json_bytes(manifest))
    games_dir = output_dir / "games"
    expected_paths = {game["game_id"] + ".json": game for game in protocol["schedule"]}
    existing = {}
    # Validate all existing results before any write, not just the next scheduled game.
    if games_dir.exists():
        for path in games_dir.glob("*.json"):
            if path.name not in expected_paths:
                raise ValueError(f"unexpected game file: {path.name}")
            payload = _read_json(path)
            validate_game(payload, expected_paths[path.name], manifest)
            existing[path.name] = payload
    games_dir.mkdir(exist_ok=True)
    games = []
    for index, game in enumerate(protocol["schedule"], 1):
        filename = game["game_id"] + ".json"
        if filename in existing:
            payload = existing[filename]
        else:
            try:
                payload = run_game(game, manifest)
                validate_game(_seal(payload), game, manifest)
            except Exception as exc:
                # Harness-level faults cannot promise a full replay; retain explicit failed evidence.
                payload = {"schema_version": SCHEMA_VERSION, "run_id": manifest["run_id"],
                           "protocol_sha256": manifest["protocol_sha256"], "input": game,
                           "actors": protocol["actors"], "rules_version": RULES_VERSION,
                           "winner": None, "winner_actor": None, "termination_reason": "runner_error",
                           "errors": [{"type": type(exc).__name__, "message": str(exc)}],
                           "result": {"turns": 0, "illegal_moves": 0, "crashes": 0, "harness_step_budget_overruns": 0},
                           "step_times_ms": [], "observed_calls": [], "by_actor": {},
                           "wall_seconds": None, "record": None}
            payload = _seal(payload)
            _atomic_new(games_dir / filename, _json_bytes(payload))
        games.append(payload)
        print(f"[{index}/{protocol['expected_games']}] {game['game_id']} winner={payload['winner_actor']} "
              f"termination={payload['termination_reason']} errors={len(payload['errors'])}", flush=True)
    summary = summarize(games, manifest, source_hashes() == protocol["source_sha256"])
    summary_path = output_dir / "summary.json"
    if summary_path.exists():
        if _read_json(summary_path) != summary:
            raise ValueError("existing summary differs; refusing to overwrite")
    else:
        _atomic_new(summary_path, _json_bytes(summary))
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=100)
    parser.add_argument("--pair-start", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = run(args.output_dir, pairs=args.pairs, pair_start=args.pair_start, resume=args.resume)
        return 0 if summary["status"] == "complete" else 1
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"rebaseline refused: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
