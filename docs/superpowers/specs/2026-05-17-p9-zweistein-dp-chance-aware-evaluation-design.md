# P9 Zweistein-DP Chance-aware Evaluation Design

日期：2026-05-17
状态：Review-Ready
范围：P9 概率估值、rollout cutoff 概率化、根后 1 层对手骰子精确期望；所有候选默认不进入 GUI/release。

---

## 1. 背景

当前 release 默认 AI 仍是 `rollout` kind，但参数已是 P3 promotion 通过后的显式配置：

```json
{
  "ai": "rollout",
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 750.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 32,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein",
  "deadline_safety_ms": 30.0,
  "fallback_ai": "greedy_risk",
  "promotion_report": "reports/ai_promotion_decision.md"
}
```

现有 `RolloutAI` 是根节点平面 rollout：对当前骰子下的每个合法根走法采样若干次，playout 内每回合随机骰子，按 `epsilon` 随机走或使用 `GreedyAI` / `greedy_risk` policy。近分候选可补采样，超时走 fallback。

P7/P8 已经说明局部补丁收益不足：

- P7 默认 rollout vs `greedy_risk` 120 局为 87 胜 / 33 负，`missed_direct_win=0`，失败信号主要是 `allowed_direct_loss`、低置信、fallback/self-capture。
- P7.2 `rollout_adaptive_close_sample` 对当前 release 默认 rollout 双边 100+100 合并 50.0%，未过 55% candidate 门槛。
- P8 threat audit 审计 307 个位置，仅 5 个有 threat-reducing alternative，低置信 threat-reducing ratio 为 0.0120；gate 不支持实现 `rollout_threat_rerank`。
- P6 timing probe 已显示默认 AI 的 p99 约 641ms，max 约 720ms，750ms 配 30ms safety 已接近实际预算，继续单纯加采样风险高。

当前真实瓶颈不是“再补一条战术规则”，而是 cutoff 和浅层搜索使用的信息太粗。

`ai/zweistein.py::zweistein_lite_score()` 已有终局、推进、子力、期望机动性、被吃风险、直接到角风险等线性零和特征，P3 已证明它能提升默认 rollout。但 `ai/rollout_ai.py::RolloutAI._cutoff_score()` 当前对 `cutoff_eval="zweistein"` 的处理是：

```text
value > 0 -> 1.0
value < 0 -> 0.0
value == 0 -> 0.5
```

这会把略优和大优都压成 1.0，把略劣和大劣都压成 0.0，丢掉 cutoff 局面的概率幅度。P9 的核心目标是补上“概率估值 + 浅层 chance-aware 搜索”，而不是继续扩大 P8 式 threat-only rerank。

## 2. 方案选择

### 方案 A：P9 概率估值 + chance-aware 轻量搜索（推荐）

先实现一个独立的 `zweistein_dp_win_prob()`，再把 rollout cutoff 从符号离散改为概率值，最后只对 root top-k 做一层精确对手骰子枚举。

优点：

- 保持 core 规则和 GUI/release 默认不变。
- 每一步都有独立候选、独立报告和门禁。
- 正好补 P3 的信息损失和 P8 的 threat-only 口径过窄问题。
- 第一层对手骰子只有 6 面，精确枚举比继续采样更可控。

缺点：

- DP 估值模型仍简化 capture，需要搜索层补偿。
- 需要新增概率表、编码测试和候选 wrapper，工程面比单个参数实验大。

### 方案 B：继续 P8 threat rerank / direct patch

只针对允许对手下一手直接胜利的局面做 top-k rerank 或防守 patch。

优点：

- 实现小，易解释。

缺点：

- P8 数据不支持：threat-reducing alternative 很少，低置信命中更少。
- 只处理直接一步败，不能系统处理吃子、推进、挡路、慢胜慢败。

### 方案 C：直接重启 MCTS / NN / PUCT

把 P4/P4.1 的 MCTS 或外部神经网络路线作为下一阶段主线。

优点：

- 长期上限可能更高。

缺点：

- 当前 MCTS candidate 已明显弱于默认 rollout。
- 神经网络/PUCT 需要训练、依赖和大量 rollout，不符合离线 GUI、赛前稳定、无新增依赖的约束。

结论：采用方案 A。P9 只做概率估值和浅层 chance-aware 候选，不默认启用；P10 以后再考虑 sampled deeper chance / Monte Carlo *-Minimax-lite。

## 3. 不可变边界

P9 禁止修改：

- `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`
- `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`
- `release/v1.0/default_params.json`
- `release/v1.0/config.json`
- `gui/opening_panel.py` 中 `balanced_v1` 默认布局行为
- `core/` 规则语义
- GUI/release 默认 AI、默认布局、默认 fallback 文案
- P5 已失败布局的晋升状态
- P8 threat rerank 结论
- MCTS 作为默认候选的状态

P9 允许新增：

- 独立 DP 概率估值模块。
- 显式 benchable AI kind。
- `RolloutAI.cutoff_eval` 的新枚举值，但不得改变旧枚举值语义。
- wrapper / rerank 模块，但 wrapper 必须在超时或缺 telemetry 时退回 base rollout 结果。
- 报告和测试。

任何默认 AI 或默认布局变更都必须另开 decision，并由用户明确批准。

## 4. 目标

1. 新增可测试的 Zweistein-DP 概率估值：
   - `zweistein_dp_win_prob(state, perspective) -> float`
   - `zweistein_dp_score(state, perspective) -> float`
2. 保留概率幅度，不再把 cutoff 叶子只压成胜/负/平。
3. 新增 `rollout_zweistein_dp_cutoff` candidate，只改变 cutoff evaluator，不改变默认 rollout 结构。
4. 新增 `rollout_exact_opp1_zdp` candidate：基于当前 release 默认 rollout 的 root top-k，枚举对手下一手骰子 1..6 和对手最优回应，用 ZDP 概率值做轻量重排。
5. 仅在 P9.1 或 P9.2 有正向 candidate 结果时，再考虑 P9.3 transposition table / move ordering。
6. 输出报告证明候选是否值得 promotion；不过门禁则归档为未晋升。

## 5. 非目标

- 不修改比赛 GUI 默认 AI。
- 不修改 release 默认参数。
- 不修改默认布局。
- 不修改 core 规则。
- 不继续实现 `rollout_threat_rerank`。
- 不重启 P4/P4.1 MCTS 作为当前主线。
- 不引入 OpenSpiel、Gymnasium、PyTorch、Polygames 或联网依赖。
- 不做神经网络训练。
- 不继续扩大 P5 opening search，除非 P9 产生更稳定 evaluator。
- 不做线性权重大规模离线调参。

## 6. P9.0 Zweistein-DP 概率估值

### 6.1 新增模块

新增：

```text
ai/zweistein_dp.py
tests/test_zweistein_dp.py
reports/p9_zweistein_dp_smoke_20260517.md
```

公共 API：

```python
def zweistein_dp_win_prob(state: GameState, perspective: Player) -> float:
    """Return a probability-like value in [0.0, 1.0] from perspective."""


def zweistein_dp_score(state: GameState, perspective: Player) -> float:
    """Return 2 * win_prob - 1 in [-1.0, 1.0]."""
```

内部 API 建议：

```python
MAX_DISTANCE = 4
DISTANCE_VECTOR_SIZE = 6
TABLE_STATES = 5 ** 6
TABLE_HORIZON = 20


def encode_distance_vector(distances: tuple[int, int, int, int, int, int]) -> int: ...
def decode_distance_index(index: int) -> tuple[int, int, int, int, int, int]: ...
def distance_vector_for(state: GameState, player: Player) -> tuple[int, int, int, int, int, int]: ...
```

### 6.2 距离向量口径

每方 6 个编号棋子映射为长度 6 的 Chebyshev 距离向量：

```text
entry[piece_id - 1] = chebyshev_distance(piece.position, target_corner(player))
```

约束：

- 距离取值为 `0..4`。
- 已死亡棋子编码为 `4`，表示在无 capture 的 DP race model 中不提供近期到角能力。
- 真实终局优先由 `state.get_winner()` 处理，因此“吃光获胜”和“到角获胜”不会依赖死亡棋子的距离编码。
- 红蓝镜像状态中，红视角概率应与蓝视角概率互补或近似互补；测试以终局和对称构造锁定方向。

这个口径是项目内 DP 估值模型，不改变 core 规则。它刻意承认 capture 被简化，后续通过 P9.2 的一层对手回应补偿。

### 6.3 DP 表语义

预计算两个小表：

```text
PDF_VAL[15625][20]
CDF_VAL[15625][20]
```

其中 `15625 = 5 ** 6`。每行代表一个距离向量。表按“单方自走回合”建模：

- 如果任意距离为 `0`，该方已经具备到角胜利状态，`CDF[t] = 1.0`。
- 否则，每个自走回合等概率掷出 1..6。
- 掷出某编号时，该编号对应距离若大于 0，则在简化 race model 中减少 1。
- `CDF[index][t]` 表示该方在 `t + 1` 个自走回合内至少一个距离降到 0 的概率。
- `PDF[index][t]` 表示首次在第 `t + 1` 个自走回合达成的概率。

有限 horizon 后仍未到角的残余概率在双方胜率合成时按 0.5 中性处理，避免把表外尾部错误归给任一方。

### 6.4 双方胜率合成

`zweistein_dp_win_prob(state, perspective)` 先处理真实终局：

```text
winner == perspective -> 1.0
winner == perspective.opponent -> 0.0
```

非终局时：

1. 计算 `own_vec` 与 `opp_vec`。
2. 查表得到 `own_pdf/own_cdf`、`opp_pdf/opp_cdf`。
3. 根据 `state.current_player` 处理先手 tempo：
   - 若 `state.current_player is perspective`，perspective 的第 k 次自走回合先于 opponent 的第 k 次自走回合。
   - 若 `state.current_player is perspective.opponent`，opponent 的第 k 次自走回合先于 perspective 的第 k 次自走回合。
4. 用“己方首次到角时，对手在其已有回合内尚未到角”的概率求和。
5. 表外残余按 0.5 加回：

```text
win_prob = resolved_win_prob + 0.5 * unresolved_prob
```

输出必须 clamp 到 `[0.0, 1.0]`。`zweistein_dp_score()` 只做 `2.0 * p - 1.0`。

### 6.5 测试要求

`tests/test_zweistein_dp.py` 至少覆盖：

- `encode_distance_vector()` 与 `decode_distance_index()` 互逆。
- 非法距离（小于 0、大于 4、长度不是 6）抛 `ValueError`。
- 表大小为 `5 ** 6` 行、每行 `20` 列。
- `CDF` 单调不下降，`PDF` 非负，单行概率不超过 1。
- 任意向量中存在 `0` 时，win CDF 为 1。
- 距离整体更近的向量概率不低于更远向量。
- 真实终局：perspective 已胜返回 1.0，对手已胜返回 0.0。
- 红蓝镜像局面下，双方概率方向正确。
- `zweistein_dp_score()` 与 `zweistein_dp_win_prob()` 一致。

P9.0 验收命令：

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein_dp.py"
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

报告：

```text
reports/p9_zweistein_dp_smoke_20260517.md
```

报告必须写明：

- DP 表尺寸。
- 构建耗时。
- 单次 `zweistein_dp_win_prob()` 粗略调用耗时。
- 测试命令和结果。
- GUI/release 默认未变。

## 7. P9.1 Rollout DP Cutoff Candidate

### 7.1 设计

新增 `RolloutAI.cutoff_eval` 枚举值：

```text
zweistein_dp
```

修改点：

```text
ai/rollout_ai.py
ai/match.py
scripts/bench_ai.py
```

`RolloutAI.__init__()` 接受：

```python
cutoff_eval in {"draw", "current", "zweistein", "zweistein_dp"}
```

`_cutoff_score()` 新增分支：

```python
if self.cutoff_eval == "zweistein_dp":
    return zweistein_dp_win_prob(state, perspective)
```

旧分支保持不变：

- `draw` 仍返回 0.5。
- `current` 仍调用 `evaluate()` 并离散为 1/0/0.5。
- `zweistein` 仍调用 `zweistein_lite_score()` 并离散为 1/0/0.5。

### 7.2 新增 kind

在 `ai/match.py::build_ai()` 新增：

```text
rollout_zweistein_dp_cutoff
```

初始参数复制当前 release 默认 rollout，只改：

```json
{
  "cutoff_eval": "zweistein_dp"
}
```

也就是说有效候选参数应为：

```json
{
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 750.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 32,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein_dp",
  "deadline_safety_ms": 30.0
}
```

`ai_version_signature()` 不需要新增字段；现有 `cutoff_eval` 会记录新值。

### 7.3 Bench profile

在 `scripts/bench_ai.py::CANDIDATE_PROFILES` 新增：

```python
"rollout_zweistein_dp_cutoff": {
    "candidate": {
        "opponent": "rollout",
        "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
        "starting_layout": "balanced_v1",
        "games_per_side": 100,
    },
    "promotion": {
        "opponent": "rollout",
        "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
        "starting_layout": "balanced_v1",
        "games_per_side": 400,
    },
}
```

重要口径：

- P9 candidate 必须对当前 release 默认 rollout 显式 kwargs。
- 不得把裸 `--opponent rollout` 当作当前 release 默认；裸 `build_ai("rollout")` 是代码默认参数，不等于 `release/v1.0/default_params.json`。
- 命令应依赖内置 profile 自动注入 `opponent_kwargs` 和 `balanced_v1`。

候选命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_zweistein_dp_cutoff `
  --stage candidate `
  --report-name p9_candidate_rollout_zweistein_dp_cutoff_20260517
```

promotion 命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_zweistein_dp_cutoff `
  --stage promotion `
  --report-name p9_promotion_rollout_zweistein_dp_cutoff_20260517
```

### 7.4 门禁

candidate：

```text
balanced_v1
candidate vs current release default rollout
双边 100+100
candidate_win_rate >= 55%
illegal_moves = 0
crashes = 0
timeouts = 0
average_step_time_ms <= 500ms
max_step_time_ms <= 5000ms
```

promotion：

```text
balanced_v1
candidate vs current release default rollout
双边 400+400
candidate_win_rate >= 55%
Wilson lower >= 52%
illegal_moves = 0
crashes = 0
timeouts = 0
average_step_time_ms <= 500ms
max_step_time_ms <= 5000ms
```

即使 promotion 通过，也只形成默认替换候选；不得在 P9 自动改 GUI/release。

## 8. P9.2 Exact Opponent Dice Top-k Rerank

### 8.1 设计目标

P8 threat rerank 只问“有没有更少直接败骰子的走法”。P9.2 改问：

```text
我走完以后，对手下一手骰子 1..6 各出现时，
对手按最优回应后，我方 ZDP 胜率期望是多少？
```

它不只处理一步直接败，也覆盖吃子、推进、挡路和慢胜慢败。它正好补 P9.0 DP race model 对 capture 的简化。

### 8.2 新增模块和 kind

新增：

```text
ai/chance_rerank.py
tests/test_chance_rerank.py
```

新增 kind：

```text
rollout_exact_opp1_zdp
```

候选初始参数：

```json
{
  "base_kind": "rollout",
  "base_kwargs": "RELEASE_DEFAULT_ROLLOUT_KWARGS",
  "top_k": 3,
  "exact_mix": 0.35,
  "min_time_remaining_ms": 20.0,
  "max_step_time_ms": 750.0
}
```

`max_step_time_ms` 是 wrapper 对外签名和 timeout telemetry 的上限。wrapper 内部先调用 base rollout；如果 base 已接近 deadline，则直接返回 base move。

### 8.3 评分公式

base rollout 运行后，从 `base.last_root_stats` 取 root score：

```text
rollout_score = root_stats.score
exact_opp1_value = exact_opp1_zdp_value(state, root_move, perspective)
mixed_score = 0.65 * rollout_score + 0.35 * exact_opp1_value
```

`exact_mix` 可作为参数：

```text
mixed_score = (1.0 - exact_mix) * rollout_score + exact_mix * exact_opp1_value
```

选择范围只限 root top-k。top-k 排序按：

```text
root score 降序、visits 降序、move 稳定键
```

若 `base.last_root_stats` 缺失、chosen move 不在 stats 中、top-k 为空、或剩余时间不足，返回 base move。

### 8.4 exact_opp1_zdp_value

对某个 root move：

```text
apply root_move
if perspective 已胜: return 1.0
if opponent 已胜: return 0.0

total = 0.0
for dice in 1..6:
    opp_moves = legal_moves(opponent, dice)
    if no opp_moves:
        total += 1.0
    else:
        opponent chooses move that minimizes zweistein_dp_win_prob(after_opp_move, perspective)
        total += min_value
return total / 6.0
```

实现要求：

- 使用 `GameState.deserialize(state.serialize(include_history=False))` 或 apply/undo，禁止修改调用方 state。
- 胜负必须通过 `state.get_winner()` 判定。
- 合法步必须通过 `state.legal_moves()` 生成。
- 不复制 core 规则逻辑。
- 对手没有合法步时，按 perspective 胜利计 1.0。

### 8.5 时间边界

wrapper 需要维护 outer deadline：

```text
outer_deadline = choose_move_start + max_step_time_ms
```

流程：

1. 调用 base rollout。
2. 若 base 返回 `None`，直接返回 `None`。
3. 若当前时间已超过 `outer_deadline - min_time_remaining_ms`，直接返回 base move。
4. 枚举 top-k，每个候选前检查 deadline。
5. 若枚举中途时间不足，返回当前已评分候选中的 mixed best；若没有已评分候选，返回 base move。

这个设计不让 exact rerank 破坏现场稳定性。候选如果因时间压力收益不足，bench 会自然失败或显示 telemetry 风险。

### 8.6 Telemetry

wrapper 建议暴露 `fire_counts`，使 `bench_ai.py` 现有聚合能统计：

```text
fire_exact_opp1_considered
fire_exact_opp1_applied
fire_exact_opp1_passthrough_no_stats
fire_exact_opp1_passthrough_no_time
fire_exact_opp1_passthrough_no_change
```

`ai_version_signature()` 若检测到 wrapper，应记录：

- wrapper name。
- base signature。
- `top_k`。
- `exact_mix`。
- `min_time_remaining_ms`。
- `max_step_time_ms`。

### 8.7 Bench profile

在 `scripts/bench_ai.py::CANDIDATE_PROFILES` 新增：

```python
"rollout_exact_opp1_zdp": {
    "candidate": {
        "opponent": "rollout",
        "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
        "starting_layout": "balanced_v1",
        "games_per_side": 100,
    },
    "promotion": {
        "opponent": "rollout",
        "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
        "starting_layout": "balanced_v1",
        "games_per_side": 400,
    },
}
```

候选命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_exact_opp1_zdp `
  --stage candidate `
  --report-name p9_candidate_rollout_exact_opp1_zdp_20260517
```

promotion 命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_exact_opp1_zdp `
  --stage promotion `
  --report-name p9_promotion_rollout_exact_opp1_zdp_20260517
```

### 8.8 测试要求

`tests/test_chance_rerank.py` 至少覆盖：

- base 返回 `None` 时 wrapper 返回 `None`。
- base stats 缺失时透传 base move。
- top-k 中 exact value 更高且 mixed score 反超时，wrapper 选择该 move。
- exact value 更高但 mixed score 未反超时，wrapper 不改变 base move。
- 对手某骰子无合法步时，该 dice 计 1.0。
- 对手存在直接胜利回应时，exact value 能降到 0.0 或接近 0.0。
- wrapper 返回的 move 必须属于当前 `state.legal_moves(state.current_player, dice)`。
- wrapper 不污染输入 state。
- signature 包含 base signature 与 rerank 参数。

## 9. P9.3 Transposition Table + Move Ordering（条件执行）

P9.3 不是独立晋升项。只有 P9.1 或 P9.2 candidate 至少接近正向，才继续做。

启动条件：

```text
P9.1 或 P9.2 candidate_win_rate >= 52%
illegal_moves = 0
crashes = 0
timeouts = 0
timing 未明显恶化
```

建议新增：

```text
ai/state_key.py
tests/test_state_key.py
```

`state_key` 只编码局面，不编码 history：

```python
def state_key(state: GameState) -> tuple:
    return (
        state.current_player.value,
        tuple(
            (
                player.value,
                piece_id,
                piece.alive,
                piece.position.row if piece.alive else -1,
                piece.position.col if piece.alive else -1,
            )
            for player in (Player.RED, Player.BLUE)
            for piece_id, piece in sorted(state.pieces[player].items())
        ),
    )
```

P9.3 可服务两个位置：

1. `ExactOpponentDiceRerankAI` 的 `exact_opp1_zdp_value()` 缓存。
2. 后续 `ExpectimaxAI` / `ExpectimaxV2` 的浅层 chance node 缓存。

TT key 建议：

```text
(
  state_key_without_history,
  current_player,
  perspective,
  node_type,
  dice_or_none,
  depth,
  evaluator_id
)
```

move ordering 建议：

```text
直接胜
阻止对手直接胜
吃对方子
ZDP 值高
opponent exact value 高
风险下降
稳定 move key
```

P9.3 验收：

- 单元测试证明缓存命中不改变结果。
- `ai_version_signature()` 记录 TT enabled / cache size。
- bench 报告显示 timing 未变差。
- 不因 P9.3 单独默认晋升。

## 10. 总体验收

P9.0 基础验收：

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein_dp.py"
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

P9.1/P9.2 候选验收：

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate <candidate> --stage candidate --report-name <report_name>
```

candidate gate：

```text
candidate vs current release default rollout
balanced_v1
双边 100+100
candidate_win_rate >= 55%
illegal_moves = 0
crashes = 0
timeouts = 0
average_step_time_ms <= 500ms
max_step_time_ms <= 5000ms
```

promotion gate：

```text
candidate vs current release default rollout
balanced_v1
双边 400+400
candidate_win_rate >= 55%
Wilson lower >= 52%
illegal_moves = 0
crashes = 0
timeouts = 0
average_step_time_ms <= 500ms
max_step_time_ms <= 5000ms
```

配置验收：

- `release/v1.0/default_params.json` 不变。
- GUI 默认推荐不变。
- 默认布局仍是 `balanced_v1`。
- `core/` 规则语义不变。
- `greedy_risk` 仍是 fallback。
- 所有 P9 候选只作为 benchable kind 和 reports 产物存在。

## 11. 执行顺序

```text
P9.0 实现 ai/zweistein_dp.py + 单元测试 + smoke 报告
  -> P9.1 实现 rollout_zweistein_dp_cutoff candidate
  -> 跑 P9.1 100+100 candidate
  -> 若 P9.1 明显失败，仍可继续 P9.2，因为 P9.2 使用 exact value 补 capture
  -> P9.2 实现 rollout_exact_opp1_zdp wrapper
  -> 跑 P9.2 100+100 candidate
  -> 若 P9.1 或 P9.2 candidate >= 52% 且 telemetry 稳定，考虑 P9.3 TT/move ordering
  -> 只有 candidate 过 55% 后才跑 400+400 promotion
  -> promotion 过门禁后只写 decision 候选，不自动替换默认
```

## 12. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| DP race model 简化 capture | 估值偏乐观或偏悲观 | P9.0 不接默认；P9.2 用一层对手回应补偿 capture |
| cutoff 概率值校准不准 | rollout 叶子偏置 | 先 candidate gate；不过门禁不晋升 |
| exact rerank 超时 | 现场步时恶化 | outer deadline + min time remaining；无时间时透传 base |
| bench baseline 误用裸 rollout | 结论无效 | `CANDIDATE_PROFILES` 必须注入 `RELEASE_DEFAULT_ROLLOUT_KWARGS` 与 `balanced_v1` |
| DP 表初始化成本 | GUI 首步卡顿 | 表小且常驻；P9.0 smoke 报告记录构建耗时 |
| TT key 不稳定 | 缓存污染结果 | 独立 `state_key` 测试；key 不含 history，只含规则相关局面 |

## 13. P10/P11 后续边界

P9 结束后才考虑：

- P10：MC *-Minimax-lite / sampled deeper chance。
- P11：用 P9 产出的稳定 evaluator 重跑 720 布局 opening search。
- P12：线性权重离线调参。
- P13：NN / PUCT / Polygames 类长期路线。

P10 起点应是：

```text
depth 1 精确枚举对手 6 个骰子
depth 2 只展开 root top-k
depth 3+ 才采样 chance outcomes
leaf 使用 zweistein_dp_win_prob
deadline 硬退
```

P11 起点应是：

```text
先用 zweistein_dp_win_prob(initial_state) 给 720 布局做便宜先验
每类 aggressive / balanced / defensive 取 top 候选
再做双边 common-dice paired games
只保留跨 3 seed pool 稳定的候选
```

这些不是 P9 交付物。

## 14. Spec 自检

- 已覆盖 P9.0 / P9.1 / P9.2 / P9.3。
- 已明确当前默认 AI、默认布局、release 配置不变。
- 已纠正 bench baseline：P9 candidate 必须对当前 release 默认 rollout 显式 kwargs，不使用裸 rollout 口径。
- 已定义 DP 表尺寸、距离向量编码、概率合成和有限 horizon 残余处理。
- 已明确 `rollout_zweistein_dp_cutoff` 只改变 cutoff evaluator。
- 已明确 `rollout_exact_opp1_zdp` 只对 root top-k 做对手 1 层骰子精确枚举，超时透传 base。
- 已把 TT/move ordering 放到条件执行项，避免过早复杂化。
- 已把 MCTS、NN、opening search 和参数大调参排除在 P9 范围外。
- 无占位项或未定义默认启用路径。
