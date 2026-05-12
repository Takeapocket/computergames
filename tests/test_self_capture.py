from ai.self_capture import self_capture_mobility_gain
from core.game_state import GameState
from core.types import Player, Position


def test_self_capture_gain_is_zero_when_no_self_capture_exists():
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )

    assert self_capture_mobility_gain(state, Player.RED) == 0.0


def test_self_capture_gain_does_not_mutate_state():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(1, 1), 3: Position(0, 2)},
        blue={1: Position(4, 4)},
        current_player=Player.BLUE,
    )
    before = state.serialize()

    self_capture_mobility_gain(state, Player.RED)

    assert state.serialize() == before


def test_self_capture_gain_is_non_negative():
    # 红 1 在 (0,0)，红 2 在 (1,1)：dice=2 可以让 piece 1 自残吃掉 piece 2，
    # 红 3 在 (0,2) 给 RED 留下更多机动性参考点。
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(1, 1), 3: Position(0, 2)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )

    gain = self_capture_mobility_gain(state, Player.RED)

    assert gain >= 0.0


def test_self_capture_gain_accepts_string_player():
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )

    assert self_capture_mobility_gain(state, "red") == 0.0
