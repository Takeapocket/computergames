"""Compare one searched opening candidate against the current default layout.

This is a P5 promotion pre-check helper. It does not modify presets or GUI
defaults; it only runs both-side games and writes a report.
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

from ai.match import build_ai, play_one_game
from ai.opening_layouts import PRESETS
from core.game_state import GameState
from core.types import Player, Position
from scripts.quick_bench import wilson_ci
from scripts.search_openings import (
    _combine_stats,
    _layout_label,
    load_release_default_ai_config,
    mirror_layout_for_blue,
    parse_seed_pool,
    promotion_gate_lines,
)

DEFAULT_DECISION_REASON = "This layout duel is a pre-check; promotion still requires the full layout gate."
LAYOUT_SIGNAL_THRESHOLD = 0.55


@dataclass(frozen=True)
class CandidateLayout:
    style: str
    red_layout: dict[int, Position]
    source_report: str
    source_section: str
    source_index: int


def load_candidate_layout(
    report_path: str | Path,
    *,
    section: str = "validation_top",
    index: int = 0,
) -> CandidateLayout:
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    rows = payload[section]
    row = rows[index]
    return CandidateLayout(
        style=str(row.get("style", "unknown")),
        red_layout=_parse_layout(row["red_layout"]),
        source_report=str(report_path),
        source_section=section,
        source_index=index,
    )


def _parse_layout(raw: dict[str, list[int]]) -> dict[int, Position]:
    return {int(piece_id): Position(int(pos[0]), int(pos[1])) for piece_id, pos in raw.items()}


def _run_direction(
    *,
    red_layout: dict[int, Position],
    blue_layout: dict[int, Position],
    candidate_player: Player,
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
        state = GameState.from_layout(red=red_layout, blue=blue_layout, current_player=Player.RED)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=max_turns,
            starting_state=state,
        )
        if result.winner is candidate_player:
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


def _run_candidate_vs_baseline(
    *,
    candidate_red: dict[int, Position],
    baseline_red: dict[int, Position],
    baseline_blue: dict[int, Position],
    games_per_side: int,
    seed_pool: list[int],
    max_turns: int,
    ai_kind: str | None = None,
    ai_kwargs: dict | None = None,
) -> dict:
    red_role_stats = []
    blue_role_stats = []
    candidate_blue = mirror_layout_for_blue(candidate_red)
    for seed in seed_pool:
        red_role_stats.append(
            _run_direction(
                red_layout=candidate_red,
                blue_layout=baseline_blue,
                candidate_player=Player.RED,
                games=games_per_side,
                master_seed=seed,
                max_turns=max_turns,
                ai_kind=ai_kind,
                ai_kwargs=ai_kwargs,
            )
        )
        blue_role_stats.append(
            _run_direction(
                red_layout=baseline_red,
                blue_layout=candidate_blue,
                candidate_player=Player.BLUE,
                games=games_per_side,
                master_seed=seed + 50_000,
                max_turns=max_turns,
                ai_kind=ai_kind,
                ai_kwargs=ai_kwargs,
            )
        )

    candidate_as_red = _combine_stats(red_role_stats)
    candidate_as_blue = _combine_stats(blue_role_stats)
    combined = _combine_stats([candidate_as_red, candidate_as_blue])
    combined["candidate_as_red"] = candidate_as_red
    combined["candidate_as_blue"] = candidate_as_blue
    combined["seed_count"] = len(seed_pool)
    combined["seeds"] = list(seed_pool)
    return combined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare a searched opening candidate against the default layout.")
    parser.add_argument("--candidate-report", required=True)
    parser.add_argument("--candidate-section", default="validation_top")
    parser.add_argument("--candidate-index", type=int, default=0)
    parser.add_argument("--baseline-layout", default="balanced_v1")
    parser.add_argument("--games-per-side", type=int, default=20)
    parser.add_argument("--seed-pool", default="2026,2027,2028")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default=str(ROOT / "reports" / "opening_layout_duel.md"))
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--decision-reason", default=None)
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)

    ai_kind, ai_kwargs = load_release_default_ai_config()
    candidate = load_candidate_layout(
        args.candidate_report,
        section=args.candidate_section,
        index=args.candidate_index,
    )
    baseline = PRESETS[args.baseline_layout]
    seed_pool = parse_seed_pool(args.seed_pool)
    start = time.perf_counter()
    stats = _run_candidate_vs_baseline(
        candidate_red=candidate.red_layout,
        baseline_red={int(pid): pos for pid, pos in baseline.red.items()},
        baseline_blue={int(pid): pos for pid, pos in baseline.blue.items()},
        games_per_side=args.games_per_side,
        seed_pool=seed_pool,
        max_turns=args.max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    elapsed = time.perf_counter() - start
    ci_low, ci_high = wilson_ci(stats["wins"], stats["games"])
    win_rate = stats["wins"] / stats["games"] if stats["games"] else 0.0
    decision_reason = args.decision_reason or _decision_reason(stats=stats, win_rate=win_rate, ci=(ci_low, ci_high))
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines = _format_markdown_report(
        generated_at=generated_at,
        argv=raw_argv,
        candidate=candidate,
        baseline_layout_id=args.baseline_layout,
        games_per_side=args.games_per_side,
        seed_pool=seed_pool,
        max_turns=args.max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
        stats=stats,
        win_rate=win_rate,
        ci=(ci_low, ci_high),
        decision_reason=decision_reason,
        wall_seconds=elapsed,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "report_path": args.output,
        "generated_at": generated_at,
        "argv": raw_argv,
        "candidate": {
            "source_report": candidate.source_report,
            "source_section": candidate.source_section,
            "source_index": candidate.source_index,
            "style": candidate.style,
            "red_layout": _layout_to_json(candidate.red_layout),
            "blue_layout": _layout_to_json(mirror_layout_for_blue(candidate.red_layout)),
        },
        "baseline_layout_id": args.baseline_layout,
        "games_per_side": args.games_per_side,
        "seed_pool": seed_pool,
        "max_turns": args.max_turns,
        "ai_kind": ai_kind,
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "ai_kwargs": ai_kwargs,
        "stats": stats,
        "candidate_win_rate": win_rate,
        "candidate_win_ci95": [ci_low, ci_high],
        "decision": {
            "promote_layout": False,
            "reason": decision_reason,
        },
        "wall_seconds": round(elapsed, 2),
    }
    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _format_markdown_report(
    *,
    generated_at: str,
    argv: list[str],
    candidate: CandidateLayout,
    baseline_layout_id: str,
    games_per_side: int,
    seed_pool: list[int],
    max_turns: int,
    ai_kind: str,
    ai_kwargs: dict,
    stats: dict,
    win_rate: float,
    ci: tuple[float, float],
    decision_reason: str,
    wall_seconds: float,
) -> list[str]:
    red_stats = stats["candidate_as_red"]
    blue_stats = stats["candidate_as_blue"]
    lines = [
        "# Opening Layout Duel Report",
        "",
        f"generated_at: {generated_at}",
        f"argv: {json.dumps(argv, ensure_ascii=False)}",
        f"candidate_source: {candidate.source_report}::{candidate.source_section}[{candidate.source_index}]",
        f"candidate_style: {candidate.style}",
        f"baseline_layout_id: {baseline_layout_id}",
        f"games_per_side_per_seed: {games_per_side}",
        f"seed_pool: {seed_pool}",
        f"max_turns: {max_turns}",
        f"ai_kind: {ai_kind}",
        "ai_kwargs_source: release/v1.0/default_params.json",
        f"ai_kwargs: {json.dumps(ai_kwargs, ensure_ascii=False, sort_keys=True)}",
        f"wall_seconds: {wall_seconds:.2f}",
        "",
        "Candidate layout vs current default layout, with both red and blue roles covered.",
        "This layout duel is a pre-check, not a promotion gate. GUI/release defaults remain unchanged.",
        "",
        "## Candidate",
        "",
        f"- red={_layout_label(candidate.red_layout)}",
        f"- blue={_layout_label(mirror_layout_for_blue(candidate.red_layout))}",
        "",
        "## Results",
        "",
        (
            f"- combined: {100.0 * win_rate:.1f}% "
            f"(wins={stats['wins']}/{stats['games']}), "
            f"CI95=[{100.0 * ci[0]:.1f}%, {100.0 * ci[1]:.1f}%], "
            f"illegal={stats['illegal_moves']}, crashes={stats['crashes']}, "
            f"timeouts={stats['timeouts']}, max_step_ms={stats['max_step_time_ms']:.1f}"
        ),
        (
            f"- candidate as red: {100.0 * red_stats['wins'] / red_stats['games']:.1f}% "
            f"(wins={red_stats['wins']}/{red_stats['games']}), "
            f"illegal={red_stats['illegal_moves']}, crashes={red_stats['crashes']}, "
            f"timeouts={red_stats['timeouts']}, max_step_ms={red_stats['max_step_time_ms']:.1f}"
        ),
        (
            f"- candidate as blue: {100.0 * blue_stats['wins'] / blue_stats['games']:.1f}% "
            f"(wins={blue_stats['wins']}/{blue_stats['games']}), "
            f"illegal={blue_stats['illegal_moves']}, crashes={blue_stats['crashes']}, "
            f"timeouts={blue_stats['timeouts']}, max_step_ms={blue_stats['max_step_time_ms']:.1f}"
        ),
        "",
        "## Decision",
        "",
        "Do not promote layout from this report.",
        f"Reason: {decision_reason}",
        "",
        "Full promotion still requires:",
        "",
    ]
    lines.extend(promotion_gate_lines())
    return lines


def _layout_to_json(layout: dict[int, Position]) -> dict[str, list[int]]:
    return {str(pid): [pos.row, pos.col] for pid, pos in sorted(layout.items())}


def _decision_reason(*, stats: dict, win_rate: float, ci: tuple[float, float]) -> str:
    if stats["illegal_moves"] or stats["crashes"] or stats["timeouts"]:
        return (
            "Layout duel failed stability guard: "
            f"illegal={stats['illegal_moves']}, crashes={stats['crashes']}, "
            f"timeouts={stats['timeouts']}; defaults unchanged."
        )
    if stats["games"] >= 60 and ci[1] < LAYOUT_SIGNAL_THRESHOLD:
        return (
            f"{stats['games']}-game expansion failed: candidate scored "
            f"{stats['wins']}/{stats['games']} ({100.0 * win_rate:.1f}%), "
            f"CI95 upper={100.0 * ci[1]:.1f}% < {100.0 * LAYOUT_SIGNAL_THRESHOLD:.1f}%; "
            "stop this candidate route; defaults unchanged."
        )
    return DEFAULT_DECISION_REASON


if __name__ == "__main__":
    raise SystemExit(main())
