"""Pairwise AI tournament harness.

为多个 AI 跑双边对战矩阵；每个有序对 (red_ai, blue_ai) 跑 N 局，
合并双边得到 candidate 的两侧胜率，写入 markdown 报告。

不复制 core 规则逻辑，只调用 ai/match.build_ai/play_one_game/starting_state_for。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import (
    LAYOUTS,
    STARTING_LAYOUT_ID,
    build_ai,
    play_one_game,
    starting_state_for,
)
from core.types import Player


def parse_ai_list(text: str) -> list[str]:
    """把 "random, greedy,greedy_risk" 解析为 list，剔除空白；空条目报错。"""
    parts = [p.strip() for p in text.split(",")]
    if any(not p for p in parts):
        raise ValueError(f"empty entry in AI list: {text!r}")
    return parts


def format_markdown_matrix(ais: list[str], matrix: dict[str, dict[str, float]]) -> str:
    """生成 markdown 表格：行 = red AI；列 = blue AI；值 = red 视角胜率（百分比）。"""
    header = "| AI | " + " | ".join(ais) + " |"
    sep = "|---|" + "".join("---:|" for _ in ais)
    lines = [header, sep]
    for row_ai in ais:
        cells: list[str] = []
        for col_ai in ais:
            if row_ai == col_ai:
                cells.append("-")
                continue
            rate = matrix.get(row_ai, {}).get(col_ai)
            cells.append("-" if rate is None else f"{rate:.1f}%")
        lines.append("| " + row_ai + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _run_pair(
    red_kind: str,
    blue_kind: str,
    games: int,
    master_seed: int,
    layout_id: str,
    max_turns: int,
) -> dict:
    starting_layout_factory = starting_state_for  # alias for clarity
    red_wins = 0
    blue_wins = 0
    draws = 0
    illegal = 0
    crashes = 0
    step_times: list[float] = []

    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        red_seed = per_game_seed * 3 + 1
        blue_seed = per_game_seed * 3 + 2
        dice_seed = per_game_seed * 3

        red_ai = build_ai(red_kind, seed=red_seed)
        blue_ai = build_ai(blue_kind, seed=blue_seed)
        dice_rng = random.Random(dice_seed)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=max_turns,
            starting_state=starting_layout_factory(layout_id),
        )
        if result.winner is Player.RED:
            red_wins += 1
        elif result.winner is Player.BLUE:
            blue_wins += 1
        else:
            draws += 1
        illegal += result.illegal_moves
        crashes += result.crashes
        step_times.extend(result.step_times_ms)

    avg_step = sum(step_times) / len(step_times) if step_times else 0.0
    max_step = max(step_times) if step_times else 0.0
    return {
        "games": games,
        "red_wins": red_wins,
        "blue_wins": blue_wins,
        "draws": draws,
        "illegal_moves": illegal,
        "crashes": crashes,
        "average_step_time_ms": avg_step,
        "max_step_time_ms": max_step,
    }


def run_tournament(
    ais: list[str],
    *,
    games_per_orientation: int,
    seed: int,
    layout_id: str,
    max_turns: int,
) -> tuple[dict[str, dict[str, float]], dict]:
    """跑所有有序对 (i, j) i != j。返回胜率矩阵 + 全局 metadata（含异常计数）。"""
    matrix: dict[str, dict[str, float]] = {ai: {} for ai in ais}
    pair_stats: list[dict] = []
    total_illegal = 0
    total_crashes = 0

    for red in ais:
        for blue in ais:
            if red == blue:
                continue
            stats = _run_pair(
                red_kind=red,
                blue_kind=blue,
                games=games_per_orientation,
                master_seed=seed,
                layout_id=layout_id,
                max_turns=max_turns,
            )
            matrix[red][blue] = 100.0 * stats["red_wins"] / stats["games"] if stats["games"] else 0.0
            pair_stats.append({
                "red": red,
                "blue": blue,
                **stats,
            })
            total_illegal += stats["illegal_moves"]
            total_crashes += stats["crashes"]

    metadata = {
        "ais": ais,
        "games_per_orientation": games_per_orientation,
        "seed": seed,
        "layout_id": layout_id,
        "max_turns": max_turns,
        "illegal_moves_total": total_illegal,
        "crashes_total": total_crashes,
        "pairs": pair_stats,
    }
    return matrix, metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a pairwise AI tournament and write a markdown matrix.")
    parser.add_argument("--ais", required=True, help="Comma-separated AI kinds, e.g. random,greedy,greedy_risk")
    parser.add_argument("--games", type=int, default=100, help="Games per ordered pair")
    parser.add_argument("--seed", type=int, default=2026, help="Master seed")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument(
        "--starting-layout",
        default=STARTING_LAYOUT_ID,
        choices=sorted(LAYOUTS),
    )
    parser.add_argument("--report", default=str(ROOT / "reports" / "tournament_matrix.md"))
    args = parser.parse_args(argv)

    ais = parse_ai_list(args.ais)
    start = time.perf_counter()
    matrix, metadata = run_tournament(
        ais,
        games_per_orientation=args.games,
        seed=args.seed,
        layout_id=args.starting_layout,
        max_turns=args.max_turns,
    )
    elapsed = time.perf_counter() - start
    metadata["wall_seconds"] = round(elapsed, 3)
    metadata["generated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    body = format_markdown_matrix(ais, matrix)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "# AI Tournament Matrix\n\n"
        f"generated_at: {metadata['generated_at']}\n"
        f"seed: {args.seed}\n"
        f"games_per_orientation: {args.games}\n"
        f"layout: {args.starting_layout}\n"
        f"wall_seconds: {metadata['wall_seconds']}\n"
        f"illegal_moves_total: {metadata['illegal_moves_total']}\n"
        f"crashes_total: {metadata['crashes_total']}\n\n"
        f"行 = Red 方 AI；列 = Blue 方 AI；值 = Red 视角胜率（按对应有序对 `--games` 局）。\n\n"
        f"{body}\n\n"
        "## Per-pair metadata\n\n"
        "```json\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    report_path.write_text(text, encoding="utf-8")

    print(json.dumps({"report_path": str(report_path), **{k: v for k, v in metadata.items() if k != "pairs"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
