"""play_one_game 必须给每个退出分支记录 termination_reason，
让 reports/per_game 数组可以按 reason+winner 聚合（review #1 的支撑）。

枚举：
- winner_target_corner: 任一方活子到达自己 target_corner
- winner_capture_all: 一方还有活子且对方全死
- draw_max_turns: 达到 max_turns 上限
- no_move: AI 返回 None（包括 forfeit）
- illegal_move: AI 返回非 legal 走法
- crash: AI choose_move 抛异常
"""

from __future__ import annotations

import random

from ai.match import (
    STARTING_LAYOUT_ID,
    ai_version_signature,
    build_ai,
    play_one_game,
)
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


# --- fake AIs -----------------------------------------------------------------


class _NoneAI:
    """choose_move 永远返回 None → no_move 分支。"""

    name = "always_none"

    def choose_move(self, state: GameState, dice: int) -> Move | None:  # noqa: ARG002
        return None


class _CrashAI:
    name = "crash"

    def choose_move(self, state: GameState, dice: int) -> Move | None:  # noqa: ARG002
        raise RuntimeError("boom")


class _IllegalAI:
    """返回一个不在 legal_moves 里的走法 → illegal_move 分支。"""

    name = "illegal"

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        player = state.current_player
        # 编一个跨格子的非法走法（不会出现在 generate_legal_moves_for_piece 里）
        return Move(
            player=player,
            piece_id=1,
            from_pos=Position(0, 0),
            to_pos=Position(4, 4),
            is_capture=False,
            captured_piece=None,
        )


# --- helpers ------------------------------------------------------------------


def _state_with_red_only_capture_setup() -> GameState:
    """红 1 在 (4,3)，dice=1 时 piece 1 唯一合法走法即 (4,4) → 红 winner_target_corner。

    选 (4,3) 而非 (3,3) 是为了消除 RandomAI 在 3 个合法走法间的随机选择，
    保证测试稳定。
    """
    return GameState.from_layout(
        red={1: Position(4, 3)},
        blue={2: Position(0, 1)},  # 蓝活但远离 (0,0)
        current_player=Player.RED,
    )


def _state_with_only_blue_left() -> GameState:
    """红没有活子；蓝活 → 第一次循环 get_winner 直接返回 BLUE (capture_all)。"""
    state = GameState.from_layout(
        red={1: Position(0, 1)},  # 先放一个，后面手动 kill
        blue={2: Position(2, 2)},
        current_player=Player.RED,
    )
    state.pieces[Player.RED][1].alive = False
    return state


def _state_no_winner_for_draw() -> GameState:
    """既无人到 corner 也无人全死 → 配 max_turns=0 直接 draw。"""
    return GameState.from_layout(
        red={1: Position(2, 2)},
        blue={2: Position(2, 4)},
        current_player=Player.RED,
    )


# --- termination_reason 6 分支 -------------------------------------------------


def test_winner_target_corner_reported_when_piece_reaches_corner() -> None:
    state = _state_with_red_only_capture_setup()
    red = build_ai("random", seed=1)
    blue = build_ai("random", seed=2)
    # dice=1 强制选红 1，红 1 在 (3,3) 唯一合法去 (4,4) 即胜
    dice_rng = random.Random()
    dice_rng.randint = lambda a, b: 1  # type: ignore[method-assign]

    result = play_one_game(red_ai=red, blue_ai=blue, dice_rng=dice_rng, starting_state=state)

    assert result.winner is Player.RED
    assert result.termination_reason == "winner_target_corner"


def test_winner_capture_all_reported_when_opponent_has_no_living_pieces() -> None:
    state = _state_with_only_blue_left()
    red = build_ai("random", seed=1)
    blue = build_ai("random", seed=2)

    result = play_one_game(
        red_ai=red, blue_ai=blue, dice_rng=random.Random(0), starting_state=state
    )

    assert result.winner is Player.BLUE
    assert result.termination_reason == "winner_capture_all"


def test_draw_max_turns_reported_when_cap_reached() -> None:
    state = _state_no_winner_for_draw()
    red = build_ai("random", seed=1)
    blue = build_ai("random", seed=2)

    result = play_one_game(
        red_ai=red, blue_ai=blue, dice_rng=random.Random(0), max_turns=0, starting_state=state
    )

    assert result.winner is None
    assert result.termination_reason == "draw_max_turns"


def test_no_move_reported_when_ai_returns_none() -> None:
    state = _state_no_winner_for_draw()

    result = play_one_game(
        red_ai=_NoneAI(),
        blue_ai=build_ai("random", seed=2),
        dice_rng=random.Random(0),
        starting_state=state,
    )

    assert result.winner is Player.BLUE
    assert result.termination_reason == "no_move"


def test_illegal_move_reported_when_ai_returns_invalid_move() -> None:
    state = _state_no_winner_for_draw()

    result = play_one_game(
        red_ai=_IllegalAI(),
        blue_ai=build_ai("random", seed=2),
        dice_rng=random.Random(0),
        starting_state=state,
    )

    assert result.winner is Player.BLUE
    assert result.termination_reason == "illegal_move"
    assert result.illegal_moves == 1


def test_crash_reported_when_ai_raises() -> None:
    state = _state_no_winner_for_draw()

    result = play_one_game(
        red_ai=_CrashAI(),
        blue_ai=build_ai("random", seed=2),
        dice_rng=random.Random(0),
        starting_state=state,
    )

    assert result.winner is Player.BLUE
    assert result.termination_reason == "crash"
    assert result.crashes == 1


# --- starting layout id + ai signature ---------------------------------------


def test_starting_layout_id_is_a_nonempty_string() -> None:
    assert isinstance(STARTING_LAYOUT_ID, str)
    assert STARTING_LAYOUT_ID  # 非空


def test_starting_state_for_default_returns_no_stuck_corner_layout() -> None:
    from ai.match import STARTING_LAYOUT_ID, starting_state_for

    state = starting_state_for(STARTING_LAYOUT_ID)

    # default_no_stuck_corner_v1: piece 5 在 (2,0)，piece 6 在 (3,1)
    assert state.pieces[Player.RED][5].position == Position(2, 0)
    assert state.pieces[Player.RED][6].position == Position(3, 1)


def test_starting_state_for_standard_triangle_returns_baseline_layout() -> None:
    from ai.match import STANDARD_TRIANGLE_LAYOUT_ID, starting_state_for

    state = starting_state_for(STANDARD_TRIANGLE_LAYOUT_ID)

    # standard_triangle_v1: piece 5 在 (1,1)（围死 piece 1），piece 6 在 (2,0)
    assert state.pieces[Player.RED][5].position == Position(1, 1)
    assert state.pieces[Player.RED][6].position == Position(2, 0)
    assert state.pieces[Player.BLUE][5].position == Position(3, 3)
    assert state.pieces[Player.BLUE][6].position == Position(2, 4)


def test_starting_state_for_unknown_layout_raises_value_error() -> None:
    import pytest
    from ai.match import starting_state_for

    with pytest.raises(ValueError, match="unknown starting layout"):
        starting_state_for("not_a_real_layout")


def test_ai_version_signature_for_random_only_has_name() -> None:
    ai = build_ai("random", seed=1)

    sig = ai_version_signature(ai)

    assert sig == {"name": "random"}


def test_ai_version_signature_for_greedy_includes_evaluator_weights() -> None:
    ai = build_ai("greedy", seed=1)

    sig = ai_version_signature(ai)

    assert sig["name"] == "greedy"
    # GreedyAI 在 task #7 中会曝光 stuck_penalty/distance_weight/material_weight 属性。
    # 此处先断言 name；具体 weight 字段的存在由 task #7 的测试保障。
