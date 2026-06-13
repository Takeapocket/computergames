from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.types import Player


def test_expected_score_is_even_for_equal_ratings():
    from scripts.ladder import expected_score

    assert expected_score(1500.0, 1500.0) == 0.5


def test_update_ratings_moves_winner_up_and_loser_down():
    from scripts.ladder import update_ratings

    red, blue = update_ratings(1500.0, 1500.0, red_score=1.0, k_factor=32.0)

    assert red == 1516.0
    assert blue == 1484.0


def test_default_anchor_player_uses_release_rollout_kwargs():
    from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
    from scripts.ladder import default_anchor_player

    player = default_anchor_player()

    assert player.player_id == "p14_default"
    assert player.kind == "rollout"
    assert player.rating == 1500.0
    assert player.kwargs == RELEASE_DEFAULT_ROLLOUT_KWARGS
    assert player.signature["rollouts_per_move"] == RELEASE_DEFAULT_ROLLOUT_KWARGS["rollouts_per_move"]


def test_load_players_config_accepts_anchor_and_kwargs(tmp_path):
    from scripts import ladder

    config_path = tmp_path / "players.json"
    config_path.write_text(
        json.dumps(
            {
                "players": [
                    "p14_default",
                    {
                        "player_id": "mcts_playout_l8",
                        "kind": "mcts_eval_v1",
                        "kwargs": {
                            "time_limit_ms": 25,
                            "max_iterations": 3,
                            "leaf_policy": "playout",
                            "leaf_playout_turns": 8,
                        },
                        "rating": 1490.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    players = ladder.load_players_config(config_path)

    assert [player.player_id for player in players] == ["p14_default", "mcts_playout_l8"]
    assert players[0].signature["rollouts_per_move"] == 64
    assert players[1].kind == "mcts_eval_v1"
    assert players[1].rating == 1490.0
    assert players[1].kwargs["leaf_policy"] == "playout"
    assert players[1].kwargs["leaf_playout_turns"] == 8
    assert players[1].signature["leaf_policy"] == "playout"


def test_main_uses_players_config_for_round_robin(tmp_path, monkeypatch):
    from scripts import ladder

    config_path = tmp_path / "players.json"
    config_path.write_text(
        json.dumps(
            {
                "players": [
                    {"player_id": "a", "kind": "random"},
                    {
                        "player_id": "b",
                        "kind": "mcts_eval_v1",
                        "kwargs": {"leaf_policy": "playout", "leaf_playout_turns": 4},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_run_ladder_round_robin(players, **kwargs):
        captured["players"] = players
        captured["kwargs"] = kwargs
        return {
            "generated_at": "2026-06-13T00:00:00+00:00",
            "games": 0,
            "seed": kwargs["seed"],
            "layout_id": kwargs["layout_id"],
            "players": {},
        }

    monkeypatch.setattr(ladder, "run_ladder_round_robin", fake_run_ladder_round_robin)

    exit_code = ladder.main(
        [
            "--players-config",
            str(config_path),
            "--games-per-pair",
            "1",
            "--max-turns",
            "40",
            "--seed",
            "3030",
            "--output-dir",
            str(tmp_path / "ladder"),
        ]
    )

    assert exit_code == 0
    assert [player.player_id for player in captured["players"]] == ["a", "b"]
    assert captured["players"][1].kwargs["leaf_policy"] == "playout"
    assert captured["kwargs"]["games_per_pair"] == 1
    assert captured["kwargs"]["max_turns"] == 40
    assert captured["kwargs"]["seed"] == 3030


def test_main_requires_explicit_output_dir_without_research_data_env(monkeypatch):
    from scripts import ladder

    monkeypatch.delenv("CG_RESEARCH_DATA_DIR", raising=False)

    with pytest.raises(SystemExit):
        ladder.main(["--red", "random", "--blue", "random", "--games", "1"])


def test_main_uses_research_data_env_for_default_output_dir(tmp_path, monkeypatch):
    from scripts import ladder

    captured = {}

    def fake_run_ladder_games(red, blue, **kwargs):
        del red, blue
        captured["kwargs"] = kwargs
        return {
            "generated_at": "2026-06-13T00:00:00+00:00",
            "games": 0,
            "seed": kwargs["seed"],
            "layout_id": kwargs["layout_id"],
            "players": {},
        }

    monkeypatch.setenv("CG_RESEARCH_DATA_DIR", str(tmp_path / "research-data"))
    monkeypatch.setattr(ladder, "run_ladder_games", fake_run_ladder_games)

    exit_code = ladder.main(["--red", "random", "--blue", "random", "--games", "1"])

    assert exit_code == 0
    assert captured["kwargs"]["output_dir"] == tmp_path / "research-data" / "ladder"


def test_append_jsonl_result_writes_one_line(tmp_path):
    from scripts.ladder import append_jsonl_result

    path = tmp_path / "ladder.jsonl"
    append_jsonl_result(path, {"game_id": "g1", "winner": "red"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"game_id": "g1", "winner": "red"}


def test_run_ladder_games_updates_ratings_and_writes_jsonl(tmp_path, monkeypatch):
    from scripts import ladder

    def fake_build_ai(kind, *, seed=None, **kwargs):
        return {"kind": kind, "seed": seed, "kwargs": kwargs}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=Player.RED,
            turns=3,
            illegal_moves=0,
            crashes=0,
            timeouts=0,
            avg_step_time_ms=1.5,
            max_step_time_ms=2.0,
            termination_reason="target",
        )

    monkeypatch.setattr(ladder, "build_ai", fake_build_ai)
    monkeypatch.setattr(ladder, "play_one_game", fake_play_one_game)

    red = ladder.LadderPlayer(player_id="red_ai", kind="random")
    blue = ladder.LadderPlayer(player_id="blue_ai", kind="random")
    report = ladder.run_ladder_games(
        red,
        blue,
        games=1,
        seed=2026,
        output_dir=tmp_path,
    )

    assert report["games"] == 1
    assert report["players"]["red_ai"]["rating"] == 1516.0
    assert report["players"]["blue_ai"]["rating"] == 1484.0
    assert (tmp_path / "games.jsonl").exists()


def test_run_ladder_games_rejects_non_empty_games_jsonl(tmp_path, monkeypatch):
    from scripts import ladder

    (tmp_path / "games.jsonl").write_text('{"game_id": "old"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="already contains games"):
        ladder.run_ladder_games(
            ladder.LadderPlayer(player_id="red_ai", kind="random"),
            ladder.LadderPlayer(player_id="blue_ai", kind="random"),
            games=1,
            seed=2026,
            output_dir=tmp_path,
        )


def test_schedule_round_robin_pairs_every_player_with_balanced_colors():
    from scripts import ladder

    players = [
        ladder.LadderPlayer(player_id="a", kind="random"),
        ladder.LadderPlayer(player_id="b", kind="random"),
        ladder.LadderPlayer(player_id="c", kind="random"),
    ]

    schedule = ladder.schedule_round_robin(players, games_per_pair=2)

    assert [(game["red"], game["blue"]) for game in schedule] == [
        ("a", "b"),
        ("b", "a"),
        ("a", "c"),
        ("c", "a"),
        ("b", "c"),
        ("c", "b"),
    ]
    assert [game["pair_index"] for game in schedule] == [0, 0, 1, 1, 2, 2]
    assert [game["game_index"] for game in schedule] == [0, 1, 0, 1, 0, 1]


def test_estimate_rating_uncertainty_shrinks_with_games_and_has_floor():
    from scripts.ladder import estimate_rating_uncertainty

    assert estimate_rating_uncertainty(0) == 350.0
    assert estimate_rating_uncertainty(40) < estimate_rating_uncertainty(10) < 350.0
    assert estimate_rating_uncertainty(1_000_000) == 30.0


def test_schedule_round_robin_rejects_invalid_inputs():
    from scripts import ladder

    one_player = [ladder.LadderPlayer(player_id="a", kind="random")]
    with pytest.raises(ValueError, match="at least two"):
        ladder.schedule_round_robin(one_player, games_per_pair=1)

    players = [
        ladder.LadderPlayer(player_id="a", kind="random"),
        ladder.LadderPlayer(player_id="b", kind="random"),
    ]
    with pytest.raises(ValueError, match="positive"):
        ladder.schedule_round_robin(players, games_per_pair=0)

    duplicate_players = [
        ladder.LadderPlayer(player_id="a", kind="random"),
        ladder.LadderPlayer(player_id="a", kind="random"),
    ]
    with pytest.raises(ValueError, match="unique"):
        ladder.schedule_round_robin(duplicate_players, games_per_pair=1)


def test_render_markdown_report_escapes_table_pipes():
    from scripts import ladder

    report = {
        "generated_at": "2026-06-13T00:00:00+00:00",
        "games": 0,
        "seed": 2026,
        "layout_id": "balanced_v1",
        "players": {
            "a|b": {
                "player_id": "a|b",
                "kind": "rand|om",
                "rating": 1500.0,
                "uncertainty": 350.0,
                "games": 0,
            }
        },
    }

    text = ladder.render_markdown_report(report)

    assert "a\\|b" in text
    assert "rand\\|om" in text


def test_run_ladder_round_robin_updates_all_players_and_writes_reports(tmp_path, monkeypatch):
    from scripts import ladder

    def fake_build_ai(kind, *, seed=None, **kwargs):
        return {"kind": kind, "seed": seed, "kwargs": kwargs}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=Player.RED,
            turns=3,
            illegal_moves=0,
            crashes=0,
            timeouts=0,
            avg_step_time_ms=1.5,
            max_step_time_ms=2.0,
            termination_reason="target",
        )

    monkeypatch.setattr(ladder, "build_ai", fake_build_ai)
    monkeypatch.setattr(ladder, "play_one_game", fake_play_one_game)

    players = [
        ladder.LadderPlayer(player_id="a", kind="random"),
        ladder.LadderPlayer(player_id="b", kind="random"),
        ladder.LadderPlayer(player_id="c", kind="random"),
    ]
    report = ladder.run_ladder_round_robin(
        players,
        games_per_pair=1,
        seed=2026,
        output_dir=tmp_path,
    )

    assert report["games"] == 3
    assert report["schedule"] == [
        {"pair_index": 0, "game_index": 0, "red": "a", "blue": "b"},
        {"pair_index": 1, "game_index": 0, "red": "a", "blue": "c"},
        {"pair_index": 2, "game_index": 0, "red": "b", "blue": "c"},
    ]
    assert {player["games"] for player in report["players"].values()} == {2}
    assert all("rating_interval" in player for player in report["players"].values())
    assert (tmp_path / "games.jsonl").exists()
    rows = [
        json.loads(line)
        for line in (tmp_path / "games.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len({row["game_id"] for row in rows}) == 3
    assert [row["schedule"] for row in rows] == report["schedule"]
    assert rows[0]["players"]["red"]["kind"] == "random"
    assert rows[0]["players"]["red"]["signature"] == {}
    assert rows[0]["players"]["blue"]["kind"] == "random"
    assert (tmp_path / "report.json").exists()
    report_md = tmp_path / "report.md"
    assert report_md.exists()
    assert "| Player | Kind | Rating | Uncertainty Estimate | Games |" in report_md.read_text(encoding="utf-8")
