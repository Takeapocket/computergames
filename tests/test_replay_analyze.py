from __future__ import annotations

from ai.match import default_starting_state
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from record.game_record import GameRecord


def _single_step_record(*, source: str = "opponent", dice: int = 1) -> GameRecord:
    state = default_starting_state()
    record = GameRecord.from_state(state)
    move = state.legal_moves(Player.RED, dice)[0]
    applied = state.apply_move(move, dice=dice)
    record.append(dice=dice, move=applied, state_after=state, source=source)
    return record


class _FirstLegalAI:
    name = "first_legal"

    def choose_move(self, state: GameState, dice: int):
        legal = state.legal_moves(state.current_player, dice)
        return legal[0] if legal else None


def _two_step_record_with_one_recommendation_mismatch() -> GameRecord:
    state = default_starting_state()
    record = GameRecord.from_state(state)

    first_dice = 1
    first_move = state.legal_moves(state.current_player, first_dice)[0]
    applied_first = state.apply_move(first_move, dice=first_dice)
    record.append(dice=first_dice, move=applied_first, state_after=state, source="self")

    for second_dice in range(1, 7):
        legal = state.legal_moves(state.current_player, second_dice)
        if len(legal) > 1:
            second_move = legal[-1]
            applied_second = state.apply_move(second_move, dice=second_dice)
            record.append(dice=second_dice, move=applied_second, state_after=state, source="self")
            return record

    raise AssertionError("test setup requires a second position with multiple legal moves")


def test_load_records_accepts_game_record_json(tmp_path):
    from scripts.replay_analyze import load_records

    record = _single_step_record()
    path = tmp_path / "game.json"
    record.save(path)

    loaded = load_records([path])

    assert len(loaded) == 1
    assert loaded[0].steps[0].dice == 1


def test_summarize_records_counts_steps_sources_and_results():
    from scripts.replay_analyze import summarize_records

    record = _single_step_record(source="opponent", dice=2)
    record.result = {"winner": "red", "reason": "target"}

    summary = summarize_records([record])

    assert summary["games"] == 1
    assert summary["steps"] == 1
    assert summary["sources"] == {"opponent": 1}
    assert summary["dice_counts"] == {"2": 1}
    assert summary["results"] == {"red:target": 1}


def test_classify_step_marks_target_threat_and_hit():
    from scripts.replay_analyze import classify_step

    state = GameState.from_layout(
        red={
            1: Position(3, 4),
            2: Position(0, 1),
            3: Position(1, 0),
            4: Position(1, 1),
            5: Position(2, 0),
            6: Position(0, 2),
        },
        blue={
            1: Position(4, 3),
            2: Position(3, 3),
            3: Position(4, 2),
            4: Position(2, 4),
            5: Position(2, 3),
            6: Position(3, 2),
        },
        current_player=Player.RED,
    )
    move = Move(Player.RED, 1, Position(3, 4), Position(4, 4))

    labels = classify_step(state, dice=1, move=move)

    assert "mover_had_target_threat" in labels
    assert "mover_hit_target" in labels


def test_compare_record_recommendations_marks_matches_and_mismatches():
    from scripts.replay_analyze import compare_record_recommendations

    record = _two_step_record_with_one_recommendation_mismatch()

    rows = compare_record_recommendations(
        record,
        recommender_factory=lambda step_index: _FirstLegalAI(),
    )

    assert [row["matched_recommendation"] for row in rows] == [True, False]
    assert rows[0]["turn"] == 1
    assert rows[0]["source"] == "self"
    assert rows[0]["recommended_move"] == rows[0]["recorded_move"]
    assert rows[1]["recommended_move"] != rows[1]["recorded_move"]


def test_summarize_recommendation_comparison_counts_by_source():
    from scripts.replay_analyze import summarize_recommendation_comparison

    record = _two_step_record_with_one_recommendation_mismatch()

    summary = summarize_recommendation_comparison(
        [record],
        recommender_factory=lambda step_index: _FirstLegalAI(),
    )

    assert summary["records"] == 1
    assert summary["compared_steps"] == 2
    assert summary["matches"] == 1
    assert summary["mismatches"] == 1
    assert summary["no_recommendation"] == 0
    assert summary["by_source"] == {
        "self": {
            "compared_steps": 2,
            "matches": 1,
            "mismatches": 1,
            "no_recommendation": 0,
        }
    }


def test_summarize_recommendation_comparison_can_include_step_rows():
    from scripts.replay_analyze import summarize_recommendation_comparison

    record = _two_step_record_with_one_recommendation_mismatch()

    summary = summarize_recommendation_comparison(
        [record],
        recommender_factory=lambda step_index: _FirstLegalAI(),
        include_rows=True,
    )

    assert len(summary["rows"]) == 2
    assert summary["rows"][0]["turn"] == 1
    assert summary["rows"][0]["recorded_move"] == summary["rows"][0]["recommended_move"]


def test_default_recommender_factory_loads_release_default_kwargs(monkeypatch):
    from scripts import replay_analyze

    calls = {}

    def fake_load_release_default_rollout_kwargs():
        calls["loaded"] = True
        return {"rollouts_per_move": 64, "epsilon": 0.05}

    def fake_build_ai(kind, *, seed=None, **kwargs):
        calls["kind"] = kind
        calls["seed"] = seed
        calls["kwargs"] = kwargs
        return "ai"

    monkeypatch.setattr(
        replay_analyze,
        "load_release_default_rollout_kwargs",
        fake_load_release_default_rollout_kwargs,
    )
    monkeypatch.setattr(replay_analyze, "build_ai", fake_build_ai)

    ai = replay_analyze.default_recommender_factory(3)

    assert ai == "ai"
    assert calls == {
        "loaded": True,
        "kind": "rollout",
        "seed": 202600003,
        "kwargs": {"rollouts_per_move": 64, "epsilon": 0.05},
    }
