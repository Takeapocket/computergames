# MCTS Phase 1 实验设计：启发式树搜索候选

日期：2026-05-13
范围：在现有 AI 基础上新增一个 **实验性** MCTS 候选。Phase 1 只验证 UCT 树搜索、骰子随机节点建模和 root-player 视角回传；不替换默认 AI，不改变 release 配置。

> 2026-05-16 entry guard 更新：当前 GUI/release 工作默认已不是旧 flat `rollout`，而是 `kind="rollout"` + P3 promotion 显式 kwargs（32 rollout / move、risk-aware playout、Zweistein cutoff、30ms deadline safety）。P4 的 `mcts_eval_v1` candidate/promotion profile 必须对这个当前 release 默认配置；裸 `opponent="rollout"` 不能作为 P4 晋升对手。
>
> 2026-05-16 candidate probe 更新：`mcts_eval_v1` 对当前 release 默认 rollout 的两组小样本均未过 candidate 门禁。`time_limit_ms=200` 双边 25+25 合并胜率 30.0%；默认 `time_limit_ms=500` 双边 10+10 合并胜率 30.0%；两者均 0 illegal/crash/timeout，但强度不足，不进入正式 200+200 candidate 或 promotion。
>
> 2026-05-16 P4.1 targeted fix 更新：新增最小真实局面测试验证 opponent DecisionNode 选择对 `root_player` 最差的应手；`MCTSAI` leaf 支持 `current|zweistein` evaluator。`mcts_eval_v1(leaf_evaluator=zweistein)` 双边 10+10 对当前 release 默认 rollout 胜率 25.0%，0 illegal/crash/timeout，低于 45% 停止线；停止 MCTS，转 P5。

## 0. 路线定位

当前比赛版本已经具备稳定 GUI、七盘制流程、auto-save、release/v1.0 和默认 `rollout` AI。下一阶段 AI 提升的优先级不是“引入更高级算法”，而是用 harness 证明候选确实强于当前默认版本。

短期主线优先级：

1. 保持 release/v1.0 稳定，默认 AI 继续使用 `rollout`。
2. 优先推进低风险增量：rollout 参数、开局搜索、战术补丁、终局 race 检查。
3. MCTS 作为候选实验并行保留，只有数据证明强于 `rollout` 才考虑晋升。
4. 不做神经网络、训练框架、PUCT/APV-MCTS 或任何新增重依赖。

本文件不是默认 AI 晋升方案，而是 `mcts_eval_v1` 的实验设计草案。

## 1. 背景

历史背景：2026-05-13 本设计起草时默认 AI 是旧 flat `rollout`。2026-05-16 P3 已受控替换为 `kind="rollout"` + P3 promotion 显式 kwargs；后续 P4 候选必须对当前 release 默认配置复验。旧 flat `rollout` vs `greedy_risk` 的历史胜率只能作为背景，不再是 P4 晋升基线。

`rollout` 使用 flat Monte Carlo：对每个候选走法独立做 N 次随机模拟，不共享搜索树。这种方式简单稳定，但会把预算平均花到所有候选走法上，可能浪费在明显较差的分支。

MCTS 通过维护共享搜索树解决这个问题，把计算资源集中到最有希望的分支上。

专利 CN110119804A 的核心贡献是 APV-MCTS：用神经网络替代纯随机 rollout 做叶节点估值和先验策略。Phase 1 不实现 APV-MCTS，也不引入神经网络；只用现有 `evaluate()` 作为叶节点启发式，先验证树结构和骰子节点建模是否值得继续投入。

## 2. 设计目标

1. 新增 `MCTSAI` 类，注册 kind `mcts_eval_v1`，不替换默认 AI。
2. 正确建模决策节点与骰子随机节点的交替。
3. 叶节点用现有 `evaluate()` 估值，不做 rollout。
4. 统一 `root_player` 视角回传，避免视角翻转 bug。
5. 先用 smoke 验证稳定性，再用 harness 判断是否值得扩大样本。
6. 晋升候选必须对当前 release 默认 `rollout` 显式 kwargs 有统计优势；只打赢 `greedy_risk` 或旧 flat `rollout` 不足以替换默认 AI。

## 3. 非目标

- 不做 PUCT / prior policy。
- 不做 rollout fallback。
- 不做关键节点识别、深度阈值分支。
- 不引入 numpy 或任何新依赖（纯 Python stdlib + 现有 `core/` API）。
- 不修改 `core/` 规则逻辑。
- 不修改 GUI / release 默认 AI。
- 不在未获明确批准时运行大样本 benchmark。
- 不把专利 APV-MCTS 作为短期赛前工程目标。

## 4. 树结构

```
决策节点 (DecisionNode)
  state_hash: str
  player: Player                    # 当前轮到谁走（决策方）
  dice: int                         # 该节点已被确定的骰子值（根节点由 choose_move 提供）
  children: dict[Move, ChanceNode]  # 走法 → 骰子节点

骰子节点 (ChanceNode)
  parent_decision: DecisionNode
  parent_move: Move
  visit_count: int                 # 该 move 边的聚合访问次数
  total_value: float               # 该 move 边的 root_player 视角累计价值
  children: dict[int, DecisionNode] # 骰子值 (1-6) → 对方的决策节点
```

回合流程：

```
我方决策 (已知 dice) → 选 Move → 对方骰子 (1-6 均匀随机) → 对方决策 → ...
```

每层交替，直到终局或叶节点截断。

## 5. 算法

### choose_move(state, dice) → Move

```
root = 获取或创建 DecisionNode(state, dice)
deadline = now + time_limit_ms / 1000

while now < deadline:
    leaf = select(root, state, dice)       # 用 state 副本沿树走到叶节点
    winner = state.get_winner()
    if winner is not None:
        value = WIN_VALUE if winner == root_player else -WIN_VALUE
    else:
        value = evaluate(state, root_player)  # 叶节点估值
        value = tanh(value / SCALE)           # 归一化到 [-1, 1]
    backprop(leaf, value)                     # 沿路径回传
    state 恢复为 root 局面

return root.children 中 visit_count 最大的 Move
```

### select(leaf, state, dice)

```
while leaf 已完全展开:
    if leaf is DecisionNode:
        # UCT: root-player 节点最大化 root-player value；opponent 节点最小化 root-player value
        move, chance = select_by_turn_aware_uct(leaf, root_player)
        在 state 上 apply 对应的 move
        leaf = chance
    elif leaf is ChanceNode:
        # 均匀随机事件：不对骰子结果做 UCT
        dice = sample_dice()
        leaf = leaf.children[dice]  # 或 lazily 创建对方 DecisionNode
return leaf
```

### 关键：骰子节点不是决策节点

骰子节点不允许用 UCT。处理方式：

- **Lazy 创建**：当第一次访问某个 `(decision_node, move, dice)` 组合时才创建对应的下层 DecisionNode。
- **边统计**：ChanceNode 保存 parent move 的聚合 visit/value，用于父 DecisionNode 的 UCT 选 move。
- **骰子不决策**：ChanceNode 的 dice children 不参与 UCT；按均匀概率 1/6 随机采样骰子值，然后进入对应的 DecisionNode。

### 归一化

```python
SCALE = 100.0  # evaluate 的距离差×1 + 子力差×10 + 风险×3 + 胜风险×500 ≈ 几百量级

def normalize(raw: float) -> float:
    return math.tanh(raw / SCALE)
```

`math.tanh` 把任意实数压到 (-1, 1)，天然适合 UCT 的 exploitation 项。

evaluate 的 `perspective` 参数始终传 `root_player`，保证回传值含义一致。
因为回传值始终是 `root_player` 视角，DecisionNode 选择必须区分行动方：`node.player is root_player` 时最大化 exploitation；`node.player is root_player.opponent` 时最小化 exploitation。探索项仍为正，未访问子节点仍优先探索。

### backprop(path, value)

```
for node in reversed(path):
    node.visit_count += 1
    node.total_value += value
```

所有节点的 `q` 值都是 root_player 视角的期望价值，由 `total_value / visit_count` 计算得到。

## 6. 模块设计

新增一个文件：

```
ai/mcts.py   # DecisionNode, ChanceNode, mcts_choose_move, MCTSAI
```

`ai/__init__.py` 及 `ai/match.py` 中注册 kind `mcts_eval_v1`。

Phase 1 使用显式的两类节点，避免把骰子随机事件误写成可决策分支。

### Node 数据结构草案

```python
@dataclass(slots=True)
class DecisionNode:
    state_hash: str
    player: Player
    dice: int
    visit_count: int = 0
    total_value: float = 0.0
    children: dict[Move, ChanceNode] = field(default_factory=dict)
    expanded_moves: bool = False

    @property
    def q(self) -> float:
        return self.total_value / self.visit_count if self.visit_count else 0.0


@dataclass(slots=True)
class ChanceNode:
    parent_move: Move
    visit_count: int = 0
    total_value: float = 0.0
    children: dict[int, DecisionNode] = field(default_factory=dict)

    @property
    def q(self) -> float:
        return self.total_value / self.visit_count if self.visit_count else 0.0
```

Phase 1 每次 `choose_move()` 新建树，不做跨步 transposition table。这样损失一点复用，但实现更容易验证，风险更低。

### MCTSAI 类

```python
class MCTSAI:
    def __init__(
        self,
        *,
        time_limit_ms: float = 500.0,
        c_uct: float = math.sqrt(2),
        scale: float = 100.0,
        rng: random.Random | None = None,
        name: str = "mcts_eval_v1",
    ):
        ...

    def choose_move(self, state: GameState, dice: int) -> Move | None:
        ...
```

### UCT 公式

```python
def uct_score(child: ChanceNode, parent_visits: int, c: float) -> float:
    exploitation = child.q
    exploration = c * math.sqrt(math.log(parent_visits) / child.visit_count)
    return exploitation + exploration
```

未访问过的子节点 `visit_count == 0`，返回 `float("inf")` 以优先探索。

## 7. 边界

| 边界 | 约定 |
|------|------|
| 不修改 core/ | 只调用 `legal_moves`、`apply_move`、`undo_move`、`get_winner`、`serialize` |
| 不依赖外部库 | `random`、`math`、`time`、`dataclasses`，纯 stdlib |
| 不引入新 AI 协议 | 复用 `ai/__init__.py` 的 `AIPlayer` Protocol |
| evaluator 语义不变 | 只传 `perspective=root_player`，不传 risk weight |
| 不做 transposition | Phase 1 每步新建树，不做跨步状态缓存 |
| 不替换默认 AI | `mcts_eval_v1` 只作为 harness 候选 |

注意：Phase 1 的 `evaluate` 调用**不传** `expected_risk_weight` 和 `expected_win_risk_weight`。
这些参数在对手回合的语义有问题（参见 `ai/evaluator.py` 的 docstring 警告），而 MCTS 在对手回合也会调 evaluate。直接传 `expected_risk_weight=0` 和 `expected_win_risk_weight=0`，只保留距离和子力两项。

## 8. 与现有 AI 的对比

| | GreedyAI | RolloutAI | ExpectimaxAI | MCTSAI Phase 1 |
|---|---|---|---|---|
| 搜索 | 1 步前瞻 | Flat N 次独立模拟 | Min-max 树 + 骰子期望 | UCT 树 + 骰子采样 |
| 估值 | evaluate | 模拟终局胜率 | evaluate | evaluate (归一化) |
| 骰子 | 不建模 | 采样 | 均匀期望 | 采样 |
| 共享 | 无 | 无 | 无 | 共享搜索树 |
| 耗时 | <1ms | ~60ms | ~5ms (depth=1) | ≈ rollout 同级或更优 |

MCTS 的核心优势：把 RolloutAI 浪费在"差候选走法"上的模拟时间，重新分配到"有希望的候选走法"上。

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 骰子节点写歪（当成决策节点用 UCT） | 代码 review 显式区分 DecisionNode 和 ChanceNode，ChanceNode 不用 UCT |
| 回传视角错误 | 全部用 root_player 视角，`evaluate(state, root_player)`，不加 risk 项；opponent DecisionNode 选择时最小化 root-player value |
| evaluator 值域不归一 | `tanh(raw / SCALE)`；如果 bench 发现 SCALE 不当，作为第二优先级调 |
| 耗时超标 | `time_limit_ms` 硬截止，超时返回当前 visit_count 最多的 child |
| 胜率不如 `rollout` | 保留为实验代码，不进入 GUI/release 默认 |
| 只打赢 `greedy_risk` 但打不赢 `rollout` | 不晋升；默认 AI 的基准已经是 `rollout` |

## 10. 验证

### 单元测试（`tests/test_mcts.py`）

- 终局局面直接返回 None（无合法走法）或正解（唯一胜招）。
- 已知骰子下，MCTS 选择复现（固定 seed）。
- 超时 fallback 可用（time_limit_ms=1 仍能返回合法走法）。
- 不返回非法走法。
- 不修改输入 state。

### Bench（分阶段门禁）

Smoke 阶段：

```
mcts_eval_v1 vs greedy 双边各 50 局
illegal_moves = 0, crashes = 0
max_step_time_ms < 1000ms
```

候选阶段：

```
mcts_eval_v1 vs current release default rollout kwargs 双边各 ≥ 200 局
合并胜率 ≥ 55%
illegal_moves = 0, crashes = 0, 基于 quick_bench.py / bench_ai.py 聚合的真实 timeouts = 0
avg_step_time_ms ≤ 500ms
max_step_time_ms ≤ 5000ms
```

晋升阶段：

```
mcts_eval_v1 vs current release default rollout kwargs 双边各 ≥ 400 局
合并胜率 ≥ 55%
Wilson 95% CI lower ≥ 52%
illegal_moves = 0, crashes = 0, 基于 quick_bench.py / bench_ai.py 聚合的真实 timeouts = 0
avg_step_time_ms ≤ 500ms
max_step_time_ms ≤ 5000ms
```

### 对比基线

```
mcts_eval_v1 vs current release default rollout kwargs (red/blue)
mcts_eval_v1 vs greedy (smoke)
```

只有通过晋升阶段，才允许讨论修改 `gui/main_window.py`、`release/v1.0/config.json` 或 `release/v1.0/default_params.json`。

### 报告格式

同现有 `reports/*.md` 和 JSON bench 格式，额外记录 MCTS 特有参数：

- `c_uct`
- `scale`
- `time_limit_ms`
- `avg_iterations`（每一步平均做了多少次 UCT 迭代）
- `max_depth`（搜索树最大深度）

## 11. 与其他 AI 工作的关系

MCTS 不是下一阶段唯一主线。更稳的近期路线是：

1. `rollout` 参数复验：小样本筛选，避免长时间大样本压垮电脑。
2. 开局搜索：在已有 `balanced_v1` 基础上找 2-3 套候选布局，用固定 seed 验证。
3. 战术补丁：直接胜利、阻止对方一步胜利、终局 race 这类明确规则优先。
4. MCTS：作为 `mcts_eval_v1` 实验候选，独立报告，不污染默认 AI。

如果时间只够做一条线，优先做 rollout/开局/战术补丁；MCTS 可以保留到这些低风险增量之后。

## 12. 后续（Phase 2-3，不在本次范围）

- Phase 2：搜索树跨步复用（transposition table）
- Phase 3：rollout fallback（深度 ≥ 3 时用小样本 rollout 替代 evaluate）
- 再之后：PUCT + prior policy（仅在基础 MCTS 稳定优于 rollout 后考虑）
