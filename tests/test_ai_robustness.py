from __future__ import annotations

import json
import math
import random
from types import SimpleNamespace
from typing import Any

import pytest

import ai.chance_rerank as rerank_module
import ai.mcts as mcts_module
from ai.chance_rerank import ExactOpponentDiceRerankAI
from ai.endgame_solver import ExactEndgameAI
from ai.evaluator import evaluate
from ai.expectimax_ai import ExpectimaxAI
from ai.expectimax_v2 import ExpectimaxV2
from ai.greedy_ai import GreedyAI
from ai.match import build_ai, default_starting_state
from ai.mcts import DecisionNode, MCTSAI
from ai.opening_layouts import balanced_layout, list_saved_layouts, load_layout, save_layout
from ai.rollout_ai import RolloutAI, RolloutPairedAI, RolloutRootRacingAI
from ai.self_capture_guard import SelfCaptureGuardAI
from ai.zweistein_ai import ZweisteinGreedyAI
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


@pytest.mark.parametrize(
    "factory, kwargs",
    [
        (GreedyAI, {"distance_weight": math.nan}),
        (GreedyAI, {"material_weight": math.inf}),
        (GreedyAI, {"expected_risk_weight": True}),
        (GreedyAI, {"distance_weight": 10**400}),
        (GreedyAI, {"randomize_ties": "false"}),
        (ZweisteinGreedyAI, {"progress_weight": True}),
        (ZweisteinGreedyAI, {"randomize_ties": 1}),
        (ExpectimaxAI, {"depth": 1.5}),
        (ExpectimaxAI, {"time_limit_ms": math.nan}),
        (ExpectimaxAI, {"time_limit_ms": -1.0}),
        (ExpectimaxAI, {"expected_win_risk_weight": math.inf}),
        (ExpectimaxV2, {"depth": True}),
        (ExpectimaxV2, {"depth": -1}),
        (ExpectimaxV2, {"time_limit_ms": math.inf}),
        (ExpectimaxV2, {"use_transposition_table": "false"}),
        (MCTSAI, {"time_limit_ms": math.nan}),
        (MCTSAI, {"scale": 0.0}),
        (MCTSAI, {"scale": math.inf}),
        (MCTSAI, {"c_uct": math.nan}),
        (MCTSAI, {"c_uct": -0.1}),
        (MCTSAI, {"max_iterations": -1}),
        (MCTSAI, {"max_iterations": 1.5}),
        (MCTSAI, {"leaf_playout_turns": True}),
        (RolloutAI, {"rollouts_per_move": -1}),
        (RolloutAI, {"max_rollout_turns": 1.5}),
        (RolloutAI, {"max_step_time_ms": math.inf}),
        (RolloutAI, {"epsilon": math.nan}),
        (RolloutAI, {"epsilon": -0.1}),
        (RolloutAI, {"epsilon": 1.1}),
        (RolloutAI, {"close_sample_margin": math.nan}),
        (RolloutAI, {"close_sample_rollouts_per_move": True}),
        (RolloutAI, {"low_confidence_margin": -0.1}),
        (RolloutAI, {"deadline_safety_ms": -0.1}),
        (RolloutPairedAI, {"paired_trial_seed_stride": 0}),
        (RolloutPairedAI, {"paired_shuffle_moves": "false"}),
        (RolloutRootRacingAI, {"racing_initial_rollouts_per_move": 0}),
        (RolloutRootRacingAI, {"racing_survivor_count": True}),
        (SelfCaptureGuardAI, {"enemy_capture_margin": math.nan}),
        (SelfCaptureGuardAI, {"low_material_threshold": 7}),
        (SelfCaptureGuardAI, {"require_safe_alternative": "false"}),
        (ExactOpponentDiceRerankAI, {"top_k": 0}),
        (ExactOpponentDiceRerankAI, {"exact_mix": 1.1}),
        (ExactOpponentDiceRerankAI, {"max_step_time_ms": math.nan}),
        (ExactEndgameAI, {"max_total_pieces": 2.5}),
        (ExactEndgameAI, {"max_total_distance": -1}),
        (ExactEndgameAI, {"randomize_ties": 1}),
    ],
)
def test_ai_rejects_invalid_configuration_before_search(factory, kwargs):
    with pytest.raises(ValueError):
        factory(**kwargs)


@pytest.mark.parametrize(
    "kind, kwargs",
    [
        ("expectimax", {"depth": 1.5}),
        ("expectimax", {"depth": True}),
        ("rollout_exact_opp1_zdp", {"top_k": True}),
        ("rollout_exact_opp1_zdp", {"exact_mix": math.nan}),
        ("rollout_exact_opp1_zdp", {"min_time_remaining_ms": "20"}),
        ("rollout_exact_opp1_zdp", {"max_step_time_ms": True}),
    ],
)
def test_ai_factory_preserves_invalid_values_for_constructor_validation(kind, kwargs):
    with pytest.raises(ValueError):
        build_ai(kind, seed=1, **kwargs)


@pytest.mark.parametrize(
    "ai",
    [
        MCTSAI(time_limit_ms=0.0, max_iterations=0),
        RolloutAI(max_step_time_ms=0.0, max_rollout_turns=0),
        RolloutAI(rollouts_per_move=0, max_rollout_turns=0),
        ExpectimaxAI(time_limit_ms=0.0),
        ExpectimaxV2(time_limit_ms=0.0),
    ],
)
def test_zero_budget_keeps_legal_fallback_and_state(ai):
    state = default_starting_state()
    before = state.serialize()
    assert ai.choose_move(state, 6) in state.legal_moves(state.current_player, 6)
    assert state.serialize() == before


@pytest.mark.parametrize("weight", [math.nan, math.inf, -math.inf, True, 10**400])
def test_evaluator_rejects_invalid_weights(weight):
    with pytest.raises(ValueError, match="distance_weight"):
        evaluate(default_starting_state(), Player.RED, distance_weight=weight)


def test_evaluator_rejects_overflowed_score_and_restores_greedy_state():
    state = GameState.from_layout(
        red={1: Position(3, 3)}, blue={1: Position(4, 4)}, current_player=Player.RED,
    )
    before = state.serialize()
    ai = GreedyAI(distance_weight=1e308)
    with pytest.raises(ValueError, match="evaluator score"):
        ai.choose_move(state, 1)
    assert state.serialize() == before


def test_evaluator_does_not_compute_disabled_risk_terms(monkeypatch):
    def fail_if_used(*args):
        raise AssertionError("disabled risk term was evaluated")

    monkeypatch.setattr("ai.evaluator.distance_weighted_capture_risk", fail_if_used)
    monkeypatch.setattr("ai.evaluator.expected_target_win_risk", fail_if_used)
    assert evaluate(default_starting_state(), Player.RED) == 0.0


@pytest.mark.parametrize(
    "red, blue, turns, expected",
    [
        ({1: Position(0, 0)}, {1: Position(0, 1)}, 1, -1.0),
        ({1: Position(3, 2)}, {1: Position(4, 0)}, 2, 1.0),
    ],
)
def test_mcts_playout_terminal_backprop_has_full_win_value(red, blue, turns, expected):
    state = GameState.from_layout(red=red, blue=blue, current_player=Player.RED)
    before = state.serialize()
    root = DecisionNode(player=Player.RED, dice=1)
    ai = MCTSAI(leaf_policy="playout", leaf_playout_turns=turns, rng=random.Random(0))
    assert ai._iterate(root, Player.RED, state, math.inf) == 1
    child = next(iter(root.children.values()))
    assert child.q == expected
    assert child.visit_count == root.visit_count == 1
    assert state.serialize() == before


def test_mcts_playout_cutoff_normalizes_static_score_once():
    state = GameState.from_layout(
        red={1: Position(3, 2)}, blue={1: Position(4, 0)}, current_player=Player.RED,
    )
    ai = MCTSAI(leaf_policy="playout", leaf_playout_turns=0)
    raw = ai._static_leaf_score(state, Player.RED)
    assert raw != 0.0
    assert ai._leaf_score(state, Player.RED) == pytest.approx(math.tanh(raw / ai.scale))


def test_mcts_deadline_interrupts_playout_without_partial_backprop(monkeypatch):
    state = default_starting_state()
    state.apply_move(state.legal_moves(Player.RED, 6)[0], dice=6)
    before = state.serialize()
    root = DecisionNode(player=state.current_player, dice=6)
    ai = MCTSAI(leaf_policy="playout", leaf_playout_turns=20, rng=random.Random(0))
    clock = [0.0]
    apply_count = [0]
    original_apply = GameState.apply_move

    def delayed_apply(self, *args, **kwargs):
        result = original_apply(self, *args, **kwargs)
        apply_count[0] += 1
        if apply_count[0] > 1:
            clock[0] += 0.002
        return result

    monkeypatch.setattr(mcts_module.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(GameState, "apply_move", delayed_apply)
    assert ai._iterate(root, state.current_player, state, 0.001) is None
    assert apply_count[0] == 2
    assert root.visit_count == 0
    assert all(child.visit_count == 0 for child in root.children.values())
    assert state.serialize() == before


class _RerankFakeBase:
    name = "fake_base"

    def __init__(self, move: Move, stats: list[Any]) -> None:
        self.move = move
        self.last_root_stats = stats

    def choose_move(self, state: GameState, dice: int) -> Move:
        return self.move


def _rerank_state_and_base(scores):
    state = GameState.from_layout(
        red={1: Position(2, 2)}, blue={1: Position(0, 4)}, current_player=Player.RED,
    )
    legal = state.legal_moves(Player.RED, 1)
    base = _RerankFakeBase(
        move=legal[0],
        stats=[
            SimpleNamespace(move=move, score=score, visits=10)
            for move, score in zip(legal, scores)
        ],
    )
    return state, legal, base


def test_rerank_reuses_base_exact_value(monkeypatch):
    state, legal, base = _rerank_state_and_base([0.7, 0.6, 0.65])
    calls = []

    def exact(state, dice, move, perspective, *, deadline=None):
        calls.append(move)
        return 1.0 if move == legal[2] else 0.4

    monkeypatch.setattr(rerank_module, "exact_opp1_zdp_value", exact)
    monkeypatch.setattr(rerank_module.time, "perf_counter", lambda: 0.0)
    ai = ExactOpponentDiceRerankAI(base=base, top_k=3)
    assert ai.choose_move(state, 1) == legal[2]
    assert calls.count(legal[0]) == 1
    assert len(calls) == 3


def test_rerank_does_not_start_uncached_base_evaluation_after_deadline(monkeypatch):
    state, legal, base = _rerank_state_and_base([0.5, 0.6, 0.7])
    clock = [0.0]
    calls = []

    def exact(state, dice, move, perspective, *, deadline=None):
        calls.append(move)
        clock[0] = 0.8
        return 1.0

    monkeypatch.setattr(rerank_module, "exact_opp1_zdp_value", exact)
    monkeypatch.setattr(rerank_module.time, "perf_counter", lambda: clock[0])
    ai = ExactOpponentDiceRerankAI(base=base, top_k=1, max_step_time_ms=750.0)
    assert ai.choose_move(state, 1) == legal[0]
    assert calls == [legal[2]]
    assert ai.fire_counts["passthrough_no_time"] == 1


def test_rerank_interrupts_exact_candidate_and_keeps_caller_state(monkeypatch):
    state, legal, base = _rerank_state_and_base([0.7, 0.6, 0.5])
    before = state.serialize()
    clock = [0.0]

    def delayed_probability(state, perspective):
        clock[0] += 0.002
        return 0.5

    monkeypatch.setattr(rerank_module, "zweistein_dp_win_prob", delayed_probability)
    monkeypatch.setattr(rerank_module.time, "perf_counter", lambda: clock[0])
    ai = ExactOpponentDiceRerankAI(
        base=base, max_step_time_ms=1.0, min_time_remaining_ms=0.0,
    )
    assert ai.choose_move(state, 1) == legal[0]
    assert ai.fire_counts["passthrough_no_time"] == 1
    assert state.serialize() == before


def test_rerank_default_base_uses_wrapper_budget():
    ai = ExactOpponentDiceRerankAI(max_step_time_ms=750.0)
    assert isinstance(ai.base, RolloutAI)
    assert ai.base.max_step_time_ms == ai.max_step_time_ms == 750.0


@pytest.mark.parametrize(
    "bad_position", [[0.9, 0.9], [True, 0], [math.inf, 0], ["0", 0], "00", [0]],
)
def test_opening_loader_rejects_malformed_coordinates_and_skips_bad_files(tmp_path, bad_position):
    red, blue = balanced_layout()
    save_layout("valid", red, blue, "Valid", directory=tmp_path)
    payload = json.loads((tmp_path / "valid.json").read_text(encoding="utf-8"))
    payload["id"] = "invalid"
    payload["red"]["1"] = bad_position
    (tmp_path / "invalid.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid layout file"):
        load_layout("invalid", directory=tmp_path)
    assert [layout.id for layout in list_saved_layouts(directory=tmp_path)] == ["valid"]


def test_opening_loader_rejects_alias_piece_ids(tmp_path):
    red, blue = balanced_layout()
    save_layout("invalid", red, blue, "Invalid", directory=tmp_path)
    path = tmp_path / "invalid.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["red"]["01"] = payload["red"]["1"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid layout file"):
        load_layout("invalid", directory=tmp_path)
    assert list_saved_layouts(directory=tmp_path) == []
