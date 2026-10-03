from __future__ import annotations

import importlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import _bench_meta, ladder


@pytest.mark.parametrize(
    "module_name",
    ["analyze_rollout_failures", "search_openings", "timing_budget_probe", "screen_openings_light"],
)
def test_release_readers_preserve_explicit_path_and_reject_invalid_numbers(tmp_path, module_name):
    reader = importlib.import_module(f"scripts.{module_name}").load_release_default_ai_config
    path = tmp_path / "params.json"
    path.write_text(json.dumps({"ai": "rollout", "epsilon": 0.05, "fallback_ai": "greedy_risk"}), encoding="utf-8")
    assert reader(str(path)) == ("rollout", {"epsilon": 0.05})
    for payload in ("[]", '{"ai":"rollout","epsilon":NaN}', '{"ai":"rollout","epsilon":1e999}'):
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError):
            reader(path)


@pytest.mark.parametrize("error", [FileNotFoundError("git unavailable"), subprocess.CalledProcessError(1, "git"), subprocess.TimeoutExpired("git", 5)])
def test_git_metadata_failure_reports_unknown(tmp_path, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(_bench_meta.subprocess, "check_output", fail)
    metadata = _bench_meta.build_provenance(repo_root=tmp_path, script_name="probe.py", argv=[], starting_layout_id="balanced_v1")
    assert metadata["git_dirty"] is None
    assert json.loads(json.dumps(metadata))["git_dirty"] is None


def test_git_metadata_uses_only_command_local_trust(tmp_path, monkeypatch):
    commands = []

    def output(args, **kwargs):
        commands.append(args)
        return b"revision\n" if args[-2:] == ["rev-parse", "HEAD"] else b""

    monkeypatch.setattr(_bench_meta.subprocess, "check_output", output)
    assert _bench_meta.git_revision(tmp_path) == "revision"
    assert _bench_meta.git_dirty(tmp_path) is False
    assert all(args[:3] == ["git", "-c", f"safe.directory={tmp_path.resolve().as_posix()}"] for args in commands)


@pytest.mark.parametrize("field,value", [("games", -1), ("games", True), ("games", 1.5), ("max_turns", 0), ("max_turns", True), ("seed", 1.5), ("k_factor", 0), ("k_factor", -1), ("k_factor", float("nan")), ("k_factor", float("inf"))])
def test_ladder_rejects_invalid_run_inputs_before_outputs(tmp_path, monkeypatch, field, value):
    players = [ladder.LadderPlayer("a", "random"), ladder.LadderPlayer("b", "random")]
    options = {"games": 0, "seed": 1, "max_turns": 10, "k_factor": 32.0}
    options[field] = value
    output = tmp_path / "invalid"
    monkeypatch.setattr(ladder, "play_one_game", lambda **kwargs: pytest.fail("must validate before running a game"))
    with pytest.raises(ValueError):
        ladder.run_ladder_games(*players, output_dir=output, **options)
    assert not output.exists()
    assert [player.rating for player in players] == [1500.0, 1500.0]


def test_ladder_rejects_duplicate_ids_and_mutated_rating_before_outputs(tmp_path):
    red = ladder.LadderPlayer("a", "random")
    blue = ladder.LadderPlayer("a", "random")
    with pytest.raises(ValueError, match="unique"):
        ladder.run_ladder_games(red, blue, games=0, seed=1, output_dir=tmp_path / "duplicate")
    blue.player_id = "b"
    red.rating = float("nan")
    with pytest.raises(ValueError, match="rating"):
        ladder.run_ladder_round_robin([red, blue], games_per_pair=1, seed=1, output_dir=tmp_path / "nan")
    assert not (tmp_path / "duplicate").exists()
    assert not (tmp_path / "nan").exists()


def test_ladder_zero_game_probe_still_writes_reports(tmp_path):
    report = ladder.run_ladder_games(ladder.LadderPlayer("a", "random"), ladder.LadderPlayer("b", "random"), games=0, seed=1, output_dir=tmp_path)
    assert report["games"] == 0
    assert (tmp_path / "report.json").exists()
    assert not (tmp_path / "games.jsonl").exists()


@pytest.mark.parametrize("entry", [{"player_id": "", "kind": "random"}, {"player_id": None, "kind": "random"}, {"player_id": "a", "kind": "random", "rating": float("nan")}, {"player_id": "a", "kind": "rollout", "kwargs": {"epsilon": float("inf")}}])
def test_ladder_config_rejects_invalid_identity_and_numbers(tmp_path, entry):
    path = tmp_path / "players.json"
    path.write_text(json.dumps({"players": [entry, {"player_id": "b", "kind": "random"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        ladder.load_players_config(path)


def test_ladder_expected_score_handles_extreme_finite_rating_gap():
    assert ladder.expected_score(-1e308, 1e308) == 0.0
    assert ladder.expected_score(1e308, -1e308) == 1.0


@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf")])
def test_ladder_update_rejects_invalid_k(value):
    with pytest.raises(ValueError):
        ladder.update_ratings(1500, 1500, red_score=1, k_factor=value)


@pytest.mark.parametrize("returned", [{}, "move", True, 1, SimpleNamespace()])
def test_match_harness_counts_wrong_return_type_as_illegal(returned):
    import random

    from ai.match import play_one_game

    ai = SimpleNamespace(choose_move=lambda state, dice: returned)
    result = play_one_game(red_ai=ai, blue_ai=ai, dice_rng=random.Random(1))
    assert result.illegal_moves == 1
    assert result.crashes == 0
    assert result.turns == 0
    assert result.termination_reason == "illegal_move"


def test_preflight_reports_wrong_json_shape_without_attribute_error(tmp_path):
    from scripts.preflight_check import PreflightError, _read_json

    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(PreflightError, match="JSON object required"):
        _read_json(path)


def test_launcher_reports_wrong_json_shape_without_attribute_error(tmp_path):
    from scripts.launcher import LauncherError, print_release_status

    release = tmp_path / "release" / "v1.0"
    release.mkdir(parents=True)
    (release / "config.json").write_text("[]", encoding="utf-8")
    (release / "default_params.json").write_text("{}", encoding="utf-8")
    with pytest.raises(LauncherError, match="JSON"):
        print_release_status(tmp_path)


def test_ladder_cli_rejects_unknown_ai_kwargs_without_outputs(tmp_path, capsys):
    path = tmp_path / "players.json"
    path.write_text(
        json.dumps({"players": [
            {"player_id": "bad", "kind": "random", "kwargs": {"unsupported": 1}},
            {"player_id": "good", "kind": "random"},
        ]}),
        encoding="utf-8",
    )
    output = tmp_path / "unused-output"
    with pytest.raises(SystemExit) as error:
        ladder.main(["--players-config", str(path), "--output-dir", str(output)])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "does not accept kwargs" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not output.exists()
