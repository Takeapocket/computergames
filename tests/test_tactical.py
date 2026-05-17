"""Tactical AI wrapper unit tests."""
from __future__ import annotations

import random

import pytest

from ai.greedy_ai import GreedyAI
from ai.tactical import (
    TacticalAI,
    find_neutralizing_moves,
    find_winning_moves,
    opponent_winning_dice_set,
    pick_max_material,
)
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


def _state(red=None, blue=None, current_player=Player.RED) -> GameState:
    return GameState.from_layout(
        red=red or {}, blue=blue or {}, current_player=current_player
    )


def _move(player, piece_id, frm, to, captured=None) -> Move:
    return Move(
        player=player,
        piece_id=piece_id,
        from_pos=frm,
        to_pos=to,
        is_capture=captured is not None,
        captured_piece=captured,
    )


class RecordingBase:
    def __init__(self, move=None, name="recording"):
        self.move = move
        self.name = name
        self.calls = []

    def choose_move(self, state, dice):
        self.calls.append((state, dice))
        return self.move


# -------- pick_max_material --------

def test_pick_max_material_returns_only_move():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    moves = state.legal_moves(Player.RED, 1)
    assert moves, "fixture should produce at least one legal move"
    rng = random.Random(0)

    chosen = pick_max_material([moves[0]], rng)

    assert chosen == moves[0]


def test_pick_max_material_prefers_capture_of_opponent():
    state = _state(
        red={1: Position(0, 0), 2: Position(1, 1)},
        blue={1: Position(0, 1)},
    )
    legal = state.legal_moves(Player.RED, 1)
    capturing = [m for m in legal if m.captured_piece is not None and m.captured_piece.player is Player.BLUE]
    non_capturing = [m for m in legal if m.captured_piece is None]
    assert capturing and non_capturing, "fixture must contain both kinds"
    rng = random.Random(0)

    chosen = pick_max_material(capturing + non_capturing, rng)

    assert chosen in capturing


def test_pick_max_material_falls_back_to_rng_when_no_captures():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    legal = state.legal_moves(Player.RED, 1)
    moves = [m for m in legal if m.captured_piece is None]
    assert len(moves) >= 2 or moves, "need at least one non-capture"
    rng_a = random.Random(42)
    rng_b = random.Random(42)

    a = pick_max_material(moves, rng_a)
    b = pick_max_material(moves, rng_b)

    assert a == b  # deterministic given same rng seed


def test_pick_max_material_ignores_self_captures():
    """Self-captures (capturing own piece) must not count as 'material'."""
    fake_self_piece_move = _move(
        Player.RED, 1, Position(0, 0), Position(1, 1),
        captured=type("P", (), {"player": Player.RED})(),
    )
    fake_opp_capture = _move(
        Player.RED, 2, Position(2, 2), Position(3, 3),
        captured=type("P", (), {"player": Player.BLUE})(),
    )
    rng = random.Random(0)

    chosen = pick_max_material([fake_self_piece_move, fake_opp_capture], rng)

    assert chosen is fake_opp_capture


# -------- find_winning_moves --------

def test_find_winning_moves_detects_target_corner_win():
    """RED piece one step from (4,4); dice=1 should reach target_corner and win."""
    state = _state(
        red={6: Position(3, 4)},
        blue={1: Position(0, 4)},
    )

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning, "should find at least one winning move"
    assert all(m.to_pos == Position(4, 4) for m in winning)


def test_find_winning_moves_detects_capture_all_win():
    """RED has piece adjacent to BLUE's last surviving piece; capture wins by elimination."""
    state = _state(
        red={1: Position(2, 2)},
        blue={1: Position(2, 3)},  # blue has only one piece
    )

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning
    captured_targets = [m.captured_piece for m in winning if m.captured_piece]
    assert any(c and c.player is Player.BLUE for c in captured_targets)


def test_find_winning_moves_returns_empty_when_no_win():
    state = _state(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},  # blue already at target — opponent already won? skip if so
    )
    if state.get_winner() is not None:
        pytest.skip("layout produces immediate winner")

    winning = find_winning_moves(state, dice=1, perspective=Player.RED)

    assert winning == []


def test_find_winning_moves_does_not_mutate_state():
    state = _state(
        red={6: Position(3, 4)},
        blue={1: Position(0, 4)},
    )
    before = state.serialize()

    find_winning_moves(state, dice=1, perspective=Player.RED)

    assert state.serialize() == before


# -------- opponent_winning_dice_set --------

def test_opponent_winning_dice_set_detects_target_corner_threat():
    """BLUE has piece at (1,0); dice=1 reaches (0,0) — BLUE's target."""
    state = _state(
        red={1: Position(2, 2)},
        blue={5: Position(1, 0)},
        current_player=Player.RED,
    )

    threats = opponent_winning_dice_set(state, opponent=Player.BLUE)

    assert 1 in threats


def test_opponent_winning_dice_set_detects_capture_all_threat():
    """RED has one piece at (2,3); BLUE piece 4 at (2,4) captures it via dice 4.
    No pre-existing winner; win is by capture-all only."""
    state = _state(
        red={3: Position(2, 3)},
        blue={4: Position(2, 4), 1: Position(4, 4)},
        current_player=Player.RED,
    )
    assert state.get_winner() is None, "fixture must not have a pre-existing winner"

    threats = opponent_winning_dice_set(state, opponent=Player.BLUE)

    assert 4 in threats, "BLUE dice=4 should move piece 4 (0,-1) to (2,3), capturing RED's last piece"


def test_opponent_winning_dice_set_empty_when_no_threat():
    state = _state(
        red={1: Position(0, 0), 2: Position(0, 1), 3: Position(0, 2)},
        blue={1: Position(4, 4)},  # at target already? skip if so
        current_player=Player.RED,
    )
    if state.get_winner() is not None:
        pytest.skip("blue already at target")

    threats = opponent_winning_dice_set(state, opponent=Player.BLUE)

    # BLUE at (4,4) is target_corner(RED), not BLUE's target; threat set is small or empty
    # We only assert it returns a set (not raise) and contains valid dice ints
    assert isinstance(threats, set)
    assert all(1 <= d <= 6 for d in threats)


def test_opponent_winning_dice_set_does_not_mutate_state():
    state = _state(
        red={1: Position(2, 2)},
        blue={5: Position(1, 0)},
        current_player=Player.RED,
    )
    before = state.serialize()

    opponent_winning_dice_set(state, opponent=Player.BLUE)

    assert state.serialize() == before


def test_opponent_winning_dice_set_empty_when_opponent_has_no_legal_moves():
    """终局防御：BLUE 唯一活子在 (0,0)（即 BLUE 已达目标角，是 BLUE 胜利的终局），
    BLUE 此时所有骰子值下 legal_moves 都为空。函数必须返回空集且不抛。

    设计 §10.1 test 13 的语义在本游戏规则下只能在终局复现——非终局且对手有活子时
    至少有一个 legal move。这里以 terminal-edge 形式守住「无 legal action 不崩」的语义，
    保证 TacticalAI.choose_move 万一被误调用在终局上时不会因威胁扫描挂掉。
    """
    state = _state(
        red={1: Position(2, 2)},
        blue={1: Position(0, 0)},
        current_player=Player.RED,
    )
    assert state.get_winner() is Player.BLUE, "fixture must be a BLUE-won terminal state"
    for d in range(1, 7):
        assert state.legal_moves(Player.BLUE, d) == [], (
            f"BLUE piece at (0,0) must have zero legal moves for dice={d}"
        )

    threats = opponent_winning_dice_set(state, opponent=Player.BLUE)

    assert threats == set()


def test_opponent_winning_dice_set_works_on_post_apply_state():
    """After apply_move flips current_player, the call should still be valid."""
    state = _state(
        red={6: Position(3, 4)},
        blue={5: Position(1, 0)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(Player.RED, 1)
    assert legal
    state.apply_move(legal[0], dice=1)
    try:
        # After RED moves, current_player == BLUE
        threats = opponent_winning_dice_set(state, opponent=Player.BLUE)
        assert isinstance(threats, set)
    finally:
        state.undo_move()


def test_opponent_winning_dice_set_is_empty_after_game_already_won():
    state = _state(
        red={6: Position(4, 4)},
        blue={5: Position(1, 0)},
        current_player=Player.BLUE,
    )

    threats = opponent_winning_dice_set(state, opponent=Player.BLUE)

    assert threats == set()


# -------- find_neutralizing_moves --------

def test_find_neutralizing_moves_uses_perspective_opponent():
    """BLUE can capture RED's one-step target-corner threat; opponent is RED."""
    state = _state(
        red={5: Position(3, 4), 6: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.BLUE,
    )

    neutralizing = find_neutralizing_moves(state, dice=1, perspective=Player.BLUE)

    assert isinstance(neutralizing, list)
    assert {(m.from_pos, m.to_pos) for m in neutralizing} == {
        (Position(4, 4), Position(3, 4)),
    }


def test_find_neutralizing_moves_excludes_partial_threat_reduction():
    """Capturing either BLUE threat still leaves the other immediate target win."""
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(0, 1)},
        current_player=Player.RED,
    )

    neutralizing = find_neutralizing_moves(state, dice=1, perspective=Player.RED)

    assert neutralizing == []


def test_find_neutralizing_moves_does_not_mutate_state():
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(4, 0)},
        current_player=Player.RED,
    )
    before = state.serialize()

    find_neutralizing_moves(state, dice=1, perspective=Player.RED)

    assert state.serialize() == before


# -------- TacticalAI Task 5 --------

def test_tactical_ai_picks_winning_move_without_calling_base():
    state = _state(red={1: Position(3, 4)}, blue={1: Position(0, 1)})
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen is not None
    assert chosen.to_pos == Position(4, 4)
    assert base.calls == []


def test_tactical_ai_prefers_capturing_winning_move():
    state = _state(
        red={2: Position(3, 4), 4: Position(3, 3)},
        blue={1: Position(4, 3)},
    )
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 3)

    assert chosen is not None
    assert chosen.to_pos == Position(4, 3)
    assert chosen.captured_piece is not None
    assert chosen.captured_piece.player is Player.BLUE
    assert base.calls == []


def test_tactical_ai_delegates_once_when_no_direct_win():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    base_choice = state.legal_moves(Player.RED, 1)[0]
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen == base_choice
    assert base.calls == [(state, 1)]


def test_tactical_ai_returns_none_without_calling_base_when_no_legal_moves():
    state = _state(red={}, blue={1: Position(4, 4)})
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen is None
    assert base.calls == []


def test_tactical_ai_neutralizes_target_corner_threat_with_filtered_fallback():
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(4, 4)},
    )
    non_neutralizing = _move(Player.RED, 1, Position(0, 0), Position(0, 1))
    base = RecordingBase(move=non_neutralizing)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    neutralizing = find_neutralizing_moves(state, dice=1, perspective=Player.RED)
    assert {(m.from_pos, m.to_pos) for m in neutralizing} == {
        (Position(0, 0), Position(1, 0)),
    }
    assert (chosen.from_pos, chosen.to_pos) == (Position(0, 0), Position(1, 0))
    assert base.calls == [(state, 1)]


def test_tactical_ai_neutralizes_capture_all_threat_with_filtered_fallback():
    state = _state(
        red={3: Position(1, 3)},
        blue={4: Position(2, 4), 1: Position(4, 4)},
    )
    non_neutralizing = _move(Player.RED, 3, Position(1, 3), Position(2, 3))
    base = RecordingBase(move=non_neutralizing)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 3)

    neutralizing = find_neutralizing_moves(state, dice=3, perspective=Player.RED)
    assert {(m.from_pos, m.to_pos) for m in neutralizing} == {
        (Position(1, 3), Position(2, 4)),
    }
    assert (chosen.from_pos, chosen.to_pos) == (Position(1, 3), Position(2, 4))
    assert base.calls == [(state, 3)]


def test_tactical_ai_respects_base_when_base_selects_neutralizing_move():
    state = _state(
        red={2: Position(0, 1), 4: Position(1, 0)},
        blue={5: Position(1, 1), 6: Position(4, 4)},
    )
    neutralizing = find_neutralizing_moves(state, dice=3, perspective=Player.RED)
    assert {(m.from_pos, m.to_pos) for m in neutralizing} == {
        (Position(0, 1), Position(1, 1)),
        (Position(1, 0), Position(1, 1)),
    }
    base_choice = neutralizing[-1]
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 3)

    assert chosen == base_choice
    assert base.calls == [(state, 3)]


def test_tactical_ai_falls_back_to_legal_neutralizing_move_when_base_selects_other_move():
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(4, 4)},
    )
    base_choice = _move(Player.RED, 1, Position(0, 0), Position(1, 1))
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(3))

    chosen = ai.choose_move(state, 1)

    neutralizing = find_neutralizing_moves(state, dice=1, perspective=Player.RED)
    allowed_pairs = {(m.from_pos, m.to_pos) for m in neutralizing}
    assert (chosen.from_pos, chosen.to_pos) in allowed_pairs
    assert (chosen.from_pos, chosen.to_pos) != (base_choice.from_pos, base_choice.to_pos)
    assert base.calls == [(state, 1)]


def test_tactical_ai_delegates_once_when_no_pre_move_threat():
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    assert opponent_winning_dice_set(state, opponent=Player.BLUE) == set()
    base_choice = state.legal_moves(Player.RED, 1)[-1]
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen == base_choice
    assert base.calls == [(state, 1)]


def test_tactical_ai_direct_win_takes_priority_over_neutralizing_threat():
    state = _state(
        red={1: Position(3, 4)},
        blue={5: Position(1, 0), 6: Position(4, 4)},
    )
    assert opponent_winning_dice_set(state, opponent=Player.BLUE)
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen is not None
    assert chosen.to_pos == Position(4, 4)
    assert base.calls == []


def test_tactical_ai_ties_among_winning_moves_use_rng():
    """两个等价（同 material）赢手：固定 seed 必须给出确定结果。

    设计 §10.1 test 3：pick_max_material 在无吃子时退化为 rng.choice，
    TacticalAI 的 RNG 控制了 tie-break，必须是 wrapper rng 自身（不消耗 base rng）。
    """
    state = _state(
        red={2: Position(3, 4), 4: Position(4, 3)},
        blue={3: Position(1, 1)},
    )
    winning = find_winning_moves(state, dice=3, perspective=Player.RED)
    assert len(winning) >= 2, "fixture should produce ≥2 winning moves of equal material"
    assert all(m.captured_piece is None for m in winning), (
        "fixture should keep material equal — no winning move may capture"
    )

    base_a = RecordingBase()
    base_b = RecordingBase()
    ai_a = TacticalAI(base=base_a, rng=random.Random(2026))
    ai_b = TacticalAI(base=base_b, rng=random.Random(2026))

    chosen_a = ai_a.choose_move(state, 3)
    chosen_b = ai_b.choose_move(state, 3)

    assert chosen_a is not None and chosen_b is not None
    assert (chosen_a.from_pos, chosen_a.to_pos) == (chosen_b.from_pos, chosen_b.to_pos)
    winning_pairs = {(m.from_pos, m.to_pos) for m in winning}
    assert (chosen_a.from_pos, chosen_a.to_pos) in winning_pairs
    assert base_a.calls == [] and base_b.calls == []


def test_tactical_ai_partial_neutralizing_delegates_to_base_unfiltered():
    """对手 ≥2 个一步胜威胁、我方任一走法都消不光：base 被调一次且其选择被原样使用。

    设计 §10.1 test 10：Patch 2 保守语义——部分化解不算 neutralizing，
    交回 base 让它用概率/搜索能力自己决断；wrapper 不做过滤。
    """
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(0, 1)},
    )
    pre_threat = opponent_winning_dice_set(state, opponent=Player.BLUE)
    assert pre_threat, "fixture must put BLUE in one-step-win threat"
    neutralizing = find_neutralizing_moves(state, dice=1, perspective=Player.RED)
    assert neutralizing == [], "fixture must allow no full neutralization"

    base_choice = _move(Player.RED, 1, Position(0, 0), Position(1, 1))
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    chosen = ai.choose_move(state, 1)

    assert chosen == base_choice
    assert base.calls == [(state, 1)]


def test_tactical_ai_does_not_mutate_state_across_branches():
    """TacticalAI.choose_move 在 patch1 / patch2-filter / patch2-passthrough / transparent
    四条决策路径上都必须保持 state.serialize() 不变。

    设计 §10.1 test 17：包装器作为整体的不变性回归网。
    """
    from ai.match import starting_state_for, STARTING_LAYOUT_ID

    scenarios = [
        # Patch 1: 直接赢
        (
            _state(red={1: Position(3, 4)}, blue={1: Position(0, 1)}),
            1,
        ),
        # Patch 2: filter+delegate（base 选 unsafe 走法时 rng 兜底）
        (
            _state(
                red={1: Position(0, 0)},
                blue={5: Position(1, 0), 6: Position(4, 4)},
            ),
            1,
        ),
        # Patch 2: 部分化解 → base 全权决定
        (
            _state(
                red={1: Position(0, 0)},
                blue={5: Position(1, 0), 6: Position(0, 1)},
            ),
            1,
        ),
        # Transparent fallback: 无威胁 → base 直接决定
        (
            _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)}),
            1,
        ),
        # 默认开局 + 多个骰子
        (starting_state_for(STARTING_LAYOUT_ID), 3),
    ]

    for state, dice in scenarios:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            continue
        base = RecordingBase(move=legal[0])
        ai = TacticalAI(base=base, rng=random.Random(0))
        before = state.serialize()

        ai.choose_move(state, dice)

        assert state.serialize() == before, (
            f"TacticalAI mutated state on scenario dice={dice} legal[0]={legal[0]}"
        )


def test_tactical_ai_returns_legal_move_for_every_dice_from_default_state():
    """默认开局下，骰子 1-6 调用 TacticalAI(GreedyAI) 都返回 legal_moves 子集中的 move。

    设计 §10.1 test 18：把 TacticalAI 当成「黑盒 AI 协议实现」检 smoke——
    包装器自己产生的兜底（pick_max_material / rng.choice）以及透传给 base 的路径
    都不能产出非法走法。
    """
    from ai.match import starting_state_for, STARTING_LAYOUT_ID

    for dice in range(1, 7):
        state = starting_state_for(STARTING_LAYOUT_ID)
        legal = state.legal_moves(state.current_player, dice)
        assert legal, f"starting layout must give legal moves for dice={dice}"
        legal_pairs = {(m.from_pos, m.to_pos) for m in legal}

        base = GreedyAI(rng=random.Random(2026 + dice))
        ai = TacticalAI(base=base, rng=random.Random(dice))

        move = ai.choose_move(state, dice)

        assert move is not None, f"TacticalAI returned None for dice={dice}"
        assert (move.from_pos, move.to_pos) in legal_pairs, (
            f"TacticalAI returned illegal move {move} for dice={dice}; "
            f"legal options were {legal_pairs}"
        )


# -------- build_ai("rollout_tactical") + ai_version_signature --------

def test_build_ai_rollout_tactical_returns_tactical_with_rollout_base():
    from ai.match import build_ai
    from ai.rollout_ai import RolloutAI

    ai = build_ai("rollout_tactical", seed=42)

    assert isinstance(ai, TacticalAI)
    assert isinstance(ai.base, RolloutAI)
    assert ai.name == "rollout_tactical"


def test_build_ai_rollout_tactical_supports_seed_none():
    from ai.match import build_ai
    from ai.rollout_ai import RolloutAI

    ai = build_ai("rollout_tactical", seed=None)

    assert isinstance(ai, TacticalAI)
    assert isinstance(ai.base, RolloutAI)
    assert ai.name == "rollout_tactical"


def test_build_ai_rollout_tactical_isolates_wrapper_rng_from_base_rng():
    """wrapper_rng 必须独立派生；构造时不能从 base_rng 抽数派生 wrapper_seed。"""
    from ai.match import build_ai

    seed = 42
    ai = build_ai("rollout_tactical", seed=seed)

    expected_base_state = random.Random(seed).getstate()
    assert ai.base._rng.getstate() == expected_base_state, (
        "base_rng 被推进，说明 wrapper_seed 是从 base_rng 派生的"
    )

    expected_wrapper_state = random.Random(seed ^ 0x5DEECE66D).getstate()
    assert ai.rng.getstate() == expected_wrapper_state, (
        "wrapper_rng 不是 random.Random(seed ^ 0x5DEECE66D)"
    )


def test_ai_version_signature_for_rollout_tactical_includes_base_and_patches():
    from ai.match import ai_version_signature, build_ai

    ai = build_ai("rollout_tactical", seed=7)
    sig = ai_version_signature(ai)

    assert sig["name"] == "rollout_tactical"
    assert sig["patches"] == ["direct_win", "block_one_step_win"]
    assert "base" in sig
    base_sig = sig["base"]
    assert base_sig["name"] == "rollout"
    # base 子签名应当走完整的 ai_version_signature 字段循环
    assert "rollouts_per_move" in base_sig



def test_build_ai_rollout_tactical_choose_move_smoke():
    """End-to-end: TacticalAI 包装 RolloutAI 后 choose_move 必须能跑通并返回 legal move。

    单纯的构造形状测试覆盖不到 TacticalAI <-> RolloutAI 的接口拼接面；
    这里压低 rollouts_per_move / max_step_time_ms 保证耗时 << 1s。
    """
    from ai.match import build_ai

    ai = build_ai(
        "rollout_tactical",
        seed=42,
        rollouts_per_move=2,
        max_step_time_ms=20,
    )
    state = _state(
        red={1: Position(0, 0), 2: Position(1, 0)},
        blue={1: Position(4, 4), 2: Position(3, 4)},
        current_player=Player.RED,
    )
    dice = 3
    legal = state.legal_moves(state.current_player, dice)
    assert legal, "fixture should produce legal moves"

    move = ai.choose_move(state, dice)

    assert move is not None
    legal_pairs = {(m.from_pos, m.to_pos) for m in legal}
    assert (move.from_pos, move.to_pos) in legal_pairs


# -------- find_winning_moves perspective guard --------

def test_find_winning_moves_asserts_when_perspective_mismatches_current_player():
    """perspective 与 state.current_player 不一致是调用方 bug。

    apply_move 内部要求 move.player == current_player，因此若 perspective != current_player，
    实际上每个候选 move 都会抛 ValueError，函数会静默返回 []。assert 把这条隐式失败
    显式化，避免上层把空集错认成「没有赢手」。
    """
    state = _state(
        red={1: Position(3, 4)},
        blue={5: Position(1, 0)},
        current_player=Player.RED,
    )

    with pytest.raises(AssertionError):
        find_winning_moves(state, dice=1, perspective=Player.BLUE)


# -------- TacticalAI.fire_counts per-branch telemetry --------

def test_tactical_ai_fire_counts_starts_empty():
    """新构造的 TacticalAI 必须暴露空 fire_counts，用于 bench_ai _candidate_telemetry。"""
    ai = TacticalAI(base=RecordingBase(), rng=random.Random(0))

    assert dict(ai.fire_counts) == {}


def test_tactical_ai_fire_counts_records_direct_win():
    """Patch 1 触发：fire_counts 增加 direct_win，且不触碰 base。"""
    state = _state(
        red={1: Position(3, 4)},
        blue={5: Position(1, 0), 6: Position(4, 4)},
    )
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    ai.choose_move(state, 1)

    assert dict(ai.fire_counts) == {"direct_win": 1}
    assert base.calls == []


def test_tactical_ai_fire_counts_records_neutralize_filter_respected():
    """Patch 2 + base 选了 allowed 之一：记 neutralize_filter_respected。"""
    state = _state(
        red={2: Position(0, 1), 4: Position(1, 0)},
        blue={5: Position(1, 1), 6: Position(4, 4)},
    )
    neutralizing = find_neutralizing_moves(state, dice=3, perspective=Player.RED)
    assert len(neutralizing) >= 1
    base = RecordingBase(move=neutralizing[-1])
    ai = TacticalAI(base=base, rng=random.Random(0))

    ai.choose_move(state, 3)

    assert dict(ai.fire_counts) == {"neutralize_filter_respected": 1}


def test_tactical_ai_fire_counts_records_neutralize_filter_overrode():
    """Patch 2 + base 选了 allowed 之外：记 neutralize_filter_overrode。"""
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(4, 4)},
    )
    base_choice = _move(Player.RED, 1, Position(0, 0), Position(1, 1))
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(3))

    ai.choose_move(state, 1)

    assert dict(ai.fire_counts) == {"neutralize_filter_overrode": 1}


def test_tactical_ai_fire_counts_records_partial_neutralize_passthrough():
    """对手有威胁但我方无法完全化解：fire_counts 记 partial_neutralize_passthrough。

    这条分支与 no_threat_passthrough 在原实现里共用同一行 return，遥测必须能区分。
    """
    state = _state(
        red={1: Position(0, 0)},
        blue={5: Position(1, 0), 6: Position(0, 1)},
    )
    base_choice = _move(Player.RED, 1, Position(0, 0), Position(1, 1))
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    ai.choose_move(state, 1)

    assert dict(ai.fire_counts) == {"partial_neutralize_passthrough": 1}


def test_tactical_ai_fire_counts_records_no_threat_passthrough():
    """无威胁透传 base：fire_counts 记 no_threat_passthrough。"""
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    base_choice = state.legal_moves(Player.RED, 1)[-1]
    base = RecordingBase(move=base_choice)
    ai = TacticalAI(base=base, rng=random.Random(0))

    ai.choose_move(state, 1)

    assert dict(ai.fire_counts) == {"no_threat_passthrough": 1}


def test_tactical_ai_fire_counts_not_incremented_when_no_legal_moves():
    """无 legal move → choose_move 早返回 None，未做决策，不记任何分支。"""
    state = _state(red={}, blue={1: Position(4, 4)})
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    result = ai.choose_move(state, 1)

    assert result is None
    assert dict(ai.fire_counts) == {}


def test_tactical_ai_fire_counts_accumulates_across_calls():
    """同一个 TacticalAI 在多次决策中累加 fire_counts，每局新 AI 隐式重置。"""
    base = RecordingBase()
    ai = TacticalAI(base=base, rng=random.Random(0))

    # 两次 direct_win 场景
    for _ in range(2):
        state = _state(
            red={1: Position(3, 4)},
            blue={5: Position(1, 0), 6: Position(4, 4)},
        )
        ai.choose_move(state, 1)

    # 一次 no_threat_passthrough
    state = _state(red={1: Position(0, 0)}, blue={1: Position(4, 4)})
    base.move = state.legal_moves(Player.RED, 1)[-1]
    ai.choose_move(state, 1)

    assert dict(ai.fire_counts) == {"direct_win": 2, "no_threat_passthrough": 1}
