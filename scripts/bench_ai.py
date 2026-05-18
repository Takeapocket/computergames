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
    STRONG_ROLLOUT_DEFAULTS,
    ai_version_signature,
    build_ai,
    play_one_game,
    starting_state_for,
)
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
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
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 200,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
        },
    },
    "rollout_32": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
        },
    },
    "rollout_risk_playout": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
    },
    "rollout_cutoff_eval": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
    },
    "rollout_zweistein_cutoff": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 100,
            "candidate_kwargs": {"deadline_safety_ms": 30.0},
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
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
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "games_per_side": 400,
            "extra_gates": {"candidate_win_ci_lower": ("ge", 0.52)},
        },
    },
    "rollout_adaptive_close_sample": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 400,
        },
    },
    "rollout_strong_48": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_strong_64": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_strong_64_loweps": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_strong_96": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_root_racing": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_paired": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_common_random": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_self_capture_guard": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_material_guard": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_self_capture_guard_strict": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 25,
        },
    },
    "rollout_zweistein_dp_cutoff": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 400,
        },
    },
    "rollout_exact_opp1_zdp": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 400,
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
PAIRED_ROLLOUT_CANDIDATES = {"rollout_paired", "rollout_common_random"}
STRONG_ROLLOUT_CANDIDATES = set(STRONG_ROLLOUT_DEFAULTS)
SELF_CAPTURE_GUARD_CANDIDATES = {
    "rollout_self_capture_guard",
    "rollout_material_guard",
    "rollout_self_capture_guard_strict",
}


@dataclass(frozen=True)
class Side:
    label: str  # "candidate_red" / "candidate_blue"
    candidate_side: Player


def _make_ai(seed: int, *, kind: str, ai_kwargs: dict | None):
    return build_ai(kind, seed=seed, **(ai_kwargs or {}))


def _merge_profile_kwargs(
    profile: dict,
    explicit_kwargs: dict,
    *,
    key: str = "candidate_kwargs",
) -> dict:
    return {**profile.get(key, {}), **explicit_kwargs}


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


def _thinking_seconds_by_color(result) -> dict[Player, float]:
    totals = {Player.RED: 0.0, Player.BLUE: 0.0}
    record = getattr(result, "record", None)
    steps = list(getattr(record, "steps", []) or [])
    step_times = list(getattr(result, "step_times_ms", []) or [])
    for step, elapsed_ms in zip(steps, step_times):
        totals[Player.from_value(step.player)] += float(elapsed_ms) / 1000.0
    return totals


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
    red_thinking_seconds: list[float] = []
    blue_thinking_seconds: list[float] = []
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
        thinking = _thinking_seconds_by_color(r)
        red_thinking_seconds.append(thinking[Player.RED])
        blue_thinking_seconds.append(thinking[Player.BLUE])
        for k, v in t.items():
            telemetry.setdefault(k, []).append(v)
    total_step_time = sum(all_step_times)
    step_count = len(all_step_times)
    avg_step = total_step_time / step_count if step_count else 0.0
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
        "total_step_time_ms": total_step_time,
        "step_count": step_count,
        "average_step_time_ms": avg_step,
        "p95_step_time_ms": p95_step,
        "p99_step_time_ms": p99_step,
        "max_step_time_ms": max_step,
        "max_red_thinking_seconds": max(red_thinking_seconds) if red_thinking_seconds else 0.0,
        "max_blue_thinking_seconds": max(blue_thinking_seconds) if blue_thinking_seconds else 0.0,
        "avg_red_thinking_seconds": (
            sum(red_thinking_seconds) / len(red_thinking_seconds)
            if red_thinking_seconds else 0.0
        ),
        "avg_blue_thinking_seconds": (
            sum(blue_thinking_seconds) / len(blue_thinking_seconds)
            if blue_thinking_seconds else 0.0
        ),
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
    average_turns = (
        red_summary.get("average_turns", 0.0) * red_games
        + blue_summary.get("average_turns", 0.0) * blue_games
    ) / games
    total_step_time = (
        red_summary.get("total_step_time_ms", 0.0)
        + blue_summary.get("total_step_time_ms", 0.0)
    )
    step_count = int(red_summary.get("step_count", 0)) + int(blue_summary.get("step_count", 0))
    avg_step = (
        total_step_time / step_count
        if step_count
        else (
            red_summary["average_step_time_ms"] * red_games
            + blue_summary["average_step_time_ms"] * blue_games
        ) / games
    )
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
        "average_turns": average_turns,
        "total_step_time_ms": total_step_time,
        "step_count": step_count,
        "average_step_time_ms": avg_step,
        "p95_step_time_ms": p95_step,
        "p99_step_time_ms": p99_step,
        "max_step_time_ms": max_step,
        "max_red_thinking_seconds": max(
            red_summary.get("max_red_thinking_seconds", 0.0),
            blue_summary.get("max_red_thinking_seconds", 0.0),
        ),
        "max_blue_thinking_seconds": max(
            red_summary.get("max_blue_thinking_seconds", 0.0),
            blue_summary.get("max_blue_thinking_seconds", 0.0),
        ),
        "avg_red_thinking_seconds": (
            red_summary.get("avg_red_thinking_seconds", 0.0) * red_games
            + blue_summary.get("avg_red_thinking_seconds", 0.0) * blue_games
        ) / games,
        "avg_blue_thinking_seconds": (
            red_summary.get("avg_blue_thinking_seconds", 0.0) * red_games
            + blue_summary.get("avg_blue_thinking_seconds", 0.0) * blue_games
        ) / games,
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


def _paired_rollout_decision(
    candidate_kind: str,
    stage: str,
    combined: dict,
    gates_ok: bool,
) -> dict | None:
    if candidate_kind not in PAIRED_ROLLOUT_CANDIDATES or stage != "candidate":
        return None
    win_rate = combined.get("candidate_win_rate", 0.0)
    stable = (
        combined.get("illegal_moves", 0) == 0
        and combined.get("crashes", 0) == 0
        and combined.get("timeouts", 0) == 0
    )
    if win_rate < 0.52:
        status = "stop"
        suggest_expansion = False
        recommendation = "不默认启用，不扩样。"
    elif win_rate < 0.55:
        status = "signal_insufficient"
        suggest_expansion = False
        recommendation = "有信号但不足；50+50 可选但不默认。"
    elif stable:
        status = "expand_50x2"
        suggest_expansion = True
        recommendation = "达到 55% 且稳定性为 0，可扩到 50+50；今晚不自动 promotion。"
    else:
        status = "blocked_by_stability"
        suggest_expansion = False
        recommendation = "胜率达到 55%，但稳定性门禁未清零；不扩样。"
    return {
        "candidate_gate_pass": gates_ok,
        "status": status,
        "candidate_win_rate": win_rate,
        "wilson_ci95": combined.get("candidate_win_ci95", [0.0, 0.0]),
        "illegal_moves": combined.get("illegal_moves", 0),
        "crashes": combined.get("crashes", 0),
        "timeouts": combined.get("timeouts", 0),
        "average_step_time_ms": combined.get("average_step_time_ms", 0.0),
        "max_step_time_ms": combined.get("max_step_time_ms", 0.0),
        "default_config_changed": False,
        "core_rules_changed": False,
        "suggest_expansion": suggest_expansion,
        "recommendation": recommendation,
    }


def _self_capture_guard_decision(
    candidate_kind: str,
    stage: str,
    combined: dict,
    gates_ok: bool,
) -> dict | None:
    if candidate_kind not in SELF_CAPTURE_GUARD_CANDIDATES or stage != "candidate":
        return None
    win_rate = combined.get("candidate_win_rate", 0.0)
    stable = (
        combined.get("illegal_moves", 0) == 0
        and combined.get("crashes", 0) == 0
        and combined.get("timeouts", 0) == 0
    )
    if win_rate < 0.52:
        status = "stop"
        suggest_expansion = False
        reason = f"candidate_win_rate {win_rate*100:.1f}% < 52%，按 P11 停止规则不扩样。"
    elif win_rate < 0.55:
        status = "signal_insufficient"
        suggest_expansion = False
        reason = f"candidate_win_rate {win_rate*100:.1f}% < 55%，不满足 candidate 门禁。"
    elif stable:
        status = "expand_50x2"
        suggest_expansion = True
        reason = "候选达到 55% 且稳定性为 0，可扩样复验；本轮不默认启用。"
    else:
        status = "blocked_by_stability"
        suggest_expansion = False
        reason = "候选胜率达到 55%，但 illegal/crash/timeout 未清零，不扩样。"
    return {
        "default_enabled": False,
        "summary": "不默认启用",
        "status": status,
        "candidate_gate_pass": gates_ok,
        "candidate_win_rate": win_rate,
        "wilson_ci95": combined.get("candidate_win_ci95", [0.0, 0.0]),
        "illegal_moves": combined.get("illegal_moves", 0),
        "crashes": combined.get("crashes", 0),
        "timeouts": combined.get("timeouts", 0),
        "average_step_time_ms": combined.get("average_step_time_ms", 0.0),
        "max_step_time_ms": combined.get("max_step_time_ms", 0.0),
        "default_config_changed": False,
        "core_rules_changed": False,
        "suggest_expansion": suggest_expansion,
        "reason": reason,
    }


def _strong_rollout_decision(
    candidate_kind: str,
    stage: str,
    combined: dict,
    gates_ok: bool,
) -> dict | None:
    if candidate_kind not in STRONG_ROLLOUT_CANDIDATES or stage != "candidate":
        return None
    win_rate = combined.get("candidate_win_rate", 0.0)
    ci_low, ci_high = combined.get("candidate_win_ci95", [0.0, 0.0])
    stable = (
        combined.get("illegal_moves", 0) == 0
        and combined.get("crashes", 0) == 0
        and combined.get("timeouts", 0) == 0
        and combined.get("max_step_time_ms", 0.0) <= 5000.0
    )
    max_side_thinking = max(
        combined.get("max_red_thinking_seconds", 0.0),
        combined.get("max_blue_thinking_seconds", 0.0),
    )
    timing_risk = max_side_thinking > 180.0
    games = int(combined.get("games", 0))
    passed_52 = win_rate >= 0.52
    passed_55 = win_rate >= 0.55
    passed_50x2 = (
        games >= 100
        and passed_55
        and ci_low >= 0.50
        and gates_ok
        and stable
        and not timing_risk
    )

    if not passed_52:
        status = "stop"
        suggest_expansion = False
        recommendation = "不默认启用，不扩样。"
    elif not passed_55:
        status = "signal_insufficient"
        suggest_expansion = False
        recommendation = "有信号但不足；最多只跑 50+50 复验，不默认启用。"
    elif not stable:
        status = "blocked_by_stability"
        suggest_expansion = False
        recommendation = "胜率达到 55%，但 illegal/crash/timeout/max step 门禁未清零，不扩样。"
    elif not gates_ok:
        status = "blocked_by_candidate_gate"
        suggest_expansion = False
        recommendation = "胜率达到 55%，但 candidate gate 未通过；不扩样，不默认启用。"
    elif timing_risk:
        status = "timing_risk"
        suggest_expansion = False
        recommendation = "胜率达到 55%，但单方思考时间存在 timing risk；不默认启用。"
    elif games >= 100 and ci_low < 0.50:
        status = "no_promotion_ci"
        suggest_expansion = False
        recommendation = "50+50 胜率达到 55%，但 Wilson lower < 50%；不 promotion。"
    elif games >= 100:
        status = "passed_50x2_gate"
        suggest_expansion = False
        recommendation = "50+50 过门槛；仅建议明天继续 100+100，不默认启用，等用户确认。"
    else:
        status = "expand_50x2"
        suggest_expansion = True
        recommendation = "通过 55% 初筛；建议扩到 50+50，不默认启用。"

    return {
        "candidate_gate_pass": gates_ok,
        "status": status,
        "candidate_win_rate": win_rate,
        "wilson_ci95": [ci_low, ci_high],
        "passed_52_gate": passed_52,
        "passed_55_gate": passed_55,
        "passed_50x2_gate": passed_50x2,
        "illegal_moves": combined.get("illegal_moves", 0),
        "crashes": combined.get("crashes", 0),
        "timeouts": combined.get("timeouts", 0),
        "average_step_time_ms": combined.get("average_step_time_ms", 0.0),
        "p95_step_time_ms": combined.get("p95_step_time_ms", 0.0),
        "p99_step_time_ms": combined.get("p99_step_time_ms", 0.0),
        "max_step_time_ms": combined.get("max_step_time_ms", 0.0),
        "max_red_thinking_seconds": combined.get("max_red_thinking_seconds", 0.0),
        "max_blue_thinking_seconds": combined.get("max_blue_thinking_seconds", 0.0),
        "avg_red_thinking_seconds": combined.get("avg_red_thinking_seconds", 0.0),
        "avg_blue_thinking_seconds": combined.get("avg_blue_thinking_seconds", 0.0),
        "timing_risk": timing_risk,
        "default_config_changed": False,
        "core_rules_changed": False,
        "suggest_expansion": suggest_expansion,
        "recommendation": recommendation,
    }


def _resolve_profile(candidate_kind: str, stage: str) -> dict:
    return CANDIDATE_PROFILES.get(candidate_kind, {}).get(stage, {})


def _resolve_starting_layout(profile: dict, explicit_layout: str | None) -> str:
    return explicit_layout or profile.get("starting_layout", STARTING_LAYOUT_ID)


def _resolve_gates(candidate_kind: str, stage: str) -> dict:
    gates = dict(STAGE_GATES[stage])
    if candidate_kind in STRONG_ROLLOUT_CANDIDATES and stage == "candidate":
        gates.pop("average_step_time_ms", None)
        gates["max_step_time_ms"] = ("le", 5000.0)
        return gates
    extra = _resolve_profile(candidate_kind, stage).get("extra_gates")
    if extra:
        gates.update(extra)
    return gates


def _is_p4_candidate_stage(candidate_kind: str, stage: str) -> bool:
    return candidate_kind == "mcts_eval_v1" and stage in {"candidate", "promotion"}


def _is_release_default_rollout_opponent(opponent_kind: str, opponent_kwargs: dict) -> bool:
    return opponent_kind == "rollout" and opponent_kwargs == RELEASE_DEFAULT_ROLLOUT_KWARGS


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
    paired_rollout_decision: dict | None = None,
    strong_rollout_decision: dict | None = None,
    self_capture_guard_decision: dict | None = None,
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
        f"- 开局布局：`{args.starting_layout}`",
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

    if paired_rollout_decision is not None:
        ci_low, ci_high = paired_rollout_decision["wilson_ci95"]
        lines.extend([
            "",
            "## P12 paired rollout 决策",
            "",
            f"- candidate gate：{'PASS' if paired_rollout_decision['candidate_gate_pass'] else 'FAIL'}",
            f"- candidate win rate：{paired_rollout_decision['candidate_win_rate']*100:.1f}%",
            f"- Wilson 95% CI：[{ci_low*100:.1f}%, {ci_high*100:.1f}%]",
            "- illegal/crash/timeout："
            f"{paired_rollout_decision['illegal_moves']} / "
            f"{paired_rollout_decision['crashes']} / "
            f"{paired_rollout_decision['timeouts']}",
            "- avg/max step time："
            f"{paired_rollout_decision['average_step_time_ms']:.1f}ms / "
            f"{paired_rollout_decision['max_step_time_ms']:.1f}ms",
            "- 是否修改默认配置：没有",
            "- 是否修改 core 规则：没有",
            f"- 是否建议扩样：{'是' if paired_rollout_decision['suggest_expansion'] else '否'}",
            f"- 结论：{paired_rollout_decision['recommendation']}",
        ])

    if self_capture_guard_decision is not None:
        ci_low, ci_high = self_capture_guard_decision["wilson_ci95"]
        lines.extend([
            "",
            "## P11 self-capture guard 决策",
            "",
            f"**默认启用决策：{self_capture_guard_decision['summary']}。**",
            f"- candidate gate：{'PASS' if self_capture_guard_decision['candidate_gate_pass'] else 'FAIL'}",
            f"- candidate win rate：{self_capture_guard_decision['candidate_win_rate']*100:.1f}%",
            f"- Wilson 95% CI：[{ci_low*100:.1f}%, {ci_high*100:.1f}%]",
            "- illegal/crash/timeout："
            f"{self_capture_guard_decision['illegal_moves']} / "
            f"{self_capture_guard_decision['crashes']} / "
            f"{self_capture_guard_decision['timeouts']}",
            "- avg/max step time："
            f"{self_capture_guard_decision['average_step_time_ms']:.1f}ms / "
            f"{self_capture_guard_decision['max_step_time_ms']:.1f}ms",
            "- 是否修改默认配置：没有",
            "- 是否修改 core 规则：没有",
            f"- 是否建议扩样：{'是' if self_capture_guard_decision['suggest_expansion'] else '否'}",
            f"- 结论：{self_capture_guard_decision['reason']}",
        ])

    if strong_rollout_decision is not None:
        ci_low, ci_high = strong_rollout_decision["wilson_ci95"]
        lines.extend([
            "",
            "## P14 strong rollout 决策",
            "",
            f"- candidate gate：{'PASS' if strong_rollout_decision['candidate_gate_pass'] else 'FAIL'}",
            f"- 52% 门槛：{'PASS' if strong_rollout_decision['passed_52_gate'] else 'FAIL'}",
            f"- 55% 门槛：{'PASS' if strong_rollout_decision['passed_55_gate'] else 'FAIL'}",
            f"- 50+50 门槛：{'PASS' if strong_rollout_decision['passed_50x2_gate'] else '未执行或未通过'}",
            f"- candidate win rate：{strong_rollout_decision['candidate_win_rate']*100:.1f}%",
            f"- Wilson 95% CI：[{ci_low*100:.1f}%, {ci_high*100:.1f}%]",
            "- illegal/crash/timeout："
            f"{strong_rollout_decision['illegal_moves']} / "
            f"{strong_rollout_decision['crashes']} / "
            f"{strong_rollout_decision['timeouts']}",
            "- avg/p95/p99/max step ms："
            f"{strong_rollout_decision['average_step_time_ms']:.1f} / "
            f"{strong_rollout_decision['p95_step_time_ms']:.1f} / "
            f"{strong_rollout_decision['p99_step_time_ms']:.1f} / "
            f"{strong_rollout_decision['max_step_time_ms']:.1f}",
            "- per-side thinking time："
            f"max_red_thinking_seconds={strong_rollout_decision['max_red_thinking_seconds']:.1f}, "
            f"max_blue_thinking_seconds={strong_rollout_decision['max_blue_thinking_seconds']:.1f}, "
            f"avg_red_thinking_seconds={strong_rollout_decision['avg_red_thinking_seconds']:.1f}, "
            f"avg_blue_thinking_seconds={strong_rollout_decision['avg_blue_thinking_seconds']:.1f}",
            f"- timing risk：{'是' if strong_rollout_decision['timing_risk'] else '否'}",
            "- 当前 release 默认配置：未修改",
            "- core 规则语义：未修改",
            f"- 是否建议扩样：{'是' if strong_rollout_decision['suggest_expansion'] else '否'}",
            f"- 结论：{strong_rollout_decision['recommendation']}",
        ])

    lines.extend([
        "",
        "## 步时与包干估算",
        "",
        f"- total_step_time_ms：{combined.get('total_step_time_ms', 0.0):.1f}",
        f"- average_turns：{combined.get('average_turns', 0.0):.2f}",
        "- avg/p95/p99/max step ms："
        f"{combined['average_step_time_ms']:.1f} / "
        f"{combined['p95_step_time_ms']:.1f} / "
        f"{combined['p99_step_time_ms']:.1f} / "
        f"{combined['max_step_time_ms']:.1f}",
        "- max_red_thinking_seconds："
        f"{combined.get('max_red_thinking_seconds', 0.0):.1f}",
        "- max_blue_thinking_seconds："
        f"{combined.get('max_blue_thinking_seconds', 0.0):.1f}",
        "- avg_red_thinking_seconds："
        f"{combined.get('avg_red_thinking_seconds', 0.0):.1f}",
        "- avg_blue_thinking_seconds："
        f"{combined.get('avg_blue_thinking_seconds', 0.0):.1f}",
    ])

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
    parser.add_argument(
        "--starting-layout",
        default=None,
        help="开局布局；省略时按候选 profile 选择，profile 未指定则使用历史 harness 默认布局。",
    )
    parser.add_argument("--report-dir", default=str(ROOT / "reports"))
    parser.add_argument("--no-save-report", action="store_true")
    parser.add_argument("--report-name", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    profile = _resolve_profile(args.candidate, args.stage)
    args.starting_layout = _resolve_starting_layout(profile, args.starting_layout)
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
    explicit_opponent_kwargs = _parse_kv(args.opponent_arg, parser, "--opponent-arg")
    opponent_profile = profile if opponent_kind == profile.get("opponent") else {}
    opponent_kwargs = _merge_profile_kwargs(
        opponent_profile,
        explicit_opponent_kwargs,
        key="opponent_kwargs",
    )
    if _is_p4_candidate_stage(args.candidate, args.stage) and not _is_release_default_rollout_opponent(
        opponent_kind,
        opponent_kwargs,
    ):
        parser.error(
            "P4 mcts_eval_v1 candidate/promotion requires opponent=rollout with current "
            "release default rollout kwargs; use the built-in profile or pass the exact "
            "release/v1.0/default_params.json kwargs explicitly."
        )
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
    paired_rollout_decision = _paired_rollout_decision(
        args.candidate,
        args.stage,
        combined,
        gates_ok,
    )
    strong_rollout_decision = _strong_rollout_decision(
        args.candidate,
        args.stage,
        combined,
        gates_ok,
    )
    self_capture_guard_decision = _self_capture_guard_decision(
        args.candidate,
        args.stage,
        combined,
        gates_ok,
    )

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
    if paired_rollout_decision is not None:
        summary["paired_rollout_decision"] = paired_rollout_decision
    if strong_rollout_decision is not None:
        summary["strong_rollout_decision"] = strong_rollout_decision
    if self_capture_guard_decision is not None:
        summary["decision"] = self_capture_guard_decision

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
            paired_rollout_decision=paired_rollout_decision,
            strong_rollout_decision=strong_rollout_decision,
            self_capture_guard_decision=self_capture_guard_decision,
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
