import random

from ai.match import default_starting_state
from ai.rollout_ai import RolloutAI
from core.game_state import GameState
from core.types import Player, Position


def test_rollout_ai_returns_legal_move():
    state = default_starting_state()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)


def test_rollout_ai_deadline_safety_ms_reduces_internal_deadline(monkeypatch):
    state = default_starting_state()
    seen_deadlines = []

    def fake_sample(score, **kwargs):
        seen_deadlines.append(kwargs["deadline"])
        score.record_cutoff(0.5)
        return False

    monkeypatch.setattr("ai.rollout_ai.time.perf_counter", lambda: 100.0)
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=100.0,
        deadline_safety_ms=30.0,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    ai.choose_move(state, 6)

    assert seen_deadlines
    assert all(abs(deadline - 100.07) < 1e-9 for deadline in seen_deadlines)


def test_rollout_ai_cutoff_eval_zweistein_uses_zweistein_score(monkeypatch):
    state = default_starting_state()
    monkeypatch.setattr(
        "ai.rollout_ai.zweistein_lite_score",
        lambda state, perspective: 12.0,
        raising=False,
    )
    ai = RolloutAI(cutoff_eval="zweistein", rng=random.Random(1))

    assert ai._cutoff_score(state, Player.RED) == 1.0

    monkeypatch.setattr("ai.rollout_ai.zweistein_lite_score", lambda state, perspective: -12.0)
    assert ai._cutoff_score(state, Player.RED) == 0.0

    monkeypatch.setattr("ai.rollout_ai.zweistein_lite_score", lambda state, perspective: 0.0)
    assert ai._cutoff_score(state, Player.RED) == 0.5


def test_rollout_ai_records_candidate_diagnostics():
    state = GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(2, 2),
            3: Position(1, 4),
            4: Position(1, 0),
            5: Position(2, 1),
            6: Position(2, 0),
        },
        blue={
            4: Position(3, 3),
            5: Position(3, 2),
            6: Position(3, 1),
        },
        current_player=Player.RED,
    )
    ai = RolloutAI(rollouts_per_move=3, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    move = ai.choose_move(state, 5)

    legal = state.legal_moves(state.current_player, 5)
    assert move in legal
    assert [stats.move for stats in ai.last_root_stats] == legal
    assert [diagnostic.move for diagnostic in ai.last_diagnostics] == legal
    assert all(stats.visits == 3 for stats in ai.last_root_stats)
    assert all(0.0 <= stats.winrate <= 1.0 for stats in ai.last_root_stats)
    assert all(0.0 <= stats.score <= 1.0 for stats in ai.last_root_stats)
    assert all(stats.avg == 2 * stats.score - 1 for stats in ai.last_root_stats)
    assert all(stats.draws == stats.cutoffs for stats in ai.last_root_stats)
    assert all(
        stats.visits == stats.wins + stats.losses + stats.draws
        for stats in ai.last_root_stats
    )
    assert all(diagnostic.visits == 3 for diagnostic in ai.last_diagnostics)
    assert all(0.0 <= diagnostic.winrate <= 1.0 for diagnostic in ai.last_diagnostics)
    assert all(0.0 <= diagnostic.score <= 1.0 for diagnostic in ai.last_diagnostics)
    assert all(diagnostic.avg == 2 * diagnostic.score - 1 for diagnostic in ai.last_diagnostics)
    assert all(
        diagnostic.visits == diagnostic.wins + diagnostic.losses + diagnostic.cutoffs
        for diagnostic in ai.last_diagnostics
    )


def test_rollout_ai_adds_samples_for_close_candidates():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(2, 2), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )
    ai = RolloutAI(
        rollouts_per_move=1,
        close_sample_margin=1.0,
        close_sample_rollouts_per_move=3,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 5)

    assert move in state.legal_moves(state.current_player, 5)
    assert ai.last_diagnostics
    assert all(diagnostic.visits == 3 for diagnostic in ai.last_diagnostics)


def test_rollout_ai_marks_low_confidence_when_candidates_remain_close():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(2, 2), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )
    ai = RolloutAI(
        rollouts_per_move=1,
        close_sample_margin=1.0,
        close_sample_rollouts_per_move=2,
        low_confidence_margin=0.08,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    ai.choose_move(state, 5)

    assert ai.last_score_margin == 0.0
    assert ai.last_low_confidence is True
    assert ai.last_root_stats
    assert all(stats.low_confidence for stats in ai.last_root_stats)


def test_rollout_ai_timeout_during_close_sampling_returns_current_best(monkeypatch):
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(2, 2), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )
    ai = RolloutAI(
        rollouts_per_move=1,
        close_sample_margin=1.0,
        close_sample_rollouts_per_move=2,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    def fake_sample(score, **kwargs):
        destination = (score.move.to_pos.row, score.move.to_pos.col)
        if score.visits == 0:
            score.visits = 1
            score.wins = {
                (3, 1): 0.60,
                (2, 2): 0.55,
                (3, 2): 0.10,
            }[destination]
            return False
        if destination == (3, 1):
            score.visits = 2
            score.wins = 1.20
            return False
        if destination == (2, 2):
            score.visits = 2
            score.wins = 1.40
            return True
        return False

    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    move = ai.choose_move(state, 5)

    assert move is not None
    assert move.to_pos == Position(2, 2)


def test_rollout_ai_does_not_mutate_state():
    state = default_starting_state()
    before = state.serialize()
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    ai.choose_move(state, 6)

    assert state.serialize() == before


def test_rollout_ai_is_deterministic_with_same_seed():
    state_a = default_starting_state()
    state_b = default_starting_state()
    ai_a = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))
    ai_b = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(7))

    assert ai_a.choose_move(state_a, 6) == ai_b.choose_move(state_b, 6)


def test_rollout_ai_returns_none_when_no_legal_moves():
    state = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    ai = RolloutAI(rollouts_per_move=2, max_rollout_turns=6, max_step_time_ms=1000, rng=random.Random(1))

    assert ai.choose_move(state, 1) is None
    assert ai.last_root_stats == []
    assert ai.last_diagnostics == []


def test_rollout_ai_timeout_fallback_returns_legal_move():
    state = default_starting_state()
    ai = RolloutAI(rollouts_per_move=1000, max_rollout_turns=100, max_step_time_ms=0, rng=random.Random(2))

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
    assert ai.fallback_count >= 1


def test_rollout_ai_timeout_fallback_uses_greedy_risk_weights():
    state = GameState.from_layout(
        red={1: Position(0, 2), 2: Position(2, 2)},
        blue={
            1: Position(4, 4),
            2: Position(4, 2),
            3: Position(4, 0),
            4: Position(3, 2),
            5: Position(2, 3),
            6: Position(0, 4),
        },
        current_player=Player.RED,
    )
    ai = RolloutAI(rollouts_per_move=1000, max_rollout_turns=100, max_step_time_ms=0, rng=random.Random(2))

    move = ai.choose_move(state, 3)

    assert move is not None
    assert move.to_pos == Position(2, 3)


def test_rollout_ai_risk_playout_policy_uses_greedy_risk_weights(monkeypatch):
    captured = []

    class FakeGreedy:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def choose_move(self, state, dice):
            legal = state.legal_moves(state.current_player, dice)
            return legal[0] if legal else None

    monkeypatch.setattr("ai.rollout_ai.GreedyAI", FakeGreedy)
    state = default_starting_state()
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=1,
        max_step_time_ms=1000,
        epsilon=0.0,
        playout_policy="greedy_risk",
        rng=random.Random(1),
    )

    ai._playout(state, deadline=10**9)

    assert captured
    assert captured[0]["expected_risk_weight"] > 0
    assert captured[0]["expected_win_risk_weight"] > captured[0]["expected_risk_weight"]


def test_rollout_ai_current_cutoff_eval_scores_non_terminal_leaf(monkeypatch):
    state = GameState.from_layout(
        red={1: Position(0, 0), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )

    def fake_evaluate(sim, perspective):
        red_five = sim.pieces[Player.RED][5].position
        return 10.0 if red_five == Position(3, 1) else -10.0

    monkeypatch.setattr("ai.rollout_ai.evaluate", fake_evaluate)
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        cutoff_eval="current",
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 5)

    assert move.to_pos == Position(3, 1)
    assert any(stats.cutoffs == 1 for stats in ai.last_root_stats)
    assert any(stats.score == 1.0 for stats in ai.last_root_stats)


def test_rollout_ai_legacy_diagnostics_keep_cutoffs_as_draw_bucket(monkeypatch):
    state = GameState.from_layout(
        red={1: Position(0, 0), 5: Position(2, 1)},
        blue={5: Position(3, 2), 6: Position(3, 1)},
        current_player=Player.RED,
    )

    def fake_evaluate(sim, perspective):
        red_five = sim.pieces[Player.RED][5].position
        return 10.0 if red_five == Position(3, 1) else -10.0

    monkeypatch.setattr("ai.rollout_ai.evaluate", fake_evaluate)
    ai = RolloutAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        cutoff_eval="current",
        rng=random.Random(1),
    )

    ai.choose_move(state, 5)

    assert ai.last_root_stats
    assert ai.last_diagnostics
    assert any(stats.cutoffs == 1 and stats.draws == 0 for stats in ai.last_root_stats)
    assert all(
        diagnostic.visits == diagnostic.wins + diagnostic.losses + diagnostic.cutoffs
        for diagnostic in ai.last_diagnostics
    )
    assert all(diagnostic.draws == diagnostic.cutoffs for diagnostic in ai.last_diagnostics)
