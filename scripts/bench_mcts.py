"""mcts_eval_v1 Phase 1 bench：double-sided 对战 + JSON/MD 报告 + 分阶段门禁。

阶段：
  smoke      默认对手 greedy，验证稳定性（illegal=0, crashes=0, max_step<gate）
  candidate  默认对手 greedy_risk，候选门禁（+win_rate≥55%, avg/max_step 上限）
  promotion  默认对手 rollout，晋升门禁（+Wilson CI 下界≥52%）

不修改默认 AI；只有 `--stage promotion` PASS 才允许讨论改 release 配置。

依据：docs/superpowers/specs/2026-05-13-mcts-phase1-design.md 第 10 节。
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
from ai.mcts import MCTSAI
from core.types import Player
from scripts._bench_meta import build_provenance
from scripts.quick_bench import wilson_ci


# 门禁运算符：name → (op, threshold)。op ∈ {"eq", "lt", "le", "ge"}
STAGE_CONFIG: dict[str, dict] = {
    "smoke": {
        "default_opponent": "greedy",
        "default_games_per_side": 50,
        "doc_section": "smoke",
        "gates": {
            "illegal_moves": ("eq", 0),
            "crashes": ("eq", 0),
            "max_step_time_ms": ("lt", 1000.0),
        },
    },
    "candidate": {
        "default_opponent": "greedy_risk",
        "default_games_per_side": 200,
        "doc_section": "候选",
        "gates": {
            "illegal_moves": ("eq", 0),
            "crashes": ("eq", 0),
            "mcts_win_rate": ("ge", 0.55),
            "average_step_time_ms": ("le", 500.0),
            "max_step_time_ms": ("le", 5000.0),
        },
    },
    "promotion": {
        "default_opponent": "rollout",
        "default_games_per_side": 400,
        "doc_section": "晋升",
        "gates": {
            "illegal_moves": ("eq", 0),
            "crashes": ("eq", 0),
            "mcts_win_rate": ("ge", 0.55),
            "mcts_win_ci_lower": ("ge", 0.52),
            "average_step_time_ms": ("le", 500.0),
            "max_step_time_ms": ("le", 5000.0),
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
    label: str  # "mcts_red" / "mcts_blue"
    mcts_side: Player


def _make_mcts(seed: int, *, time_limit_ms: float, max_iterations: int | None) -> MCTSAI:
    return MCTSAI(
        time_limit_ms=time_limit_ms,
        max_iterations=max_iterations,
        rng=random.Random(seed),
        name="mcts_eval_v1",
    )


def _make_opponent(seed: int, *, kind: str, ai_kwargs: dict | None = None):
    """通过 build_ai 构造对手；和 build_ai(kind, seed=seed) 完全同义。"""
    return build_ai(kind, seed=seed, **(ai_kwargs or {}))


def _aggregate(results, mcts_side: Player) -> dict:
    games = len(results)
    if games == 0:
        return {}
    mcts_wins = 0
    opponent_wins = 0
    draws = 0
    total_turns = 0
    total_illegal = 0
    total_crashes = 0
    all_step_times: list[float] = []
    iter_stats: list[int] = []
    depth_stats: list[int] = []
    for r, iters, depth in results:
        if r.winner is None:
            draws += 1
        elif r.winner is mcts_side:
            mcts_wins += 1
        else:
            opponent_wins += 1
        total_turns += r.turns
        total_illegal += r.illegal_moves
        total_crashes += r.crashes
        all_step_times.extend(r.step_times_ms)
        iter_stats.append(iters)
        depth_stats.append(depth)
    avg_step = sum(all_step_times) / len(all_step_times) if all_step_times else 0.0
    max_step = max(all_step_times) if all_step_times else 0.0
    ci = wilson_ci(mcts_wins, games)
    return {
        "games": games,
        "mcts_wins": mcts_wins,
        "opponent_wins": opponent_wins,
        "draws": draws,
        "mcts_win_rate": mcts_wins / games,
        "mcts_win_ci95": [ci[0], ci[1]],
        "average_turns": total_turns / games,
        "illegal_moves": total_illegal,
        "crashes": total_crashes,
        "timeouts": 0,
        "average_step_time_ms": avg_step,
        "max_step_time_ms": max_step,
        "avg_iterations": (sum(iter_stats) / len(iter_stats)) if iter_stats else 0.0,
        "max_depth": max(depth_stats) if depth_stats else 0,
    }


def _run_direction(
    *,
    side: Side,
    games: int,
    master_seed: int,
    starting_layout_id: str,
    time_limit_ms: float,
    max_iterations: int | None,
    max_turns: int,
    opponent_kind: str,
    opponent_kwargs: dict | None = None,
) -> tuple[list, dict, dict]:
    results: list = []
    mcts_signature: dict | None = None
    opponent_signature: dict | None = None
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        mcts_seed = per_game_seed * 3 + 1
        opponent_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3
        mcts_ai = _make_mcts(mcts_seed, time_limit_ms=time_limit_ms, max_iterations=max_iterations)
        opponent_ai = _make_opponent(
            opponent_seed, kind=opponent_kind, ai_kwargs=opponent_kwargs
        )
        if side.mcts_side is Player.RED:
            red_ai, blue_ai = mcts_ai, opponent_ai
        else:
            red_ai, blue_ai = opponent_ai, mcts_ai
        if i == 0:
            mcts_signature = ai_version_signature(mcts_ai)
            opponent_signature = ai_version_signature(opponent_ai)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=random.Random(dice_seed),
            max_turns=max_turns,
            starting_state=starting_state_for(starting_layout_id),
        )
        results.append((result, mcts_ai.last_iterations, mcts_ai.last_max_depth))
    summary = _aggregate(results, mcts_side=side.mcts_side)
    return results, summary, {"mcts": mcts_signature, "opponent": opponent_signature}


def _combine(red_summary: dict, blue_summary: dict) -> dict:
    games = red_summary["games"] + blue_summary["games"]
    if games == 0:
        return {}
    mcts_wins = red_summary["mcts_wins"] + blue_summary["mcts_wins"]
    illegal = red_summary["illegal_moves"] + blue_summary["illegal_moves"]
    crashes = red_summary["crashes"] + blue_summary["crashes"]
    avg_step = (
        red_summary["average_step_time_ms"] * red_summary["games"]
        + blue_summary["average_step_time_ms"] * blue_summary["games"]
    ) / games
    max_step = max(red_summary["max_step_time_ms"], blue_summary["max_step_time_ms"])
    ci = wilson_ci(mcts_wins, games)
    return {
        "games": games,
        "mcts_wins": mcts_wins,
        "mcts_win_rate": mcts_wins / games,
        "mcts_win_ci95": [ci[0], ci[1]],
        "illegal_moves": illegal,
        "crashes": crashes,
        "average_step_time_ms": avg_step,
        "max_step_time_ms": max_step,
        "avg_iterations": (
            red_summary["avg_iterations"] * red_summary["games"]
            + blue_summary["avg_iterations"] * blue_summary["games"]
        ) / games,
        "max_depth": max(red_summary["max_depth"], blue_summary["max_depth"]),
    }


def _format_value(name: str, value) -> str:
    """门禁阈值/实测值的展示格式。"""
    if value is None:
        return "N/A"
    if name in {"mcts_win_rate", "mcts_win_ci_lower"}:
        return f"{value*100:.1f}%"
    if "step_time_ms" in name:
        return f"{value:.1f}ms"
    return str(value)


def _gate_value(combined: dict, name: str):
    if name == "mcts_win_ci_lower":
        return combined.get("mcts_win_ci95", [None, None])[0]
    return combined.get(name)


def _evaluate_gates(combined: dict, stage: str) -> tuple[bool, list[str]]:
    gates = STAGE_CONFIG[stage]["gates"]
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


def _write_markdown(
    md_path: Path,
    *,
    stage: str,
    opponent_kind: str,
    args: argparse.Namespace,
    red_summary: dict,
    blue_summary: dict,
    combined: dict,
    gates_ok: bool,
    failures: list[str],
    elapsed_seconds: float,
    generated_at: str,
) -> None:
    section = STAGE_CONFIG[stage]["doc_section"]
    gates = STAGE_CONFIG[stage]["gates"]

    lines: list[str] = [
        f"# mcts_eval_v1 Phase 1 {stage.capitalize()} Bench",
        "",
        f"- 生成时间：{generated_at}",
        f"- 命令：`python scripts/bench_mcts.py {' '.join(sys.argv[1:])}`",
        f"- 阶段：`{stage}`",
        f"- 对手：`{opponent_kind}`",
        f"- master seed：{args.seed}",
        f"- 每方局数：{args.games_per_side}",
        f"- 最大半步：{args.max_turns}",
        f"- mcts_eval_v1 参数：time_limit_ms={args.time_limit_ms}, "
        f"max_iterations={args.max_iterations}",
        f"- 总耗时：{elapsed_seconds:.1f}s",
        "",
        f"## 门禁（设计文档 §10 {section}）",
        "",
    ]

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
        "| 方向 | 局数 | MCTS 胜 | 对手胜 | 平 | MCTS 胜率 | avg_step_ms | max_step_ms | avg_iters | max_depth |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| MCTS 红 vs {opponent_kind} 蓝 | {red_summary['games']} | {red_summary['mcts_wins']} "
        f"| {red_summary['opponent_wins']} | {red_summary['draws']} "
        f"| {red_summary['mcts_win_rate']*100:.1f}% "
        f"| {red_summary['average_step_time_ms']:.1f} "
        f"| {red_summary['max_step_time_ms']:.1f} "
        f"| {red_summary['avg_iterations']:.1f} | {red_summary['max_depth']} |",
        f"| {opponent_kind} 红 vs MCTS 蓝 | {blue_summary['games']} | {blue_summary['mcts_wins']} "
        f"| {blue_summary['opponent_wins']} | {blue_summary['draws']} "
        f"| {blue_summary['mcts_win_rate']*100:.1f}% "
        f"| {blue_summary['average_step_time_ms']:.1f} "
        f"| {blue_summary['max_step_time_ms']:.1f} "
        f"| {blue_summary['avg_iterations']:.1f} | {blue_summary['max_depth']} |",
        f"| **合并** | **{combined['games']}** | **{combined['mcts_wins']}** | — | — "
        f"| **{combined['mcts_win_rate']*100:.1f}%** "
        f"(Wilson 95% CI [{combined['mcts_win_ci95'][0]*100:.1f}%, "
        f"{combined['mcts_win_ci95'][1]*100:.1f}%]) "
        f"| {combined['average_step_time_ms']:.1f} "
        f"| {combined['max_step_time_ms']:.1f} "
        f"| {combined['avg_iterations']:.1f} | {combined['max_depth']} |",
    ])

    if stage == "smoke":
        lines.extend([
            "",
            "## 注意",
            "",
            "本 smoke 只验证稳定性，胜率仅供参考；要判断 mcts_eval_v1 是否能晋升默认 AI，需要",
            "对 `rollout` 做更大样本的候选/晋升阶段 bench（见设计文档 §10）。",
        ])
    elif stage == "candidate":
        lines.extend([
            "",
            "## 注意",
            "",
            f"候选阶段证明 mcts_eval_v1 在标准对手 `{opponent_kind}` 上有统计优势。",
            "晋升为默认 AI 仍需对 `rollout` 跑晋升阶段（≥400 局/方向，Wilson 下界 ≥52%）。",
        ])
    else:  # promotion
        lines.extend([
            "",
            "## 注意",
            "",
            f"晋升阶段以 `{opponent_kind}` 为基准；仅在 PASS 时允许讨论替换默认 AI。",
            "修改 `gui/main_window.py` 或 `release/v1.0/config.json` 等需另起 PR。",
        ])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_opponent_kwargs(raw: list[str], parser: argparse.ArgumentParser) -> dict:
    out: dict = {}
    for kv in raw:
        if "=" not in kv:
            parser.error(f"--opponent-arg 必须是 KEY=VALUE 形式，得到：{kv!r}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="mcts_eval_v1 Phase 1 bench：双向对战 + 分阶段门禁。"
    )
    parser.add_argument(
        "--stage",
        choices=sorted(STAGE_CONFIG),
        default="smoke",
        help="阶段决定默认对手和门禁集合（设计文档 §10）。",
    )
    parser.add_argument(
        "--opponent",
        default=None,
        help="对手 AI kind；省略时按 --stage 选择默认值。",
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
        help="每方局数；省略时按 --stage 选择默认值。",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--time-limit-ms", type=float, default=200.0)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--starting-layout", default=STARTING_LAYOUT_ID)
    parser.add_argument("--report-dir", default=str(ROOT / "reports"))
    parser.add_argument("--no-save-report", action="store_true")
    parser.add_argument("--report-name", default=None)
    args = parser.parse_args(argv)

    stage_cfg = STAGE_CONFIG[args.stage]
    opponent_kind = args.opponent or stage_cfg["default_opponent"]
    if args.games_per_side is None:
        args.games_per_side = stage_cfg["default_games_per_side"]
    opponent_kwargs = _parse_opponent_kwargs(args.opponent_arg, parser)

    start = time.perf_counter()
    red_results, red_summary, red_sigs = _run_direction(
        side=Side("mcts_red", Player.RED),
        games=args.games_per_side,
        master_seed=args.seed,
        starting_layout_id=args.starting_layout,
        time_limit_ms=args.time_limit_ms,
        max_iterations=args.max_iterations,
        max_turns=args.max_turns,
        opponent_kind=opponent_kind,
        opponent_kwargs=opponent_kwargs or None,
    )
    blue_results, blue_summary, blue_sigs = _run_direction(
        side=Side("mcts_blue", Player.BLUE),
        games=args.games_per_side,
        master_seed=args.seed + 1,
        starting_layout_id=args.starting_layout,
        time_limit_ms=args.time_limit_ms,
        max_iterations=args.max_iterations,
        max_turns=args.max_turns,
        opponent_kind=opponent_kind,
        opponent_kwargs=opponent_kwargs or None,
    )
    elapsed = time.perf_counter() - start

    combined = _combine(red_summary, blue_summary)
    gates_ok, failures = _evaluate_gates(combined, args.stage)

    summary = {
        **build_provenance(
            repo_root=ROOT,
            script_name="bench_mcts.py",
            argv=argv,
            starting_layout_id=args.starting_layout,
        ),
        "experiment": f"mcts_eval_v1_phase1_{args.stage}",
        "stage": args.stage,
        "opponent": opponent_kind,
        "opponent_kwargs": opponent_kwargs,
        "games_per_side": args.games_per_side,
        "red_direction": {
            "label": f"mcts_red_vs_{opponent_kind}_blue",
            "summary": red_summary,
        },
        "blue_direction": {
            "label": f"{opponent_kind}_red_vs_mcts_blue",
            "summary": blue_summary,
        },
        "combined": combined,
        "gates_pass": gates_ok,
        "gate_failures": failures,
        "ai_versions": {
            "mcts": red_sigs["mcts"],
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
        stem = args.report_name or f"{args.stage}_mcts_eval_v1_{timestamp}"
        report_path = str(report_dir / f"{stem}.json")
        Path(report_path).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        md_path = str(report_dir / f"{stem}.md")
        _write_markdown(
            Path(md_path),
            stage=args.stage,
            opponent_kind=opponent_kind,
            args=args,
            red_summary=red_summary,
            blue_summary=blue_summary,
            combined=combined,
            gates_ok=gates_ok,
            failures=failures,
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
