from types import SimpleNamespace

import scripts.search_openings as search_openings
from core.types import Position
from scripts.search_openings import generate_side_layouts, mirror_layout_for_blue, promotion_gate_lines


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


def test_run_candidate_uses_symmetric_ai_matchup(monkeypatch):
    built_names: list[str] = []

    def fake_build_ai(name, seed):
        built_names.append(name)
        return {"name": name}

    def fake_play_one_game(**kwargs):
        return SimpleNamespace(
            winner=search_openings.Player.RED,
            illegal_moves=0,
            crashes=0,
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

    assert built_names == ["greedy_risk", "greedy_risk"]


def test_run_against_opponents_aggregates_each_opponent(monkeypatch):
    red = {1: Position(0, 0)}
    opponents = {
        "mirror": {1: Position(4, 4)},
        "balanced": {1: Position(3, 4)},
    }
    seen: list[dict[int, Position]] = []

    def fake_run_candidate(*, candidate_red, opponent_blue, games, master_seed, max_turns):
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
