"""Phase 1 MCTS 实验候选 AI（kind: ``mcts_eval_v1``）。

设计来源：``docs/superpowers/specs/2026-05-13-mcts-phase1-design.md``。

要点：
- 显式区分 :class:`DecisionNode` 与 :class:`ChanceNode`，骰子节点不参与 UCT，
  按均匀分布采样。
- 叶节点估值用 :func:`ai.evaluator.evaluate` 的距离 + 子力两项，``expected_risk_weight``
  与 ``expected_win_risk_weight`` 显式置 0（对手回合语义有问题，见 evaluator docstring）。
- 视角统一为 ``root_player``，回传值 ``[-1, 1]``（``math.tanh(raw / SCALE)``）。
- 每次 ``choose_move`` 新建一棵树，不做跨步 transposition。
- 不修改 core，不引入新依赖；只调用 ``legal_moves``/``apply_move``/``undo_move``/``get_winner``/
  ``serialize``。
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from ai.evaluator import evaluate
from ai.zweistein import zweistein_lite_score
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position


WIN_VALUE: float = 1.0
"""终局回传值（root_player 视角）。tanh 归一化后非终局值落在 (-1, 1)，
WIN_VALUE 取 1.0 以与归一化后量级一致。"""

DEFAULT_SCALE: float = 100.0
"""evaluate 距离 + 子力组合约几百量级，``tanh(raw/100)`` 大体把强势局面压到 0.7~1.0。"""

DEFAULT_C_UCT: float = math.sqrt(2.0)
"""UCT 探索系数，经典选择 sqrt(2)。"""

DEFAULT_TIME_LIMIT_MS: float = 500.0
"""每步默认搜索时间预算 (ms)。"""


# Move 的 captured_piece 含可变的 Piece，本身不可哈希。
# 在 state+dice 给定时，(piece_id, from_pos, to_pos) 唯一确定一个合法 Move，可作 dict key。
MoveKey = tuple[int, Position, Position]


def _move_key(move: Move) -> MoveKey:
    return (move.piece_id, move.from_pos, move.to_pos)


@dataclass
class DecisionNode:
    """决策节点：当前 player 已知 dice 的选 Move 节点。"""

    player: Player
    dice: int
    visit_count: int = 0
    total_value: float = 0.0
    children: dict[MoveKey, "ChanceNode"] = field(default_factory=dict)
    expanded: bool = False
    unexpanded_moves: list[Move] = field(default_factory=list)

    @property
    def q(self) -> float:
        return self.total_value / self.visit_count if self.visit_count else 0.0


@dataclass
class ChanceNode:
    """骰子节点：父 DecisionNode 选 ``parent_move`` 之后，对手要掷的骰子事件。"""

    parent_move: Move
    visit_count: int = 0
    total_value: float = 0.0
    children: dict[int, DecisionNode] = field(default_factory=dict)

    @property
    def q(self) -> float:
        return self.total_value / self.visit_count if self.visit_count else 0.0


def _normalize(raw: float, scale: float) -> float:
    """把 evaluate 的原始打分压到 (-1, 1)。"""
    return math.tanh(raw / scale)


def _uct_score(
    child: ChanceNode,
    parent_visits: int,
    c: float,
    *,
    exploitation_sign: float = 1.0,
) -> float:
    if child.visit_count == 0:
        return float("inf")
    exploitation = exploitation_sign * child.q
    exploration = c * math.sqrt(math.log(max(parent_visits, 1)) / child.visit_count)
    return exploitation + exploration


class MCTSAI:
    """Phase 1 MCTS 候选 AI。

    使用：和其他 AI 一致，构造时注入 ``rng`` 以保证可复现；
    ``time_limit_ms`` 控制每步硬截止；``max_iterations`` 可选地额外封顶迭代数，
    单元测试用它做确定性复现。
    """

    def __init__(
        self,
        *,
        time_limit_ms: float = DEFAULT_TIME_LIMIT_MS,
        c_uct: float = DEFAULT_C_UCT,
        scale: float = DEFAULT_SCALE,
        max_iterations: int | None = None,
        rng: random.Random | None = None,
        name: str = "mcts_eval_v1",
        leaf_evaluator: str = "current",
    ) -> None:
        if leaf_evaluator not in {"current", "zweistein"}:
            raise ValueError(f"unknown leaf_evaluator: {leaf_evaluator!r}")
        self.time_limit_ms = float(time_limit_ms)
        self.c_uct = float(c_uct)
        self.scale = float(scale)
        self.max_iterations = (
            int(max_iterations) if max_iterations is not None else None
        )
        self._rng = rng or random.Random()
        self.name = name
        self.leaf_evaluator = leaf_evaluator
        # 报告字段：最近一次 choose_move 的统计，bench 可读取作为 avg_iterations/max_depth 输入。
        self.last_iterations: int = 0
        self.last_max_depth: int = 0

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal_moves = state.legal_moves(state.current_player, dice)
        if not legal_moves:
            self.last_iterations = 0
            self.last_max_depth = 0
            return None
        if len(legal_moves) == 1:
            self.last_iterations = 0
            self.last_max_depth = 0
            return legal_moves[0]

        root_player = state.current_player
        # 不修改入参 state：在副本上搜索。
        sim = GameState.deserialize(state.serialize())
        root = DecisionNode(player=root_player, dice=dice)

        deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        iterations = 0
        max_depth = 0
        while True:
            if self.max_iterations is not None and iterations >= self.max_iterations:
                break
            if time.perf_counter() >= deadline:
                break
            depth = self._iterate(root, root_player, sim, deadline)
            if depth is None:
                break
            iterations += 1
            if depth > max_depth:
                max_depth = depth

        self.last_iterations = iterations
        self.last_max_depth = max_depth

        if not root.children:
            # 极端情况下没有跑出任何完整迭代（如 time_limit_ms ≈ 0）。
            # fallback：返回第一个合法走法，保证不输出非法走法。
            return legal_moves[0]

        # 按 visit_count 选最强分支，tie-break 用 q。
        best_key, best_chance = max(
            root.children.items(),
            key=lambda kv: (kv[1].visit_count, kv[1].q),
        )
        return best_chance.parent_move

    def _iterate(
        self,
        root: DecisionNode,
        root_player: Player,
        state: GameState,
        deadline: float,
    ) -> int | None:
        """执行一次 selection + (lazy) expansion + evaluation + backprop。

        返回这次迭代到达的最大深度（不含 root），供报告统计。
        若迭代中途超时，返回 None，调用方使用已有统计或合法 fallback。
        """
        history_size_before = len(state.history)
        path: list[DecisionNode | ChanceNode] = [root]
        node: DecisionNode | ChanceNode = root
        depth = 0
        value: float = 0.0

        try:
            while True:
                if time.perf_counter() >= deadline:
                    return None
                # 1) 先判终局：从根出发可能很快遇到现成胜负局。
                winner = state.get_winner()
                if winner is not None:
                    value = WIN_VALUE if winner is root_player else -WIN_VALUE
                    break

                if isinstance(node, DecisionNode):
                    if time.perf_counter() >= deadline:
                        return None
                    if not node.expanded:
                        node.unexpanded_moves = list(
                            state.legal_moves(node.player, node.dice)
                        )
                        node.expanded = True

                    if time.perf_counter() >= deadline:
                        return None
                    if not node.children and not node.unexpanded_moves:
                        # 当前方无合法走法 → 当前方判负（与 play_one_game 的 forfeit 一致）。
                        value = (
                            WIN_VALUE
                            if node.player.opponent is root_player
                            else -WIN_VALUE
                        )
                        break

                    if time.perf_counter() >= deadline:
                        return None
                    if node.unexpanded_moves:
                        move = node.unexpanded_moves.pop()
                        state.apply_move(move, dice=node.dice)
                        chance = ChanceNode(parent_move=move)
                        node.children[_move_key(move)] = chance
                        path.append(chance)
                        depth += 1

                        if time.perf_counter() >= deadline:
                            return None
                        terminal = state.get_winner()
                        if terminal is not None:
                            value = WIN_VALUE if terminal is root_player else -WIN_VALUE
                        else:
                            if time.perf_counter() >= deadline:
                                return None
                            raw = self._leaf_score(state, root_player)
                            if time.perf_counter() >= deadline:
                                return None
                            value = _normalize(raw, self.scale)
                        break

                    if time.perf_counter() >= deadline:
                        return None
                    move, chance = self._select_uct_child(node, root_player=root_player)
                    if time.perf_counter() >= deadline:
                        return None
                    state.apply_move(move, dice=node.dice)
                    path.append(chance)
                    node = chance
                    depth += 1
                    if time.perf_counter() >= deadline:
                        return None
                else:
                    # ChanceNode：均匀采样骰子，进入或创建对手的 DecisionNode。
                    if time.perf_counter() >= deadline:
                        return None
                    new_dice = self._rng.randint(1, 6)
                    child = node.children.get(new_dice)
                    if child is None:
                        opponent = state.current_player
                        child = DecisionNode(player=opponent, dice=new_dice)
                        node.children[new_dice] = child
                    path.append(child)
                    node = child
                    depth += 1
                    if time.perf_counter() >= deadline:
                        return None
        finally:
            # 任何路径异常都要把 state 还原到 root 局面。
            while len(state.history) > history_size_before:
                state.undo_move()

        for n in path:
            n.visit_count += 1
            n.total_value += value
        return depth

    def _select_uct_child(
        self,
        node: DecisionNode,
        *,
        root_player: Player,
    ) -> tuple[Move, "ChanceNode"]:
        parent_visits = node.visit_count if node.visit_count > 0 else 1
        c = self.c_uct
        exploitation_sign = 1.0 if node.player is root_player else -1.0
        best_chance: ChanceNode | None = None
        best_score = float("-inf")
        for chance in node.children.values():
            score = _uct_score(
                chance,
                parent_visits,
                c,
                exploitation_sign=exploitation_sign,
            )
            if score > best_score:
                best_score = score
                best_chance = chance
        assert best_chance is not None
        return best_chance.parent_move, best_chance

    def _leaf_score(self, state: GameState, perspective: Player) -> float:
        if self.leaf_evaluator == "zweistein":
            return zweistein_lite_score(state, perspective)
        return evaluate(
            state,
            perspective=perspective,
            expected_risk_weight=0.0,
            expected_win_risk_weight=0.0,
        )


def mcts_choose_move(
    state: GameState,
    dice: int,
    *,
    time_limit_ms: float = DEFAULT_TIME_LIMIT_MS,
    c_uct: float = DEFAULT_C_UCT,
    scale: float = DEFAULT_SCALE,
    max_iterations: int | None = None,
    rng: random.Random | None = None,
    leaf_evaluator: str = "current",
) -> Move | None:
    """便捷函数：在 ``state`` 给定 ``dice`` 时返回 MCTS 选出的 Move。"""
    ai = MCTSAI(
        time_limit_ms=time_limit_ms,
        c_uct=c_uct,
        scale=scale,
        max_iterations=max_iterations,
        rng=rng,
        leaf_evaluator=leaf_evaluator,
    )
    return ai.choose_move(state, dice)
