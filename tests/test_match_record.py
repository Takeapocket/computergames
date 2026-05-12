import pytest

from core.game_state import GameState
from core.types import Player, Position
from record.game_record import GameRecord
from record.match_record import JIA_FIRST_GAMES, MatchRecord


def _make_match(our_side=Player.RED, our_role="甲", **kwargs):
    return MatchRecord(our_side=our_side, our_role=our_role, **kwargs)


def _make_game(red_pos=(0, 0), blue_pos=(4, 4)):
    state = GameState.from_layout(
        red={1: Position(*red_pos)},
        blue={1: Position(*blue_pos)},
    )
    return GameRecord.from_state(state)


class TestConstruction:
    def test_default_fields(self):
        match = _make_match()
        assert match.our_side is Player.RED
        assert match.our_role == "甲"
        assert match.total_games == 7
        assert match.target_wins == 4
        assert match.games == []
        assert match.games_won_us == 0
        assert match.games_won_them == 0
        assert match.current_game_index == 1
        assert match.phase == "setup"
        assert match.last_game_winner is None
        assert match.match_id
        assert match.started_at

    def test_accepts_player_value_string(self):
        match = MatchRecord(our_side="blue", our_role="乙")
        assert match.our_side is Player.BLUE

    def test_invalid_role(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="X")

    def test_invalid_total_games(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="甲", total_games=0)

    def test_target_wins_out_of_range(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="甲", target_wins=10)

    def test_invalid_phase(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="甲", phase="weird")

    def test_invalid_last_game_winner(self):
        with pytest.raises(ValueError):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                last_game_winner="draw",
            )

    def test_invalid_current_game_index(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="甲", current_game_index=0)

    def test_negative_scores(self):
        with pytest.raises(ValueError):
            MatchRecord(our_side=Player.RED, our_role="甲", games_won_us=-1)


class TestFirstMover:
    @pytest.mark.parametrize(
        "our_role,game_index,expected",
        [
            ("甲", 1, "us"),
            ("甲", 2, "them"),
            ("甲", 3, "them"),
            ("甲", 4, "us"),
            ("甲", 5, "us"),
            ("甲", 6, "them"),
            ("甲", 7, "them"),
            ("乙", 1, "them"),
            ("乙", 2, "us"),
            ("乙", 3, "us"),
            ("乙", 4, "them"),
            ("乙", 5, "them"),
            ("乙", 6, "us"),
            ("乙", 7, "us"),
        ],
    )
    def test_first_mover_matrix(self, our_role, game_index, expected):
        match = _make_match(our_role=our_role)
        assert match.first_mover(game_index) == expected

    @pytest.mark.parametrize(
        "our_side,our_role,game_index,expected_color",
        [
            (Player.RED, "甲", 1, Player.RED),
            (Player.RED, "甲", 2, Player.BLUE),
            (Player.BLUE, "甲", 1, Player.BLUE),
            (Player.BLUE, "甲", 2, Player.RED),
            (Player.RED, "乙", 1, Player.BLUE),
            (Player.RED, "乙", 2, Player.RED),
            (Player.BLUE, "乙", 1, Player.RED),
            (Player.BLUE, "乙", 2, Player.BLUE),
        ],
    )
    def test_first_mover_color(self, our_side, our_role, game_index, expected_color):
        match = _make_match(our_side=our_side, our_role=our_role)
        assert match.first_mover_color(game_index) is expected_color

    def test_first_mover_out_of_range(self):
        match = _make_match()
        with pytest.raises(ValueError):
            match.first_mover(0)
        with pytest.raises(ValueError):
            match.first_mover(8)


class TestWinnerJudging:
    def test_initial_no_winner(self):
        assert _make_match().winner() is None

    def test_win_us_at_4(self):
        match = _make_match(games_won_us=4, phase="finished")
        assert match.winner() == "us"

    def test_win_them_at_4(self):
        match = _make_match(games_won_them=4, phase="finished")
        assert match.winner() == "them"

    def test_score_3_3_no_winner(self):
        match = _make_match(games_won_us=3, games_won_them=3, current_game_index=7)
        assert match.winner() is None


class TestAppendFinishedGame:
    def test_us_wins_one(self):
        match = _make_match()
        match.append_finished_game(_make_game(), "us")
        assert match.games_won_us == 1
        assert match.games_won_them == 0
        assert match.last_game_winner == "us"
        assert match.current_game_index == 2
        assert match.phase == "setup"
        assert len(match.games) == 1

    def test_them_wins_one(self):
        match = _make_match()
        match.append_finished_game(_make_game(), "them")
        assert match.games_won_them == 1
        assert match.last_game_winner == "them"

    def test_4_0_sweep(self):
        match = _make_match()
        for _ in range(4):
            match.append_finished_game(_make_game(), "us")
        assert match.winner() == "us"
        assert match.phase == "finished"
        # 4 胜后 current_game_index 不再推进（停在第 4 盘的索引）
        assert match.current_game_index == 4
        assert len(match.games) == 4

    def test_4_3_thriller(self):
        match = _make_match()
        for _ in range(3):
            match.append_finished_game(_make_game(), "us")
            match.append_finished_game(_make_game(), "them")
        assert match.games_won_us == 3
        assert match.games_won_them == 3
        assert match.current_game_index == 7
        assert match.phase == "setup"
        # 第 7 盘我方胜，本轮结束
        match.append_finished_game(_make_game(), "us")
        assert match.winner() == "us"
        assert match.games_won_us == 4
        assert match.phase == "finished"
        # 4 胜后停在第 7 盘的索引
        assert match.current_game_index == 7

    def test_cannot_append_after_finished(self):
        match = _make_match(games_won_us=4, phase="finished")
        with pytest.raises(ValueError):
            match.append_finished_game(_make_game(), "us")

    def test_invalid_winner(self):
        match = _make_match()
        with pytest.raises(ValueError):
            match.append_finished_game(_make_game(), "draw")  # type: ignore[arg-type]


class TestSerialization:
    def test_to_dict_preserves_games(self):
        match = _make_match()
        match.append_finished_game(_make_game(), "us")
        match.append_finished_game(_make_game(), "them")
        data = match.to_dict()
        assert len(data["games"]) == 2
        assert data["games"][0]["initial_state"]
        assert data["games_won_us"] == 1
        assert data["games_won_them"] == 1

    def test_roundtrip_preserves_state(self, tmp_path):
        match = _make_match()
        match.append_finished_game(_make_game(), "us")
        path = tmp_path / "match.json"
        match.save(path)

        loaded = MatchRecord.load(path)
        assert loaded.our_side is match.our_side
        assert loaded.our_role == match.our_role
        assert loaded.games_won_us == match.games_won_us
        assert loaded.games_won_them == match.games_won_them
        assert loaded.current_game_index == match.current_game_index
        assert loaded.phase == match.phase
        assert loaded.match_id == match.match_id
        assert loaded.started_at == match.started_at
        assert len(loaded.games) == 1

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            MatchRecord.load(path)

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(ValueError):
            MatchRecord.load(tmp_path / "nope.json")

    def test_finished_phase_roundtrip(self, tmp_path):
        match = _make_match()
        for _ in range(4):
            match.append_finished_game(_make_game(), "us")
        assert match.phase == "finished"
        path = tmp_path / "match.json"
        match.save(path)
        loaded = MatchRecord.load(path)
        assert loaded.phase == "finished"
        assert loaded.winner() == "us"


def test_jia_first_games_constant():
    assert JIA_FIRST_GAMES == frozenset({1, 4, 5})


class TestR2ReviewValidation:
    """R-2 review Critical #1/#2 + Important #8/#9/#10：构造时数据不变量加强。"""

    def test_phase_finished_requires_winner(self):
        with pytest.raises(ValueError, match="phase=finished requires"):
            MatchRecord(our_side=Player.RED, our_role="甲", phase="finished")

    def test_score_cannot_exceed_target_wins(self):
        with pytest.raises(ValueError, match="exceeds target_wins"):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                games_won_us=5,
            )

    def test_current_game_index_upper_bound(self):
        with pytest.raises(ValueError, match="exceeds total_games"):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                total_games=7,
                current_game_index=8,
            )

    def test_games_count_cannot_exceed_total_games(self):
        # 直接构造一个超过 total_games 的 games 列表
        games = [_make_game() for _ in range(8)]
        with pytest.raises(ValueError, match="exceeds total_games"):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                total_games=7,
                games=games,
                games_won_us=4,
                games_won_them=4,
            )

    def test_from_dict_rejects_inconsistent_scores_and_games(self):
        """反序列化路径：篡改 games_won_us 使其与 games 长度不符，应被拒。"""
        match = _make_match()
        match.append_finished_game(_make_game(), "us")
        payload = match.to_dict()
        payload["games_won_us"] = 2  # 篡改：scores 与 games 长度不一致
        with pytest.raises(ValueError, match="inconsistent with scores"):
            MatchRecord.from_dict(payload)

    def test_start_playing_transitions_phase(self):
        match = _make_match()
        assert match.phase == "setup"
        match.start_playing()
        assert match.phase == "playing"

    def test_start_playing_rejects_non_setup(self):
        match = _make_match()
        match.start_playing()
        with pytest.raises(ValueError, match="cannot start_playing"):
            match.start_playing()

    def test_append_finished_game_refuses_when_exhausted(self):
        """target_wins == total_games 时若打平，禁止再开一盘。"""
        match = _make_match(total_games=2, target_wins=2)
        match.append_finished_game(_make_game(), "us")   # 1:0
        match.append_finished_game(_make_game(), "them")  # 1:1
        # 走完全部 total_games 仍平局 → current_game_index 不再涨到 3
        assert match.current_game_index == 2
        assert len(match.games) == 2
        assert match.winner() is None
        with pytest.raises(ValueError, match="exhausted"):
            match.append_finished_game(_make_game(), "us")

    @pytest.mark.parametrize("phase", ["setup", "playing"])
    def test_winner_reached_requires_finished_phase(self, phase):
        """R-1/R-2/R-3 二审 #2：达 target_wins 后 phase 必须是 finished，反向不变式。"""
        with pytest.raises(ValueError, match="reached target_wins"):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                target_wins=4,
                games_won_us=4,
                phase=phase,
            )

    def test_them_reached_requires_finished_phase(self):
        """对方达 target_wins 同样要求 phase=finished。"""
        with pytest.raises(ValueError, match="reached target_wins"):
            MatchRecord(
                our_side=Player.RED,
                our_role="甲",
                target_wins=4,
                games_won_them=4,
                phase="setup",
            )
