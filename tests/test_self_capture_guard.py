from __future__ import annotations

from collections import Counter

from ai import self_capture_guard as guard_module
from ai.match import ai_version_signature, build_ai, starting_state_for
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from ai.rollout_ai import RootMoveStats
from ai.self_capture_guard import SelfCaptureGuardAI
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


class FakeBase:
    def __init__(
        self,
        move: Move | None,
        root_stats: list[RootMoveStats] | None = None,
        *,
        max_step_time_ms: float | None = None,
    ) -> None:
        self.name = "fake_base"
        self.move = move
        self.last_root_stats = root_stats or []
        self.last_diagnostics = ["diag"]
        self.last_score_margin = 0.04
        self.last_low_confidence = True
        self.last_timed_out = False
        self.last_used_fallback = False
        self.calls = 0
        if max_step_time_ms is not None:
            self.max_step_time_ms = max_step_time_ms

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        self.calls += 1
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


def test_base_move_non_self_capture_is_kept() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    base_move = move_to(state, 3, 2)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(base_move, [stats(base_move, 0.70), stats(enemy_capture, 0.70)]),
    )

    assert ai.choose_move(state, 1) == base_move
    assert ai.fire_counts == Counter()
    assert ai.last_root_stats == ai.base.last_root_stats
    assert ai.last_low_confidence is True


def test_direct_win_self_capture_is_not_overridden(monkeypatch) -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(self_capture, [stats(self_capture, 0.65), stats(enemy_capture, 0.64)]),
    )

    monkeypatch.setattr("ai.self_capture_guard.move_wins_immediately", lambda *_args: True)

    assert ai.choose_move(state, 1) == self_capture
    assert ai.fire_counts["kept_self_direct_win"] == 1


def test_self_capture_switches_to_close_enemy_capture() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0), 4: Position(4, 1)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(self_capture, [stats(self_capture, 0.72), stats(enemy_capture, 0.66)]),
    )

    assert ai.choose_move(state, 1) == enemy_capture
    assert ai.fire_counts["override_self_to_enemy_capture"] == 1


def test_deadline_exhausted_after_base_keeps_base_move() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0), 4: Position(4, 1)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(
            self_capture,
            [stats(self_capture, 0.72), stats(enemy_capture, 0.66)],
            max_step_time_ms=0.0,
        ),
    )

    assert ai.max_step_time_ms == 0.0
    assert ai.choose_move(state, 1) == self_capture
    assert ai.last_timed_out is True
    assert ai.fire_counts["kept_base_after_deadline"] == 1


def test_deadline_exhausted_before_guard_filtering_keeps_base_move(monkeypatch) -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0), 4: Position(4, 1)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    clock = iter([0.0, 0.0, 1.0])

    def fake_perf_counter() -> float:
        return next(clock, 1.0)

    monkeypatch.setattr(guard_module.time, "perf_counter", fake_perf_counter)
    ai = SelfCaptureGuardAI(
        base=FakeBase(
            self_capture,
            [stats(self_capture, 0.72), stats(enemy_capture, 0.66)],
            max_step_time_ms=500.0,
        ),
    )

    assert ai.choose_move(state, 1) == self_capture
    assert ai.last_timed_out is True
    assert ai.fire_counts["kept_base_after_deadline"] == 1


def test_self_capture_is_kept_when_enemy_capture_score_gap_is_too_large() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0), 4: Position(4, 1)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(self_capture, [stats(self_capture, 0.90), stats(enemy_capture, 0.70)]),
    )

    assert ai.choose_move(state, 1) == self_capture
    assert ai.fire_counts["kept_self_score_gap"] == 1


def test_low_material_self_capture_switches_to_close_non_self_move() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0)},
        blue={6: Position(0, 4)},
    )
    self_capture = move_to(state, 3, 3)
    non_self = move_to(state, 3, 2)
    ai = SelfCaptureGuardAI(
        base=FakeBase(self_capture, [stats(self_capture, 0.84), stats(non_self, 0.74)]),
    )

    assert ai.choose_move(state, 1) == non_self
    assert ai.fire_counts["override_self_to_non_self_low_material"] == 1


def test_unsafe_alternative_is_skipped() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0)},
        blue={6: Position(1, 1), 5: Position(2, 3)},
    )
    self_capture = move_to(state, 3, 3)
    enemy_capture = move_to(state, 2, 3)
    non_self = move_to(state, 3, 2)
    ai = SelfCaptureGuardAI(
        base=FakeBase(
            self_capture,
            [stats(self_capture, 0.72), stats(enemy_capture, 0.70), stats(non_self, 0.70)],
        ),
    )

    assert ai.choose_move(state, 1) == self_capture
    assert ai.fire_counts["kept_self_unsafe_alt"] == 1


def test_soft_enemy_capture_bias_requires_explicit_margin() -> None:
    state = make_state(
        red={1: Position(2, 2), 2: Position(3, 3), 3: Position(4, 0)},
        blue={6: Position(0, 4), 5: Position(2, 3)},
    )
    base_move = move_to(state, 3, 2)
    enemy_capture = move_to(state, 2, 3)
    ai = SelfCaptureGuardAI(
        base=FakeBase(base_move, [stats(base_move, 0.74), stats(enemy_capture, 0.72)]),
        prefer_enemy_capture_margin=0.04,
    )

    assert ai.choose_move(state, 1) == enemy_capture
    assert ai.fire_counts["override_to_enemy_capture_soft"] == 1


def test_illegal_base_move_falls_back_to_legal_move() -> None:
    state = make_state(red={1: Position(2, 2)}, blue={6: Position(0, 4)})
    illegal = Move(Player.RED, 1, Position(2, 2), Position(0, 0))
    ai = SelfCaptureGuardAI(base=FakeBase(illegal, []))

    move = ai.choose_move(state, 1)

    assert move in state.legal_moves(Player.RED, 1)
    assert ai.fire_counts["fallback_illegal_base"] == 1


def test_ai_version_signature_includes_guard_parameters() -> None:
    state = make_state(red={1: Position(2, 2)}, blue={6: Position(0, 4)})
    base_move = move_to(state, 3, 2)
    ai = SelfCaptureGuardAI(
        base=FakeBase(base_move, [stats(base_move, 0.5)]),
        enemy_capture_margin=0.11,
        non_self_low_material_margin=0.13,
        prefer_enemy_capture_margin=0.05,
        low_material_threshold=4,
        require_safe_alternative=False,
    )

    sig = ai_version_signature(ai)

    assert sig["name"] == "rollout_self_capture_guard"
    assert sig["base"]["name"] == "fake_base"
    assert sig["enemy_capture_margin"] == 0.11
    assert sig["non_self_low_material_margin"] == 0.13
    assert sig["prefer_enemy_capture_margin"] == 0.05
    assert sig["low_material_threshold"] == 4
    assert sig["require_safe_alternative"] is False


def test_build_ai_rollout_self_capture_guard_constructs_and_chooses_legal_move() -> None:
    state = starting_state_for("balanced_v1")
    ai = build_ai("rollout_self_capture_guard", seed=20260518)

    move = ai.choose_move(state, 1)

    assert move in state.legal_moves(state.current_player, 1)


def test_bench_profiles_register_guard_candidates_against_release_default_rollout() -> None:
    from scripts import bench_ai

    for kind in (
        "rollout_self_capture_guard",
        "rollout_material_guard",
        "rollout_self_capture_guard_strict",
    ):
        profile = bench_ai._resolve_profile(kind, "candidate")
        assert profile["opponent"] == "rollout"
        assert profile["opponent_kwargs"] == RELEASE_DEFAULT_ROLLOUT_KWARGS
        assert profile["starting_layout"] == "balanced_v1"
        assert profile["games_per_side"] == 25
