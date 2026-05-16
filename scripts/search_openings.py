"""出发区 720 种布局枚举/采样 + release default rollout 实验 harness。

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
STYLE_ORDER = ("aggressive", "balanced", "defensive")


def load_release_default_ai_config(
    path: str | Path = ROOT / "release" / "v1.0" / "default_params.json",
) -> tuple[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout' for P5 opening baselines")
    metadata_keys = {"ai", "fallback_ai", "promotion_report"}
    return "rollout", {key: value for key, value in data.items() if key not in metadata_keys}


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


def classify_layout_style(red: dict[int, Position]) -> str:
    low_ids = (1, 2, 3)
    high_ids = (4, 5, 6)

    def avg_distance(piece_ids: tuple[int, ...]) -> float:
        return sum((4 - red[piece_id].row) + (4 - red[piece_id].col) for piece_id in piece_ids) / len(piece_ids)

    low_distance = avg_distance(low_ids)
    high_distance = avg_distance(high_ids)
    delta = low_distance - high_distance
    if delta <= -1.0:
        return "aggressive"
    if delta >= 1.0:
        return "defensive"
    return "balanced"


def generate_stratified_layouts(*, per_style: int, seed: int | None = None) -> Iterable[tuple[str, dict[int, Position]]]:
    if per_style < 1:
        raise ValueError("per_style must be >= 1")

    grouped: dict[str, list[dict[int, Position]]] = {style: [] for style in STYLE_ORDER}
    for layout in _all_permutation_layouts():
        grouped[classify_layout_style(layout)].append(layout)

    if seed is not None:
        rng = random.Random(seed)
        for layouts in grouped.values():
            rng.shuffle(layouts)

    rows: list[tuple[str, dict[int, Position]]] = []
    for style in STYLE_ORDER:
        rows.extend((style, layout) for layout in grouped[style][:per_style])
    return iter(rows)


def parse_seed_pool(raw: str) -> list[int]:
    seeds: list[int] = []
    seen: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        seed = int(token)
        if seed not in seen:
            seeds.append(seed)
            seen.add(seed)
    if not seeds:
        raise ValueError("seed pool must contain at least one seed")
    return seeds


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
    ai_kind: str | None = None,
    ai_kwargs: dict | None = None,
) -> dict:
    if ai_kind is None or ai_kwargs is None:
        default_kind, default_kwargs = load_release_default_ai_config()
        ai_kind = default_kind if ai_kind is None else ai_kind
        ai_kwargs = default_kwargs if ai_kwargs is None else ai_kwargs

    wins = 0
    illegal = 0
    crashes = 0
    timeouts = 0
    step_times: list[float] = []
    for i in range(games):
        per_game_seed = master_seed * 100_000 + i
        red_ai = build_ai(ai_kind, seed=per_game_seed * 3 + 1, **ai_kwargs)
        blue_ai = build_ai(ai_kind, seed=per_game_seed * 3 + 2, **ai_kwargs)
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
        timeouts += result.timeouts
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


def _run_against_opponents(
    *,
    candidate_red: dict[int, Position],
    opponents: dict[str, dict[int, Position]],
    games_per_opponent: int,
    master_seed: int,
    max_turns: int,
    ai_kind: str | None = None,
    ai_kwargs: dict | None = None,
) -> dict:
    stats_list = []
    for index, blue_layout in enumerate(opponents.values()):
        stats_list.append(_run_candidate(
            candidate_red=candidate_red,
            opponent_blue=blue_layout,
            games=games_per_opponent,
            master_seed=master_seed + index * 10_000,
            max_turns=max_turns,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
        ))
    return _combine_stats(stats_list)


def _run_against_seed_pool(
    *,
    candidate_red: dict[int, Position],
    opponents: dict[str, dict[int, Position]],
    games_per_opponent: int,
    seed_pool: list[int],
    max_turns: int,
    ai_kind: str | None = None,
    ai_kwargs: dict | None = None,
) -> dict:
    stats_list = [
        _run_against_opponents(
            candidate_red=candidate_red,
            opponents=opponents,
            games_per_opponent=games_per_opponent,
            master_seed=seed,
            max_turns=max_turns,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
        )
        for seed in seed_pool
    ]
    stats = _combine_stats(stats_list)
    stats["seed_count"] = len(seed_pool)
    stats["seeds"] = list(seed_pool)
    return stats


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


def promotion_gate_lines() -> list[str]:
    return [
        "候选布局晋升需通过：",
        "",
        "- candidate layout vs current default layout 双边合并胜率 >= 55%",
        "- Wilson 95% CI 下界 >= 50%",
        "- 至少 3 个不同 seed 池复验",
        "- illegal_moves = 0, crashes = 0, timeouts = 0",
        "- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局",
        "- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search 720 red-zone permutations for promising opening candidates.")
    parser.add_argument("--sample-size", type=int, default=100, help="Random sample from 720 permutations")
    parser.add_argument("--games", type=int, default=50, help="Train games per candidate per opponent")
    parser.add_argument("--validation-games", type=int, default=200, help="Validation games per candidate per opponent")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--seed-pool", default=None, help="Comma-separated seed pool; defaults to --seed.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default=str(ROOT / "reports" / "opening_report.md"))
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--candidate-mode", choices=("sample", "stratified"), default="sample")
    parser.add_argument("--per-style", type=int, default=3)
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)

    ai_kind, ai_kwargs = load_release_default_ai_config()
    seed_pool = parse_seed_pool(args.seed_pool) if args.seed_pool else [args.seed]
    validation_seed_pool = [seed + 10_000 for seed in seed_pool]
    blue_presets = _preset_blue_layouts()
    start = time.perf_counter()
    if args.candidate_mode == "stratified":
        candidates = list(generate_stratified_layouts(per_style=args.per_style, seed=args.seed))
    else:
        candidates = [
            (classify_layout_style(red_layout), red_layout)
            for red_layout in generate_side_layouts(limit=args.sample_size, seed=args.seed)
        ]
    train_rows: list[tuple[str, dict, dict]] = []
    for style, red_layout in candidates:
        opponents = _opponent_blue_layouts(red_layout, blue_presets)
        stats = _run_against_seed_pool(
            candidate_red=red_layout,
            opponents=opponents,
            games_per_opponent=args.games,
            seed_pool=seed_pool,
            max_turns=args.max_turns,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
        )
        train_rows.append((style, red_layout, stats))
    train_rows.sort(key=lambda row: row[2]["wins"] / row[2]["games"] if row[2]["games"] else 0.0, reverse=True)
    top_rows = train_rows[: args.top_k]

    validation_rows: list[tuple[str, dict, dict]] = []
    for style, red_layout, _ in top_rows:
        opponents = _opponent_blue_layouts(red_layout, blue_presets)
        stats = _run_against_seed_pool(
            candidate_red=red_layout,
            opponents=opponents,
            games_per_opponent=args.validation_games,
            seed_pool=validation_seed_pool,
            max_turns=args.max_turns,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
        )
        validation_rows.append((style, red_layout, stats))

    elapsed = time.perf_counter() - start
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines: list[str] = []
    lines.append("# Opening Search Report")
    lines.append("")
    lines.append(f"generated_at: {generated_at}")
    lines.append(f"sample_size: {args.sample_size}")
    lines.append(f"candidate_mode: {args.candidate_mode}")
    lines.append(f"per_style: {args.per_style}")
    lines.append(f"candidate_count: {len(candidates)}")
    lines.append(f"games_per_train_opponent: {args.games}")
    lines.append(f"validation_games_per_opponent: {args.validation_games}")
    lines.append(f"seed_pool_train: {seed_pool}")
    lines.append(f"seed_pool_validation: {validation_seed_pool}")
    lines.append(f"top_k: {args.top_k}")
    lines.append(f"ai_kind: {ai_kind}")
    lines.append("ai_kwargs_source: release/v1.0/default_params.json")
    lines.append(f"ai_kwargs: {json.dumps(ai_kwargs, ensure_ascii=False, sort_keys=True)}")
    lines.append(f"wall_seconds: {elapsed:.2f}")
    lines.append("")
    lines.append("Train: candidate red layout vs (mirror + balanced + aggressive + defensive) 蓝方布局，双方 AI 均为当前 release 默认 rollout 显式 kwargs。")
    lines.append("Validation: 使用同一 4 对手集合，以 validation_games_per_opponent 做更大样本确认。")
    lines.append("注意：本脚本仍是红方布局筛选；默认布局晋升还需按门禁补红蓝两侧覆盖。")
    lines.append("candidate_mode=stratified 时按 aggressive/balanced/defensive 分层采样；seed_pool 只用于复现实验组织，不代表晋升样本。")
    lines.append("结论：这是 opening-search sample gate，样本不足以晋升布局，GUI/release 默认布局不变。")
    lines.append("")
    lines.append("## Train pass (top to bottom)")
    lines.append("")
    for style, red_layout, stats in train_rows:
        rate = 100.0 * stats["wins"] / stats["games"] if stats["games"] else 0.0
        lines.append(
            f"- {rate:.1f}% (wins={stats['wins']}/{stats['games']}) "
            f"style={style} seeds={stats['seed_count']} "
            f"illegal={stats['illegal_moves']} crashes={stats['crashes']} "
            f"timeouts={stats['timeouts']} max_step_ms={stats['max_step_time_ms']:.1f} "
            f"| red={_layout_label(red_layout)}"
        )
    lines.append("")
    lines.append(f"## Validation (top {len(validation_rows)} vs same 4 opponents)")
    lines.append("")
    for style, red_layout, stats in validation_rows:
        rate = 100.0 * stats["wins"] / stats["games"] if stats["games"] else 0.0
        lines.append(
            f"- {rate:.1f}% (wins={stats['wins']}/{stats['games']}) "
            f"style={style} seeds={stats['seed_count']} "
            f"illegal={stats['illegal_moves']} crashes={stats['crashes']} "
            f"timeouts={stats['timeouts']} max_step_ms={stats['max_step_time_ms']:.1f} "
            f"| red={_layout_label(red_layout)}"
        )
    lines.append("")
    lines.append("## Promotion gate")
    lines.append("")
    lines.extend(promotion_gate_lines())

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "report_path": args.output,
        "generated_at": generated_at,
        "argv": raw_argv,
        "seed": args.seed,
        "sample_size": args.sample_size,
        "candidate_mode": args.candidate_mode,
        "per_style": args.per_style,
        "candidate_count": len(candidates),
        "games": args.games,
        "validation_games": args.validation_games,
        "games_per_train_opponent": args.games,
        "validation_games_per_opponent": args.validation_games,
        "top_k": args.top_k,
        "max_turns": args.max_turns,
        "seed_pool": seed_pool,
        "validation_seed_pool": validation_seed_pool,
        "ai_kind": ai_kind,
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "ai_kwargs": ai_kwargs,
        "train_rows": [
            {
                "style": style,
                "red_layout": {str(pid): [pos.row, pos.col] for pid, pos in sorted(layout.items())},
                "stats": stats,
            }
            for style, layout, stats in train_rows
        ],
        "validation_top": [
            {
                "style": style,
                "red_layout": {str(pid): [pos.row, pos.col] for pid, pos in sorted(layout.items())},
                "stats": stats,
            }
            for style, layout, stats in validation_rows
        ],
        "decision": {
            "promote_layout": False,
            "reason": "This opening-search sample gate is intentionally too small for layout promotion.",
        },
        "wall_seconds": round(elapsed, 2),
    }
    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
