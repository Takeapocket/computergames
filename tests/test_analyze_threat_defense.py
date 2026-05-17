from __future__ import annotations

import json
from dataclasses import replace

from ai.rollout_ai import RootMoveStats
from core.game_state import GameState
from core.types import Player, Position
from scripts import analyze_threat_defense


class _FixedDice:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, lower: int, upper: int) -> int:
        return self.value


class _NoneMoveAI:
    def choose_move(self, state, dice):
        return None


class _CrashingTimeoutAI:
    max_step_time_ms = -1.0

    def choose_move(self, state, dice):
        raise RuntimeError("boom")


def test_opponent_winning_dice_after_move_detects_goal_threat() -> None:
    state = GameState.from_layout(
        red={6: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]

    dice_set = analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert dice_set == [1, 2, 3]


def test_opponent_winning_dice_after_move_restores_state() -> None:
    state = GameState.from_layout(
        red={6: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    before = state.serialize()
    move = state.legal_moves(Player.RED, 6)[0]

    analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert state.serialize() == before


def test_opponent_winning_dice_after_move_terminal_win_has_no_opponent_turn() -> None:
    state = GameState.from_layout(
        red={6: Position(3, 4)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    move = next(move for move in state.legal_moves(Player.RED, 6) if move.to_pos == Position(4, 4))

    dice_set = analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert dice_set == []


def test_move_identity_is_stable_for_equivalent_moves() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={6: Position(4, 4)},
        current_player=Player.RED,
    )
    first = state.legal_moves(Player.RED, 1)[0]
    second = replace(first)

    assert analyze_threat_defense.move_identity(first) == analyze_threat_defense.move_identity(second)


def test_root_stats_index_uses_sorted_rank_by_score() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={6: Position(4, 4)},
        current_player=Player.RED,
    )
    moves = state.legal_moves(Player.RED, 1)
    stats = [
        RootMoveStats(
            moves[0],
            visits=4,
            wins=1,
            losses=3,
            draws=0,
            cutoffs=0,
            score=-0.2,
            winrate=0.25,
            avg=-0.2,
        ),
        RootMoveStats(
            moves[1],
            visits=4,
            wins=3,
            losses=1,
            draws=0,
            cutoffs=0,
            score=0.5,
            winrate=0.75,
            avg=0.5,
        ),
    ]

    index = analyze_threat_defense.root_stats_index(stats)

    assert index[analyze_threat_defense.move_identity(moves[1])]["rank"] == 1
    assert index[analyze_threat_defense.move_identity(moves[0])]["rank"] == 2


def test_score_margin_bucket_boundaries() -> None:
    assert analyze_threat_defense.score_margin_bucket(None) == ">0.08_or_null"
    assert analyze_threat_defense.score_margin_bucket(0.01) == "<=0.02"
    assert analyze_threat_defense.score_margin_bucket(0.03) == "(0.02,0.04]"
    assert analyze_threat_defense.score_margin_bucket(0.08) == "(0.04,0.08]"
    assert analyze_threat_defense.score_margin_bucket(0.09) == ">0.08_or_null"


def test_audit_position_finds_full_block_alternative() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(Player.RED, 1)
    chosen = next(move for move in legal if (move.to_pos.row, move.to_pos.col) == (1, 0))
    root_stats = [
        RootMoveStats(
            move,
            visits=4,
            wins=2,
            losses=2,
            draws=0,
            cutoffs=0,
            score=0.1 - index * 0.01,
            winrate=0.5,
            avg=0.0,
        )
        for index, move in enumerate(legal)
    ]

    position = analyze_threat_defense.audit_position(
        state=state,
        dice=1,
        chosen=chosen,
        root_stats=root_stats,
        low_confidence=True,
        score_margin=0.03,
        game_index=0,
        turn=3,
        subject_player=Player.RED,
        failure_tags=["allowed_direct_loss", "low_confidence_loss"],
        top_k=5,
    )

    assert position["chosen"]["opponent_winning_dice_count"] >= 1
    assert position["threat_reducing_alternative_exists"] is True
    assert position["best_threat_count"] == 0
    assert position["full_block_alternative_exists"] is True
    assert position["score_margin_bucket"] == "(0.02,0.04]"


def test_summarize_positions_counts_low_confidence_and_self_capture() -> None:
    positions = [
        {
            "low_confidence": True,
            "score_margin_bucket": "<=0.02",
            "threat_reducing_alternative_exists": True,
            "full_block_alternative_exists": True,
            "best_threat_reducing_rank": 2,
            "chosen": {"opponent_winning_dice_count": 2, "self_capture": True},
            "best_threat_count": 0,
        },
        {
            "low_confidence": False,
            "score_margin_bucket": ">0.08_or_null",
            "threat_reducing_alternative_exists": False,
            "full_block_alternative_exists": False,
            "best_threat_reducing_rank": None,
            "chosen": {"opponent_winning_dice_count": 0, "self_capture": False},
            "best_threat_count": 0,
        },
    ]

    summary = analyze_threat_defense.summarize_positions(positions, top_k=5)

    assert summary["threat_defense"]["chosen_allowed_direct_loss_positions"] == 1
    assert summary["threat_defense"]["threat_reducing_alternative_positions"] == 1
    assert summary["low_confidence"]["positions"] == 1
    assert summary["low_confidence"]["with_threat_reducing_alternative"] == 1
    assert summary["low_confidence"]["threat_reducing_ratio"] == 1.0
    assert summary["self_capture_correlation"]["self_capture_and_allowed_direct_loss"] == 1
    assert summary["score_margin_buckets"]["<=0.02"]["positions"] == 1
    assert summary["top_k"]["best_threat_reducing_in_top_k"] == 1


def test_select_examples_keeps_key_threat_defense_cases() -> None:
    quiet_position = {
        "game_index": 1,
        "turn": 1,
        "dice": 1,
        "low_confidence": False,
        "threat_reducing_alternative_exists": False,
        "chosen": {"opponent_winning_dice_count": 0},
        "best_threat_count": 0,
    }
    threat_reducing_position = {
        "game_index": 2,
        "turn": 4,
        "dice": 5,
        "low_confidence": False,
        "threat_reducing_alternative_exists": True,
        "chosen": {"opponent_winning_dice_count": 2},
        "best_threat_count": 0,
    }
    low_confidence_threat_position = {
        "game_index": 3,
        "turn": 7,
        "dice": 6,
        "low_confidence": True,
        "threat_reducing_alternative_exists": True,
        "chosen": {"opponent_winning_dice_count": 1},
        "best_threat_count": 0,
    }

    examples = analyze_threat_defense.select_examples(
        [quiet_position, threat_reducing_position, low_confidence_threat_position],
        max_examples=1,
    )

    assert examples["threat_reducing_examples"] == [threat_reducing_position]
    assert examples["low_confidence_threat_reducing_examples"] == [low_confidence_threat_position]
    assert examples["allowed_direct_loss_examples"] == [threat_reducing_position]


def test_decide_supports_threat_rerank_when_ratios_are_strong() -> None:
    summary = {
        "low_confidence": {
            "positions": 40,
            "with_threat_reducing_alternative": 12,
            "threat_reducing_ratio": 0.30,
            "best_threat_reducing_in_top_k_ratio": 8 / 12,
        },
        "top_k": {
            "threat_reducing_positions": 12,
            "best_threat_reducing_in_top_k": 8,
            "best_threat_reducing_in_top_k_ratio": 8 / 12,
        },
    }

    decision = analyze_threat_defense.decide_supports_threat_rerank(summary)

    assert decision["supports_threat_rerank_candidate"] is True


def test_decide_rejects_threat_rerank_when_low_confidence_sample_is_small() -> None:
    summary = {
        "low_confidence": {
            "positions": 10,
            "with_threat_reducing_alternative": 8,
            "threat_reducing_ratio": 0.80,
            "best_threat_reducing_in_top_k_ratio": 1.0,
        },
        "top_k": {
            "threat_reducing_positions": 8,
            "best_threat_reducing_in_top_k": 8,
            "best_threat_reducing_in_top_k_ratio": 1.0,
        },
    }

    decision = analyze_threat_defense.decide_supports_threat_rerank(summary)

    assert decision["supports_threat_rerank_candidate"] is False
    assert any("low_confidence positions" in reason for reason in decision["reasons"])


def test_write_reports_mentions_defaults_unchanged(tmp_path) -> None:
    payload = {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": "greedy_risk",
        "games": 1,
        "seed_pool": [28016],
        "default_layout": "balanced_v1",
        "analysis_window": {
            "subject_losses_only": True,
            "subject_to_move_only": True,
            "score_margin": 0.08,
            "top_k": 5,
        },
        "summary": {
            "subject_wins": 0,
            "subject_losses": 1,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "audited_positions": 0,
        },
        "threat_defense": {
            "chosen_allowed_direct_loss_positions": 0,
            "threat_reducing_alternative_positions": 0,
            "full_block_alternative_positions": 0,
            "partial_reduction_alternative_positions": 0,
            "average_chosen_threat_count": 0.0,
            "average_best_alternative_threat_count": 0.0,
            "average_reduction_when_available": 0.0,
        },
        "low_confidence": {
            "positions": 0,
            "with_allowed_direct_loss": 0,
            "with_threat_reducing_alternative": 0,
            "with_full_block_alternative": 0,
            "threat_reducing_ratio": 0.0,
            "full_block_ratio": 0.0,
        },
        "self_capture_correlation": {
            "self_capture_positions": 0,
            "self_capture_and_allowed_direct_loss": 0,
            "non_self_capture_positions": 0,
            "non_self_capture_and_allowed_direct_loss": 0,
            "allowed_direct_loss_rate_given_self_capture": 0.0,
            "allowed_direct_loss_rate_given_non_self_capture": 0.0,
            "self_capture_with_threat_reducing_alternative": 0,
            "self_capture_with_full_block_alternative": 0,
        },
        "score_margin_buckets": {
            bucket: {"positions": 0, "with_threat_reducing_alternative": 0}
            for bucket in analyze_threat_defense.MARGIN_BUCKETS
        },
        "top_k": {
            "threat_reducing_positions": 0,
            "best_threat_reducing_in_top_k": 0,
            "best_threat_reducing_in_top_k_ratio": 0.0,
        },
        "positions": [],
        "examples": {
            "threat_reducing_examples": [
                {
                    "game_index": 4,
                    "turn": 8,
                    "dice": 6,
                    "low_confidence": False,
                    "threat_reducing_alternative_exists": True,
                    "chosen": {"opponent_winning_dice_count": 2},
                    "best_threat_count": 0,
                }
            ],
            "low_confidence_threat_reducing_examples": [
                {
                    "game_index": 5,
                    "turn": 9,
                    "dice": 1,
                    "low_confidence": True,
                    "threat_reducing_alternative_exists": True,
                    "chosen": {"opponent_winning_dice_count": 1},
                    "best_threat_count": 0,
                }
            ],
            "allowed_direct_loss_examples": [
                {
                    "game_index": 6,
                    "turn": 10,
                    "dice": 2,
                    "low_confidence": False,
                    "threat_reducing_alternative_exists": False,
                    "chosen": {"opponent_winning_dice_count": 1},
                    "best_threat_count": 1,
                }
            ],
        },
        "decision": {
            "supports_threat_rerank_candidate": False,
            "reasons": ["low_confidence positions 0 < 30"],
        },
        "command": "python scripts/analyze_threat_defense.py --games 1",
    }
    md_path = tmp_path / "p8.md"
    json_path = tmp_path / "p8.json"

    analyze_threat_defense.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["games"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "默认 AI、默认布局、release 配置未变" in markdown
    assert "threat-reducing alternative" in markdown
    assert "rollout_threat_rerank" in markdown
    assert "Threat-reducing Examples" in markdown
    assert "Low-confidence Threat-reducing Examples" in markdown
    assert "Allowed Direct-loss Examples" in markdown
    assert "game=4 turn=8 dice=6 chosen_threat=2 best_threat=0" in markdown


def test_main_writes_smoke_reports(tmp_path) -> None:
    md_path = tmp_path / "p8_smoke.md"
    json_path = tmp_path / "p8_smoke.json"

    exit_code = analyze_threat_defense.main(
        [
            "--games",
            "2",
            "--seed-pool",
            "28016",
            "--opponent",
            "greedy_risk",
            "--starting-layout",
            "balanced_v1",
            "--max-turns",
            "30",
            "--max-examples",
            "3",
            "--output",
            str(md_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert md_path.exists()
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["subject"]["ai"] == "rollout"
    assert payload["default_layout"] == "balanced_v1"
    assert "decision" in payload
    assert set(payload["examples"]) == {
        "threat_reducing_examples",
        "low_confidence_threat_reducing_examples",
        "allowed_direct_loss_examples",
    }


def test_analyze_one_game_classifies_none_move_as_no_move_not_illegal() -> None:
    result = analyze_threat_defense.analyze_one_game(
        subject_player=Player.RED,
        subject_ai=_NoneMoveAI(),
        opponent_ai=_NoneMoveAI(),
        dice_rng=_FixedDice(1),
        layout="balanced_v1",
        max_turns=1,
        top_k=5,
    )

    assert result["termination_reason"] == "no_move"
    assert result["illegal_moves"] == 0


def test_analyze_one_game_counts_crash_timeout_like_match_harness() -> None:
    result = analyze_threat_defense.analyze_one_game(
        subject_player=Player.RED,
        subject_ai=_CrashingTimeoutAI(),
        opponent_ai=_NoneMoveAI(),
        dice_rng=_FixedDice(1),
        layout="balanced_v1",
        max_turns=1,
        top_k=5,
    )

    assert result["termination_reason"] == "crash"
    assert result["crashes"] == 1
    assert result["timeouts"] == 1


def test_default_report_paths_are_repo_relative() -> None:
    args = analyze_threat_defense.build_parser().parse_args([])

    assert args.output == analyze_threat_defense.ROOT / "reports/p8_threat_defense_audit_20260517.md"
    assert args.json_output == analyze_threat_defense.ROOT / "reports/p8_threat_defense_audit_20260517.json"
