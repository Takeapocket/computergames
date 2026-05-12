"""出发区 720 种布局枚举/采样 + greedy_risk 实验 harness。

只调用 GameState / ai.match.play_one_game，不复制规则。不直接改 GUI 默认布局；
候选晋升由 reports/opening_report.md 单独决定。
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

from ai.match import build_ai, play_one_game
from ai.opening_layouts import PRESETS
from core.game_state import GameState
from core.types import Player, Position


RED_HOME: list[Position] = [
    Position(0, 0),
    Position(0, 1),
    Position(0, 2),
    Position(1, 0),
    Position(1, 1),
    Position(2, 0),
]


def _all_permutation_layouts() -> list[dict[int, Position]]:
    layouts: list[dict[int, Position]] = []
    for perm in itertools.permutations(RED_HOME, 6):
        layouts.append({pid: pos for pid, pos in zip(range(1, 7), perm)})
    return layouts


def generate_side_layouts(*, limit: int | None = None, seed: int | None = None) -> Iterable[dict[int, Position]]:
    """从 720 种红方布局中采样 ``limit`` 个；seed 固定时结果稳定。"""
    layouts = _all_permutation_layouts()
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(layouts)
    if limit is not None:
        layouts = layouts[:limit]
    return iter(layouts)


def mirror_layout_for_blue(red: dict[int, Position]) -> dict[int, Position]:
    """中心对称镜像：(r, c) -> (4-r, 4-c)，保留 piece id。"""
    return {int(pid): Position(4 - pos.row, 4 - pos.col) for pid, pos in red.items()}


def _build_state(red: dict[int, Position], blue: dict[int, Position]) -> GameState:
    return GameState.from_layout(red=red, blue=blue, current_player=Player.RED)


def _run_candidate(
    *,
    candidate_red: dict[int, Position],
    opponent_blue: dict[int, Position],
    games: int,
    master_seed: int,
    max_turns: int,
) -> dict:
    wins = 0
    illegal = 0
    crashes = 0
    step_times: list[float] = []
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        red_ai = build_ai("greedy_risk", seed=per_game_seed * 3 + 1)
        blue_ai = build_ai("greedy_risk", seed=per_game_seed * 3 + 2)
        dice_rng = random.Random(per_game_seed * 3)
        state = _build_state(candidate_red, opponent_blue)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=max_turns,
            starting_state=state,
        )
        if result.winner is Player.RED:
            wins += 1
        illegal += result.illegal_moves
        crashes += result.crashes
        step_times.extend(result.step_times_ms)
    return {
        "wins": wins,
        "games": games,
        "illegal_moves": illegal,
        "crashes": crashes,
        "max_step_time_ms": max(step_times) if step_times else 0.0,
        "avg_step_time_ms": (sum(step_times) / len(step_times)) if step_times else 0.0,
        "total_step_time_ms": sum(step_times),
        "step_time_count": len(step_times),
    }


def _combine_stats(stats_list: list[dict]) -> dict:
    games = sum(stats["games"] for stats in stats_list)
    step_count = sum(stats.get("step_time_count", 0) for stats in stats_list)
    total_step_time = sum(stats.get("total_step_time_ms", 0.0) for stats in stats_list)
    return {
        "wins": sum(stats["wins"] for stats in stats_list),
        "games": games,
        "illegal_moves": sum(stats["illegal_moves"] for stats in stats_list),
        "crashes": sum(stats["crashes"] for stats in stats_list),
        "max_step_time_ms": max((stats["max_step_time_ms"] for stats in stats_list), default=0.0),
        "avg_step_time_ms": (total_step_time / step_count) if step_count else 0.0,
        "total_step_time_ms": total_step_time,
        "step_time_count": step_count,
    }


def _run_against_opponents(
    *,
    candidate_red: dict[int, Position],
    opponents: dict[str, dict[int, Position]],
    games_per_opponent: int,
    master_seed: int,
    max_turns: int,
) -> dict:
    stats_list = []
    for index, blue_layout in enumerate(opponents.values()):
        stats_list.append(_run_candidate(
            candidate_red=candidate_red,
            opponent_blue=blue_layout,
            games=games_per_opponent,
            master_seed=master_seed + index * 10_000,
            max_turns=max_turns,
        ))
    return _combine_stats(stats_list)


def _layout_label(red: dict[int, Position]) -> str:
    return "/".join(f"{pid}:{red[pid].row}{red[pid].col}" for pid in sorted(red))


def _preset_blue_layouts() -> dict[str, dict[int, Position]]:
    out: dict[str, dict[int, Position]] = {}
    for preset_id in ("balanced_v1", "aggressive_v1", "defensive_v1"):
        layout = PRESETS[preset_id].blue
        out[preset_id] = {int(pid): pos for pid, pos in layout.items()}
    return out


def _opponent_blue_layouts(
    red_layout: dict[int, Position],
    blue_presets: dict[str, dict[int, Position]],
) -> dict[str, dict[int, Position]]:
    return {"mirror": mirror_layout_for_blue(red_layout), **blue_presets}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search 720 red-zone permutations for promising opening candidates.")
    parser.add_argument("--sample-size", type=int, default=100, help="Random sample from 720 permutations")
    parser.add_argument("--games", type=int, default=50, help="Train games per candidate per opponent")
    parser.add_argument("--validation-games", type=int, default=200, help="Validation games per candidate per opponent")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default=str(ROOT / "reports" / "opening_report.md"))
    args = parser.parse_args(argv)

    blue_presets = _preset_blue_layouts()
    start = time.perf_counter()
    candidates = list(generate_side_layouts(limit=args.sample_size, seed=args.seed))
    train_rows: list[tuple[dict, dict]] = []
    for red_layout in candidates:
        opponents = _opponent_blue_layouts(red_layout, blue_presets)
        stats = _run_against_opponents(
            candidate_red=red_layout,
            opponents=opponents,
            games_per_opponent=args.games,
            master_seed=args.seed,
            max_turns=args.max_turns,
        )
        train_rows.append((red_layout, stats))
    train_rows.sort(key=lambda row: row[1]["wins"], reverse=True)
    top_rows = train_rows[: args.top_k]

    validation_rows: list[tuple[dict, dict]] = []
    for red_layout, _ in top_rows:
        opponents = _opponent_blue_layouts(red_layout, blue_presets)
        stats = _run_against_opponents(
            candidate_red=red_layout,
            opponents=opponents,
            games_per_opponent=args.validation_games,
            master_seed=args.seed + 10_000,
            max_turns=args.max_turns,
        )
        validation_rows.append((red_layout, stats))

    elapsed = time.perf_counter() - start

    lines: list[str] = []
    lines.append("# Opening Search Report")
    lines.append("")
    lines.append(f"generated_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    lines.append(f"sample_size: {args.sample_size}")
    lines.append(f"games_per_train_opponent: {args.games}")
    lines.append(f"validation_games_per_opponent: {args.validation_games}")
    lines.append(f"seed_train: {args.seed} / seed_validation: {args.seed + 10_000}")
    lines.append(f"top_k: {args.top_k}")
    lines.append(f"wall_seconds: {elapsed:.2f}")
    lines.append("")
    lines.append("Train: candidate(red, greedy_risk) vs (mirror + balanced + aggressive + defensive) 蓝方布局，双方 AI 均为 greedy_risk。")
    lines.append("Validation: 使用同一 4 对手集合，以 validation_games_per_opponent 做更大样本确认。")
    lines.append("注意：本脚本仍是红方布局筛选；默认布局晋升还需按门禁补红蓝两侧覆盖。")
    lines.append("")
    lines.append("## Train pass (top to bottom)")
    lines.append("")
    for red_layout, stats in train_rows:
        rate = 100.0 * stats["wins"] / stats["games"] if stats["games"] else 0.0
        lines.append(
            f"- {rate:.1f}% (wins={stats['wins']}/{stats['games']}) "
            f"max_step_ms={stats['max_step_time_ms']:.1f} "
            f"| red={_layout_label(red_layout)}"
        )
    lines.append("")
    lines.append(f"## Validation (top {len(validation_rows)} vs same 4 opponents)")
    lines.append("")
    for red_layout, stats in validation_rows:
        rate = 100.0 * stats["wins"] / stats["games"] if stats["games"] else 0.0
        lines.append(
            f"- {rate:.1f}% (wins={stats['wins']}/{stats['games']}) "
            f"illegal={stats['illegal_moves']} crashes={stats['crashes']} "
            f"max_step_ms={stats['max_step_time_ms']:.1f} "
            f"| red={_layout_label(red_layout)}"
        )
    lines.append("")
    lines.append("## Promotion gate")
    lines.append("")
    lines.append("候选布局晋升需通过：")
    lines.append("")
    lines.append("- candidate vs current default 至少 400 总局，红蓝两侧覆盖")
    lines.append("- 合并胜率 > 53%")
    lines.append("- Wilson 95% CI 下界 >= 50%")
    lines.append("- illegal_moves = 0, crashes = 0, timeouts = 0")
    lines.append("- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "report_path": args.output,
        "sample_size": args.sample_size,
        "validation_top": [
            {
                "red_layout": {str(pid): [pos.row, pos.col] for pid, pos in sorted(layout.items())},
                "stats": stats,
            }
            for layout, stats in validation_rows
        ],
        "wall_seconds": round(elapsed, 2),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
