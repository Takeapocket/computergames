"""Audit release-default rollout self-capture choices.

本脚本只量化当前 release 默认 rollout 的 root 推荐行为，不是候选晋升证据，
也不会修改 GUI / release 默认配置。
"""
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

from ai.match import _step_timed_out, build_ai, starting_state_for
from ai.release_defaults import load_release_default_rollout_kwargs
from ai.tactical import find_winning_moves
from core.game_state import GameState
from core.move import Move
from core.types import Player
from scripts._bench_meta import build_provenance


def parse_seed_pool(value: str) -> list[int]:
    seeds = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not seeds:
        raise ValueError("seed pool must contain at least one integer")
    return seeds


def board_key(state: GameState) -> str:
    return repr(state.serialize(include_history=False))


def move_identity(move: Move) -> tuple[int, int, int, int, int]:
    return (
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def move_sort_key(move: Move) -> tuple[int, int, int, int, int]:
    return move_identity(move)


def move_to_dict(move: Move) -> dict[str, Any]:
    captured = move.captured_piece
    return {
        "piece_id": move.piece_id,
        "from": [move.from_pos.row, move.from_pos.col],
        "to": [move.to_pos.row, move.to_pos.col],
        "is_capture": move.is_capture,
        "captured_player": None if captured is None else captured.player.value,
        "captured_piece_id": None if captured is None else captured.piece_id,
    }


def is_self_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player


def is_enemy_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player.opponent


def move_wins_immediately(state: GameState, move: Move, dice: int) -> bool:
    state.apply_move(move, dice=dice)
    try:
        return state.get_winner() is move.player
    finally:
        state.undo_move()


def opponent_direct_win_dice_after_move(state: GameState, move: Move, dice: int) -> list[int]:
    state.apply_move(move, dice=dice)
    try:
        if state.get_winner() is move.player:
            return []
        opponent = state.current_player
        winning_dice = []
        for next_dice in range(1, 7):
            if find_winning_moves(state, next_dice, opponent):
                winning_dice.append(next_dice)
        return winning_dice
    finally:
        state.undo_move()


def own_alive_count(state: GameState, player: Player) -> int:
    return sum(1 for piece in state.pieces[player].values() if piece.alive)


def own_alive_after_move(state: GameState, move: Move, dice: int) -> int:
    state.apply_move(move, dice=dice)
    try:
        return own_alive_count(state, move.player)
    finally:
        state.undo_move()


def root_stats_index(root_stats: list[Any]) -> dict[tuple[int, int, int, int, int], dict[str, Any]]:
    ranked = sorted(
        root_stats,
        key=lambda item: (-float(getattr(item, "score", 0.0)), move_sort_key(item.move)),
    )
    index: dict[tuple[int, int, int, int, int], dict[str, Any]] = {}
    for rank, item in enumerate(ranked, start=1):
        index[move_identity(item.move)] = {
            "rank": rank,
            "score": float(getattr(item, "score", 0.0)),
            "winrate": float(getattr(item, "winrate", 0.0)),
            "visits": int(getattr(item, "visits", 0)),
        }
    return index


def _root_entry(
    move: Move,
    stats: dict[tuple[int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    entry = stats.get(move_identity(move))
    if entry is None:
        return {"rank": None, "score": None, "winrate": None, "visits": 0}
    return entry


def _alternative_entry(
    move: Move,
    stats: dict[tuple[int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    root = _root_entry(move, stats)
    return {
        **move_to_dict(move),
        "root_rank": root["rank"],
        "root_score": root["score"],
        "root_winrate": root["winrate"],
        "root_visits": root["visits"],
    }


def _sorted_alternatives(
    moves: list[Move],
    stats: dict[tuple[int, int, int, int, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [_alternative_entry(move, stats) for move in moves]
    rows.sort(
        key=lambda item: (
            1 if item["root_score"] is None else -float(item["root_score"]),
            999999 if item["root_rank"] is None else item["root_rank"],
            item["piece_id"],
            item["from"][0],
            item["from"][1],
            item["to"][0],
            item["to"][1],
        )
    )
    return rows


def _best_alternative_margin(chosen_score: float | None, alternatives: list[dict[str, Any]]) -> float | None:
    if chosen_score is None:
        return None
    scored = [item["root_score"] for item in alternatives if item["root_score"] is not None]
    if not scored:
        return None
    return float(chosen_score) - max(float(score) for score in scored)


def audit_subject_choice(
    *,
    state: GameState,
    dice: int,
    chosen: Move,
    root_stats: list[Any],
    game_index: int,
    turn: int,
    subject_player: Player,
) -> dict[str, Any]:
    legal = state.legal_moves(state.current_player, dice)
    if chosen not in legal:
        raise ValueError("chosen move must be legal in audited position")

    stats = root_stats_index(root_stats)
    chosen_root = _root_entry(chosen, stats)
    enemy_capture_moves = [
        move for move in legal
        if move != chosen and is_enemy_capture(move)
    ]
    non_self_moves = [
        move for move in legal
        if move != chosen and not is_self_capture(move)
    ]
    enemy_alternatives = _sorted_alternatives(enemy_capture_moves, stats)
    non_self_alternatives = _sorted_alternatives(non_self_moves, stats)
    chosen_score = chosen_root["score"]
    chosen_direct_win = move_wins_immediately(state, chosen, dice)
    allowed_direct_win = [] if chosen_direct_win else opponent_direct_win_dice_after_move(state, chosen, dice)

    return {
        "game_index": game_index,
        "turn": turn,
        "board": board_key(state),
        "subject_player": subject_player.value,
        "player": state.current_player.value,
        "subject_to_move": state.current_player is subject_player,
        "dice": dice,
        "chosen": {
            **move_to_dict(chosen),
            "root_rank": chosen_root["rank"],
            "root_score": chosen_score,
            "root_winrate": chosen_root["winrate"],
            "root_visits": chosen_root["visits"],
        },
        "chosen_score": chosen_score,
        "chosen_self_capture": is_self_capture(chosen),
        "chosen_enemy_capture": is_enemy_capture(chosen),
        "chosen_direct_win": chosen_direct_win,
        "chosen_move_allowed_opponent_direct_win_dice": allowed_direct_win,
        "own_alive_before": own_alive_count(state, chosen.player),
        "own_alive_after": own_alive_after_move(state, chosen, dice),
        "enemy_capture_alt_available": bool(enemy_capture_moves),
        "non_self_alt_available": bool(non_self_moves),
        "enemy_capture_alternatives": enemy_alternatives,
        "non_self_alternatives": non_self_alternatives,
        "best_alternative_score_margin": _best_alternative_margin(chosen_score, non_self_alternatives),
    }


def analyze_one_game(
    *,
    subject_player: Player,
    subject_ai,
    opponent_ai,
    dice_rng: random.Random,
    layout: str,
    max_turns: int,
    game_index: int = 0,
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
        except Exception:  # noqa: BLE001 - audit records crashes.
            crashes += 1
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if _step_timed_out(ai, elapsed_ms):
                timeouts += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "crash",
            }
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if _step_timed_out(ai, elapsed_ms):
            timeouts += 1

        if move is None:
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "no_move",
            }

        if move not in legal:
            illegal_moves += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "illegal_move",
            }

        if active is subject_player:
            step = audit_subject_choice(
                state=state,
                dice=dice,
                chosen=move,
                root_stats=list(getattr(ai, "last_root_stats", [])),
                game_index=game_index,
                turn=turn,
                subject_player=subject_player,
            )
            step["low_confidence"] = bool(getattr(ai, "last_low_confidence", False))
            step["timed_out"] = bool(getattr(ai, "last_timed_out", False))
            step["used_fallback"] = bool(getattr(ai, "last_used_fallback", False))
            step["score_margin"] = getattr(ai, "last_score_margin", None)
            step["elapsed_ms"] = elapsed_ms
            subject_steps.append(step)

        state.apply_move(move, dice=dice)

    return {
        "winner": None,
        "subject_won": False,
        "turns": max_turns,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "subject_steps": subject_steps,
        "termination_reason": "draw_max_turns",
    }


def _safe_ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def summarize_games(results: list[dict[str, Any]], *, max_examples: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    subject_steps = [
        step
        for result in results
        for step in result["subject_steps"]
        if step.get("subject_to_move", True)
    ]
    self_steps = [step for step in subject_steps if step["chosen_self_capture"]]
    margins = [
        float(step["best_alternative_score_margin"])
        for step in self_steps
        if step.get("best_alternative_score_margin") is not None
    ]
    losses = [result for result in results if not result["subject_won"]]
    summary = {
        "games": len(results),
        "subject_wins": sum(1 for result in results if result["subject_won"]),
        "subject_losses": len(losses),
        "total_subject_moves": len(subject_steps),
        "chosen_self_capture": len(self_steps),
        "chosen_self_capture_rate": _safe_ratio(len(self_steps), len(subject_steps)),
        "chosen_self_capture_with_enemy_capture_alt": sum(
            1 for step in self_steps if step["enemy_capture_alt_available"]
        ),
        "chosen_self_capture_with_non_self_alt": sum(
            1 for step in self_steps if step["non_self_alt_available"]
        ),
        "chosen_self_capture_when_own_alive_le_3": sum(
            1 for step in self_steps if int(step["own_alive_after"]) <= 3
        ),
        "chosen_self_capture_when_own_alive_le_2": sum(
            1 for step in self_steps if int(step["own_alive_after"]) <= 2
        ),
        "self_capture_direct_win_count": sum(1 for step in self_steps if step["chosen_direct_win"]),
        "losses_with_self_capture": sum(
            1
            for result in losses
            if any(step["chosen_self_capture"] for step in result["subject_steps"])
        ),
        "enemy_capture_alt_available": sum(
            1 for step in subject_steps if step["enemy_capture_alt_available"]
        ),
        "non_self_alt_available": sum(
            1 for step in subject_steps if step["non_self_alt_available"]
        ),
        "avg_score_margin_when_self_capture": _average(margins),
        "illegal_moves": sum(int(result["illegal_moves"]) for result in results),
        "crashes": sum(int(result["crashes"]) for result in results),
        "timeouts": sum(int(result["timeouts"]) for result in results),
    }
    return summary, self_steps[:max_examples]


def analyze_games(*, games: int, seed_pool: list[int], opponent: str, layout: str, max_turns: int) -> dict[str, Any]:
    subject_kwargs = load_release_default_rollout_kwargs()
    opponent_kwargs = (
        load_release_default_rollout_kwargs()
        if opponent == "rollout"
        else {}
    )
    results: list[dict[str, Any]] = []

    for game_index in range(games):
        seed = seed_pool[game_index % len(seed_pool)] * 100_000 + game_index
        subject_player = Player.RED if game_index % 2 == 0 else Player.BLUE
        subject_ai = build_ai("rollout", seed=seed * 3 + 1, **subject_kwargs)
        opponent_ai = build_ai(opponent, seed=seed * 3 + 2, **opponent_kwargs)
        results.append(
            analyze_one_game(
                subject_player=subject_player,
                subject_ai=subject_ai,
                opponent_ai=opponent_ai,
                dice_rng=random.Random(seed * 3),
                layout=layout,
                max_turns=max_turns,
                game_index=game_index,
            )
        )

    summary, examples = summarize_games(results, max_examples=20)
    return {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": opponent,
        "opponent_kwargs_source": (
            "release/v1.0/default_params.json"
            if opponent == "rollout"
            else "build_ai defaults"
        ),
        "games": games,
        "seed_pool": seed_pool,
        "default_layout": layout,
        "summary": summary,
        "examples": examples,
    }


def write_reports(payload: dict[str, Any], output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Self-capture Choice Audit",
        "",
        "默认 AI、默认布局、release 配置未变。",
        "",
        "本审计不是 promotion evidence；它只量化当前 release 默认 rollout 的 root 推荐行为，不默认启用任何候选。",
        "losses_with_self_capture 表示输掉的对局中曾发生 self-capture，是相关性统计，不代表 self-capture 导致失败。",
        "",
        f"- subject: `{payload['subject']['ai']}`",
        f"- subject_kwargs_source: `{payload['subject']['ai_kwargs_source']}`",
        f"- opponent: `{payload['opponent']}`",
        f"- games: `{payload['games']}`",
        f"- seed_pool: `{payload['seed_pool']}`",
        f"- default_layout: `{payload['default_layout']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Examples", ""])
    examples = payload.get("examples", [])
    if not examples:
        lines.append("- none")
    for item in examples[:20]:
        chosen = item["chosen"]
        lines.append(
            "- "
            f"game={item['game_index']} turn={item['turn']} player={item['player']} dice={item['dice']} "
            f"move={chosen['piece_id']}:{chosen['from']}->{chosen['to']} "
            f"score={item['chosen_score']} own={item['own_alive_before']}->{item['own_alive_after']} "
            f"enemy_alt={len(item['enemy_capture_alternatives'])} "
            f"non_self_alt={len(item['non_self_alternatives'])} "
            f"opp_win_dice={item['chosen_move_allowed_opponent_direct_win_dice']}"
        )

    lines.extend(["", "## Reproduce", "", "```powershell", payload["command"], "```"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze release default rollout self-capture choices.")
    parser.add_argument("--games", type=int, default=60)
    parser.add_argument("--seed-pool", default="31026,31027,31028")
    parser.add_argument("--opponent", default="greedy_risk")
    parser.add_argument("--starting-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "self_capture_audit_20260518.md",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "reports" / "self_capture_audit_20260518.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        seed_pool = parse_seed_pool(args.seed_pool)
    except ValueError as exc:
        parser.error(f"--seed-pool: {exc}")

    payload = {
        **build_provenance(
            repo_root=ROOT,
            script_name="analyze_self_capture_choices.py",
            argv=argv,
            starting_layout_id=args.starting_layout,
        ),
        **analyze_games(
            games=args.games,
            seed_pool=seed_pool,
            opponent=args.opponent,
            layout=args.starting_layout,
            max_turns=args.max_turns,
        ),
    }
    payload["command"] = (
        f'& ".venv/Scripts/python.exe" "scripts/analyze_self_capture_choices.py" '
        f"--games {args.games} --seed-pool {args.seed_pool} --opponent {args.opponent} "
        f"--starting-layout {args.starting_layout} --max-turns {args.max_turns} "
        f'--output "{args.output}" --json-output "{args.json_output}"'
    )
    write_reports(payload, args.output, args.json_output)
    print(f"wrote {args.output}")
    print(f"wrote {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
