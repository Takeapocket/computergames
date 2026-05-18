import random

from ai.match import ai_version_signature, build_ai, default_starting_state
from ai.rollout_ai import RolloutRootRacingAI
from scripts import bench_ai


def test_build_ai_rollout_root_racing_uses_release_budget_and_policy():
    ai = build_ai("rollout_root_racing", seed=2026)
    signature = ai_version_signature(ai)

    assert isinstance(ai, RolloutRootRacingAI)
    assert ai.name == "rollout_root_racing"
    assert ai.max_rollout_turns == 80
    assert ai.max_step_time_ms == 750.0
    assert ai.deadline_safety_ms == 30.0
    assert ai.epsilon == 0.1
    assert ai.playout_policy == "greedy_risk"
    assert ai.cutoff_eval == "zweistein"
    assert ai.racing_initial_rollouts_per_move == 6
    assert ai.racing_survivor_count == 4
    assert ai.racing_final_survivor_count == 2
    assert ai.racing_batch_rollouts_per_move == 2
    assert signature["name"] == "rollout_root_racing"
    assert signature["racing_initial_rollouts_per_move"] == 6
    assert signature["racing_survivor_count"] == 4
    assert signature["racing_final_survivor_count"] == 2
    assert signature["racing_batch_rollouts_per_move"] == 2


def test_rollout_root_racing_samples_survivors_more_than_eliminated_moves(monkeypatch):
    state = default_starting_state()
    dice = 6
    legal = state.legal_moves(state.current_player, dice)
    calls = [[] for _ in legal]

    def fake_sample(score, **kwargs):
        target_visits = kwargs["target_visits"]
        move_rank = legal.index(score.move)
        calls[move_rank].append(target_visits)
        if target_visits > 3:
            return True
        while score.visits < target_visits:
            if move_rank == 0:
                score.record_win()
            elif move_rank == 1:
                score.record_cutoff(0.5)
            else:
                score.record_loss()
        return False

    ai = RolloutRootRacingAI(
        racing_initial_rollouts_per_move=2,
        racing_survivor_count=2,
        racing_final_survivor_count=1,
        racing_batch_rollouts_per_move=1,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    move = ai.choose_move(state, dice)

    assert move == legal[0]
    assert calls[0] == [2, 3, 4]
    assert calls[1] == [2, 3]
    assert calls[2] == [2]
    assert [stats.visits for stats in ai.last_root_stats] == [3, 3, 2]


def test_rollout_root_racing_caps_visits_to_flat_rollout_budget(monkeypatch):
    state = default_starting_state()
    dice = 6
    legal = state.legal_moves(state.current_player, dice)

    def fake_sample(score, **kwargs):
        target_visits = kwargs["target_visits"]
        move_rank = legal.index(score.move)
        while score.visits < target_visits:
            if move_rank == 0:
                score.record_win()
            elif move_rank == 1:
                score.record_cutoff(0.5)
            else:
                score.record_loss()
        return False

    ai = RolloutRootRacingAI(
        rollouts_per_move=3,
        racing_initial_rollouts_per_move=1,
        racing_survivor_count=2,
        racing_final_survivor_count=1,
        racing_batch_rollouts_per_move=1,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    move = ai.choose_move(state, dice)

    assert move == legal[0]
    assert sum(stats.visits for stats in ai.last_root_stats) == len(legal) * 3
    assert ai.last_root_stats[0].visits > ai.last_root_stats[2].visits


def test_rollout_root_racing_stops_after_initial_when_initial_budget_is_larger(monkeypatch):
    state = default_starting_state()
    dice = 6
    legal = state.legal_moves(state.current_player, dice)
    calls = [[] for _ in legal]

    def fake_sample(score, **kwargs):
        target_visits = kwargs["target_visits"]
        move_rank = legal.index(score.move)
        calls[move_rank].append(target_visits)
        while score.visits < target_visits:
            score.record_win()
        return False

    ai = RolloutRootRacingAI(
        rollouts_per_move=1,
        racing_initial_rollouts_per_move=2,
        racing_survivor_count=2,
        racing_final_survivor_count=1,
        racing_batch_rollouts_per_move=1,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", fake_sample)

    move = ai.choose_move(state, dice)

    assert move in legal
    assert calls == [[2], [2], [2]]
    assert sum(stats.visits for stats in ai.last_root_stats) == len(legal) * 2


def test_rollout_root_racing_initial_timeout_uses_greedy_risk_fallback(monkeypatch):
    state = default_starting_state()
    dice = 6
    legal = state.legal_moves(state.current_player, dice)
    fallback_move = legal[-1]

    class FakeGreedy:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def choose_move(self, state, dice):
            return fallback_move

    monkeypatch.setattr("ai.rollout_ai.GreedyAI", FakeGreedy)
    ai = RolloutRootRacingAI(
        racing_initial_rollouts_per_move=2,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )
    monkeypatch.setattr(ai, "_sample_move_score", lambda score, **kwargs: True)

    move = ai.choose_move(state, dice)

    assert move == fallback_move
    assert ai.last_timed_out is True
    assert ai.last_used_fallback is True
    assert ai.fallback_count == 1


def test_rollout_root_racing_returns_legal_move_without_mutating_state():
    state = default_starting_state()
    before = state.serialize()
    ai = build_ai(
        "rollout_root_racing",
        seed=2026,
        racing_initial_rollouts_per_move=1,
        racing_survivor_count=2,
        racing_final_survivor_count=1,
        racing_batch_rollouts_per_move=1,
        max_step_time_ms=20,
    )

    move = ai.choose_move(state, 3)

    assert move is None or move in state.legal_moves(state.current_player, 3)
    assert state.serialize() == before


def test_rollout_root_racing_bench_profile_uses_release_default_rollout():
    profile = bench_ai.CANDIDATE_PROFILES["rollout_root_racing"]["candidate"]

    assert profile["opponent"] == "rollout"
    assert profile["opponent_kwargs"] == bench_ai.RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert profile["starting_layout"] == "balanced_v1"
    assert profile["games_per_side"] == 25
