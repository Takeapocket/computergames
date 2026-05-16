import json
from types import SimpleNamespace

import scripts.search_openings as search_openings
from ai.opening_layouts import PRESETS
from core.types import Position
from scripts.search_openings import (
    classify_layout_style,
    generate_side_layouts,
    generate_stratified_layouts,
    load_release_default_ai_config,
    mirror_layout_for_blue,
    parse_seed_pool,
    promotion_gate_lines,
)


def test_generate_side_layouts_can_limit_count():
    layouts = list(generate_side_layouts(limit=3))

    assert len(layouts) == 3
    assert all(set(layout) == {1, 2, 3, 4, 5, 6} for layout in layouts)


def test_generate_side_layouts_seed_is_deterministic():
    a = list(generate_side_layouts(limit=5, seed=42))
    b = list(generate_side_layouts(limit=5, seed=42))

    assert a == b


def test_generate_side_layouts_uses_red_home_only():
    red_home = {
        Position(0, 0), Position(0, 1), Position(0, 2),
        Position(1, 0), Position(1, 1), Position(2, 0),
    }

    layouts = list(generate_side_layouts(limit=10))

    for layout in layouts:
        assert set(layout.values()) == red_home


def test_mirror_layout_for_blue_keeps_piece_ids():
    red = next(iter(generate_side_layouts(limit=1)))
    blue = mirror_layout_for_blue(red)

    assert set(blue) == set(red)
    assert all(position.row + position.col >= 6 for position in blue.values())


def test_mirror_layout_for_blue_is_centro_symmetric():
    red = {
        1: Position(0, 0),
        2: Position(2, 0),
    }
    blue = mirror_layout_for_blue(red)

    assert blue[1] == Position(4, 4)
    assert blue[2] == Position(2, 4)


def test_classify_layout_style_labels_aggressive_balanced_defensive():
    aggressive = PRESETS["aggressive_v1"].red
    defensive = PRESETS["defensive_v1"].red
    balanced = PRESETS["balanced_v1"].red

    assert classify_layout_style(aggressive) == "aggressive"
    assert classify_layout_style(defensive) == "defensive"
    assert classify_layout_style(balanced) == "balanced"


def test_generate_stratified_layouts_returns_per_style_limit():
    rows = list(generate_stratified_layouts(per_style=2, seed=2026))

    assert len(rows) == 6
    styles = [style for style, _ in rows]
    assert styles.count("aggressive") == 2
    assert styles.count("balanced") == 2
    assert styles.count("defensive") == 2


def test_load_release_default_ai_config_reads_rollout_kwargs(tmp_path):
    params = tmp_path / "default_params.json"
    params.write_text(
        """{
  "ai": "rollout",
  "fallback_ai": "greedy_risk",
  "promotion_report": "reports/p3.md",
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 750.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 32,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein",
  "deadline_safety_ms": 30.0
}
""",
        encoding="utf-8",
    )

    kind, kwargs = load_release_default_ai_config(params)

    assert kind == "rollout"
    assert kwargs == {
        "rollouts_per_move": 32,
        "max_rollout_turns": 80,
        "max_step_time_ms": 750.0,
        "epsilon": 0.1,
        "close_sample_margin": 0.08,
        "close_sample_rollouts_per_move": 32,
        "low_confidence_margin": 0.08,
        "playout_policy": "greedy_risk",
        "cutoff_eval": "zweistein",
        "deadline_safety_ms": 30.0,
    }


def test_load_release_default_ai_config_rejects_non_rollout_default(tmp_path):
    params = tmp_path / "default_params.json"
    params.write_text("""{"ai": "greedy_risk"}\n""", encoding="utf-8")

    try:
        load_release_default_ai_config(params)
    except ValueError as exc:
        assert "must use ai='rollout'" in str(exc)
    else:
        raise AssertionError("expected non-rollout release default to fail")


def test_run_candidate_uses_release_default_ai_matchup(monkeypatch):
    built_configs: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        search_openings,
        "load_release_default_ai_config",
        lambda: ("rollout", {"rollouts_per_move": 32, "cutoff_eval": "zweistein"}),
    )

    def fake_build_ai(name, seed, **kwargs):
        built_configs.append((name, kwargs))
        return {"name": name}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=search_openings.Player.RED,
            illegal_moves=0,
            crashes=0,
            timeouts=1,
            step_times_ms=[1.0],
        )

    monkeypatch.setattr(search_openings, "build_ai", fake_build_ai)
    monkeypatch.setattr(search_openings, "play_one_game", fake_play_one_game)

    search_openings._run_candidate(
        candidate_red={1: Position(0, 0)},
        opponent_blue={1: Position(4, 4)},
        games=1,
        master_seed=2026,
        max_turns=200,
    )

    assert built_configs == [
        ("rollout", {"rollouts_per_move": 32, "cutoff_eval": "zweistein"}),
        ("rollout", {"rollouts_per_move": 32, "cutoff_eval": "zweistein"}),
    ]
    assert all(name != "greedy_risk" for name, _ in built_configs)


def test_run_candidate_aggregates_match_timeouts(monkeypatch):
    def fake_build_ai(name, seed, **kwargs):
        return {"name": name}

    results = [
        SimpleNamespace(
            winner=search_openings.Player.RED,
            illegal_moves=0,
            crashes=0,
            timeouts=1,
            step_times_ms=[1.0],
        ),
        SimpleNamespace(
            winner=search_openings.Player.BLUE,
            illegal_moves=0,
            crashes=0,
            timeouts=2,
            step_times_ms=[2.0],
        ),
    ]

    def fake_play_one_game(**kwargs):
        return results.pop(0)

    monkeypatch.setattr(search_openings, "build_ai", fake_build_ai)
    monkeypatch.setattr(search_openings, "play_one_game", fake_play_one_game)

    stats = search_openings._run_candidate(
        candidate_red={1: Position(0, 0)},
        opponent_blue={1: Position(4, 4)},
        games=2,
        master_seed=2026,
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )

    assert stats["timeouts"] == 3


def test_combine_stats_aggregates_timeouts():
    stats = search_openings._combine_stats([
        {
            "wins": 1,
            "games": 2,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 1,
            "max_step_time_ms": 3.0,
            "total_step_time_ms": 4.0,
            "step_time_count": 2,
        },
        {
            "wins": 2,
            "games": 3,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 2,
            "max_step_time_ms": 5.0,
            "total_step_time_ms": 6.0,
            "step_time_count": 3,
        },
    ])

    assert stats["timeouts"] == 3


def test_parse_seed_pool_deduplicates_and_preserves_order():
    assert parse_seed_pool("2026,2027,2026") == [2026, 2027]


def test_run_against_seed_pool_aggregates_each_seed(monkeypatch):
    red = {1: Position(0, 0)}
    opponents = {"mirror": {1: Position(4, 4)}}
    seen_seeds: list[int] = []
    timeout_by_seed = {2026: 1, 2027: 2}

    def fake_run_against_opponents(
        *,
        candidate_red,
        opponents,
        games_per_opponent,
        master_seed,
        max_turns,
        ai_kind=None,
        ai_kwargs=None,
    ):
        assert candidate_red is red
        seen_seeds.append(master_seed)
        return {
            "wins": 1,
            "games": games_per_opponent,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": timeout_by_seed[master_seed],
            "max_step_time_ms": 1.0,
            "avg_step_time_ms": 1.0,
            "total_step_time_ms": 2.0,
            "step_time_count": 2,
        }

    monkeypatch.setattr(search_openings, "_run_against_opponents", fake_run_against_opponents)

    stats = search_openings._run_against_seed_pool(
        candidate_red=red,
        opponents=opponents,
        games_per_opponent=3,
        seed_pool=[2026, 2027],
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )

    assert seen_seeds == [2026, 2027]
    assert stats["seed_count"] == 2
    assert stats["wins"] == 2
    assert stats["games"] == 6
    assert stats["timeouts"] == 3


def test_main_json_output_includes_reproducible_decision_and_train_rows(tmp_path, monkeypatch):
    red = {1: Position(0, 0)}

    monkeypatch.setattr(
        search_openings,
        "load_release_default_ai_config",
        lambda: ("rollout", {"rollouts_per_move": 32}),
    )
    monkeypatch.setattr(
        search_openings,
        "generate_stratified_layouts",
        lambda *, per_style, seed: iter([("aggressive", red)]),
    )
    monkeypatch.setattr(search_openings, "_preset_blue_layouts", lambda: {})
    monkeypatch.setattr(search_openings, "_opponent_blue_layouts", lambda red_layout, blue_presets: {"mirror": red})
    monkeypatch.setattr(
        search_openings,
        "_run_against_seed_pool",
        lambda **kwargs: {
            "wins": 1,
            "games": 2,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "max_step_time_ms": 1.0,
            "avg_step_time_ms": 1.0,
            "total_step_time_ms": 2.0,
            "step_time_count": 2,
            "seed_count": len(kwargs["seed_pool"]),
            "seeds": list(kwargs["seed_pool"]),
        },
    )

    output = tmp_path / "opening.md"
    json_output = tmp_path / "opening.json"
    search_openings.main([
        "--candidate-mode", "stratified",
        "--per-style", "1",
        "--sample-size", "4",
        "--games", "1",
        "--validation-games", "1",
        "--top-k", "1",
        "--seed", "99",
        "--seed-pool", "2026,2027",
        "--max-turns", "7",
        "--output", str(output),
        "--json-output", str(json_output),
    ])

    payload = json.loads(json_output.read_text(encoding="utf-8"))

    assert payload["generated_at"]
    assert payload["argv"] == [
        "--candidate-mode", "stratified",
        "--per-style", "1",
        "--sample-size", "4",
        "--games", "1",
        "--validation-games", "1",
        "--top-k", "1",
        "--seed", "99",
        "--seed-pool", "2026,2027",
        "--max-turns", "7",
        "--output", str(output),
        "--json-output", str(json_output),
    ]
    assert payload["seed"] == 99
    assert payload["sample_size"] == 4
    assert payload["games_per_train_opponent"] == 1
    assert payload["validation_games_per_opponent"] == 1
    assert payload["top_k"] == 1
    assert payload["max_turns"] == 7
    assert payload["seed_pool"] == [2026, 2027]
    assert payload["validation_seed_pool"] == [12026, 12027]
    assert payload["decision"]["promote_layout"] is False
    assert "intentionally too small" in payload["decision"]["reason"]
    assert payload["train_rows"][0]["style"] == "aggressive"


def test_run_against_opponents_aggregates_each_opponent(monkeypatch):
    red = {1: Position(0, 0)}
    opponents = {
        "mirror": {1: Position(4, 4)},
        "balanced": {1: Position(3, 4)},
    }
    seen: list[dict[int, Position]] = []

    def fake_run_candidate(
        *,
        candidate_red,
        opponent_blue,
        games,
        master_seed,
        max_turns,
        ai_kind=None,
        ai_kwargs=None,
    ):
        assert candidate_red is red
        assert games == 3
        seen.append(opponent_blue)
        return {
            "wins": len(seen),
            "games": games,
            "illegal_moves": 0,
            "crashes": 0,
            "max_step_time_ms": float(len(seen)),
            "avg_step_time_ms": 1.0,
            "total_step_time_ms": 2.0,
            "step_time_count": 2,
        }

    monkeypatch.setattr(search_openings, "_run_candidate", fake_run_candidate)

    stats = search_openings._run_against_opponents(
        candidate_red=red,
        opponents=opponents,
        games_per_opponent=3,
        master_seed=2026,
        max_turns=200,
    )

    assert seen == list(opponents.values())
    assert stats["wins"] == 3
    assert stats["games"] == 6
    assert stats["max_step_time_ms"] == 2.0

def test_promotion_gate_lines_match_ai_strengthening_spec():
    text = "\n".join(promotion_gate_lines())

    assert "candidate layout vs current default layout 双边合并胜率 >= 55%" in text
    assert "Wilson 95% CI 下界 >= 50%" in text
    assert "至少 3 个不同 seed 池复验" in text
