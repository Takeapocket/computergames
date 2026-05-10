"""阶段 4.2 weight 选择的统计稳健性验证（n=1000）。

reports/4-2-failure-analysis.md 在 n=400 时报告 weight=3.0 是唯一跨过 55% 门槛的配置，
但跟次优 weight=2.0（54.75%）只差 1 局，远小于 n=400 的 ~2.5% 标准误。本脚本在 n=1000
下重跑同一 grid，看排名是否稳定。

输出：stdout markdown 表 + 各 weight 的合并胜率。
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.evaluator import EXPECTED_WIN_RISK_WEIGHT
from ai.greedy_ai import GreedyAI
from ai.match import default_starting_state, play_one_game
from core.types import Player


def run_direction(*, weight: float, candidate_is_red: bool, games: int, master_seed: int) -> int:
    """跑 ``games`` 局，返回 candidate（greedy_risk(weight)）的胜局数。"""
    candidate_wins = 0
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        candidate_seed = per_game_seed * 3 + (1 if candidate_is_red else 2)
        baseline_seed = per_game_seed * 3 + (2 if candidate_is_red else 1)
        dice_seed = per_game_seed * 3

        candidate = GreedyAI(
            rng=random.Random(candidate_seed),
            name=f"greedy_risk_w{weight}",
            expected_risk_weight=weight,
            expected_win_risk_weight=EXPECTED_WIN_RISK_WEIGHT,
        )
        baseline = GreedyAI(rng=random.Random(baseline_seed), name="greedy")

        red_ai = candidate if candidate_is_red else baseline
        blue_ai = baseline if candidate_is_red else candidate

        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=random.Random(dice_seed),
            max_turns=200,
            starting_state=default_starting_state(),
        )

        winner_is_red = result.winner is Player.RED
        candidate_won = (winner_is_red and candidate_is_red) or (
            not winner_is_red and not candidate_is_red and result.winner is Player.BLUE
        )
        if candidate_won:
            candidate_wins += 1

    return candidate_wins


def main() -> int:
    weights = [1.0, 2.0, 3.0, 5.0, 10.0]
    games_per_direction = 1000
    master_seed = 2026

    print("# 4.2 grid search 重跑（n=1000）")
    print()
    print(f"games_per_direction={games_per_direction}, master_seed={master_seed}")
    print()
    print("| Weight | 红 candidate 胜率 | 蓝 candidate 胜率 | 合并 |")
    print("|---|---:|---:|---:|")

    grid_start = time.perf_counter()
    rows: list[tuple[float, int, int]] = []

    for weight in weights:
        t0 = time.perf_counter()
        red_wins = run_direction(
            weight=weight, candidate_is_red=True, games=games_per_direction, master_seed=master_seed
        )
        blue_wins = run_direction(
            weight=weight,
            candidate_is_red=False,
            games=games_per_direction,
            master_seed=master_seed,
        )
        elapsed = time.perf_counter() - t0
        rows.append((weight, red_wins, blue_wins))

        red_rate = red_wins / games_per_direction
        blue_rate = blue_wins / games_per_direction
        combined_rate = (red_wins + blue_wins) / (2 * games_per_direction)
        print(
            f"| {weight} | {red_rate:.3%} ({red_wins}/{games_per_direction}) | "
            f"{blue_rate:.3%} ({blue_wins}/{games_per_direction}) | "
            f"{combined_rate:.3%} ({red_wins + blue_wins}/{2*games_per_direction}) |  "
            f"<!-- {elapsed:.1f}s -->",
            flush=True,
        )

    print()
    print(f"<!-- 总耗时 {time.perf_counter() - grid_start:.1f}s -->")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
