from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.game_state import GameState
from core.rules import target_corner
from record.game_record import GameRecord
from scripts.replay_analyze import load_records


def count_dice_by_source(records: Iterable[GameRecord]) -> dict[str, dict[int, int]]:
    grouped: dict[str, Counter[int]] = {}
    for record in records:
        for step in record.steps:
            grouped.setdefault(step.source, Counter())[step.dice] += 1
    return {
        source: {dice: counts.get(dice, 0) for dice in range(1, 7)}
        for source, counts in sorted(grouped.items())
    }


def _chi_square_df5_survival(chi_square: float) -> float:
    if chi_square <= 0.0:
        return 1.0
    half_x = chi_square / 2.0
    q_half = math.erfc(half_x ** 0.5)
    q_three_halves = q_half + (half_x ** 0.5) * math.exp(-half_x) / (0.5 * math.gamma(0.5))
    q_five_halves = q_three_halves + (half_x ** 1.5) * math.exp(-half_x) / (1.5 * math.gamma(1.5))
    return max(0.0, min(1.0, q_five_halves))


def _target_threat_piece_ids(state: GameState, player) -> set[int]:
    threat_piece_ids: set[int] = set()
    target = target_corner(player)
    for dice in range(1, 7):
        for move in state.legal_moves(player, dice):
            if move.to_pos == target:
                threat_piece_ids.add(move.piece_id)
    return threat_piece_ids


def _capturable_threat_piece_ids(state: GameState, *, dice: int, mover, threat_player, threat_piece_ids: set[int]) -> set[int]:
    capturable: set[int] = set()
    for move in state.legal_moves(mover, dice):
        captured = move.captured_piece
        if (
            captured is not None
            and captured.player is threat_player
            and captured.piece_id in threat_piece_ids
        ):
            capturable.add(captured.piece_id)
    return capturable


def _threat_capture_probability(state: GameState, *, mover, threat_player, threat_piece_ids: set[int]) -> float:
    hit_dice = 0
    for dice in range(1, 7):
        if _capturable_threat_piece_ids(
            state,
            dice=dice,
            mover=mover,
            threat_player=threat_player,
            threat_piece_ids=threat_piece_ids,
        ):
            hit_dice += 1
    return hit_dice / 6.0

def chi_square_uniform(counts: dict[int, int]) -> dict[str, float | int | None]:
    observed = [int(counts.get(dice, 0)) for dice in range(1, 7)]
    n = sum(observed)
    if n == 0:
        return {
            "n": 0,
            "df": 5,
            "chi_square": 0.0,
            "p_value": None,
            "cramers_v": None,
        }
    expected = n / 6.0
    chi_square = sum((count - expected) ** 2 / expected for count in observed)
    return {
        "n": n,
        "df": 5,
        "chi_square": chi_square,
        "p_value": _chi_square_df5_survival(chi_square),
        "cramers_v": (chi_square / (n * 5)) ** 0.5,
    }


def threat_coincidence_summary(records: Iterable[GameRecord]) -> dict[str, float | int | None]:
    opponent_target_threat_steps = 0
    dice_capture_opportunity_steps = 0
    chosen_capture_steps = 0
    expected_probability_total = 0.0

    for record in records:
        state = GameState.deserialize(record.initial_state)
        for step in record.steps:
            mover = step.player
            threat_player = mover.opponent
            threat_piece_ids = _target_threat_piece_ids(state, threat_player)
            if threat_piece_ids:
                opponent_target_threat_steps += 1
                expected_probability_total += _threat_capture_probability(
                    state,
                    mover=mover,
                    threat_player=threat_player,
                    threat_piece_ids=threat_piece_ids,
                )
                capturable = _capturable_threat_piece_ids(
                    state,
                    dice=step.dice,
                    mover=mover,
                    threat_player=threat_player,
                    threat_piece_ids=threat_piece_ids,
                )
                if capturable:
                    dice_capture_opportunity_steps += 1
                occupant = state.piece_at(step.move.to_pos)
                if (
                    occupant is not None
                    and occupant.player is threat_player
                    and occupant.piece_id in threat_piece_ids
                ):
                    chosen_capture_steps += 1
            state.apply_move(step.move, dice=step.dice)

    actual_dice_hit_rate = (
        dice_capture_opportunity_steps / opponent_target_threat_steps
        if opponent_target_threat_steps
        else 0.0
    )
    chosen_capture_rate = (
        chosen_capture_steps / opponent_target_threat_steps
        if opponent_target_threat_steps
        else 0.0
    )
    expected_dice_hit_probability = (
        expected_probability_total / opponent_target_threat_steps
        if opponent_target_threat_steps
        else 0.0
    )
    effect_ratio = (
        actual_dice_hit_rate / expected_dice_hit_probability
        if expected_dice_hit_probability > 0.0
        else None
    )
    return {
        "opponent_target_threat_steps": opponent_target_threat_steps,
        "dice_capture_opportunity_steps": dice_capture_opportunity_steps,
        "chosen_capture_steps": chosen_capture_steps,
        "actual_dice_hit_rate": actual_dice_hit_rate,
        "chosen_capture_rate": chosen_capture_rate,
        "expected_dice_hit_probability": expected_dice_hit_probability,
        "dice_hit_effect_ratio": effect_ratio,
    }


def summarize_forensics(records: Iterable[GameRecord]) -> dict[str, Any]:
    record_list = list(records)
    grouped = count_dice_by_source(record_list)
    return {
        "sample_note": (
            "MoveRecord.source is move-entry provenance, not an independent dice-source field; "
            "treat grouped dice counts as source-segmented replay audit only."
        ),
        "dice_by_source": grouped,
        "uniformity_by_source": {
            source: chi_square_uniform(counts) for source, counts in grouped.items()
        },
        "target_threat_coincidence": threat_coincidence_summary(record_list),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit dice sequences in saved replay JSON files.")
    parser.add_argument("paths", nargs="+", help="GameRecord or MatchRecord JSON files")
    args = parser.parse_args(argv)

    print(json.dumps(summarize_forensics(load_records(args.paths)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
