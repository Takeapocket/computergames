import random

from ai.match import ai_version_signature, build_ai, default_starting_state
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from ai.rollout_ai import RolloutPairedAI
from core.game_state import GameState
from core.types import Player, Position
from scripts import bench_ai


def _multi_move_state() -> GameState:
    return GameState.from_layout(
        red={
            1: Position(0, 0),
            2: Position(2, 2),
            5: Position(2, 1),
        },
        blue={
            5: Position(3, 2),
            6: Position(3, 1),
        },
        current_player=Player.RED,
    )


def test_build_ai_rollout_paired_uses_release_defaults_and_signature():
    ai = build_ai("rollout_paired", seed=2026)
    signature = ai_version_signature(ai)

    assert isinstance(ai, RolloutPairedAI)
    assert ai.name == "rollout_paired"
    assert ai.rollouts_per_move == RELEASE_DEFAULT_ROLLOUT_KWARGS["rollouts_per_move"]
    assert ai.max_rollout_turns == RELEASE_DEFAULT_ROLLOUT_KWARGS["max_rollout_turns"]
    assert ai.max_step_time_ms == RELEASE_DEFAULT_ROLLOUT_KWARGS["max_step_time_ms"]
    assert ai.deadline_safety_ms == RELEASE_DEFAULT_ROLLOUT_KWARGS["deadline_safety_ms"]
    assert ai.epsilon == RELEASE_DEFAULT_ROLLOUT_KWARGS["epsilon"]
    assert ai.playout_policy == RELEASE_DEFAULT_ROLLOUT_KWARGS["playout_policy"]
    assert ai.cutoff_eval == RELEASE_DEFAULT_ROLLOUT_KWARGS["cutoff_eval"]
    assert signature["name"] == "rollout_paired"
    assert signature["paired_trial_seed_stride"] == 1000003
    assert signature["paired_shuffle_moves"] is False
    assert signature["close_sample_enabled"] is False
    assert signature["rollouts_per_move"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["rollouts_per_move"]
    assert signature["max_rollout_turns"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["max_rollout_turns"]
    assert signature["max_step_time_ms"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["max_step_time_ms"]
    assert signature["epsilon"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["epsilon"]
    assert signature["playout_policy"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["playout_policy"]
    assert signature["cutoff_eval"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["cutoff_eval"]
    assert signature["deadline_safety_ms"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["deadline_safety_ms"]


def test_build_ai_rollout_common_random_alias_accepts_paired_overrides():
    ai = build_ai(
        "rollout_common_random",
        seed=2026,
        paired_trial_seed_stride=17,
        paired_shuffle_moves=True,
    )

    assert isinstance(ai, RolloutPairedAI)
    assert ai.name == "rollout_common_random"
    assert ai.paired_trial_seed_stride == 17
    assert ai.paired_shuffle_moves is True


def test_rollout_paired_returns_legal_move_without_mutating_state():
    state = default_starting_state()
    before = state.serialize()
    ai = RolloutPairedAI(
        rollouts_per_move=2,
        max_rollout_turns=4,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
    assert state.serialize() == before
    assert ai.last_root_stats
    assert [diagnostic.move for diagnostic in ai.last_diagnostics] == [
        stats.move for stats in ai.last_root_stats
    ]


def test_rollout_paired_returns_none_when_no_legal_moves():
    state = GameState.from_layout(
        red={1: Position(4, 4)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    ai = RolloutPairedAI(
        rollouts_per_move=2,
        max_rollout_turns=4,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    assert ai.choose_move(state, 1) is None
    assert ai.last_root_stats == []
    assert ai.last_diagnostics == []


def test_rollout_paired_gives_every_root_move_equal_visits():
    state = _multi_move_state()
    dice = 5
    legal = state.legal_moves(state.current_player, dice)
    ai = RolloutPairedAI(
        rollouts_per_move=2,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    move = ai.choose_move(state, dice)

    assert move in legal
    assert [stats.move for stats in ai.last_root_stats] == legal
    assert all(stats.visits == 2 for stats in ai.last_root_stats)
    assert all(stats.cutoffs == 2 for stats in ai.last_root_stats)
    assert all(0.0 <= stats.score <= 1.0 for stats in ai.last_root_stats)
    assert all(stats.avg == 2 * stats.score - 1 for stats in ai.last_root_stats)
    assert all(
        stats.visits == stats.wins + stats.losses + stats.draws
        for stats in ai.last_root_stats
    )


def test_rollout_paired_reuses_trial_seed_for_all_root_moves(monkeypatch):
    state = _multi_move_state()
    dice = 5
    legal = state.legal_moves(state.current_player, dice)
    seen_first_randoms: list[float] = []
    ai = RolloutPairedAI(
        rollouts_per_move=2,
        max_rollout_turns=1,
        max_step_time_ms=1000,
        rng=random.Random(1),
    )

    def fake_playout(sim, *, deadline, rng):
        seen_first_randoms.append(rng.random())
        return None

    monkeypatch.setattr(ai, "_playout_with_rng", fake_playout)

    ai.choose_move(state, dice)

    assert len(seen_first_randoms) == len(legal) * 2
    chunks = [
        seen_first_randoms[index:index + len(legal)]
        for index in range(0, len(seen_first_randoms), len(legal))
    ]
    assert all(len(set(chunk)) == 1 for chunk in chunks)
    assert chunks[0][0] != chunks[1][0]


def test_rollout_paired_cutoff_eval_zweistein_can_run():
    state = _multi_move_state()
    ai = RolloutPairedAI(
        rollouts_per_move=1,
        max_rollout_turns=0,
        max_step_time_ms=1000,
        cutoff_eval="zweistein",
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 5)

    assert move in state.legal_moves(state.current_player, 5)
    assert ai.last_root_stats


def test_rollout_paired_greedy_risk_playout_policy_can_run():
    state = default_starting_state()
    ai = RolloutPairedAI(
        rollouts_per_move=1,
        max_rollout_turns=1,
        max_step_time_ms=1000,
        epsilon=0.0,
        playout_policy="greedy_risk",
        rng=random.Random(1),
    )

    move = ai.choose_move(state, 6)

    assert move in state.legal_moves(state.current_player, 6)
    assert ai.last_root_stats


def test_rollout_paired_bench_profiles_use_release_default_rollout():
    for candidate in ("rollout_paired", "rollout_common_random"):
        profile = bench_ai.CANDIDATE_PROFILES[candidate]["candidate"]

        assert profile["opponent"] == "rollout"
        assert profile["opponent_kwargs"] == bench_ai.RELEASE_DEFAULT_ROLLOUT_KWARGS
        assert profile["starting_layout"] == "balanced_v1"
        assert profile["games_per_side"] == 25
