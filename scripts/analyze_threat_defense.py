from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, starting_state_for
from ai.release_defaults import load_release_default_rollout_kwargs
from ai.tactical import find_winning_moves
from core.move import Move
from core.types import Player


MARGIN_BUCKETS = ("<=0.02", "(0.02,0.04]", "(0.04,0.08]", ">0.08_or_null")


def move_identity(move: Move) -> tuple[str, int, int, int, int, int]:
    return (
        move.player.value,
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def move_sort_key(move: Move) -> tuple[int, int, int, int, int]:
    return (
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def move_to_dict(move: Move) -> dict[str, Any]:
    return {
        "piece_id": move.piece_id,
        "from": [move.from_pos.row, move.from_pos.col],
        "to": [move.to_pos.row, move.to_pos.col],
    }


def is_self_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player


def board_key(state) -> str:
    return json.dumps(state.serialize(include_history=False), ensure_ascii=False, sort_keys=True)


def root_stats_index(root_stats: list[Any]) -> dict[tuple[str, int, int, int, int, int], dict[str, Any]]:
    ranked = sorted(
        root_stats,
        key=lambda item: (-float(getattr(item, "score", 0.0)), move_sort_key(item.move)),
    )
    index: dict[tuple[str, int, int, int, int, int], dict[str, Any]] = {}
    for rank, item in enumerate(ranked, start=1):
        index[move_identity(item.move)] = {
            "rank": rank,
            "score": float(getattr(item, "score", 0.0)),
            "winrate": float(getattr(item, "winrate", 0.0)),
        }
    return index


def score_margin_bucket(value: float | None) -> str:
    if value is None:
        return ">0.08_or_null"
    value = float(value)
    if value <= 0.02:
        return "<=0.02"
    if value <= 0.04:
        return "(0.02,0.04]"
    if value <= 0.08:
        return "(0.04,0.08]"
    return ">0.08_or_null"


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def opponent_winning_dice_after_move(state, move: Move, dice: int) -> list[int]:
    state.apply_move(move, dice=dice)
    try:
        if state.get_winner() is move.player:
            return []
        opponent = state.current_player
        winning_dice: list[int] = []
        for next_dice in range(1, 7):
            if find_winning_moves(state, next_dice, opponent):
                winning_dice.append(next_dice)
        return winning_dice
    finally:
        state.undo_move()


def _root_entry(
    move: Move,
    stats: dict[tuple[str, int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    entry = stats.get(move_identity(move))
    if entry is None:
        return {"rank": None, "score": None, "winrate": None}
    return entry


def _candidate_entry(
    *,
    state,
    dice: int,
    move: Move,
    chosen_threat_count: int | None,
    chosen_score: float | None,
    stats: dict[tuple[str, int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    root = _root_entry(move, stats)
    winning_dice = opponent_winning_dice_after_move(state, move, dice)
    score = root["score"]
    return {
        **move_to_dict(move),
        "root_rank": root["rank"],
        "root_score": score,
        "root_winrate": root["winrate"],
        "score_delta_from_chosen": None if score is None or chosen_score is None else score - chosen_score,
        "opponent_winning_dice_set": winning_dice,
        "opponent_winning_dice_count": len(winning_dice),
        "threat_delta_from_chosen": None if chosen_threat_count is None else len(winning_dice) - chosen_threat_count,
        "self_capture": is_self_capture(move),
    }


def audit_position(
    *,
    state,
    dice: int,
    chosen: Move,
    root_stats: list[Any],
    low_confidence: bool,
    score_margin: float | None,
    game_index: int,
    turn: int,
    subject_player: Player,
    failure_tags: list[str],
    top_k: int,
) -> dict[str, Any]:
    legal = state.legal_moves(state.current_player, dice)
    if chosen not in legal:
        raise ValueError("chosen move must be legal in audited position")

    stats = root_stats_index(root_stats)
    chosen_root = _root_entry(chosen, stats)
    chosen_winning_dice = opponent_winning_dice_after_move(state, chosen, dice)
    chosen_threat_count = len(chosen_winning_dice)
    chosen_score = chosen_root["score"]
    chosen_payload = {
        **move_to_dict(chosen),
        "root_rank": chosen_root["rank"],
        "root_score": chosen_score,
        "root_winrate": chosen_root["winrate"],
        "opponent_winning_dice_set": chosen_winning_dice,
        "opponent_winning_dice_count": chosen_threat_count,
        "self_capture": is_self_capture(chosen),
    }

    alternatives = [
        _candidate_entry(
            state=state,
            dice=dice,
            move=move,
            chosen_threat_count=chosen_threat_count,
            chosen_score=chosen_score,
            stats=stats,
        )
        for move in legal
        if move != chosen
    ]
    alternatives.sort(
        key=lambda item: (
            item["opponent_winning_dice_count"],
            999999 if item["root_rank"] is None else item["root_rank"],
            item["piece_id"],
            item["from"][0],
            item["from"][1],
            item["to"][0],
            item["to"][1],
        )
    )
    best_threat_count = min([chosen_threat_count] + [item["opponent_winning_dice_count"] for item in alternatives])
    reducing = [item for item in alternatives if item["opponent_winning_dice_count"] < chosen_threat_count]
    full_blocks = [item for item in reducing if item["opponent_winning_dice_count"] == 0]
    ranked_reducing = [item for item in reducing if item["root_rank"] is not None and item["root_rank"] <= top_k]

    return {
        "game_index": game_index,
        "turn": turn,
        "board": board_key(state),
        "subject_player": subject_player.value,
        "player": state.current_player.value,
        "dice": dice,
        "low_confidence": bool(low_confidence),
        "score_margin": score_margin,
        "score_margin_bucket": score_margin_bucket(score_margin),
        "failure_tags": list(failure_tags),
        "chosen": chosen_payload,
        "alternatives": alternatives,
        "best_threat_count": best_threat_count,
        "threat_reducing_alternative_exists": bool(reducing),
        "full_block_alternative_exists": bool(full_blocks),
        "best_threat_reducing_rank": min((item["root_rank"] for item in ranked_reducing), default=None),
    }


def summarize_positions(positions: list[dict[str, Any]], *, top_k: int) -> dict[str, Any]:
    audited = len(positions)
    chosen_allowed = [item for item in positions if item["chosen"]["opponent_winning_dice_count"] > 0]
    reducing = [item for item in positions if item["threat_reducing_alternative_exists"]]
    full_blocks = [item for item in positions if item["full_block_alternative_exists"]]
    partial_reductions = [item for item in reducing if item["best_threat_count"] > 0]
    reduction_amounts = [
        item["chosen"]["opponent_winning_dice_count"] - item["best_threat_count"]
        for item in reducing
    ]

    low_confidence = [item for item in positions if item["low_confidence"]]
    low_confidence_allowed = [item for item in low_confidence if item["chosen"]["opponent_winning_dice_count"] > 0]
    low_confidence_reducing = [item for item in low_confidence if item["threat_reducing_alternative_exists"]]
    low_confidence_full_blocks = [item for item in low_confidence if item["full_block_alternative_exists"]]
    low_confidence_top_k_hits = [
        item
        for item in low_confidence_reducing
        if item["best_threat_reducing_rank"] is not None and item["best_threat_reducing_rank"] <= top_k
    ]

    self_capture = [item for item in positions if item["chosen"]["self_capture"]]
    non_self_capture = [item for item in positions if not item["chosen"]["self_capture"]]
    self_capture_allowed = [item for item in self_capture if item["chosen"]["opponent_winning_dice_count"] > 0]
    non_self_capture_allowed = [
        item for item in non_self_capture if item["chosen"]["opponent_winning_dice_count"] > 0
    ]

    score_margin_buckets = {
        bucket: {"positions": 0, "with_threat_reducing_alternative": 0}
        for bucket in MARGIN_BUCKETS
    }
    for item in positions:
        bucket = item["score_margin_bucket"]
        score_margin_buckets[bucket]["positions"] += 1
        if item["threat_reducing_alternative_exists"]:
            score_margin_buckets[bucket]["with_threat_reducing_alternative"] += 1

    top_k_hits = [
        item
        for item in reducing
        if item["best_threat_reducing_rank"] is not None and item["best_threat_reducing_rank"] <= top_k
    ]

    return {
        "threat_defense": {
            "chosen_allowed_direct_loss_positions": len(chosen_allowed),
            "threat_reducing_alternative_positions": len(reducing),
            "full_block_alternative_positions": len(full_blocks),
            "partial_reduction_alternative_positions": len(partial_reductions),
            "average_chosen_threat_count": safe_ratio(
                sum(item["chosen"]["opponent_winning_dice_count"] for item in positions),
                audited,
            ),
            "average_best_alternative_threat_count": safe_ratio(
                sum(item["best_threat_count"] for item in positions),
                audited,
            ),
            "average_reduction_when_available": safe_ratio(sum(reduction_amounts), len(reduction_amounts)),
        },
        "low_confidence": {
            "positions": len(low_confidence),
            "with_allowed_direct_loss": len(low_confidence_allowed),
            "with_threat_reducing_alternative": len(low_confidence_reducing),
            "with_full_block_alternative": len(low_confidence_full_blocks),
            "threat_reducing_ratio": safe_ratio(len(low_confidence_reducing), len(low_confidence)),
            "full_block_ratio": safe_ratio(len(low_confidence_full_blocks), len(low_confidence)),
            "best_threat_reducing_in_top_k": len(low_confidence_top_k_hits),
            "best_threat_reducing_in_top_k_ratio": safe_ratio(
                len(low_confidence_top_k_hits),
                len(low_confidence_reducing),
            ),
        },
        "self_capture_correlation": {
            "self_capture_positions": len(self_capture),
            "self_capture_and_allowed_direct_loss": len(self_capture_allowed),
            "non_self_capture_positions": len(non_self_capture),
            "non_self_capture_and_allowed_direct_loss": len(non_self_capture_allowed),
            "allowed_direct_loss_rate_given_self_capture": safe_ratio(len(self_capture_allowed), len(self_capture)),
            "allowed_direct_loss_rate_given_non_self_capture": safe_ratio(
                len(non_self_capture_allowed),
                len(non_self_capture),
            ),
            "self_capture_with_threat_reducing_alternative": sum(
                1 for item in self_capture if item["threat_reducing_alternative_exists"]
            ),
            "self_capture_with_full_block_alternative": sum(
                1 for item in self_capture if item["full_block_alternative_exists"]
            ),
        },
        "score_margin_buckets": score_margin_buckets,
        "top_k": {
            "threat_reducing_positions": len(reducing),
            "best_threat_reducing_in_top_k": len(top_k_hits),
            "best_threat_reducing_in_top_k_ratio": safe_ratio(len(top_k_hits), len(reducing)),
        },
    }


def decide_supports_threat_rerank(summary: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    low_confidence_positions = int(summary["low_confidence"]["positions"])
    threat_ratio = float(summary["low_confidence"]["threat_reducing_ratio"])
    top_k_ratio = float(summary["low_confidence"]["best_threat_reducing_in_top_k_ratio"])

    if low_confidence_positions < 30:
        reasons.append(f"low_confidence positions {low_confidence_positions} < 30")
    if threat_ratio < 0.25:
        reasons.append(f"low_confidence threat_reducing_ratio {threat_ratio:.3f} < 0.250")
    if top_k_ratio < 0.60:
        reasons.append(f"low-confidence best threat-reducing in top_k ratio {top_k_ratio:.3f} < 0.600")

    return {
        "supports_threat_rerank_candidate": not reasons,
        "reasons": reasons
        or [
            "low-confidence threat-reducing alternatives are frequent enough for a rollout_threat_rerank candidate"
        ],
    }


def select_examples(positions: list[dict[str, Any]], *, max_examples: int) -> dict[str, list[dict[str, Any]]]:
    limit = max(0, int(max_examples))

    def take(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return items[:limit]

    threat_reducing = [item for item in positions if item["threat_reducing_alternative_exists"]]
    low_confidence_threat_reducing = [
        item for item in threat_reducing if item["low_confidence"]
    ]
    allowed_direct_loss = [
        item for item in positions if item["chosen"]["opponent_winning_dice_count"] > 0
    ]

    return {
        "threat_reducing_examples": take(threat_reducing),
        "low_confidence_threat_reducing_examples": take(low_confidence_threat_reducing),
        "allowed_direct_loss_examples": take(allowed_direct_loss),
    }


def example_line(item: dict[str, Any]) -> str:
    return (
        "- "
        f"game={item['game_index']} turn={item['turn']} dice={item['dice']} "
        f"chosen_threat={item['chosen']['opponent_winning_dice_count']} "
        f"best_threat={item['best_threat_count']} "
        f"low_confidence={item['low_confidence']}"
    )


def write_reports(payload: dict[str, Any], output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# P8 Threat Defense Audit",
        "",
        "默认 AI、默认布局、release 配置未变。",
        "",
        "本报告只审计 threat-reducing alternative 是否存在；它不是默认 AI 晋升证据。",
        "P8.4 候选名为 `rollout_threat_rerank`，只有审计 gate 支持且用户明确批准后才可继续实现。",
        "",
        f"- subject: `{payload['subject']['ai']}`",
        f"- opponent: `{payload['opponent']}`",
        f"- games: `{payload['games']}`",
        f"- seed_pool: `{payload['seed_pool']}`",
        f"- default_layout: `{payload['default_layout']}`",
        f"- audited_positions: `{payload['summary']['audited_positions']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Threat Defense", ""])
    for key, value in payload["threat_defense"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Low Confidence", ""])
    for key, value in payload["low_confidence"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Self-capture Correlation", ""])
    for key, value in payload["self_capture_correlation"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Score Margin Buckets", ""])
    for bucket, values in payload["score_margin_buckets"].items():
        lines.append(
            f"- {bucket}: positions=`{values['positions']}`, "
            f"with_threat_reducing_alternative=`{values['with_threat_reducing_alternative']}`"
        )

    lines.extend(["", "## Top-k Coverage", ""])
    for key, value in payload["top_k"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Decision", ""])
    lines.append(
        f"- supports_threat_rerank_candidate: "
        f"`{payload['decision']['supports_threat_rerank_candidate']}`"
    )
    for reason in payload["decision"]["reasons"]:
        lines.append(f"- reason: `{reason}`")

    lines.extend(["", "## Examples", ""])
    example_groups = payload.get(
        "examples",
        {"chronological_examples": payload["positions"][:5]},
    )
    labels = {
        "threat_reducing_examples": "Threat-reducing Examples",
        "low_confidence_threat_reducing_examples": "Low-confidence Threat-reducing Examples",
        "allowed_direct_loss_examples": "Allowed Direct-loss Examples",
        "chronological_examples": "Chronological Examples",
    }
    for key, examples in example_groups.items():
        lines.extend(["", f"### {labels.get(key, key)}", ""])
        if not examples:
            lines.append("- none")
            continue
        for item in examples[:5]:
            lines.append(example_line(item))

    lines.extend(["", "## Reproduce", "", "```powershell", payload["command"], "```"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def step_failure_tags(step: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if step["chosen_allowed_direct_loss"]:
        tags.append("allowed_direct_loss")
    if step["low_confidence"]:
        tags.append("low_confidence_loss")
    if step["timed_out"] or step["used_fallback"]:
        tags.append("timeout_or_fallback")
    if step["self_capture"] and float(step.get("score_margin") or 0.0) < 0.08:
        tags.append("bad_self_capture")
    return tags


def analyze_one_game(
    *,
    subject_player: Player,
    subject_ai,
    opponent_ai,
    dice_rng: random.Random,
    layout: str,
    max_turns: int,
    top_k: int,
) -> dict[str, Any]:
    state = starting_state_for(layout)
    subject_steps: list[dict[str, Any]] = []
    illegal_moves = 0
    crashes = 0
    timeouts = 0

    for turn in range(max_turns):
        winner = state.get_winner()
        if winner is not None:
            return {
                "winner": winner.value,
                "subject_won": winner is subject_player,
                "subject_lost": winner is subject_player.opponent,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "winner",
            }

        active = state.current_player
        ai = subject_ai if active is subject_player else opponent_ai
        dice = dice_rng.randint(1, 6)
        legal = state.legal_moves(active, dice)
        if not legal:
            winner = active.opponent
            return {
                "winner": winner.value,
                "subject_won": winner is subject_player,
                "subject_lost": winner is subject_player.opponent,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "no_move",
            }

        started = time.perf_counter()
        try:
            move = ai.choose_move(state, dice)
        except Exception as exc:  # noqa: BLE001 - audit records crash class.
            crashes += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "subject_lost": active is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": f"crash:{type(exc).__name__}",
            }
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms > float(getattr(ai, "max_step_time_ms", 10**9)):
            timeouts += 1

        if move not in legal:
            illegal_moves += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "subject_lost": active is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "illegal_move",
            }

        if active is subject_player:
            snapshot = state.serialize(include_history=True)
            allowed_direct_loss_dice = opponent_winning_dice_after_move(state, move, dice)
            step = {
                "turn": turn,
                "snapshot": snapshot,
                "dice": dice,
                "move": move.to_dict(),
                "root_stats": list(getattr(ai, "last_root_stats", [])),
                "low_confidence": bool(getattr(ai, "last_low_confidence", False)),
                "timed_out": bool(getattr(ai, "last_timed_out", False)),
                "used_fallback": bool(getattr(ai, "last_used_fallback", False)),
                "score_margin": getattr(ai, "last_score_margin", None),
                "chosen_allowed_direct_loss": bool(allowed_direct_loss_dice),
                "self_capture": is_self_capture(move),
            }
            step["failure_tags"] = step_failure_tags(step)
            subject_steps.append(step)

        state.apply_move(move, dice=dice)

    return {
        "winner": None,
        "subject_won": False,
        "subject_lost": False,
        "turns": max_turns,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "subject_steps": subject_steps,
        "termination_reason": "draw_max_turns",
    }


def analyze_games(
    *,
    games: int,
    seed_pool: list[int],
    opponent: str,
    starting_layout: str,
    max_turns: int,
    top_k: int,
    max_examples: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    kwargs = load_release_default_rollout_kwargs()
    summary = {
        "subject_wins": 0,
        "subject_losses": 0,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "draw_max_turns": 0,
        "audited_positions": 0,
    }
    positions: list[dict[str, Any]] = []

    for game_index in range(games):
        subject_player = Player.RED if game_index % 2 == 0 else Player.BLUE
        seed = seed_pool[game_index % len(seed_pool)] + game_index * 9973
        subject_ai = build_ai("rollout", seed=seed, **kwargs)
        opponent_ai = build_ai(opponent, seed=seed ^ 0xA5A5A5)
        result = analyze_one_game(
            subject_player=subject_player,
            subject_ai=subject_ai,
            opponent_ai=opponent_ai,
            dice_rng=random.Random(seed ^ 0xC0FFEE),
            layout=starting_layout,
            max_turns=max_turns,
            top_k=top_k,
        )
        summary["illegal_moves"] += int(result["illegal_moves"])
        summary["crashes"] += int(result["crashes"])
        summary["timeouts"] += int(result["timeouts"])
        if result["subject_won"]:
            summary["subject_wins"] += 1
            continue
        if result["termination_reason"] == "draw_max_turns":
            summary["draw_max_turns"] += 1
        if not result["subject_lost"]:
            continue
        summary["subject_losses"] += 1

        from core.game_state import GameState

        for step in result["subject_steps"]:
            state = GameState.deserialize(step["snapshot"])
            chosen = Move.from_dict(step["move"])
            position = audit_position(
                state=state,
                dice=int(step["dice"]),
                chosen=chosen,
                root_stats=step["root_stats"],
                low_confidence=bool(step["low_confidence"]),
                score_margin=step["score_margin"],
                game_index=game_index,
                turn=int(step["turn"]),
                subject_player=subject_player,
                failure_tags=list(step["failure_tags"]),
                top_k=top_k,
            )
            positions.append(position)

    summary["audited_positions"] = len(positions)
    return summary, positions[:max_examples] if max_examples else positions


def parse_seed_pool(value: str) -> list[int]:
    seeds = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("seed pool must contain at least one integer")
    return seeds


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    summary, positions = analyze_games(
        games=args.games,
        seed_pool=args.seed_pool,
        opponent=args.opponent,
        starting_layout=args.starting_layout,
        max_turns=args.max_turns,
        top_k=args.top_k,
        max_examples=0,
    )
    aggregate = summarize_positions(positions, top_k=args.top_k)
    decision = decide_supports_threat_rerank(aggregate)
    limited_positions = positions[: args.max_examples]
    examples = select_examples(positions, max_examples=args.max_examples)
    command = (
        f'& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" '
        f"--games {args.games} --seed-pool {','.join(str(seed) for seed in args.seed_pool)} "
        f"--opponent {args.opponent} --starting-layout {args.starting_layout} "
        f"--max-turns {args.max_turns} --score-margin {args.score_margin} --top-k {args.top_k} "
        f'--max-examples {args.max_examples} --output "{args.output}" --json-output "{args.json_output}"'
    )
    return {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": args.opponent,
        "games": args.games,
        "seed_pool": args.seed_pool,
        "default_layout": args.starting_layout,
        "analysis_window": {
            "subject_losses_only": True,
            "subject_to_move_only": True,
            "score_margin": args.score_margin,
            "top_k": args.top_k,
        },
        "summary": summary,
        **aggregate,
        "positions": limited_positions,
        "examples": examples,
        "decision": decision,
        "command": command,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit rollout threat-defense alternatives.")
    parser.add_argument("--games", type=int, default=120)
    parser.add_argument("--seed-pool", type=parse_seed_pool, default=parse_seed_pool("28016,28017,28018"))
    parser.add_argument("--opponent", default="greedy_risk")
    parser.add_argument("--starting-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--score-margin", type=float, default=0.08)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("reports/p8_threat_defense_audit_20260517.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/p8_threat_defense_audit_20260517.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_payload(args)
    write_reports(payload, args.output, args.json_output)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.json_output}")
    print(f"supports_threat_rerank_candidate={payload['decision']['supports_threat_rerank_candidate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
