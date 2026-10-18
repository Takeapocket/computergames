"""Validate immutable paired P14 evidence and report pair-level uncertainty.

This reads completed records only; no AI search is run. The runner owns the
protocol, seed schedule and record checksum format, which are reused here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import rebaseline_p14 as runner

BOOTSTRAP_SEED = 20261018
BOOTSTRAP_RESAMPLES = 50_000
ERROR_REASONS = {"crash", "illegal_move", "no_move", "runner_error"}
WIN_REASONS = {"winner_target_corner", "winner_capture_all"}
COUNT_KEYS = ("internal_deadline_reached", "used_fallback",
              "completed_root_visits", "harness_budget_exceeded")


def _reject(message: str) -> None:
    raise ValueError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _reject(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                       parse_constant=lambda value: _reject(f"nonfinite JSON: {value}"))
    if not isinstance(value, dict):
        _reject(f"JSON object required: {path}")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        _reject(f"{name} must be a finite nonnegative number")
    return float(value)


def _integer(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        _reject(f"{name} must be a nonnegative integer")
    return value


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_interval(pair_wins: list[int], *, resamples: int = BOOTSTRAP_RESAMPLES) -> dict[str, Any]:
    """Bootstrap whole two-game pairs, using win indicators (draws score zero)."""
    if not pair_wins or any(type(value) is not int or value not in (0, 1, 2) for value in pair_wins):
        _reject("pair_wins must contain 0, 1 or 2 wins for each complete pair")
    if type(resamples) is not int or resamples < 1:
        _reject("resamples must be positive")
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(pair_wins)
    means = [sum(pair_wins[rng.randrange(size)] for _ in range(size)) / (2 * size)
             for _ in range(resamples)]
    return {"unit": "two-game color-swapped pair", "pair_count": size,
            "estimate": sum(pair_wins) / (2 * size), "level": 0.95,
            "low": _percentile(means, 0.025), "high": _percentile(means, 0.975),
            "method": "percentile bootstrap; linear quantile interpolation",
            "seed": BOOTSTRAP_SEED, "resamples": resamples,
            "pair_win_distribution": {str(wins): pair_wins.count(wins) for wins in range(3)}}


def _validate_manifest(manifest: dict[str, Any], run_dir: Path, expected_pairs: int) -> dict[str, Any]:
    protocol = manifest["protocol"]
    if manifest["protocol_sha256"] != runner._digest(runner._json_bytes(protocol)):
        _reject("manifest protocol checksum mismatch")
    if protocol["schema_version"] != runner.SCHEMA_VERSION or protocol["rules_version"] != runner.RULES_VERSION:
        _reject("unsupported schema or rules version")
    if _integer(protocol["pairs"], "pairs") != expected_pairs or protocol["expected_games"] != 2 * expected_pairs:
        _reject("incomplete or unexpected pair count")
    if protocol["layout"] != "balanced_v1" or protocol["first_player"] != "red" or protocol["max_turns"] != 200:
        _reject("layout, first player or turn limit differs from protocol")
    if expected_pairs == 100 and protocol["pair_start"] != 0:
        _reject("formal batch must start at pair 0")
    expected_schedule = runner.make_schedule(expected_pairs, protocol["pair_start"])
    if protocol["schedule"] != expected_schedule:
        _reject("schedule, color assignment or seed plan mismatch")
    actors = protocol["actors"]
    if set(actors) != {runner.P14, runner.LEGACY}:
        _reject("unexpected algorithm identities")
    for actor, kwargs in ((runner.P14, runner.RELEASE_DEFAULT_ROLLOUT_KWARGS),
                          (runner.LEGACY, runner.LEGACY_KWARGS)):
        spec = actors[actor]
        if spec["actor_id"] != actor or spec["kind"] != "rollout" or spec["kwargs"] != kwargs:
            _reject(f"algorithm parameters mismatch: {actor}")
        signature = spec["signature"]
        if signature["rules_version"] != protocol["rules_version"] or any(signature.get(k) != v for k, v in kwargs.items()):
            _reject(f"algorithm signature mismatch: {actor}")
    snapshot = (run_dir / "source_snapshot").resolve()
    for name, digest in protocol["source_sha256"].items():
        source = (snapshot / name).resolve()
        if snapshot not in source.parents or runner._digest(source.read_bytes()) != digest:
            _reject(f"source snapshot checksum mismatch: {name}")
    for name, digest in protocol["config_raw_sha256"].items():
        if protocol["source_sha256"].get(name) != digest:
            _reject(f"configuration snapshot checksum mismatch: {name}")
    return protocol


def _validate_measurements(game: dict[str, Any], protocol: dict[str, Any]) -> None:
    planned, result = game["input"], game["result"]
    reason, winner = game["termination_reason"], game["winner"]
    if reason not in WIN_REASONS | ERROR_REASONS | {"draw_max_turns"}:
        _reject("unknown termination reason")
    if winner not in ("red", "blue", None) or game["winner_actor"] != (planned[winner] if winner else None):
        _reject("winner color/identity mismatch")
    if (reason in WIN_REASONS | {"crash", "illegal_move", "no_move"}) != (winner is not None):
        _reject("winner and termination reason mismatch")
    if bool(game["errors"]) != (reason in ERROR_REASONS):
        _reject("errors and termination reason mismatch")
    turns = _integer(result["turns"], "turns")
    if turns > protocol["max_turns"] or (reason == "draw_max_turns" and turns != protocol["max_turns"]):
        _reject("invalid completed turn count")
    if result["illegal_moves"] != int(reason == "illegal_move") or result["crashes"] != int(reason == "crash"):
        _reject("harness failure count mismatch")
    times, calls = game["step_times_ms"], game["observed_calls"]
    if not isinstance(times, list) or not isinstance(calls, list):
        _reject("step times and observed calls must be lists")
    expected_calls = turns + int(reason in {"crash", "illegal_move", "no_move"})
    if len(times) != len(calls) or len(calls) != expected_calls:
        _reject("harness timing/call/turn length mismatch")
    if reason == "runner_error":
        if turns or calls or game["record"] is not None or game["by_actor"]:
            _reject("malformed runner failure evidence")
        return
    _number(game["wall_seconds"], "wall_seconds")
    record = game["record"]
    if record["initial_state"] != runner.starting_state_for(protocol["layout"]).serialize():
        _reject("record initial layout mismatch")
    if record["metadata"].get("rules_version") != protocol["rules_version"] or len(record["steps"]) != turns:
        _reject("record rule version or step count mismatch")
    restored = runner.GameRecord.from_dict(record).restore_state()
    actual_winner = restored.get_winner()
    if reason in WIN_REASONS and (actual_winner is None or actual_winner.value != winner):
        _reject("record final winner differs from result")
    if reason == "draw_max_turns" and actual_winner is not None:
        _reject("terminal record cannot be a turn-limit draw")
    dice_rng = random.Random(planned["dice_seed"])
    overrun_count = 0
    for index, (elapsed, call) in enumerate(zip(times, calls)):
        _number(elapsed, "step time")
        color = "red" if index % 2 == 0 else "blue"
        actor = planned[color]
        if call["color"] != color or call["actor_id"] != actor or call["elapsed_ms"] != elapsed:
            _reject("step actor, color or harness elapsed mismatch")
        if call["dice"] != dice_rng.randint(1, 6):
            _reject("dice stream differs from fixed seed")
        if index < turns and (record["steps"][index]["dice"] != call["dice"] or record["steps"][index]["player"] != color):
            _reject("record and observed step mismatch")
        for key in ("internal_deadline_reached", "used_fallback", "harness_budget_exceeded"):
            if type(call[key]) is not bool:
                _reject(f"{key} must be boolean")
        _integer(call["completed_root_visits"], "completed_root_visits")
        exceeded = elapsed > protocol["actors"][actor]["kwargs"]["max_step_time_ms"]
        if call["harness_budget_exceeded"] != exceeded:
            _reject("harness overrun flag differs from actual elapsed/limit")
        if (call["error"] is not None) != (reason == "crash" and index == len(calls) - 1):
            _reject("call exception and crash result mismatch")
        overrun_count += exceeded
    if result["harness_step_budget_overruns"] != overrun_count:
        _reject("harness overrun total mismatch")
    if reason in {"crash", "illegal_move", "no_move"} and winner == calls[-1]["color"]:
        _reject("failed actor cannot be the winner")
    if set(game["by_actor"]) != set(protocol["actors"]):
        _reject("missing algorithm timing aggregate")
    for actor, aggregate in game["by_actor"].items():
        own = [call for call in calls if call["actor_id"] == actor]
        expected = {"step_count": len(own), **{key: sum(call[key] for call in own) for key in COUNT_KEYS}}
        if any(aggregate.get(key) != value for key, value in expected.items()):
            _reject(f"algorithm telemetry aggregate mismatch: {actor}")
        if not math.isclose(_number(aggregate["thinking_seconds"], "thinking_seconds"),
                            math.fsum(call["elapsed_ms"] for call in own) / 1000, abs_tol=1e-9):
            _reject(f"algorithm cumulative time mismatch: {actor}")


def load_evidence(run_dir: Path, *, expected_pairs: int = 100) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reject absent, extra, duplicated, corrupt or internally inconsistent games."""
    run_dir = run_dir.resolve()
    manifest = _read(run_dir / "manifest.json")
    protocol = _validate_manifest(manifest, run_dir, expected_pairs)
    expected = {entry["game_id"] + ".json": entry for entry in protocol["schedule"]}
    actual = {path.name: path for path in (run_dir / "games").glob("*.json")}
    if set(actual) != set(expected):
        _reject(f"game file set mismatch: missing={sorted(set(expected) - set(actual))}; extra={sorted(set(actual) - set(expected))}")
    games = []
    for filename, planned in expected.items():
        game = _read(actual[filename])
        runner.validate_game(game, planned, manifest)
        _validate_measurements(game, protocol)
        games.append(game)
    completion = _read(run_dir / "summary.json")
    expected_completion = runner.summarize(games, manifest, source_unchanged=True)
    if completion != expected_completion:
        _reject("runner completion summary or source_unchanged mismatch")
    return manifest, games


def summarize(manifest: dict[str, Any], games: list[dict[str, Any]]) -> dict[str, Any]:
    protocol = manifest["protocol"]
    color_stats = {}
    for color in ("red", "blue"):
        own = [game for game in games if game["input"][color] == runner.P14]
        wins = sum(game["winner_actor"] == runner.P14 for game in own)
        losses = sum(game["winner_actor"] == runner.LEGACY for game in own)
        color_stats[color] = {"games": len(own), "wins": wins, "losses": losses,
                              "draw_max_turns": sum(game["termination_reason"] == "draw_max_turns" for game in own),
                              "runner_errors": sum(game["termination_reason"] == "runner_error" for game in own),
                              "win_rate": wins / len(own),
                              "termination_reasons": dict(Counter(game["termination_reason"] for game in own))}
    pair_wins = [sum(game["winner_actor"] == runner.P14 for game in games if game["input"]["pair_index"] == index)
                 for index in range(protocol["pair_start"], protocol["pair_start"] + protocol["pairs"])]
    actor_stats = {}
    for actor in protocol["actors"]:
        calls = [call for game in games for call in game["observed_calls"] if call["actor_id"] == actor]
        times = [call["elapsed_ms"] for call in calls]
        # A runner-level failure has no timing evidence; do not substitute zero.
        totals = [game["by_actor"][actor]["thinking_seconds"] for game in games if actor in game["by_actor"]]
        actor_stats[actor] = {"steps": len(times), "timed_games": len(totals),
            "step_ms": {"mean": statistics.fmean(times) if times else 0.0,
                        "p50": _percentile(times, .5), "p95": _percentile(times, .95),
                        "p99": _percentile(times, .99), "max": max(times, default=0.0)},
            "per_game_thinking_seconds": {"mean": statistics.fmean(totals) if totals else 0.0,
                                          "max": max(totals, default=0.0)},
            **{key: sum(call[key] for call in calls) for key in COUNT_KEYS}}
    failures = sum(bool(game["errors"]) for game in games)
    return {"run_id": manifest["run_id"], "protocol_sha256": manifest["protocol_sha256"],
            "rules_version": protocol["rules_version"], "games": len(games), "pairs": len(pair_wins),
            "p14_wins": sum(pair_wins), "p14_win_rate": sum(pair_wins) / len(games),
            "p14_by_color": color_stats, "paired_win_rate_interval": paired_interval(pair_wins),
            "termination_reasons": dict(Counter(game["termination_reason"] for game in games)),
            "failed_games": failures, "strength_evidence_has_failures": bool(failures),
            "algorithm_measurements": actor_stats,
            "game_content_sha256": {game["input"]["game_id"]: game["content_sha256"] for game in games},
            "limitations": protocol["limitations"] + [
                "Wins are divided by all scheduled games; failed or truncated games are not removed.",
                "Runner failures have no observed thinking time and are excluded from timing means only.",
                "The interval resamples pairs, not 200 independent games; no Elo or promotion is inferred."]}


def render_markdown(summary: dict[str, Any]) -> str:
    interval = summary["paired_win_rate_interval"]
    lines = ["# P14 修正规则配对基线分析", "", f"规则：`{summary['rules_version']}`；运行：`{summary['run_id']}`。", "",
             f"P14 获胜 {summary['p14_wins']}/{summary['games']} = {summary['p14_win_rate']:.1%}；"
             f"以 {summary['pairs']} 个换色 pair 重采样的 95% 区间为 [{interval['low']:.1%}, {interval['high']:.1%}]。", "",
             "| P14 颜色 | 局数 | 胜 | 负 | 截断局 | Runner 错误 | 胜率 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for color, row in summary["p14_by_color"].items():
        lines.append(f"| {color} | {row['games']} | {row['wins']} | {row['losses']} | {row['draw_max_turns']} | {row['runner_errors']} | {row['win_rate']:.1%} |")
    lines += ["", f"每对 P14 胜 0/1/2 局：{interval['pair_win_distribution']}。",
              f"终止原因：{summary['termination_reasons']}；错误局数：{summary['failed_games']}。", "",
              "| 算法 | 步数 | 均值 ms | P50 ms | P95 ms | P99 ms | 最大 ms | 单局累计均值 s | 单局累计最大 s |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for actor, row in summary["algorithm_measurements"].items():
        times, totals = row["step_ms"], row["per_game_thinking_seconds"]
        lines.append(f"| {actor} | {row['steps']} | {times['mean']:.3f} | {times['p50']:.3f} | {times['p95']:.3f} | {times['p99']:.3f} | {times['max']:.3f} | {totals['mean']:.3f} | {totals['max']:.3f} |")
    lines += ["", "| 算法 | 真实单步越限 | 内部截止 | 逐步回退 | 完成 root visits |", "|---|---:|---:|---:|---:|"]
    for actor, row in summary["algorithm_measurements"].items():
        lines.append(f"| {actor} | {row['harness_budget_exceeded']} | {row['internal_deadline_reached']} | {row['used_fallback']} | {row['completed_root_visits']} |")
    lines += ["", f"区间方法：固定 seed {interval['seed']}，{interval['resamples']:,} 次 pair bootstrap，2.5%/97.5% 百分位（线性插值）。每局胜为 1、其余为 0；截断不算正式和棋或胜局。",
              "", "双方保留各自历史预算（P14 2000ms、对照 750ms）；本结果比较完整配置，不能解释为同预算算法优劣。",
              "真实越限由 harness 的完整调用耗时判定；内部截止是安全停止采样，逐步回退使用 last_used_fallback。累计思考时间不含人工操作，不能作为现场四分钟验收。",
              "固定种子与限时搜索不保证逐步确定性复现；只采样 balanced_v1。保留全部局，不进行 Elo 推断、调参或默认晋升。"]
    if summary["failed_games"]:
        lines += ["", "本批存在错误终止；错误判胜仍按协议保留，不能把统计结果视为正常棋力认证。"]
    return "\n".join(lines) + "\n"


def analyze(run_dir: Path, output_dir: Path, *, expected_pairs: int = 100) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        _reject("analysis output must be outside the repository")
    destinations = (output_dir / "analysis_summary.json", output_dir / "analysis_summary.md")
    if any(path.exists() for path in destinations):
        _reject("analysis output already exists; choose a new output directory")
    manifest, games = load_evidence(run_dir, expected_pairs=expected_pairs)
    summary = summarize(manifest, games)
    markdown = render_markdown(summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents overwriting existing evidence or previous reports.
    for path, content in zip(destinations, (runner._json_bytes(summary), markdown.encode("utf-8"))):
        with path.open("xb") as stream:
            stream.write(content)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-pairs", type=int, default=100, help="Formal batch is 100; use 1 only for separate smoke evidence")
    args = parser.parse_args(argv)
    try:
        summary = analyze(args.run_dir, args.output_dir, expected_pairs=args.expected_pairs)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: summary[key] for key in ("games", "pairs", "p14_wins", "p14_win_rate", "failed_games")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
