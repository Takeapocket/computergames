from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from scripts import analyze_p14_baseline as analysis
from scripts import rebaseline_p14 as runner


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(runner._json_bytes(value))


def _game(planned, manifest):
    """Create real replay evidence cheaply, with first-legal moves and no AI."""
    state = runner.starting_state_for("balanced_v1")
    record = runner.GameRecord.from_state(state)
    rng = random.Random(planned["dice_seed"])
    calls = []
    while state.get_winner() is None:
        dice = rng.randint(1, 6)
        color = state.current_player.value
        actor = planned[color]
        move = state.legal_moves(state.current_player, dice)[0]
        applied = state.apply_move(move, dice=dice)
        record.append(dice=dice, move=applied, state_after=state, source="self")
        calls.append({"color": color, "actor_id": actor, "dice": dice, "error": None,
                      "elapsed_ms": 20.0 if actor == runner.P14 else 10.0,
                      "internal_deadline_reached": len(calls) % 3 == 0,
                      "used_fallback": len(calls) == 0, "completed_root_visits": 64,
                      "harness_budget_exceeded": False})
    winner = state.get_winner().value
    by_actor = {}
    for actor in (runner.P14, runner.LEGACY):
        own = [call for call in calls if call["actor_id"] == actor]
        by_actor[actor] = {"step_count": len(own), "thinking_seconds": sum(call["elapsed_ms"] for call in own) / 1000,
                           **{key: sum(call[key] for call in own) for key in analysis.COUNT_KEYS}}
    game = {"schema_version": runner.SCHEMA_VERSION, "run_id": manifest["run_id"],
            "protocol_sha256": manifest["protocol_sha256"], "input": planned,
            "actors": manifest["protocol"]["actors"], "rules_version": runner.RULES_VERSION,
            "winner": winner, "winner_actor": planned[winner], "termination_reason": "winner_target_corner",
            "errors": [], "result": {"turns": len(calls), "illegal_moves": 0, "crashes": 0, "harness_step_budget_overruns": 0},
            "observed_calls": calls, "step_times_ms": [call["elapsed_ms"] for call in calls],
            "by_actor": by_actor, "record": record.to_dict(), "wall_seconds": 1.0}
    return runner._seal(game)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "source_hashes", lambda: {})
    protocol = runner.make_protocol(2, 0)
    protocol["config_raw_sha256"] = {}
    manifest = {"run_id": "test-run", "created_utc": "2026-10-18T00:00:00+00:00",
                "protocol": protocol, "protocol_sha256": runner._digest(runner._json_bytes(protocol))}
    run_dir = tmp_path / "run"
    _write(run_dir / "manifest.json", manifest)
    games = []
    for planned in protocol["schedule"]:
        game = _game(planned, manifest)
        games.append(game)
        _write(run_dir / "games" / (planned["game_id"] + ".json"), game)
    _write(run_dir / "summary.json", runner.summarize(games, manifest, source_unchanged=True))
    monkeypatch.setattr(analysis, "ROOT", tmp_path / "repository")
    return run_dir


def test_pair_bootstrap_is_deterministic_and_uses_pairs():
    assert analysis.paired_interval([1] * 100)["low"] == 0.5
    assert analysis.paired_interval([1] * 100)["high"] == 0.5
    first = analysis.paired_interval([0, 1, 2], resamples=500)
    assert first == analysis.paired_interval([0, 1, 2], resamples=500)
    assert first["pair_win_distribution"] == {"0": 1, "1": 1, "2": 1}
    assert first["estimate"] == 0.5


def test_valid_paired_evidence_uses_true_harness_timings(evidence, tmp_path):
    before = {path: path.read_bytes() for path in evidence.rglob("*.json")}
    summary = analysis.analyze(evidence, tmp_path / "analysis", expected_pairs=2)
    assert summary["games"] == 4
    assert summary["p14_wins"] == 2  # Same dice path and first-legal policy wins one color per pair.
    assert summary["paired_win_rate_interval"]["low"] == 0.5
    assert summary["paired_win_rate_interval"]["high"] == 0.5
    assert summary["algorithm_measurements"][runner.P14]["step_ms"]["mean"] == 20.0
    assert summary["algorithm_measurements"][runner.LEGACY]["step_ms"]["mean"] == 10.0
    assert summary["algorithm_measurements"][runner.P14]["harness_budget_exceeded"] == 0
    assert summary["algorithm_measurements"][runner.P14]["internal_deadline_reached"] > 0
    assert all(path.read_bytes() == data for path, data in before.items())
    assert (tmp_path / "analysis" / "analysis_summary.md").exists()
    with pytest.raises(ValueError, match="already exists"):
        analysis.analyze(evidence, tmp_path / "analysis", expected_pairs=2)


@pytest.mark.parametrize("mutation,match", [
    (lambda game: game["step_times_ms"].pop(), "length"),
    (lambda game: game["observed_calls"][0].update(dice=7), "dice stream"),
    (lambda game: game["observed_calls"][0].update(actor_id="invalid_actor"), "actor"),
    (lambda game: game["observed_calls"][0].update(elapsed_ms=99.0), "elapsed"),
    (lambda game: game["observed_calls"][0].update(harness_budget_exceeded=True), "overrun flag"),
    (lambda game: game["by_actor"][runner.P14].update(completed_root_visits=0), "aggregate"),
    (lambda game: game.update(winner_actor=runner.LEGACY if game["winner_actor"] == runner.P14 else runner.P14), "winner"),
])
def test_resealed_inconsistent_measurements_rejected_before_output(evidence, tmp_path, mutation, match):
    path = next((evidence / "games").glob("*.json"))
    game = json.loads(path.read_text(encoding="utf-8"))
    mutation(game)
    _write(path, runner._seal({key: value for key, value in game.items() if key != "content_sha256"}))
    output = tmp_path / "invalid-output"
    with pytest.raises(ValueError, match=match):
        analysis.analyze(evidence, output, expected_pairs=2)
    assert not output.exists()


@pytest.mark.parametrize("case", ["missing", "duplicate", "bad_checksum", "wrong_pairs", "duplicate_key"])
def test_corrupt_or_incomplete_evidence_has_no_summary(evidence, tmp_path, case):
    path = next((evidence / "games").glob("*.json"))
    if case == "missing":
        path.rename(path.with_suffix(".held"))
    elif case == "duplicate":
        (path.parent / "duplicate.json").write_bytes(path.read_bytes())
    elif case == "bad_checksum":
        game = json.loads(path.read_text(encoding="utf-8"))
        game["content_sha256"] = "bad"
        _write(path, game)
    elif case == "duplicate_key":
        path.write_text('{"winner": "red", "winner": "blue"}', encoding="utf-8")
    output = tmp_path / "invalid-output"
    with pytest.raises(ValueError):
        analysis.analyze(evidence, output, expected_pairs=100 if case == "wrong_pairs" else 2)
    assert not output.exists()


def test_manifest_seed_or_signature_tampering_rejected(evidence):
    path = evidence / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["protocol"]["schedule"][0]["actor_seeds"][runner.P14] += 1
    manifest["protocol_sha256"] = runner._digest(runner._json_bytes(manifest["protocol"]))
    _write(path, manifest)
    with pytest.raises(ValueError, match="seed plan"):
        analysis.load_evidence(evidence, expected_pairs=2)


def test_output_inside_repository_rejected(evidence, monkeypatch):
    monkeypatch.setattr(analysis, "ROOT", evidence)
    with pytest.raises(ValueError, match="outside the repository"):
        analysis.analyze(evidence, evidence / "out", expected_pairs=2)
