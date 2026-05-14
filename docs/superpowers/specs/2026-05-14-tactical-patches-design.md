# 战术补丁实验设计：rollout_tactical 候选 AI

日期：2026-05-14
范围：在现有 AI 体系上新增一个**包装器 AI** `TacticalAI`，把两类「明确规则」局面（直接胜利、彻底化解对手一步胜）做成硬规则，其余局面完全透明地交给被包装的 base AI。这里的“一步胜”同时覆盖到达目标角和吃光对方两种胜利条件。Phase 1 只接 `rollout` 作为 base，注册为 `rollout_tactical` kind；通过候选阶段 bench 后再考虑替换 release 默认。

## 0. 路线定位

当前 release/v1.0 默认 AI 是 `rollout`，对 `greedy_risk` 合并胜率约 62.62%（800 局，见 `docs/superpowers/specs/2026-05-13-mcts-phase1-design.md` §1）。MCTS Phase 1 已确认在 200ms / 500ms 两档算力下对 `greedy_risk` 都打平（51%-50%），瓶颈是叶节点估值，不在本次范围。

本次工作是 `docs/superpowers/specs/2026-05-13-mcts-phase1-design.md` §11 列出的低风险增量第 3 条「战术补丁」。MCTS Phase 1 的 `mcts_eval_v1` 代码以及 `bench_mcts.py` 已经落地但未提交，本设计与之解耦——既不依赖 MCTS，也不影响其作为实验候选的地位。

短期主线优先级（与 MCTS 设计 §0 一致）：

1. 保持 release/v1.0 稳定，默认 AI 继续 `rollout`，除非战术补丁通过候选门禁。
2. 不引入新依赖、不改 `core/` 规则、不改 evaluator 数值语义。
3. 包装器模式保证可回滚——新 kind 不替换原 `rollout`，bench 数据不支持就保留为实验代码。

## 1. 背景

### 1.1 现有 AI 对战术局面的处理

| AI | 直接胜利 | 阻止对手一步胜 |
|---|---|---|
| `greedy` | ✓ 隐式（`evaluate` 终局返回 `WIN_SCORE=1e6`，量级压倒一切） | ✗（不带 risk 权重） |
| `greedy_risk` | ✓ 隐式 | ✓ 连续惩罚（`EXPECTED_WIN_RISK_WEIGHT=500` × `expected_target_win_risk`） |
| `rollout` | ✓ 隐式（终局后 `_playout` 第一行 `get_winner()` 返回 winner，每次 rollout 给 +1.0） | △ 隐式但有噪声（16 次随机模拟里对手有时会赢有时不会，score 是平均） |
| `mcts_eval_v1` | ✓ 隐式（`_iterate` 检 `get_winner` 后回传 `±WIN_VALUE`） | ✗（设计 §7 显式把 risk 权重清零，色盲） |

### 1.2 为什么对 `rollout` 还有价值

`rollout` 的弱点是**采样噪声**：

- `rollouts_per_move=16` 时，两个不同走法的 score 差 0.06-0.13 都可能由随机摆动产生
- 当某走法 A 直接终局（score=1.0）、走法 B 经过几步必胜（score=0.95）时不容易出错；但当 A 走法**让对手必胜** vs B 走法**化解对手必胜**时，rollout 的 16 次模拟里对手能否抓住胜机本身就有概率波动，可能把两手 score 算成 0.30 vs 0.45 这种「明显但不决定性」的差距，被随机 tie-break 或 ε-rollout 翻盘。

战术补丁把这两类极端局面从「概率近似」抽出来做**确定性规则**，作为 rollout 决策上的安全网。预期增量集中在 5-15% 触发战术规则的局面，平均到全局期望胜率提升 3-7 个百分点。

### 1.3 为什么不直接调 `rollout` 的参数

提高 `rollouts_per_move` 或降低 `epsilon` 能减少噪声，但代价是每步时间膨胀；release 已经基于现有参数做过门禁验证。本设计走「包装器加战术安全网」而非「调底层 rollout 参数」，是为了**保留 `rollout` 自身的 release 资质**，让战术包装作为独立可回滚的增量。

## 2. 设计目标

1. 新增 `TacticalAI` 包装类，注册 kind `rollout_tactical`；不替换 `rollout`。
2. 实现 Patch 1（直接胜利硬短路）和 Patch 2（彻底化解对手一步胜的过滤 + 委托）。一步胜判定必须覆盖到角胜和吃光胜。
3. 对 base AI 完全透明：没有战术规则触发时，base 看到同一个 state/dice，并且只调用一次。
4. TacticalAI 自身产生的走法永远来自 `state.legal_moves(...)` 子集；透明 fallback 依赖 base AI 遵守现有 `AIPlayer` 协议。
5. 不修改 `state` 入参（与现有 AI 协议一致）。
6. 通过候选阶段 bench（vs `rollout`，800 局，Wilson 下界 ≥52%）才允许讨论替换 release 默认。

## 3. 非目标

- **不做 Patch 3「终局 race」**——设计文档 §11 提到但语义模糊。`distance_weight` 已经隐式处理「双方都接近角落时优先冲线」；找不到比连续权重更清晰的硬规则形式。
- **不做部分化解**——Patch 2 只在能 100% 消除对手胜威胁时触发。部分减少（如 5 骰子 → 3 骰子）让 base AI 用概率/搜索判断。
- **不改 `core/`、`evaluator`、`risk` 的语义**。
- **不在本次包装 `greedy_risk` 或 `mcts_eval_v1`**。包装器是通用的，未来可扩，但 Phase 1 只验 `rollout_tactical`。
- **不引入新依赖**（纯 stdlib + 现有 `ai/`、`core/` API）。
- **不修改 GUI、release 配置、默认参数**——这些只有 bench PASS 后另起 PR。

## 4. 架构

### 4.1 包装器协议

```python
class TacticalAI:
    """战术包装器：对 base AI 套两类硬规则。

    使用：和其他 AI 一致，构造时注入 ``base`` 和 ``rng``；
    name 默认 ``"{base.name}_tactical"`` 或显式指定。
    """

    def __init__(
        self,
        *,
        base: "AIPlayer",
        rng: random.Random | None = None,
        name: str | None = None,
    ) -> None: ...

    def choose_move(self, state: GameState, dice: int) -> Move | None: ...
```

### 4.2 决策流程

```
choose_move(state, dice):
    legal = state.legal_moves(state.current_player, dice)
    if not legal: return None

    perspective = state.current_player

    # Patch 1：直接胜利硬短路
    winning = find_winning_moves(state, dice, perspective)
    if winning:
        return pick_max_material(winning, rng)    # tie-break：最大吃子 → rng 抽签

    # Patch 2 守卫：先看「我方行动前」对手是否已经有一步胜威胁；
    # 没威胁就跳过逐 move 检
    threat = opponent_winning_dice_set(state, opponent=perspective.opponent)
    if threat:
        neutralizing = find_neutralizing_moves(state, dice, perspective)
        if neutralizing:
            return _delegate_to_base_filtered(state, dice, neutralizing)

    # 无规则触发：完全透明
    return base.choose_move(state, dice)
```

### 4.3 关键决策

- **Patch 1 硬短路 vs filter+delegate**：直接胜利时，所有 winning move 在「赢」这件事上等价，没必要让 base 再花时间打分。硬短路也确保 rollout 噪声不会把 tied winning move 排在更差的非赢手后面。
- **Patch 2 filter+delegate**：多个 neutralizing move 时，先调一次 base AI；如果 base 本来就选了 neutralizing move，则尊重 base 判断，否则在 neutralizing 子集内随机兜底。这样硬规则只提供「安全过滤」，不需要包装或修改 `GameState`。
- **完全透明 fallback**：没规则触发时，TacticalAI 应该和 `base` 行为完全一致——同样的 state、同样的 dice、调用一次。这样可以把差异归因限定在战术规则触发局面，避免无战术局面引入回归。

## 5. 组件

### 5.1 文件清单

新增：

```
ai/tactical.py              # TacticalAI + 模块级辅助函数
tests/test_tactical.py      # 18 个单测
```

修改：

```
ai/__init__.py              # 导出 TacticalAI
ai/match.py                 # build_ai 注册 "rollout_tactical"，ai_version_signature 收 base 字段
```

通用化（一并完成）：

```
scripts/bench_ai.py           # 候选 AI 参数化
scripts/bench_mcts.py         # 可保留为 mcts_eval_v1 默认参数的兼容入口
```

### 5.2 模块结构

`ai/tactical.py`：

```python
class TacticalAI:
    name: str
    base: "AIPlayer"
    rng: random.Random

    def __init__(self, *, base, rng=None, name=None) -> None: ...
    def choose_move(self, state, dice) -> Move | None: ...
    # 内部
    def _delegate_to_base_filtered(self, state, dice, allowed) -> Move: ...


# 模块级纯函数辅助（无状态、便于单测）
def find_winning_moves(
    state: GameState, dice: int, perspective: Player
) -> list[Move]:
    """返回所有 apply 后让 perspective 立即获胜的 legal_moves 子集。"""


def opponent_winning_dice_set(state: GameState, *, opponent: Player) -> set[int]:
    """``opponent`` 下一回合能用哪些骰子值一步获胜。

    显式收 ``opponent``——不依赖 ``state.current_player``，因为本函数会在
    perspective 行动前后两种 state 状态下被调用（行动前 current_player==perspective，
    行动后 current_player==perspective.opponent），current_player 含义不同。

    一步获胜必须同时覆盖两类 core 胜利条件：到达目标角、吃光对方棋子。
    """


def find_neutralizing_moves(
    state: GameState,
    dice: int,
    perspective: Player,
) -> list[Move]:
    """返回当前方哪些走法 apply 后，``opponent_winning_dice_set`` 变空集。

    Patch 2 的保守语义——只接受 100% 消除对手一步胜威胁；
    部分减少不在本函数返回，交给 base AI 用其概率/搜索能力判断。
    """


def pick_max_material(moves: list[Move], rng: random.Random) -> Move:
    """从 moves 里选 captured_piece 不为 None 的；多个则 rng.choice；
    若全无吃子则 rng.choice 全部。"""
```

### 5.3 `build_ai` 注册

```python
if kind == "rollout_tactical":
    from ai.rollout_ai import RolloutAI
    from ai.tactical import TacticalAI
    # base_rng 与 build_ai("rollout", seed=seed) 保持同源；
    # wrapper_rng 独立派生，避免 tie-break 消耗 base 的 rollout 随机流。
    base_rng = random.Random(seed)
    wrapper_seed = None if seed is None else (int(seed) ^ 0x5DEECE66D)
    wrapper_rng = random.Random(wrapper_seed)
    base = RolloutAI(rng=base_rng, **ai_kwargs)
    return TacticalAI(base=base, rng=wrapper_rng, name="rollout_tactical")
```

**rng 隔离的理由**：base AI 用 `base_rng` 抽 rollout 的随机模拟；wrapper 用独立 `wrapper_rng` 做 tie-break，避免「TacticalAI 多消耗几次 random，rollout 的种子流就漂了」破坏 bench 复现性。不要从已经传给 base 的 RNG 上调用 `randrange()` 派生 wrapper seed，否则构造阶段就会提前推进 base 随机流。

### 5.4 `ai_version_signature` 扩展

`TacticalAI` 实例上额外暴露：

```python
sig = {
    "name": "rollout_tactical",
    "base": ai_version_signature(self.base),     # 递归签名 base
    "patches": ["direct_win", "block_one_step_win"],
}
```

`ai_version_signature` 需识别 `TacticalAI`（通过 `hasattr(ai, "base")` 或 `isinstance` 检），其余 AI 的签名逻辑不变。

## 6. 数据流

### 6.1 Patch 1 详细

```python
def find_winning_moves(state, dice, perspective):
    winning = []
    for move in state.legal_moves(perspective, dice):
        state.apply_move(move, dice=dice)
        try:
            if state.get_winner() is perspective:
                winning.append(move)
        finally:
            state.undo_move()
    return winning
```

注意 `state.legal_moves` 返回的 `Move` 对象不一定是 `apply_move` 内部匹配出的对象（`apply_move` 用 `_find_matching_legal_move` 重新解析），但 from_pos/to_pos 等价；返回 `move` 后让 `TacticalAI.choose_move` 直接用——下次调 `apply_move(move, dice)` 时会重新匹配。

### 6.2 Patch 2 详细

```python
def opponent_winning_dice_set(state: GameState, *, opponent: Player) -> set[int]:
    winning_dice = set()
    snapshot = state.serialize()
    for d in range(1, 7):
        for move in state.legal_moves(opponent, d):
            sim = GameState.deserialize(snapshot)
            sim.current_player = opponent
            sim.apply_move(move, dice=d)
            if sim.get_winner() is opponent:
                winning_dice.add(d)
                break
    return winning_dice


def find_neutralizing_moves(state, dice, perspective):
    """对每个候选 move：apply → 检对手 winning_dice_set →
    若为空集 → 该 move 是 neutralizing。"""
    neutralizing = []
    for move in state.legal_moves(perspective, dice):
        state.apply_move(move, dice=dice)
        try:
            post_threat = opponent_winning_dice_set(state, opponent=perspective.opponent)
            if not post_threat:
                neutralizing.append(move)
        finally:
            state.undo_move()
    return neutralizing
```

**一步胜判定**：不能只检查 `move.to_pos == target_corner(opponent)`；core 的胜利条件还包括吃光对方棋子。`opponent_winning_dice_set` 用 `GameState.deserialize(state.serialize())` 创建副本，把副本 `current_player` 设为 `opponent` 后 apply 假想走法，再用 `get_winner()` 判定，避免污染原始 `state`，也避免 pre-move state 上 `current_player != opponent` 导致 `apply_move` 抛错。

**保守判定**：post-move threat 必须为空集。部分减少（如 5 骰子 → 3 骰子）不算 neutralizing，让 base AI 用它的概率/搜索能力衡量。

**优化短路**：`TacticalAI.choose_move` 主流程先调 `opponent_winning_dice_set(state, opponent=perspective.opponent)` 检 pre-move threat，空集时整个 patch 2 不触发，避免逐 move 调 `find_neutralizing_moves`。后者每个 move 在 apply 后做 6 组骰子威胁扫描（含副本模拟），具体开销以 §10 bench 为准。

### 6.3 完整调用链

```python
def choose_move(state, dice):
    legal = state.legal_moves(state.current_player, dice)
    if not legal: return None

    perspective = state.current_player

    # Patch 1
    winning = find_winning_moves(state, dice, perspective)
    if winning:
        return pick_max_material(winning, self.rng)

    # Patch 2 守卫：「我方行动前」对手有没有一步胜威胁
    pre_move_threat = opponent_winning_dice_set(state, opponent=perspective.opponent)
    if pre_move_threat:
        neutralizing = find_neutralizing_moves(state, dice, perspective)
        if neutralizing:
            return self._delegate_to_base_filtered(state, dice, neutralizing)

    return self.base.choose_move(state, dice)
```

### 6.4 `_delegate_to_base_filtered` 实现

```python
def _delegate_to_base_filtered(self, state, dice, allowed: list[Move]) -> Move:
    """优先尊重 base 选择；若 base 选到 allowed 外，则在 allowed 内兜底。

    实现策略：调一次 base.choose_move(state, dice)，
    如果 base 的返回在 allowed 里就用；否则在 allowed 里 rng.choice。
    
    选这个策略而非「修改 state 限制 legal_moves」的理由：
    - 不需要修改 state 或包装 GameState
    - base 看到完整 state，能用全部信息推理；只是最后的输出可能被替换
    - rollout 的 rollout 内部还是按完整 legal_moves 跑，不影响其评估准确度
    """
    base_choice = self.base.choose_move(state, dice)
    allowed_keys = {(m.from_pos, m.to_pos) for m in allowed}
    if base_choice is not None and (base_choice.from_pos, base_choice.to_pos) in allowed_keys:
        return base_choice
    return self.rng.choice(allowed)
```

**取舍**：这个策略**没强制 base 在子集里挑**，只是「base 自己想挑的如果不在子集就替换」。这有个风险——base 看到完整选项，可能挑了一个 unsafe move（落在 allowed 之外），我们就把它替换成 rng 抽样。换言之，base 的「最优判断」可能被覆盖。

更激进的策略是给 base 一个 mock state，只让它看到 allowed 的 legal_moves。但这需要包装 GameState，对 rollout 这种自己模拟的 AI 还会破坏其 rollout 视野。

**保守选择**：用「调 base 一次，不合规则就替换」策略。Patch 2 的核心价值是「至少不输给对手的一步胜」，rng tie-break 在 allowed 里是 acceptable fallback。bench 数据会暴露这个策略是否需要升级。

## 7. 边界

| 边界 | 约定 |
|---|---|
| 不修改 core/ | 只调 `legal_moves`、`apply_move`、`undo_move`、`get_winner`、`serialize` |
| 不修改 evaluator | 完全不调 `evaluate` |
| 不引入外部库 | `random`、`dataclasses`（如需）；纯 stdlib |
| 不破坏 base AI 协议 | base 必须有 `choose_move(state, dice) -> Move \| None` |
| 不修改 state | 当前方假想走法用 apply/undo 配对；对手假想走法只在反序列化副本上执行 |
| 不返回非法走法 | 战术分支永远从 `state.legal_moves(...)` 子集里返回；透明 fallback 沿用 base AI 协议 |
| 不替换 `rollout` 默认 | bench 候选门禁通过才允许另起 PR 改 release 配置 |

## 8. 与现有 AI 的对比

| | RolloutAI | TacticalAI(RolloutAI) | 改动量 |
|---|---|---|---|
| 决策方式 | 16 次 rollout 平均胜率 | 战术规则优先；否则 rollout | 包装层 |
| 直接胜利 | rollout score=1.0 自然选出 | 硬规则短路，不跑 rollout | 重叠 |
| 对手一步胜威胁 | rollout 平均会反映在 score 上，但有噪声 | 100% 消除时硬规则触发 | 互补 |
| 部分缓解威胁 | rollout 概率近似 | 不触发；交给 rollout | rollout 主导 |
| 对手无威胁 | 正常 rollout | 完全透明 | 0 |
| 单步时间（无规则触发） | ~100ms | ~100ms + threat scan（6 个骰子 × legal moves × clone/apply） | 需 bench 校准 |
| 单步时间（patch 1 触发） | ~100ms | <1ms（短路） | -99ms |
| 单步时间（patch 2 触发） | ~100ms | ~100ms + 检测开销（仍调 base 一次） | 需 bench 校准 |

预期每步平均开销增加 5-15%，不会突破 rollout 现有 500ms `max_step_time_ms` 上限；最终以 smoke/candidate bench 的 `avg_step` / `max_step` 为准。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `_delegate_to_base_filtered` 让 base 看完整 state 但只用 allowed → base 选 unsafe move 被 rng 替换，决策质量下降 | bench 数据评估；若胜率不升反降，升级到「mock state 限制 legal_moves」策略 |
| Patch 2 的逐 move 计算开销超 max_step_time_ms | 守卫先检 `pre_move_threat` 空集；空集时直接跳过 patch 2 |
| `apply_move`/`undo_move` 配对错误或 opponent 假想走法污染 state | 当前方走法用 `try/finally` 配对；对手假想走法在反序列化副本上执行；单测 `test_does_not_mutate_state` 兜底 |
| rng 共享导致 base 复现性破坏 | wrapper 用独立 RNG（§5.3） |
| `ai_version_signature` 没递归处理 base | 递归实现 + 单测 `test_rollout_tactical_signature_includes_base` |
| Patch 1 和 Patch 2 同时该触发的边界（既能直接赢又有威胁） | 流程上 Patch 1 优先；既然能直接赢就赢，不必考虑对手 |
| 与 `mcts_eval_v1_tactical` 未来共存的命名冲突 | name 字段约定 `"{base.name}_tactical"`，build_ai kind 串约定 `"{base_kind}_tactical"` |

## 10. 验证

### 10.1 单元测试（`tests/test_tactical.py`，rigid TDD 顺序）

**Patch 1**：

1. `test_picks_winning_move_when_available` — 构造一手必胜局面，断言 TacticalAI 返回该 move
2. `test_picks_max_material_winning_move` — 两个赢手中只有一个吃子，断言选吃子
3. `test_ties_among_winning_moves_use_rng` — 固定 seed，多个等价赢手输出确定
4. `test_no_winning_move_falls_through_to_patch2_or_base` — 没赢手时进入 patch 2 守卫或 base

**Patch 2**：

5. `test_no_threat_means_full_delegation` — `pre_move_threat` 空集时 base 调用一次且不被过滤
6. `test_single_legal_non_tactical_move_still_delegates_to_base` — 唯一合法但无战术规则时仍调用 base，保证透明性
7. `test_target_corner_threat_fully_neutralizing` — 对手到角一步胜 + 我方可完全化解，断言选 neutralizing move
8. `test_capture_all_threat_is_detected` — 对手可吃光我方最后一子时，`opponent_winning_dice_set` 必须识别该骰子
9. `test_capture_all_threat_fully_neutralizing` — 对手吃光威胁 + 我方可完全化解，断言触发 Patch 2
10. `test_partial_neutralizing_falls_through_to_base` — 多威胁只能消一个，断言 base 被调（不被过滤）
11. `test_multiple_neutralizing_delegates_to_base_choice` — 多 neutralizing 时若 base 选其中之一就用之
12. `test_base_picks_outside_allowed_fallback_to_rng` — base 选了非 neutralizing move 时 rng 在 allowed 里抽
13. `test_pre_move_threat_skip_when_no_opponent_legal` — 对手任何骰子都无 legal_moves（罕见）→ pre_move_threat 空集

**集成**：

14. `test_build_ai_rollout_tactical` — `build_ai("rollout_tactical", seed=...)` 返回 TacticalAI(RolloutAI)
15. `test_rollout_tactical_signature_includes_base` — `ai_version_signature` 含 base 子签名和 patches 列表
16. `test_rollout_tactical_rng_isolation_does_not_advance_base_rng` — wrapper tie-break 不消耗 base rollout RNG

**不变性**：

17. `test_does_not_mutate_state` — 跟现有 MCTS/Greedy 测试一致
18. `test_returns_legal_move_for_every_dice_from_default_state` — 默认开局 6 个骰子 × N 次都返回合法 move

### 10.2 Bench（设计文档 §10 风格的分阶段门禁）

复用 `bench_mcts.py` 的阶段框架，泛化成 `scripts/bench_ai.py`；保留 `bench_mcts.py` 作为兼容入口或薄 wrapper，避免既有复现实验命令失效：

- 候选 AI 由 `--candidate <kind>` 参数指定（`bench_mcts.py` wrapper 可默认传 `mcts_eval_v1`）
- 对手由 `--opponent <kind>` 参数指定（与现有 `bench_mcts.py` 行为一致）
- 阶段配置 `STAGE_CONFIG` 不变；门禁集合不变
- 报告字段：`candidate_wins / candidate_win_rate / candidate_win_ci95`（替换原 `mcts_*` 命名）
- AI-specific 遥测（`avg_iterations`、`max_depth`）变为 optional——只在候选 AI 暴露相应字段时记录

`rollout_tactical` 的 bench 计划：

| 阶段 | 候选 | 对手 | 局数/方向 | 关键门禁 |
|---|---|---|---|---|
| smoke | `rollout_tactical` | `greedy` | 50 | illegal=0, crashes=0, max_step<1000ms |
| candidate | `rollout_tactical` | `rollout` | 400（共 800） | 胜率≥55%, Wilson lower≥52%, avg_step≤500ms, max_step≤5000ms |

**为什么 800 局**：补丁只在小概率局面（赢手 / 胜威胁）触发，单局期望增量小。预估真胜率 53-58%，需较大样本让 CI 下界稳定 ≥52%。粗略 22 min（rollout 比 mcts 慢，按 1.7s/局算）。

**为什么用 `rollout` 做对手而非 `greedy_risk`**：候选阶段的核心问题是「能不能上 release」，对照组应当是当前 release 默认（rollout）；与 `greedy_risk` 对比对评估「相对其他低强度对手是否变强」有意义，但不是晋升决策点。

### 10.3 跳过 promotion 阶段

MCTS Phase 1 设计的 promotion 阶段是 vs `rollout` ≥ 400 局，与本设计的 candidate 完全等价（候选本身就是 vs rollout）。所以**通过 candidate 即直接进 release 候选名单**，不再额外跑 promotion。

## 11. 与其他工作的关系

- **MCTS Phase 1**：解耦。`rollout_tactical` 不依赖 MCTS。MCTS 后续若需要类似战术安全网，可通过 `TacticalAI(base=MCTSAI(...))` 包装得到 `mcts_eval_v1_tactical`，但本次不做。
- **`bench_mcts.py` 泛化**：§10.2 已说明。改完后 MCTS 候选仍能用 `scripts/bench_ai.py --candidate mcts_eval_v1 --opponent greedy_risk` 跑；如保留 `bench_mcts.py` wrapper，旧命令继续可用。
- **设计文档 §11 其他低风险增量**：
  - 「rollout 参数复验」：独立工作；如果它先做，可能改变 `rollout` 的 baseline，但 `rollout_tactical` 仍以「当前 release rollout」为基准做对比，逻辑无变。
  - 「开局搜索」：完全独立，不冲突。
- **release/v1.0**：本设计 `gate_pass=True` 后才另起 PR 改 GUI/config 默认，本次 spec 不涉及。

## 12. 后续（不在本次范围）

- `greedy_risk_tactical`：把战术包装套到 `greedy_risk` 上，验证「确定性 + greedy_risk 风险权重」组合是否比纯 `greedy_risk` 强。
- `mcts_eval_v1_tactical`：MCTS Phase 1 的色盲问题用战术安全网部分补偿；可能让 MCTS 候选门禁通过。
- Patch 2 升级到「部分化解」：当无法 100% 消除威胁时，按「化解骰子数最大」打分，再交 base。需要参数化「化解多少算够」。
- Patch 3 「终局 race」：若有具体且可测的语义出现再加。
- 战术规则参数化：允许通过 kwargs 关闭某个 patch 做 ablation 实验。
