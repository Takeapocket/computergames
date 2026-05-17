import random
from collections import Counter

import pytest

from ai.chance_rerank import ExactOpponentDiceRerankAI, exact_opp1_zdp_value
from ai.rollout_ai import RootMoveStats
from core.game_state import GameState
from core.types import Player, Position


def _state_with_three_red_moves() -> GameState:
    return GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )


def _stats(move, score: float, visits: int = 8) -> RootMoveStats:
    wins = score * visits
    losses = visits - wins
    return RootMoveStats(
        move=move,
        visits=visits,
        wins=wins,
        losses=losses,
        draws=0.0,
        cutoffs=0.0,
        score=score,
        winrate=wins / visits,
        avg=2 * score - 1,
    )


class _FakeBase:
    name = "fake_base"

    def __init__(self, move=None, stats=None):
        self.move = move
        self.last_root_stats = list(stats or [])

    def choose_move(self, state, dice):
        return self.move


def test_exact_opp1_rerank_returns_none_when_base_returns_none() -> None:
    state = _state_with_three_red_moves()
    ai = ExactOpponentDiceRerankAI(base=_FakeBase(move=None), rng=random.Random(1))

    assert ai.choose_move(state, 1) is None
    assert ai.fire_counts["passthrough_base_none"] == 1


def test_exact_opp1_rerank_passthrough_when_base_has_no_root_stats() -> None:
    state = _state_with_three_red_moves()
    base_move = state.legal_moves(Player.RED, 1)[0]
    ai = ExactOpponentDiceRerankAI(base=_FakeBase(move=base_move), rng=random.Random(1))

    assert ai.choose_move(state, 1) == base_move
    assert ai.fire_counts["passthrough_no_stats"] == 1


def test_exact_opp1_rerank_selects_topk_move_when_mixed_score_improves(monkeypatch) -> None:
    state = _state_with_three_red_moves()
    legal = state.legal_moves(Player.RED, 1)
    base_move, better_exact_move = legal[0], legal[2]
    base = _FakeBase(
        move=base_move,
        stats=[
            _stats(base_move, 0.70),
            _stats(legal[1], 0.60),
            _stats(better_exact_move, 0.65),
        ],
    )
    exact_values = {
        base_move: 0.40,
        legal[1]: 0.40,
        better_exact_move: 1.00,
    }
    monkeypatch.setattr(
        "ai.chance_rerank.exact_opp1_zdp_value",
        lambda state, dice, move, perspective: exact_values[move],
    )
    ai = ExactOpponentDiceRerankAI(base=base, exact_mix=0.35, top_k=3, rng=random.Random(1))

    assert ai.choose_move(state, 1) == better_exact_move
    assert ai.fire_counts["considered"] == 1
    assert ai.fire_counts["applied"] == 1


def test_exact_opp1_rerank_keeps_base_when_exact_score_does_not_flip_choice(monkeypatch) -> None:
    state = _state_with_three_red_moves()
    legal = state.legal_moves(Player.RED, 1)
    base_move, alt_move = legal[0], legal[2]
    base = _FakeBase(
        move=base_move,
        stats=[
            _stats(base_move, 0.70),
            _stats(alt_move, 0.65),
        ],
    )
    exact_values = {base_move: 0.70, alt_move: 0.71}
    monkeypatch.setattr(
        "ai.chance_rerank.exact_opp1_zdp_value",
        lambda state, dice, move, perspective: exact_values[move],
    )
    ai = ExactOpponentDiceRerankAI(base=base, exact_mix=0.35, top_k=2, rng=random.Random(1))

    assert ai.choose_move(state, 1) == base_move
    assert ai.fire_counts == Counter({"considered": 1, "passthrough_no_change": 1})


def test_exact_opp1_zdp_value_counts_opponent_direct_win_as_zero() -> None:
    state = GameState.from_layout(
        red={1: Position(2, 2)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    root_move = state.legal_moves(Player.RED, 1)[0]

    assert exact_opp1_zdp_value(state, 1, root_move, Player.RED) == 0.0


def test_exact_opp1_zdp_value_counts_opponent_no_move_as_win(monkeypatch) -> None:
    class _FakeSim:
        def apply_move(self, move, dice):
            return move

        def get_winner(self):
            return None

        def legal_moves(self, player, dice):
            return []

    state = _state_with_three_red_moves()
    root_move = state.legal_moves(Player.RED, 1)[0]
    monkeypatch.setattr("ai.chance_rerank.GameState.deserialize", lambda data: _FakeSim())

    assert exact_opp1_zdp_value(state, 1, root_move, Player.RED) == 1.0


def test_exact_opp1_rerank_returns_legal_move_without_mutating_state(monkeypatch) -> None:
    state = _state_with_three_red_moves()
    before = state.serialize()
    legal = state.legal_moves(Player.RED, 1)
    base = _FakeBase(move=legal[0], stats=[_stats(move, 0.5) for move in legal])
    monkeypatch.setattr(
        "ai.chance_rerank.exact_opp1_zdp_value",
        lambda state, dice, move, perspective: 1.0 if move == legal[-1] else 0.0,
    )
    ai = ExactOpponentDiceRerankAI(base=base, exact_mix=1.0, top_k=3, rng=random.Random(1))

    move = ai.choose_move(state, 1)

    assert move in legal
    assert state.serialize() == before
