from __future__ import annotations

import time
from threading import Event
from types import SimpleNamespace

from ai.match import default_starting_state
from gui.recommendation_worker import (
    RecommendationRequest, RecommendationWorker, calculate_recommendation,
)


class FirstLegalAI:
    def choose_move(self, state, dice):
        return state.legal_moves(state.current_player, dice)[0]


def request(generation, ai, *, fallback=None):
    state = default_starting_state()
    return RecommendationRequest(
        generation, (generation, str(generation)), generation, state,
        ai, fallback or FirstLegalAI(),
    )


def results(worker, count):
    collected = []
    deadline = time.monotonic() + 3
    while len(collected) < count and time.monotonic() < deadline:
        collected.extend(worker.drain())
        Event().wait(0.001)
    assert len(collected) == count
    return collected


def test_worker_keeps_only_latest_pending_request():
    entered = Event()
    release = Event()
    calls = []

    class BlockingAI(FirstLegalAI):
        def choose_move(self, state, dice):
            calls.append(dice)
            if dice == 1:
                entered.set()
                assert release.wait(3)
            return super().choose_move(state, dice)

    worker = RecommendationWorker()
    ai = BlockingAI()
    try:
        worker.submit(request(1, ai))
        assert entered.wait(3)
        worker.submit(request(2, ai))
        worker.submit(request(3, ai))
        release.set()
        completed = results(worker, 2)
        assert calls == [1, 3]
        assert [result.generation for result in completed] == [1, 3]
    finally:
        release.set()
        worker.close()
        worker._thread.join(3)


def test_close_returns_while_ai_is_running_and_discards_its_result():
    entered = Event()
    release = Event()

    class BlockingAI(FirstLegalAI):
        def choose_move(self, state, dice):
            entered.set()
            assert release.wait(3)
            return super().choose_move(state, dice)

    worker = RecommendationWorker()
    try:
        worker.submit(request(1, BlockingAI()))
        assert entered.wait(3)
        worker.close()
        assert worker.is_alive()
        worker.submit(request(2, FirstLegalAI()))
        release.set()
        worker._thread.join(3)
        assert not worker.is_alive()
        assert worker.drain() == []
    finally:
        release.set()
        worker.close()


def test_invalidate_removes_pending_work():
    entered = Event()
    release = Event()
    calls = []

    class BlockingAI(FirstLegalAI):
        def choose_move(self, state, dice):
            calls.append(dice)
            entered.set()
            assert release.wait(3)
            return super().choose_move(state, dice)

    worker = RecommendationWorker()
    try:
        ai = BlockingAI()
        worker.submit(request(1, ai))
        assert entered.wait(3)
        worker.submit(request(2, ai))
        worker.invalidate()
        release.set()
        assert results(worker, 1)[0].generation == 1
        worker.close()
        worker._thread.join(3)
        assert calls == [1]
    finally:
        release.set()
        worker.close()


def test_failed_ai_cannot_mutate_the_fallback_or_original_snapshot():
    class MutatingAI:
        def choose_move(self, state, dice):
            state.apply_move(state.legal_moves(state.current_player, dice)[0], dice=dice)
            raise RuntimeError("failed after mutation")

    work = request(1, MutatingAI())
    before = work.state.serialize()
    result = calculate_recommendation(work)
    assert result.source == "greedy_risk"
    assert result.move in work.state.legal_moves(work.state.current_player, work.dice)
    assert work.state.serialize() == before


def test_invalid_return_from_both_ais_uses_rules():
    class InvalidAI:
        def choose_move(self, state, dice):
            return {"piece_id": 1}

    work = request(1, InvalidAI(), fallback=InvalidAI())
    result = calculate_recommendation(work)
    assert result.source == "rules"
    assert result.move == work.state.legal_moves(work.state.current_player, work.dice)[0]


def test_diagnostics_are_immutable_per_decision():
    class DiagnosticAI(FirstLegalAI):
        last_low_confidence = True
        last_score_margin = 0.01

        def choose_move(self, state, dice):
            move = super().choose_move(state, dice)
            self.last_root_stats = [SimpleNamespace(move=move, visits=2, score=0.25)]
            return move

    ai = DiagnosticAI()
    first = calculate_recommendation(request(1, ai))
    saved = first.diagnostics
    ai.last_score_margin = 0.9
    second = calculate_recommendation(request(2, ai))
    assert first.diagnostics == saved
    assert "候选差距=0.01" in saved[0]
    assert "候选差距=0.90" in second.diagnostics[0]
    assert any("score=0.25" in line for line in saved)


def test_diagnostic_runtime_error_keeps_worker_alive_for_next_request():
    class BadDiagnosticAI(FirstLegalAI):
        @property
        def last_root_stats(self):
            raise RuntimeError("diagnostics failed")

    worker = RecommendationWorker()
    first_work = request(1, BadDiagnosticAI())
    try:
        worker.submit(first_work)
        first = results(worker, 1)[0]
        assert first.generation == 1
        assert first.source == "rollout"
        assert first.move in first_work.state.legal_moves(first_work.state.current_player, first_work.dice)
        assert "候选诊断不可用。" in first.diagnostics
        assert worker.is_alive()

        second_work = request(2, FirstLegalAI())
        worker.submit(second_work)
        second = results(worker, 1)[0]
        assert second.generation == 2
        assert second.source == "rollout"
        assert second.move in second_work.state.legal_moves(second_work.state.current_player, second_work.dice)
        assert worker.is_alive()
    finally:
        worker.close()
        worker._thread.join(3)


def test_unexpected_calculation_error_returns_rules_result_and_worker_continues(monkeypatch):
    def fail_first(work):
        if work.generation == 1:
            raise RuntimeError("unexpected calculation failure")
        return calculate_recommendation(work)

    monkeypatch.setattr("gui.recommendation_worker.calculate_recommendation", fail_first)
    worker = RecommendationWorker()
    first_work = request(1, FirstLegalAI())
    before = first_work.state.serialize()
    try:
        worker.submit(first_work)
        first = results(worker, 1)[0]
        assert first.generation == 1
        assert first.key == first_work.key
        assert first.source == "rules"
        assert first.move == first_work.state.legal_moves(first_work.state.current_player, first_work.dice)[0]
        assert first_work.state.serialize() == before
        assert worker.is_alive()

        second_work = request(2, FirstLegalAI())
        worker.submit(second_work)
        second = results(worker, 1)[0]
        assert second.generation == 2
        assert second.source == "rollout"
        assert second.move in second_work.state.legal_moves(second_work.state.current_player, second_work.dice)
        assert worker.is_alive()
    finally:
        worker.close()
        worker._thread.join(3)
