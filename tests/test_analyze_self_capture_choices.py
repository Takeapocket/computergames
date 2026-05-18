from __future__ import annotations

import json
import random

import pytest

from ai.rollout_ai import RootMoveStats
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from scripts import analyze_self_capture_choices as audit


class _FixedDice:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)
        self.index = 0

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (1, 6)
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value


class _FixedAI:
    def __init__(self, move: Move | None, root_stats: list[RootMoveStats] | None = None) -> None:
        self.name = "fixed"
        self.move = move
        self.last_root_stats = root_stats or []
        self.last_low_confidence = False
        self.last_timed_out = False
        self.last_used_fallback = False
        self.last_score_margin = 0.05

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        return self.move


def make_state(red=None, blue=None, current_player=Player.RED) -> GameState:
    return GameState.from_layout(
        red=red or {},
        blue=blue or {},
        current_player=current_player,
    )


def move_to(state: GameState, row: int, col: int, *, dice: int = 1) -> Move:
    return next(move for move in state.legal_moves(state.current_player, dice) if move.to_pos == Position(row, col))


def stats(move: Move, score: float, *, visits: int = 8) -> RootMoveStats:
    return RootMoveStats(
        move=move,
        visits=visits,
        wins=score * visits,
        losses=(1.0 - score) * visits,
        draws=0.0,
        cutoffs=0.0,
        score=score,
        winrate=score,
        avg=2 * score - 1,
    )


def test_audit_subject_choice_records_self_capture_alternatives_and_margin() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    non_self = move_to(state, 3, 2)
    root_stats = [stats(self_capture, 0.80), stats(enemy_capture, 0.77), stats(non_self, 0.70)]

    row = audit.audit_subject_choice(
        state=state,
        dice=1,
        chosen=self_capture,
        root_stats=root_stats,
        game_index=0,
        turn=0,
        subject_player=Player.RED,
    )

    assert row["chosen_self_capture"] is True
    assert row["chosen_enemy_capture"] is False
    assert row["own_alive_before"] == 3
    assert row["own_alive_after"] == 2
    assert row["enemy_capture_alt_available"] is True
    assert row["non_self_alt_available"] is True
    assert row["chosen_score"] == 0.80
    assert row["best_alternative_score_margin"] == pytest.approx(0.03)
    assert row["enemy_capture_alternatives"][0]["root_score"] == 0.77
    assert row["non_self_alternatives"][0]["root_score"] == 0.77


def test_summarize_games_counts_self_capture_loss_once_per_game() -> None:
    self_capture_step = {
        "subject_to_move": True,
        "chosen_self_capture": True,
        "chosen_direct_win": False,
        "enemy_capture_alt_available": True,
        "non_self_alt_available": True,
        "own_alive_after": 2,
        "best_alternative_score_margin": 0.03,
    }
    non_self_step = {
        "subject_to_move": True,
        "chosen_self_capture": False,
        "chosen_direct_win": False,
        "enemy_capture_alt_available": True,
        "non_self_alt_available": True,
        "own_alive_after": 3,
        "best_alternative_score_margin": None,
    }
    summary, examples = audit.summarize_games(
        [
            {
                "subject_won": False,
                "illegal_moves": 0,
                "crashes": 0,
                "timeouts": 0,
                "subject_steps": [self_capture_step, self_capture_step, non_self_step],
            },
            {
                "subject_won": True,
                "illegal_moves": 0,
                "crashes": 0,
                "timeouts": 0,
                "subject_steps": [non_self_step],
            },
        ],
        max_examples=20,
    )

    assert summary["games"] == 2
    assert summary["subject_wins"] == 1
    assert summary["subject_losses"] == 1
    assert summary["total_subject_moves"] == 4
    assert summary["chosen_self_capture"] == 2
    assert summary["chosen_self_capture_rate"] == 0.5
    assert summary["chosen_self_capture_with_enemy_capture_alt"] == 2
    assert summary["chosen_self_capture_when_own_alive_le_3"] == 2
    assert summary["chosen_self_capture_when_own_alive_le_2"] == 2
    assert summary["losses_with_self_capture"] == 1
    assert "self_capture_losses" not in summary
    assert summary["enemy_capture_alt_available"] == 4
    assert summary["avg_score_margin_when_self_capture"] == pytest.approx(0.03)
    assert len(examples) == 2


def test_analyze_one_game_classifies_none_move_without_illegal() -> None:
    result = audit.analyze_one_game(
        subject_player=Player.RED,
        subject_ai=_FixedAI(None),
        opponent_ai=_FixedAI(None),
        dice_rng=_FixedDice([1]),
        layout="balanced_v1",
        max_turns=1,
    )

    assert result["termination_reason"] == "no_move"
    assert result["illegal_moves"] == 0
    assert result["subject_won"] is False


def test_parse_seed_pool_rejects_empty_value() -> None:
    with pytest.raises(ValueError):
        audit.parse_seed_pool(" , ")


def test_analyze_games_uses_release_default_kwargs_for_rollout_opponent(monkeypatch) -> None:
    calls = []

    def fake_build_ai(kind, *, seed=None, **kwargs):
        calls.append((kind, seed, kwargs))
        return object()

    def fake_analyze_one_game(**kwargs):
        return {
            "subject_won": True,
            "subject_steps": [],
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
        }

    monkeypatch.setattr(audit, "build_ai", fake_build_ai)
    monkeypatch.setattr(audit, "analyze_one_game", fake_analyze_one_game)

    audit.analyze_games(
        games=1,
        seed_pool=[2026],
        opponent="rollout",
        layout="balanced_v1",
        max_turns=1,
    )

    expected = audit.load_release_default_rollout_kwargs()
    assert calls[0][0] == "rollout"
    assert calls[0][2] == expected
    assert calls[1][0] == "rollout"
    assert calls[1][2] == expected


def test_write_reports_mentions_audit_not_promotion_evidence(tmp_path) -> None:
    payload = {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": "greedy_risk",
        "games": 1,
        "seed_pool": [31026],
        "default_layout": "balanced_v1",
        "summary": {
            "games": 1,
            "subject_wins": 0,
            "subject_losses": 1,
            "total_subject_moves": 0,
            "chosen_self_capture": 0,
            "chosen_self_capture_rate": 0.0,
            "chosen_self_capture_with_enemy_capture_alt": 0,
            "chosen_self_capture_with_non_self_alt": 0,
            "chosen_self_capture_when_own_alive_le_3": 0,
            "chosen_self_capture_when_own_alive_le_2": 0,
            "self_capture_direct_win_count": 0,
            "losses_with_self_capture": 0,
            "enemy_capture_alt_available": 0,
            "non_self_alt_available": 0,
            "avg_score_margin_when_self_capture": None,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
        },
        "examples": [],
        "command": "python scripts/analyze_self_capture_choices.py",
    }
    output = tmp_path / "audit.md"
    json_output = tmp_path / "audit.json"

    audit.write_reports(payload, output, json_output)

    text = output.read_text(encoding="utf-8")
    assert "不是 promotion evidence" in text
    assert "默认 AI、默认布局、release 配置未变" in text
    json_text = json_output.read_text(encoding="utf-8")
    assert json_text.endswith("\n")
    assert json.loads(json_text)["summary"]["games"] == 1
