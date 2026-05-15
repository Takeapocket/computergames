"""候选 AI 通用 bench：double-sided 对战 + JSON/MD 报告 + 分阶段门禁。

阶段（STAGE_GATES）：
  smoke      验证稳定性（illegal=0, crashes=0, max_step<1000ms）
  candidate  候选门禁（+win_rate≥55%, avg/max_step 上限）
  promotion  晋升门禁（+Wilson CI 下界≥52%）

候选 AI 由 ``--candidate <kind>`` 指定（透传到 ``build_ai``）；对手 / 局数 / 额外门禁
按 ``CANDIDATE_PROFILES`` 给定的候选-阶段默认值决定，可被 ``--opponent`` /
``--games-per-side`` 覆盖。AI-specific 遥测（``last_iterations`` / ``last_max_depth``）
按候选 AI 是否暴露相应属性自动收/略。

依据：
  docs/superpowers/specs/2026-05-13-mcts-phase1-design.md §10（mcts_eval_v1）
  docs/superpowers/specs/2026-05-14-tactical-patches-design.md §10.2（rollout_tactical）
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import (
    STARTING_LAYOUT_ID,
    ai_version_signature,
    build_ai,
    play_one_game,
    starting_state_for,
)
from core.types import Player
from scripts._bench_meta import build_provenance
from scripts.quick_bench import _percentile, wilson_ci


# 门禁运算符：name → (op, threshold)。op ∈ {"eq", "lt", "le", "ge"}
STAGE_GATES: dict[str, dict] = {
    "smoke": {
        "illegal_moves": ("eq", 0),
        "crashes": ("eq", 0),
        "timeouts": ("eq", 0),
        "max_step_time_ms": ("lt", 1000.0),
    },
    "candidate": {
        "illegal_moves": ("eq", 0),
        "crashes": ("eq", 0),
        "timeouts": ("eq", 0),
        "candidate_win_rate": ("ge", 0.55),
        "average_step_time_ms": ("le", 500.0),
        "max_step_time_ms": ("le", 5000.0),
    },
    "promotion": {
        "illegal_moves": ("eq", 0),
        "crashes": ("eq", 0),
        "timeouts": ("eq", 0),
        "candidate_win_rate": ("ge", 0.55),
        "candidate_win_ci_lower": ("ge", 0.52),
        "average_step_time_ms": ("le", 500.0),
        "max_step_time_ms": ("le", 5000.0),
    },
}

# 每个候选 AI 的默认对手 / 局数 / 额外门禁；显式 --opponent / --games-per-side 优先。
CANDIDATE_PROFILES: dict[str, dict[str, dict]] = {
    "mcts_eval_v1": {
        "smoke":     {"opponent": "greedy",      "games_per_side": 50},
        "candidate": {"opponent": "greedy_risk", "games_per_side": 200},
        "promotion": {"opponent": "rollout",     "games_per_side": 400},
    },
    "rollout_32": {
        "candidate": {"opponent": "rollout", "games_per_side": 100},
        "promotion": {"opponent": "rollout", "games_per_side": 400},
    },
    "rollout_risk_playout": {
        "candidate": {
            "opponent": "rollout",
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "games_per_side": 400,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
    },
    "rollout_cutoff_eval": {
        "candidate": {
            "opponent": "rollout",
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "games_per_side": 400,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
    },
    "rollout_zweistein_cutoff": {
        "candidate": {
            "opponent": "rollout",
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "games_per_side": 400,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
    },
    "rollout_tactical": {
        # 设计 §10.3：candidate vs rollout 等价于 MCTS 的 promotion，
        # 因此候选阶段直接套晋升级 Wilson 下界门禁，不另跑 promotion。
        "smoke": {"opponent": "greedy", "games_per_side": 50},
        "candidate": {
            "opponent": "rollout",
            "games_per_side": 400,
            "extra_gates": {"candidate_win_ci_lower": ("ge", 0.52)},
        },
    },
}

OP_LABEL = {"eq": "=", "lt": "<", "le": "≤", "ge": "≥"}
OP_CHECK = {
    "eq": lambda a, t: a == t,
    "lt": lambda a, t: a < t,
    "le": lambda a, t: a <= t,
    "ge": lambda a, t: a >= t,
}


@dataclass(frozen=True)
class Side:
    label: str  # "candidate_red" / "candidate_blue"
    candidate_side: Player


def _make_ai(seed: int, *, kind: str, ai_kwargs: dict | None):
    return build_ai(kind, seed=seed, **(ai_kwargs or {}))


def _merge_profile_kwargs(profile: dict, explicit_kwargs: dict) -> dict:
    return {**profile.get("candidate_kwargs", {}), **explicit_kwargs}


def _candidate_telemetry(ai) -> dict[str, int]:
    """Pull AI-specific per-game telemetry if the AI exposes the well-known attrs.

    ``last_iterations`` / ``last_max_depth`` are MCTS-specific; rollout / tactical
    AIs don't expose them and we just record an empty dict for those games.
    ``fire_counts`` is TacticalAI-specific (Counter[str] of per-branch fire counts);
    each label becomes a ``fire_<label>`` entry so _aggregate can sum it across games.
    """
    out: dict[str, int] = {}
    for attr, key in (
        ("last_iterations", "iterations"),
        ("last_max_depth", "max_depth"),
    ):
        value = getattr(ai, attr, None)
        if value is not None:
            out[key] = int(value)
    fire_counts = getattr(ai, "fire_counts", None)
    if fire_counts is not None:
        for label, count in fire_counts.items():
            out[f"fire_{label}"] = int(count)
    return out


def _aggregate(results, candidate_side: Player) -> dict:
    games = len(results)
    if games == 0:
        return {}
    candidate_wins = 0
    opponent_wins = 0
    draws = 0
    total_turns = 0
    total_illegal = 0
    total_crashes = 0
    total_timeouts = 0
    all_step_times: list[float] = []
    telemetry: dict[str, list[int]] = {}
    for r, t in results:
        if r.winner is None:
            draws += 1
        elif r.winner is candidate_side:
            candidate_wins += 1
        else:
            opponent_wins += 1
        total_turns += r.turns
        total_illegal += r.illegal_moves
        total_crashes += r.crashes
        total_timeouts += int(getattr(r, "timeouts", 0))
        all_step_times.extend(r.step_times_ms)
        for k, v in t.items():
            telemetry.setdefault(k, []).append(v)
    avg_step = sum(all_step_times) / len(all_step_times) if all_step_times else 0.0
    p95_step = _percentile(all_step_times, 0.95)
    p99_step = _percentile(all_step_times, 0.99)
    max_step = max(all_step_times) if all_step_times else 0.0
    ci = wilson_ci(candidate_wins, games)
    summary: dict = {
        "games": games,
        "candidate_wins": candidate_wins,
        "opponent_wins": opponent_wins,
        "draws": draws,
        "candidate_win_rate": candidate_wins / games,
        "candidate_win_ci95": [ci[0], ci[1]],
        "average_turns": total_turns / games,
        "illegal_moves": total_illegal,
        "crashes": total_crashes,
        "timeouts": total_timeouts,
        "average_step_time_ms": avg_step,
        "p95_step_time_ms": p95_step,
        "p99_step_time_ms": p99_step,
        "max_step_time_ms": max_step,
    }
    if "iterations" in telemetry:
        summary["avg_iterations"] = sum(telemetry["iterations"]) / len(telemetry["iterations"])
    if "max_depth" in telemetry:
        summary["max_depth"] = max(telemetry["max_depth"])
    for k, values in telemetry.items():
        if k.startswith("fire_"):
            summary[k] = sum(values)
    return summary


def _run_direction(
    *,
    side: Side,
    games: int,
    master_seed: int,
    starting_layout_id: str,
    max_turns: int,
    candidate_kind: str,
    candidate_kwargs: dict | None,
    opponent_kind: str,
    opponent_kwargs: dict | None,
) -> tuple[list, dict, dict]:
    results: list = []
    candidate_signature: dict | None = None
    opponent_signature: dict | None = None
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        candidate_seed = per_game_seed * 3 + 1
        opponent_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3
        candidate_ai = _make_ai(candidate_seed, kind=candidate_kind, ai_kwargs=candidate_kwargs)
        opponent_ai = _make_ai(opponent_seed, kind=opponent_kind, ai_kwargs=opponent_kwargs)
        if side.candidate_side is Player.RED:
            red_ai, blue_ai = candidate_ai, opponent_ai
        else:
            red_ai, blue_ai = opponent_ai, candidate_ai
        if i == 0:
            candidate_signature = ai_version_signature(candidate_ai)
            opponent_signature = ai_version_signature(opponent_ai)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=random.Random(dice_seed),
            max_turns=max_turns,
            starting_state=starting_state_for(starting_layout_id),
        )
        results.append((result, _candidate_telemetry(candidate_ai)))
    summary = _aggregate(results, candidate_side=side.candidate_side)
    return results, summary, {"candidate": candidate_signature, "opponent": opponent_signature}


def _combine(red_summary: dict, blue_summary: dict) -> dict:
    games = red_summary["games"] + blue_summary["games"]
    if games == 0:
        return {}
    candidate_wins = red_summary["candidate_wins"] + blue_summary["candidate_wins"]
    illegal = red_summary["illegal_moves"] + blue_summary["illegal_moves"]
    crashes = red_summary["crashes"] + blue_summary["crashes"]
    timeouts = red_summary.get("timeouts", 0) + blue_summary.get("timeouts", 0)
    red_games = red_summary["games"]
    blue_games = blue_summary["games"]
    avg_step = (
        red_summary["average_step_time_ms"] * red_games
        + blue_summary["average_step_time_ms"] * blue_games
    ) / games
    p95_step = max(red_summary.get("p95_step_time_ms", 0.0), blue_summary.get("p95_step_time_ms", 0.0))
    p99_step = max(red_summary.get("p99_step_time_ms", 0.0), blue_summary.get("p99_step_time_ms", 0.0))
    max_step = max(red_summary["max_step_time_ms"], blue_summary["max_step_time_ms"])
    ci = wilson_ci(candidate_wins, games)
    combined: dict = {
        "games": games,
        "candidate_wins": candidate_wins,
        "candidate_win_rate": candidate_wins / games,
        "candidate_win_ci95": [ci[0], ci[1]],
        "illegal_moves": illegal,
        "crashes": crashes,
        "timeouts": timeouts,
        "average_step_time_ms": avg_step,
        "p95_step_time_ms": p95_step,
        "p99_step_time_ms": p99_step,
        "max_step_time_ms": max_step,
    }
    if "avg_iterations" in red_summary or "avg_iterations" in blue_summary:
        red_iters = red_summary.get("avg_iterations", 0.0) * red_games
        blue_iters = blue_summary.get("avg_iterations", 0.0) * blue_games
        combined["avg_iterations"] = (red_iters + blue_iters) / games
    if "max_depth" in red_summary or "max_depth" in blue_summary:
        combined["max_depth"] = max(
            red_summary.get("max_depth", 0),
            blue_summary.get("max_depth", 0),
        )
    fire_keys = {
        k for k in (*red_summary.keys(), *blue_summary.keys())
        if k.startswith("fire_")
    }
    for k in fire_keys:
        combined[k] = red_summary.get(k, 0) + blue_summary.get(k, 0)
    return combined


def _format_value(name: str, value) -> str:
    if value is None:
        return "N/A"
    if name in {"candidate_win_rate", "candidate_win_ci_lower"}:
        return f"{value*100:.1f}%"
    if "step_time_ms" in name:
        return f"{value:.1f}ms"
    return str(value)


def _gate_value(combined: dict, name: str):
    if name == "candidate_win_ci_lower":
        return combined.get("candidate_win_ci95", [None, None])[0]
    return combined.get(name)


def _evaluate_gates(combined: dict, gates: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for name, (op, threshold) in gates.items():
        actual = _gate_value(combined, name)
        if actual is None:
            failures.append(f"{name}: 缺字段")
            continue
        if not OP_CHECK[op](actual, threshold):
            failures.append(
                f"{name} = {_format_value(name, actual)}"
                f"（要求 {OP_LABEL[op]} {_format_value(name, threshold)}）"
            )
    return (not failures), failures


def _resolve_profile(candidate_kind: str, stage: str) -> dict:
    return CANDIDATE_PROFILES.get(candidate_kind, {}).get(stage, {})


def _resolve_gates(candidate_kind: str, stage: str) -> dict:
    gates = dict(STAGE_GATES[stage])
    extra = _resolve_profile(candidate_kind, stage).get("extra_gates")
    if extra:
        gates.update(extra)
    return gates


def _write_markdown(
    md_path: Path,
    *,
    candidate_kind: str,
    stage: str,
    opponent_kind: str,
    args: argparse.Namespace,
    candidate_kwargs: dict,
    opponent_kwargs: dict,
    candidate_signature: dict | None,
    opponent_signature: dict | None,
    red_summary: dict,
    blue_summary: dict,
    combined: dict,
    gates_ok: bool,
    failures: list[str],
    gates: dict,
    elapsed_seconds: float,
    generated_at: str,
) -> None:
    has_telemetry = "avg_iterations" in combined or "max_depth" in combined

    lines: list[str] = [
        f"# {candidate_kind} bench: stage={stage}",
        "",
        f"- 生成时间：{generated_at}",
        f"- 命令：`python scripts/bench_ai.py {' '.join(sys.argv[1:])}`",
        f"- 候选：`{candidate_kind}`",
        f"- 阶段：`{stage}`",
        f"- 对手：`{opponent_kind}`",
        f"- master seed：{args.seed}",
        f"- 每方局数：{args.games_per_side}",
        f"- 最大半步：{args.max_turns}",
        "- 候选参数（有效）："
        f"`{json.dumps(candidate_kwargs, ensure_ascii=False, sort_keys=True)}`",
        "- 对手参数（有效）："
        f"`{json.dumps(opponent_kwargs, ensure_ascii=False, sort_keys=True)}`",
        "- 候选签名："
        f"`{json.dumps(candidate_signature or {}, ensure_ascii=False, sort_keys=True)}`",
        "- 对手签名："
        f"`{json.dumps(opponent_signature or {}, ensure_ascii=False, sort_keys=True)}`",
    ]
    if args.candidate_arg:
        lines.append(f"- 候选参数：{', '.join(args.candidate_arg)}")
    if args.opponent_arg:
        lines.append(f"- 对手参数：{', '.join(args.opponent_arg)}")
    lines.extend([
        f"- 总耗时：{elapsed_seconds:.1f}s",
        "",
        f"## 门禁（stage={stage}）",
        "",
    ])
    for name, (op, threshold) in gates.items():
        actual = _gate_value(combined, name)
        ok = OP_CHECK[op](actual, threshold) if actual is not None else False
        verdict = "PASS" if ok else "FAIL"
        lines.append(
            f"- {name} {OP_LABEL[op]} {_format_value(name, threshold)}：{verdict} "
            f"(实测 {_format_value(name, actual)})"
        )

    lines.extend([
        "",
        f"**{stage.capitalize()} 结论：{'PASS' if gates_ok else 'FAIL'}**",
    ])
    if failures:
        lines.append("")
        lines.append("失败原因：")
        for f in failures:
            lines.append(f"- {f}")

    lines.extend([
        "",
        "## 双向胜率",
        "",
    ])
    if has_telemetry:
        lines.append(
            "| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms | avg_iters | max_depth |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    else:
        lines.append(
            "| 方向 | 局数 | 候选胜 | 对手胜 | 平 | 候选胜率 | avg_step_ms | p95_step_ms | p99_step_ms | max_step_ms |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    def _row(label: str, s: dict) -> str:
        base = (
            f"| {label} | {s['games']} | {s['candidate_wins']} "
            f"| {s['opponent_wins']} | {s['draws']} "
            f"| {s['candidate_win_rate']*100:.1f}% "
            f"| {s['average_step_time_ms']:.1f} "
            f"| {s['p95_step_time_ms']:.1f} "
            f"| {s['p99_step_time_ms']:.1f} "
            f"| {s['max_step_time_ms']:.1f} "
        )
        if has_telemetry:
            base += f"| {s.get('avg_iterations', 0.0):.1f} | {s.get('max_depth', 0)} "
        return base + "|"

    lines.append(_row(f"候选 红 vs {opponent_kind} 蓝", red_summary))
    lines.append(_row(f"{opponent_kind} 红 vs 候选 蓝", blue_summary))

    combined_row = (
        f"| **合并** | **{combined['games']}** | **{combined['candidate_wins']}** | — | — "
        f"| **{combined['candidate_win_rate']*100:.1f}%** "
        f"(Wilson 95% CI [{combined['candidate_win_ci95'][0]*100:.1f}%, "
        f"{combined['candidate_win_ci95'][1]*100:.1f}%]) "
        f"| {combined['average_step_time_ms']:.1f} "
        f"| {combined['p95_step_time_ms']:.1f} "
        f"| {combined['p99_step_time_ms']:.1f} "
        f"| {combined['max_step_time_ms']:.1f} "
    )
    if has_telemetry:
        combined_row += f"| {combined.get('avg_iterations', 0.0):.1f} | {combined.get('max_depth', 0)} "
    combined_row += "|"
    lines.append(combined_row)

    fire_keys = sorted(k for k in combined if k.startswith("fire_"))
    if fire_keys:
        lines.extend(["", "## 战术分支命中统计", ""])
        for k in fire_keys:
            lines.append(f"- {k}: {combined[k]}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_kv(raw: list[str], parser: argparse.ArgumentParser, flag: str) -> dict:
    out: dict = {}
    for kv in raw:
        if "=" not in kv:
            parser.error(f"{flag} 必须是 KEY=VALUE 形式，得到：{kv!r}")
        key, value = kv.split("=", 1)
        for caster in (int, float):
            try:
                out[key] = caster(value)
                break
            except ValueError:
                continue
        else:
            if value.lower() in {"true", "false"}:
                out[key] = value.lower() == "true"
            else:
                out[key] = value
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="候选 AI 通用 bench：双向对战 + 分阶段门禁。"
    )
    parser.add_argument("--candidate", required=True, help="候选 AI 的 build_ai kind。")
    parser.add_argument(
        "--candidate-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="透传给 build_ai 的候选 kwargs，可多次使用。",
    )
    parser.add_argument(
        "--stage",
        choices=sorted(STAGE_GATES),
        default="smoke",
        help="阶段决定门禁集合；候选默认对手/局数由 CANDIDATE_PROFILES 决定。",
    )
    parser.add_argument(
        "--opponent",
        default=None,
        help="对手 AI kind；省略时按 --stage + 候选 profile 选默认值。",
    )
    parser.add_argument(
        "--opponent-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="透传给 build_ai 的对手 kwargs，可多次使用。",
    )
    parser.add_argument(
        "--games-per-side",
        type=int,
        default=None,
        help="每方局数；省略时按 --stage + 候选 profile 选默认值。",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--starting-layout", default=STARTING_LAYOUT_ID)
    parser.add_argument("--report-dir", default=str(ROOT / "reports"))
    parser.add_argument("--no-save-report", action="store_true")
    parser.add_argument("--report-name", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    profile = _resolve_profile(args.candidate, args.stage)
    opponent_kind = args.opponent or profile.get("opponent")
    if opponent_kind is None:
        parser.error(
            f"--opponent 未指定且 {args.candidate!r} stage={args.stage!r} 无默认对手"
        )
    if args.games_per_side is None:
        args.games_per_side = profile.get("games_per_side")
        if args.games_per_side is None:
            parser.error(
                f"--games-per-side 未指定且 {args.candidate!r} stage={args.stage!r} 无默认局数"
            )

    candidate_kwargs = _parse_kv(args.candidate_arg, parser, "--candidate-arg")
    candidate_kwargs = _merge_profile_kwargs(profile, candidate_kwargs)
    opponent_kwargs = _parse_kv(args.opponent_arg, parser, "--opponent-arg")
    gates = _resolve_gates(args.candidate, args.stage)

    start = time.perf_counter()
    red_results, red_summary, red_sigs = _run_direction(
        side=Side("candidate_red", Player.RED),
        games=args.games_per_side,
        master_seed=args.seed,
        starting_layout_id=args.starting_layout,
        max_turns=args.max_turns,
        candidate_kind=args.candidate,
        candidate_kwargs=candidate_kwargs or None,
        opponent_kind=opponent_kind,
        opponent_kwargs=opponent_kwargs or None,
    )
    blue_results, blue_summary, blue_sigs = _run_direction(
        side=Side("candidate_blue", Player.BLUE),
        games=args.games_per_side,
        master_seed=args.seed + 1,
        starting_layout_id=args.starting_layout,
        max_turns=args.max_turns,
        candidate_kind=args.candidate,
        candidate_kwargs=candidate_kwargs or None,
        opponent_kind=opponent_kind,
        opponent_kwargs=opponent_kwargs or None,
    )
    elapsed = time.perf_counter() - start

    combined = _combine(red_summary, blue_summary)
    gates_ok, failures = _evaluate_gates(combined, gates)

    summary = {
        **build_provenance(
            repo_root=ROOT,
            script_name="bench_ai.py",
            argv=argv,
            starting_layout_id=args.starting_layout,
        ),
        "experiment": f"{args.candidate}_{args.stage}",
        "candidate": args.candidate,
        "candidate_kwargs": candidate_kwargs,
        "stage": args.stage,
        "opponent": opponent_kind,
        "opponent_kwargs": opponent_kwargs,
        "games_per_side": args.games_per_side,
        "red_direction": {
            "label": f"candidate_red_vs_{opponent_kind}_blue",
            "summary": red_summary,
        },
        "blue_direction": {
            "label": f"{opponent_kind}_red_vs_candidate_blue",
            "summary": blue_summary,
        },
        "combined": combined,
        "gates_pass": gates_ok,
        "gate_failures": failures,
        "ai_versions": {
            "candidate": red_sigs["candidate"],
            "opponent": red_sigs["opponent"],
        },
        "max_turns": args.max_turns,
        "wall_seconds": round(elapsed, 3),
    }

    generated_at = summary["generated_at"]
    report_path: str | None = None
    md_path: str | None = None
    if not args.no_save_report:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = args.report_name or f"{args.stage}_{args.candidate}_{timestamp}"
        report_path = str(report_dir / f"{stem}.json")
        Path(report_path).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        md_path = str(report_dir / f"{stem}.md")
        _write_markdown(
            Path(md_path),
            candidate_kind=args.candidate,
            stage=args.stage,
            opponent_kind=opponent_kind,
            args=args,
            candidate_kwargs=candidate_kwargs,
            opponent_kwargs=opponent_kwargs,
            candidate_signature=red_sigs["candidate"],
            opponent_signature=red_sigs["opponent"],
            red_summary=red_summary,
            blue_summary=blue_summary,
            combined=combined,
            gates_ok=gates_ok,
            failures=failures,
            gates=gates,
            elapsed_seconds=elapsed,
            generated_at=generated_at,
        )
        summary["report_path"] = report_path
        summary["markdown_path"] = md_path

    print(json.dumps(
        {k: v for k, v in summary.items() if k not in {"red_direction", "blue_direction"}},
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if gates_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
