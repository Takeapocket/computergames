from __future__ import annotations

import json

from core.game_state import GameState
from core.types import Player, Position
from scripts import analyze_rollout_failures


def test_move_wins_immediately_detects_goal_corner() -> None:
    state = GameState.from_layout(
        red={6: Position(3, 3)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    move = next(move for move in state.legal_moves(Player.RED, 6) if move.to_pos == Position(4, 4))

    assert analyze_rollout_failures.move_wins_immediately(state, move, 6) is True


def test_opponent_direct_win_dice_after_move_detects_allowed_loss() -> None:
    state = GameState.from_layout(
        red={6: Position(2, 2)},
        blue={1: Position(1, 1)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]

    dice_set = analyze_rollout_failures.opponent_direct_win_dice_after_move(state, move, 6)

    assert isinstance(dice_set, list)


def test_bucket_loss_tags_counts_known_labels() -> None:
    steps = [
        {
            "subject_player": "red",
            "subject_to_move": True,
            "exists_direct_win": True,
            "chosen_direct_win": False,
            "allowed_direct_loss_dice": [],
            "low_confidence": False,
            "timed_out": False,
            "used_fallback": False,
            "self_capture": False,
            "score_margin": 0.2,
        }
    ]

    buckets = analyze_rollout_failures.bucket_loss_tags(steps, subject_player=Player.RED)

    assert buckets["missed_direct_win"] == 1
    assert buckets["unclassified"] == 0


def test_write_reports_mentions_attribution_not_causation(tmp_path) -> None:
    payload = {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": "greedy_risk",
        "games": 1,
        "seed_pool": [27016],
        "summary": {"subject_wins": 0, "subject_losses": 1, "illegal_moves": 0, "crashes": 0, "timeouts": 0},
        "failure_buckets": {
            "missed_direct_win": 1,
            "allowed_direct_loss": 0,
            "low_confidence_loss": 0,
            "timeout_or_fallback": 0,
            "bad_self_capture": 0,
            "opening_side_bias": 0,
            "material_race_loss": 0,
            "unclassified": 0,
        },
        "examples": [],
        "command": "python scripts/analyze_rollout_failures.py --games 1",
        "default_layout": "balanced_v1",
    }
    md_path = tmp_path / "analysis.md"
    json_path = tmp_path / "analysis.json"

    analyze_rollout_failures.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["games"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "标签是归因线索，不是因果证明" in markdown
    assert "默认 AI、默认布局、release 配置未变" in markdown


def test_parse_seed_pool_rejects_empty_value() -> None:
    try:
        analyze_rollout_failures._parse_seed_pool("")
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("expected empty seed pool to fail")
