"""greedy_risk 参数随机采样 + train/validation 双轮评估。

不替换默认 AI；候选晋升由 reports/ai_promotion_decision.md 单独决定。
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import STARTING_LAYOUT_ID, build_ai, play_one_game, starting_state_for
from core.types import Player


DISTANCE_WEIGHTS = [0.5, 1.0, 2.0, 3.0]
MATERIAL_WEIGHTS = [5.0, 10.0, 20.0]
EXPECTED_RISK_WEIGHTS = [1.0, 3.0, 5.0]
EXPECTED_WIN_RISK_WEIGHTS = [100.0, 500.0, 1000.0]
SELF_CAPTURE_WEIGHTS = [0.0, 0.5, 1.0]


def _full_grid() -> list[dict[str, float]]:
    grid: list[dict[str, float]] = []
    for dw, mw, erw, ewrw, scw in itertools.product(
        DISTANCE_WEIGHTS,
        MATERIAL_WEIGHTS,
        EXPECTED_RISK_WEIGHTS,
        EXPECTED_WIN_RISK_WEIGHTS,
        SELF_CAPTURE_WEIGHTS,
    ):
        grid.append({
            "distance_weight": dw,
            "material_weight": mw,
            "expected_risk_weight": erw,
            "expected_win_risk_weight": ewrw,
            "self_capture_weight": scw,
        })
    return grid


def iter_param_grid(*, limit: int | None = None, seed: int = 0) -> Iterable[dict[str, float]]:
    """从笛卡尔积中随机抽 ``limit`` 个候选；seed 固定时结果稳定。"""
    grid = _full_grid()
    rng = random.Random(seed)
    rng.shuffle(grid)
    if limit is not None:
        grid = grid[:limit]
    return iter(grid)


def summarize_candidate(
    *,
    params: dict[str, float],
    wins: int,
    games: int,
    illegal_moves: int,
    crashes: int,
    timeouts: int,
    max_step_time_ms: float,
) -> str:
    """单候选 markdown 行（用于 report 主体）。"""
    rate = (100.0 * wins / games) if games else 0.0
    params_str = ", ".join(f"{k}={v}" for k, v in params.items())
    return (
        f"- {rate:.1f}% (wins={wins}/{games}) "
        f"illegal={illegal_moves} crashes={crashes} timeouts={timeouts} "
        f"max_step_ms={max_step_time_ms:.1f} "
        f"| {params_str}"
    )


def _combine_stats(stats_list: list[dict]) -> dict:
    games = sum(stats["games"] for stats in stats_list)
    step_count = sum(stats.get("step_time_count", 0) for stats in stats_list)
    total_step_time = sum(stats.get("total_step_time_ms", 0.0) for stats in stats_list)
    return {
        "wins": sum(stats["wins"] for stats in stats_list),
        "games": games,
        "illegal_moves": sum(stats["illegal_moves"] for stats in stats_list),
        "crashes": sum(stats["crashes"] for stats in stats_list),
        "timeouts": sum(stats.get("timeouts", 0) for stats in stats_list),
        "max_step_time_ms": max((stats["max_step_time_ms"] for stats in stats_list), default=0.0),
        "avg_step_time_ms": (total_step_time / step_count) if step_count else 0.0,
        "total_step_time_ms": total_step_time,
        "step_time_count": step_count,
    }


def _run_candidate(
    params: dict[str, float],
    *,
    games: int,
    master_seed: int,
    layout_id: str,
    max_turns: int,
    candidate_player: Player = Player.RED,
) -> dict:
    wins = 0
    illegal = 0
    crashes = 0
    timeouts = 0
    step_times: list[float] = []
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        red_seed = per_game_seed * 3 + 1
        blue_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3
        if candidate_player is Player.RED:
            red_ai = build_ai("greedy_risk", seed=red_seed, **params)
            blue_ai = build_ai("greedy_risk", seed=blue_seed)
        elif candidate_player is Player.BLUE:
            red_ai = build_ai("greedy_risk", seed=red_seed)
            blue_ai = build_ai("greedy_risk", seed=blue_seed, **params)
        else:
            raise ValueError(f"unsupported candidate player: {candidate_player!r}")
        dice_rng = random.Random(dice_seed)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=max_turns,
            starting_state=starting_state_for(layout_id),
        )
        if result.winner is candidate_player:
            wins += 1
        illegal += result.illegal_moves
        crashes += result.crashes
        timeouts += int(getattr(result, "timeouts", 0))
        step_times.extend(result.step_times_ms)

    return {
        "wins": wins,
        "games": games,
        "illegal_moves": illegal,
        "crashes": crashes,
        "timeouts": timeouts,
        "max_step_time_ms": max(step_times) if step_times else 0.0,
        "avg_step_time_ms": (sum(step_times) / len(step_times)) if step_times else 0.0,
        "total_step_time_ms": sum(step_times),
        "step_time_count": len(step_times),
    }


def _run_bilateral_candidate(
    params: dict[str, float],
    *,
    games_per_side: int,
    master_seed: int,
    layout_id: str,
    max_turns: int,
) -> dict:
    red_stats = _run_candidate(
        params,
        games=games_per_side,
        master_seed=master_seed,
        layout_id=layout_id,
        max_turns=max_turns,
        candidate_player=Player.RED,
    )
    blue_stats = _run_candidate(
        params,
        games=games_per_side,
        master_seed=master_seed + 50_000,
        layout_id=layout_id,
        max_turns=max_turns,
        candidate_player=Player.BLUE,
    )
    return _combine_stats([red_stats, blue_stats])


def promotion_gate_lines() -> list[str]:
    return [
        "候选晋升判断由 `reports/ai_promotion_decision.md` 单独决定，并需通过：",
        "",
        "- candidate vs greedy_risk 双边合并胜率 >= 60%",
        "- Wilson 95% CI 下界 >= 52%",
        "- 每个方向至少 400 局，合并至少 800 局；若时间不足，最小可接受为双边各 200 局",
        "- illegal_moves = 0, crashes = 0, timeouts = 0",
        "- avg_step_time_ms < 1000, max_step_time_ms < 5000",
        "- 报告写入 reports/",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Random sweep over greedy_risk evaluator weights.")
    parser.add_argument("--sample-size", type=int, default=20, help="Random samples drawn from full grid")
    parser.add_argument("--games", type=int, default=100, help="Train games per candidate")
    parser.add_argument("--validation-games", type=int, default=200, help="Validation games per color orientation for top-K")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed (train); validation uses seed+10000")
    parser.add_argument("--top-k", type=int, default=5, help="Validate top-K train candidates")
    parser.add_argument(
        "--starting-layout",
        default=STARTING_LAYOUT_ID,
        help="Starting layout id",
    )
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default=str(ROOT / "reports" / "param_sweep.md"))
    args = parser.parse_args(argv)

    start = time.perf_counter()
    candidates = list(iter_param_grid(limit=args.sample_size, seed=args.seed))
    train_rows: list[tuple[dict, dict]] = []
    for params in candidates:
        stats = _run_candidate(
            params,
            games=args.games,
            master_seed=args.seed,
            layout_id=args.starting_layout,
            max_turns=args.max_turns,
        )
        train_rows.append((params, stats))
    train_rows.sort(key=lambda row: row[1]["wins"], reverse=True)
    top_rows = train_rows[: args.top_k]

    validation_rows: list[tuple[dict, dict]] = []
    for params, _ in top_rows:
        stats = _run_bilateral_candidate(
            params,
            games_per_side=args.validation_games,
            master_seed=args.seed + 10_000,
            layout_id=args.starting_layout,
            max_turns=args.max_turns,
        )
        validation_rows.append((params, stats))

    elapsed = time.perf_counter() - start

    lines: list[str] = []
    lines.append("# Param Sweep Report")
    lines.append("")
    lines.append(f"generated_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    lines.append(f"sample_size: {args.sample_size}")
    lines.append(f"games_per_train: {args.games}")
    lines.append(f"validation_games_per_side: {args.validation_games}")
    lines.append(f"seed_train: {args.seed} / seed_validation: {args.seed + 10_000}")
    lines.append(f"layout: {args.starting_layout}")
    lines.append(f"top_k: {args.top_k}")
    lines.append(f"wall_seconds: {elapsed:.2f}")
    lines.append("")
    lines.append("Baseline = `greedy_risk` 默认权重；candidate = `greedy_risk` 透传被采样权重。")
    lines.append("Train 胜率视角：red = candidate，用于低成本筛选。")
    lines.append("Validation 胜率视角：candidate 红/蓝双边各跑 validation_games_per_side 局后合并。")
    lines.append("")
    lines.append("## Train pass (top to bottom)")
    lines.append("")
    for params, stats in train_rows:
        lines.append(summarize_candidate(
            params=params,
            wins=stats["wins"],
            games=stats["games"],
            illegal_moves=stats["illegal_moves"],
            crashes=stats["crashes"],
            timeouts=stats["timeouts"],
            max_step_time_ms=stats["max_step_time_ms"],
        ))
    lines.append("")
    lines.append(f"## Validation (top {len(validation_rows)}, bilateral)")
    lines.append("")
    for params, stats in validation_rows:
        lines.append(summarize_candidate(
            params=params,
            wins=stats["wins"],
            games=stats["games"],
            illegal_moves=stats["illegal_moves"],
            crashes=stats["crashes"],
            timeouts=stats["timeouts"],
            max_step_time_ms=stats["max_step_time_ms"],
        ))
    lines.append("")
    lines.append("## Promotion gate")
    lines.append("")
    lines.extend(promotion_gate_lines())

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "report_path": args.output,
        "sample_size": args.sample_size,
        "games_per_train": args.games,
        "validation_games_per_side": args.validation_games,
        "top_candidates": [
            {"params": p, "stats": s} for p, s in validation_rows
        ],
        "wall_seconds": round(elapsed, 2),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
