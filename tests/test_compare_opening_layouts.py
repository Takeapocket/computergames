import json
from types import SimpleNamespace

import scripts.compare_opening_layouts as compare_opening_layouts
from core.types import Player, Position


def _stats(*, wins: int, games: int) -> dict:
    return {
        "wins": wins,
        "games": games,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "max_step_time_ms": 1.0,
        "avg_step_time_ms": 1.0,
        "total_step_time_ms": float(games),
        "step_time_count": games,
    }


def test_load_candidate_layout_reads_validation_row(tmp_path):
    report = tmp_path / "opening.json"
    report.write_text(
        json.dumps(
            {
                "validation_top": [
                    {
                        "style": "balanced",
                        "red_layout": {
                            "1": [0, 0],
                            "2": [0, 1],
                            "3": [0, 2],
                            "4": [1, 0],
                            "5": [1, 1],
                            "6": [2, 0],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    candidate = compare_opening_layouts.load_candidate_layout(report, section="validation_top", index=0)

    assert candidate.style == "balanced"
    assert candidate.red_layout[6] == Position(2, 0)


def test_run_direction_counts_candidate_wins_for_blue(monkeypatch):
    built: list[tuple[str, int, dict]] = []

    def fake_build_ai(kind, seed, **kwargs):
        built.append((kind, seed, kwargs))
        return {"kind": kind, "seed": seed}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=Player.BLUE,
            illegal_moves=0,
            crashes=0,
            timeouts=1,
            step_times_ms=[2.0, 4.0],
        )

    monkeypatch.setattr(compare_opening_layouts, "build_ai", fake_build_ai)
    monkeypatch.setattr(compare_opening_layouts, "play_one_game", fake_play_one_game)

    stats = compare_opening_layouts._run_direction(
        red_layout={1: Position(0, 0)},
        blue_layout={1: Position(4, 4)},
        candidate_player=Player.BLUE,
        games=1,
        master_seed=2026,
        max_turns=10,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 1},
    )

    assert stats["wins"] == 1
    assert stats["games"] == 1
    assert stats["timeouts"] == 1
    assert stats["avg_step_time_ms"] == 3.0
    assert [kind for kind, _, _ in built] == ["rollout", "rollout"]


def test_run_candidate_vs_baseline_covers_red_and_blue_roles(monkeypatch):
    candidate_red = {
        1: Position(0, 0),
        2: Position(0, 1),
        3: Position(0, 2),
        4: Position(1, 0),
        5: Position(1, 1),
        6: Position(2, 0),
    }
    baseline_red = {
        1: Position(0, 0),
        2: Position(1, 0),
        3: Position(1, 1),
        4: Position(2, 0),
        5: Position(0, 2),
        6: Position(0, 1),
    }
    baseline_blue = compare_opening_layouts.mirror_layout_for_blue(baseline_red)
    seen_players: list[Player] = []

    def fake_run_direction(*, candidate_player, games, **kwargs):
        seen_players.append(candidate_player)
        return _stats(wins=1 if candidate_player is Player.RED else 2, games=games)

    monkeypatch.setattr(compare_opening_layouts, "_run_direction", fake_run_direction)

    result = compare_opening_layouts._run_candidate_vs_baseline(
        candidate_red=candidate_red,
        baseline_red=baseline_red,
        baseline_blue=baseline_blue,
        games_per_side=3,
        seed_pool=[2026, 2027],
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={},
    )

    assert seen_players == [Player.RED, Player.BLUE, Player.RED, Player.BLUE]
    assert result["wins"] == 6
    assert result["games"] == 12
    assert result["candidate_as_red"]["games"] == 6
    assert result["candidate_as_blue"]["games"] == 6
    assert result["seed_count"] == 2


def test_decision_reason_marks_failed_expansion():
    reason = compare_opening_layouts._decision_reason(
        stats=_stats(wins=23, games=60),
        win_rate=23 / 60,
        ci=(0.2708, 0.5098),
    )

    assert "60-game expansion failed" in reason
    assert "23/60" in reason
    assert "defaults unchanged" in reason


def test_main_writes_json_report(tmp_path, monkeypatch):
    candidate_report = tmp_path / "p53.json"
    output = tmp_path / "p54.md"
    json_output = tmp_path / "p54.json"
    candidate_report.write_text(
        json.dumps(
            {
                "validation_top": [
                    {
                        "style": "balanced",
                        "red_layout": {
                            "1": [0, 0],
                            "2": [1, 0],
                            "3": [1, 1],
                            "4": [2, 0],
                            "5": [0, 2],
                            "6": [0, 1],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        compare_opening_layouts,
        "load_release_default_ai_config",
        lambda: ("rollout", {"rollouts_per_move": 32}),
    )
    monkeypatch.setattr(
        compare_opening_layouts,
        "_run_candidate_vs_baseline",
        lambda **kwargs: {
            **_stats(wins=3, games=8),
            "seed_count": 2,
            "seeds": [2026, 2027],
            "candidate_as_red": _stats(wins=2, games=4),
            "candidate_as_blue": _stats(wins=1, games=4),
        },
    )

    compare_opening_layouts.main(
        [
            "--candidate-report",
            str(candidate_report),
            "--games-per-side",
            "2",
            "--seed-pool",
            "2026,2027",
            "--max-turns",
            "7",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--decision-reason",
            "60-game expansion failed; stop this candidate route.",
        ]
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))

    assert payload["baseline_layout_id"] == "balanced_v1"
    assert payload["candidate"]["style"] == "balanced"
    assert payload["stats"]["wins"] == 3
    assert payload["stats"]["games"] == 8
    assert payload["decision"]["promote_layout"] is False
    assert payload["decision"]["reason"] == "60-game expansion failed; stop this candidate route."
    text = output.read_text(encoding="utf-8")
    assert "Candidate layout vs current default layout, with both red and blue roles covered." in text
    assert "Reason: 60-game expansion failed; stop this candidate route." in text
    assert "P5.4" not in text
