from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from scripts import rebaseline_p14 as runner


class FastAI:
    name = "rollout"
    last_timed_out = False
    last_used_fallback = False
    last_root_stats = []

    def __init__(self, seed, kwargs):
        self.rng = random.Random(seed)
        self.__dict__.update(kwargs)

    def choose_move(self, state, dice):
        return self.rng.choice(state.legal_moves(state.current_player, dice))


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for folder in ("core", "ai", "record", "scripts", "gui"):
        (root / folder).mkdir(parents=True)
        (root / folder / "source.py").write_text("# frozen source\n", encoding="utf-8")
    (root / "release/v1.0").mkdir(parents=True)
    for name in runner.CONFIG_PATHS:
        (root / name).write_text("{}\n", encoding="utf-8")
    builds = []

    def build(kind, *, seed, **kwargs):
        assert kind == "rollout"
        builds.append((seed, dict(kwargs)))
        return FastAI(seed, kwargs)

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "_git", lambda *args: "a" * 40 if args[0] == "rev-parse" else " M core/source.py")
    monkeypatch.setattr(runner, "build_ai", build)
    return tmp_path / "results", root, builds


def test_schedule_pairs_reset_identity_seeds_and_alternate_order():
    schedule = runner.make_schedule(2)
    assert [game["red"] for game in schedule] == [runner.P14, runner.LEGACY, runner.LEGACY, runner.P14]
    for a, b in (schedule[:2], schedule[2:]):
        assert a["dice_seed"] == b["dice_seed"] == a["pair_seed"] * 3
        assert a["actor_seeds"] == b["actor_seeds"] == {
            runner.P14: a["pair_seed"] * 3 + 1, runner.LEGACY: a["pair_seed"] * 3 + 2,
        }
        assert (a["red"], a["blue"]) == (b["blue"], b["red"])
    assert runner.make_schedule(1, 1000)[0]["pair_seed"] == runner.BASE_SEED + 1000


@pytest.mark.parametrize("pairs,pair_start", [(0, 0), (-1, 0), (1, -1), (True, 0)])
def test_invalid_schedule_rejected(pairs, pair_start):
    with pytest.raises((ValueError, TypeError)):
        runner.make_schedule(pairs, pair_start)


def test_protocol_pins_both_explicit_parameter_sets(environment):
    protocol = runner.make_protocol(100, 0)
    assert protocol["actors"][runner.P14]["kwargs"] == RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert protocol["actors"][runner.LEGACY]["kwargs"] == runner.LEGACY_KWARGS
    assert protocol["actors"][runner.LEGACY]["kwargs"]["deadline_safety_ms"] == 30.0
    assert protocol["expected_games"] == 200
    assert protocol["first_player"] == "red"
    assert protocol["layout"] == "balanced_v1"
    assert protocol["max_turns"] == 200
    assert protocol["git_dirty"] is True
    assert "core/source.py" in protocol["source_sha256"]


def test_run_records_legal_games_and_resume_never_replays_or_overwrites(environment, monkeypatch):
    output, root, builds = environment
    summary = runner.run(output, pairs=2)
    assert summary["status"] == "complete"
    assert summary["completed_games"] == 4
    manifest = runner._read_json(output / "manifest.json")
    files = sorted((output / "games").glob("*.json"))
    assert len(files) == 4
    for path in files:
        game = runner._read_json(path)
        runner.validate_game(game, game["input"], manifest)
        assert len(game["step_times_ms"]) == game["result"]["turns"]
        assert game["observed_calls"][0]["color"] == "red"
        assert sum(value["step_count"] for value in game["by_actor"].values()) == len(game["step_times_ms"])
        assert sum(value["thinking_seconds"] for value in game["by_actor"].values()) == pytest.approx(sum(game["step_times_ms"]) / 1000)
    assert (output / "source_snapshot/core/source.py").read_bytes() == (root / "core/source.py").read_bytes()
    # Manifest constructs 2 signature-only AIs; each game constructs 2 independent AIs.
    assert len(builds) == 10
    assert builds[2:4] == builds[4:6]
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    monkeypatch.setattr(runner, "run_game", lambda *args: pytest.fail("resume replayed a finished game"))
    assert runner.run(output, pairs=2, resume=True) == summary
    after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    assert before == after


def test_existing_directory_requires_resume_and_repo_output_rejected(environment):
    output, root, _ = environment
    output.mkdir()
    (output / "untouched.txt").write_text("user file")
    with pytest.raises(ValueError, match="not empty"):
        runner.run(output, pairs=1)
    with pytest.raises(ValueError, match="outside"):
        runner.run(root / "data", pairs=1)
    assert (output / "untouched.txt").read_text() == "user file"


@pytest.mark.parametrize("mutation", ["source", "config", "seeds", "corrupt_game", "snapshot"])
def test_resume_rejects_mismatch_before_any_write(environment, mutation):
    output, root, _ = environment
    runner.run(output, pairs=1)
    if mutation == "source":
        (root / "core/source.py").write_text("# changed source\n", encoding="utf-8")
    elif mutation == "config":
        (root / runner.CONFIG_PATHS[0]).write_text('{"changed": true}', encoding="utf-8")
    elif mutation == "corrupt_game":
        path = next((output / "games").glob("*.json"))
        data = runner._read_json(path)
        data["winner_actor"] = "tampered"
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "snapshot":
        (output / "source_snapshot/core/source.py").write_text("tampered", encoding="utf-8")
    before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    with pytest.raises(ValueError):
        runner.run(output, pairs=1, pair_start=1 if mutation == "seeds" else 0, resume=True)
    assert before == {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}


def test_interrupted_run_resumes_only_missing_game(environment, monkeypatch):
    output, _, _ = environment
    original = runner.run_game
    calls = []

    def interrupt(game, manifest):
        calls.append(game["game_id"])
        if len(calls) == 2:
            raise KeyboardInterrupt
        return original(game, manifest)

    monkeypatch.setattr(runner, "run_game", interrupt)
    with pytest.raises(KeyboardInterrupt):
        runner.run(output, pairs=1)
    assert len(list((output / "games").glob("*.json"))) == 1
    monkeypatch.setattr(runner, "run_game", original)
    assert runner.run(output, pairs=1, resume=True)["status"] == "complete"


def test_choose_exception_preserves_replay_and_failed_attempt_time(environment, monkeypatch):
    output, _, _ = environment
    monkeypatch.setattr(FastAI, "choose_move", lambda *args: (_ for _ in ()).throw(RuntimeError("expected fault")))
    summary = runner.run(output, pairs=1)
    assert summary["status"] == "failed"
    assert summary["failed_games"] == 2
    for path in (output / "games").glob("*.json"):
        data = runner._read_json(path)
        assert data["termination_reason"] == "crash"
        assert data["record"] is not None
        assert data["result"]["turns"] == 0
        assert len(data["step_times_ms"]) == 1
        assert data["errors"][0] == {"type": "RuntimeError", "message": "expected fault"}
        assert data["by_actor"][data["input"]["red"]]["step_count"] == 1


def test_runner_fault_saved_and_main_nonzero(environment, monkeypatch):
    output, _, _ = environment
    monkeypatch.setattr(runner, "run_game", lambda *args: (_ for _ in ()).throw(RuntimeError("outside harness")))
    assert runner.main(["--output-dir", str(output), "--pairs", "1"]) == 1
    data = runner._read_json(next((output / "games").glob("*.json")))
    assert data["termination_reason"] == "runner_error"
    assert data["record"] is None
    assert data["errors"][0]["message"] == "outside harness"


def test_source_mutation_during_run_cannot_complete(environment, monkeypatch):
    output, root, _ = environment
    original = runner.run_game

    def changed(game, manifest):
        result = original(game, manifest)
        (root / "core/source.py").write_text("# concurrent edit\n", encoding="utf-8")
        return result

    monkeypatch.setattr(runner, "run_game", changed)
    result = runner.run(output, pairs=1)
    assert result["status"] == "failed"
    assert result["source_unchanged"] is False


def test_atomic_publish_cannot_overwrite(tmp_path):
    path = tmp_path / "result.json"
    runner._atomic_new(path, b"original")
    with pytest.raises(FileExistsError):
        runner._atomic_new(path, b"replacement")
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]
