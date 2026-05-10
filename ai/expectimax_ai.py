from __future__ import annotations

import random
import time

from ai.evaluator import WIN_SCORE, evaluate
from core.game_state import GameState
from core.move import Move
from core.types import Player


class ExpectimaxAI:
    """Expectimax AI：在已知本方骰子的前提下，枚举对手下轮骰子 1-6 及其最优回应。

    depth=0 → 等价 GreedyAI（只评估自己走完后的局面）。
    depth=1 → 我的走法 → 对手骰子期望 → 对手最优回应 → 评估。
    depth=2 → 再加一层我的回应（更贵，暂不建议）。

    **注意（2026-05-10 评测）**：depth=1 + `greedy_risk` 默认 evaluator kwargs 在 200×2 局
    bench 中合并胜率仅 46.5%，**显著弱于** `greedy_risk`。详见
    ``reports/4-4-failure-analysis.md``。当前不建议用于竞赛；保留主要供后续 lookahead /
    evaluator 解耦实验复用。
    """

    def __init__(
        self,
        *,
        depth: int = 1,
        time_limit_ms: float = 5000.0,
        rng: random.Random | None = None,
        name: str = "expectimax",
        randomize_ties: bool = True,
        **eval_kwargs: float,
    ) -> None:
        if depth < 0:
            raise ValueError(f"depth must be >= 0, got {depth}")
        self.depth = depth
        self.time_limit_ms = time_limit_ms
        self._rng = rng or random.Random()
        self.name = name
        self.randomize_ties = randomize_ties
        self._eval_kwargs = eval_kwargs
        # 把 evaluator 类权重提升为公共属性，供 ai_version_signature 反射记录到 bench metadata。
        self.expected_risk_weight = eval_kwargs.get("expected_risk_weight", 0.0)
        self.expected_win_risk_weight = eval_kwargs.get("expected_win_risk_weight", 0.0)

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        perspective = state.current_player
        best_score = float("-inf")
        best_moves: list[Move] = []
        deadline = time.perf_counter() + self.time_limit_ms / 1000.0

        for move in legal:
            if time.perf_counter() > deadline:
                break

            applied = state.apply_move(move, dice=dice)
            try:
                score = self._expectimin(state, perspective, self.depth - 1, deadline)
            finally:
                state.undo_move()

            if score > best_score:
                best_score = score
                best_moves = [applied]
            elif score == best_score:
                best_moves.append(applied)

        if not best_moves:
            # timeout fallback: deadline 在任何 move 评分前触发。
            # 用 RNG 抽签而不是 legal[0]，避免 move 生成顺序决定选择。
            return self._rng.choice(legal)

        if self.randomize_ties:
            return self._rng.choice(best_moves)
        return best_moves[0]

    # ------------------------------------------------------------------
    # internal search
    # ------------------------------------------------------------------

    def _expectimin(
        self,
        state: GameState,
        perspective: Player,
        depth: int,
        deadline: float,
    ) -> float:
        """对手回合的期望值：枚举骰子 1-6，对每个骰子取对手最优（对我最差）回应的评估值，再平均。

        返回从 ``perspective`` 视角的期望分数。
        """
        winner = state.get_winner()
        if winner is not None:
            return WIN_SCORE if winner is perspective else -WIN_SCORE

        if depth < 0:
            return evaluate(state, perspective, **self._eval_kwargs)

        total = 0.0
        opponent = perspective.opponent

        for dice_val in range(1, 7):
            if time.perf_counter() > deadline:
                # emergency: use the running average so far
                remaining = 6 - (dice_val - 1)
                if remaining > 0:
                    total += (total / max(dice_val - 1, 1)) * remaining
                return total / 6.0

            opp_moves = state.legal_moves(opponent, dice_val)
            if not opp_moves:
                total += WIN_SCORE
                continue

            best_for_opp = float("inf")
            for opp_move in opp_moves:
                state.apply_move(opp_move, dice=dice_val)
                try:
                    if depth > 0:
                        val = self._expectimax(state, perspective, depth - 1, deadline)
                    else:
                        val = evaluate(state, perspective, **self._eval_kwargs)
                finally:
                    state.undo_move()

                if val < best_for_opp:
                    best_for_opp = val

            total += best_for_opp

        return total / 6.0

    def _expectimax(
        self,
        state: GameState,
        perspective: Player,
        depth: int,
        deadline: float,
    ) -> float:
        """我方回合（骰子未知）的期望值：枚举骰子 1-6，对每个骰子取我方最优回应，再平均。"""
        winner = state.get_winner()
        if winner is not None:
            return WIN_SCORE if winner is perspective else -WIN_SCORE

        if depth < 0:
            return evaluate(state, perspective, **self._eval_kwargs)

        total = 0.0

        for dice_val in range(1, 7):
            if time.perf_counter() > deadline:
                remaining = 6 - (dice_val - 1)
                if remaining > 0:
                    total += (total / max(dice_val - 1, 1)) * remaining
                return total / 6.0

            my_moves = state.legal_moves(perspective, dice_val)
            if not my_moves:
                total += -WIN_SCORE
                continue

            best_for_me = float("-inf")
            for my_move in my_moves:
                state.apply_move(my_move, dice=dice_val)
                try:
                    val = self._expectimin(state, perspective, depth - 1, deadline)
                finally:
                    state.undo_move()

                if val > best_for_me:
                    best_for_me = val

            total += best_for_me

        return total / 6.0
