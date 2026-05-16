# AI 下一阶段强化路线设计

日期：2026-05-15
范围：把 rollout 可解释性、候选 rollout 变体、Zweistein-lite evaluator、MCTS 对手节点修复和开局搜索拆成可逐步推进的任务组。

## 1. 背景

当前项目已经完成比赛现场主链路：规则、GUI、计时、棋谱、七盘制、自动保存恢复和 release/v1.0 均可用。默认 AI 已从 `greedy_risk` 晋升为旧 flat `rollout`。后续 adaptive rollout 增加了候选统计、低置信提示和候选复验，但直接对旧 rollout 的 800 局合并胜率为 59.00%，未达到 60% 默认晋升线，因此不进入 release 默认参数。

现在的问题不再是“程序能不能比赛”，而是“默认 AI 能不能进一步变强，并且每一步增强都有可解释数据”。截图里的红 5 自吃案例说明：单看推荐走法不够，必须能看到每个候选根走法的 visits、胜率、回报和置信情况。后续 AI 强化必须遵循 harness-first：小样本筛选、通过门禁后再扩大样本，不能因单局主观感觉改默认。

## 2. 当前事实快照

已经具备：

- `RolloutAI.last_diagnostics`：兼容性记录候选 move 的 visits / score / winrate / cutoffs / avg。
- `RolloutAI.last_root_stats`：canonical root stats 记录候选 move 的 visits / wins / losses / draws / score / winrate / avg / low_confidence；`last_diagnostics` 保持兼容别名。
- GUI 右侧推荐区：显示候选 rollout 明细，并能标记“置信：低”。
- `scripts/rollout_stability.py`：固定局面重复推荐稳定性审计。
- `scripts/quick_bench.py --red-kwargs/--blue-kwargs`：可以用 JSON kwargs 评测参数候选。
- `RolloutAI.deadline_safety_ms`：默认 `0.0`；P2.5 candidate profile 可显式传 `30.0`，让内部 playout deadline 早于外部 `max_step_time_ms`。
- adaptive rollout 候选参数（显式传参使用，不是 release 默认）：

```json
{
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 500.0,
  "epsilon": 0.15,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 128,
  "low_confidence_margin": 0.08
}
```

还缺：

- 可注册到 `build_ai()` 和 `bench_ai.py` profile 的 rollout 候选 kind。
- 截断估值 evaluator，当前 rollout 遇到未终局仍把结果当 `None -> 0.5`，方差偏高。
- Zweistein-lite 估值函数。
- MCTS opponent node 的方向性小局面回归测试。
- AI 稳定后再做开局搜索。

## 3. 目标

1. 让 rollout 推荐可解释：每个候选根走法都能显示样本数、胜/负/截断、score、winrate 和置信状态。
2. 把 rollout 参数和策略变体注册为可 bench 的候选，而不是临时传参。
3. 实现一个可测、可解释的 Zweistein-lite evaluator，先服务 rollout 截断，再服务 greedy / expectimax / MCTS leaf。
4. 修正或验证 MCTS 在对手节点是否按对手最优响应处理。
5. 等 AI 策略稳定后再做开局搜索，避免用旧 AI 搜出很快失效的布局。

## 4. 非目标

- 不引入神经网络训练。
- 不引入 OpenSpiel、Gymnasium、Stable-Baselines3、PyTorch 等现场不可控依赖。
- 不改 core 规则语义。
- 不重写 GUI。
- 不把单个截图局面作为默认 AI 晋升依据。
- 不在没有通过默认晋升门禁的情况下替换 release 默认 AI、默认参数或默认布局。

## 5. 方案选择

### 方案 A：分阶段候选流水线（推荐）

先收敛 rollout 可观测性，再做 3 个 rollout 候选，小样本筛掉明显不行的，再实现 Zweistein-lite，最后修 MCTS 和做开局搜索。

优点：

- 每一步可独立验证、可回滚。
- 与现有 `bench_ai.py`、`quick_bench.py`、reports 流水线一致。
- 不会把多个变量混在一起导致无法归因。

缺点：

- 节奏比“一次性重写 AI”慢。

### 方案 B：直接做完整强 AI 组合

一次性实现 risk-aware playout + cutoff evaluator + Zweistein + MCTS 修复。

优点：

- 理论上最快接近强 AI。

缺点：

- 无法判断收益来源。
- 一旦失败，调试面过大。
- 赛前风险高，不符合当前封版纪律。

### 方案 C：先做开局搜索

先枚举或采样 720 开局布局，用当前 AI 搜候选。

优点：

- 不改 AI 代码，工程风险小。

缺点：

- 当前 AI 策略还在变化，用旧策略搜出的布局可能被新策略推翻。
- 容易产生“布局过拟合当前 AI”的假收益。

结论：采用方案 A。

## 6. 晋升门禁

### rollout / evaluator / MCTS 候选门禁

小样本筛选：

```text
candidate vs rollout 双边各 100 局
candidate_win_rate >= 55%
illegal_moves = 0
crashes = 0
基于 quick_bench.py / bench_ai.py 聚合的真实 timeouts = 0
average_step_time_ms <= 500
max_step_time_ms <= 5000
报告写入 reports/
```

扩大样本：

```text
candidate vs rollout 双边各 400 局
candidate_win_rate >= 55%
candidate_win_ci_lower >= 52%
illegal_moves = 0
crashes = 0
基于 quick_bench.py / bench_ai.py 聚合的真实 timeouts = 0
average_step_time_ms <= 500
max_step_time_ms <= 5000
报告写入 reports/
```

默认晋升：

```text
candidate vs current default 双边合并至少 800 局
合并胜率 >= 60%
Wilson 95% lower >= 52%
0 illegal / 0 crash / 真实 timeout telemetry 为 0
release/v1.0/default_params.json 或后续 release 版本同步
reports/ai_promotion_decision.md 更新
```

### 开局搜索门禁

```text
AI 策略固定后再跑
candidate layout vs current default layout 双边合并至少 400 局
胜率 >= 55%
Wilson 95% lower >= 50%
至少 3 个 seed 池复验
保留均衡 / 速攻 / 防守候选，不声称最优
```

## 7. 任务组 P1：Rollout 根节点诊断收敛

状态：已完成（2026-05-15）。

目标：解释怪棋，不先改棋力。

设计：

- 新增 canonical dataclass：`RootMoveStats`。
- `RolloutAI.last_root_stats: list[RootMoveStats]` 作为正式诊断接口。
- 现有 `last_diagnostics` 保留一段时间作为兼容别名或派生视图。
- GUI 优先读取 `last_root_stats`，若不存在再 fallback 到 `last_diagnostics`。

建议字段：

```python
@dataclass(frozen=True)
class RootMoveStats:
    move: Move
    visits: int
    wins: float
    losses: float
    draws: float
    score: float
    winrate: float
    avg: float
    low_confidence: bool = False
```

score 语义：

```text
score = (wins + 0.5 * draws) / visits
winrate = wins / visits
avg = 2 * score - 1
losses = visits - wins - draws
```

GUI 显示：

```text
红方 5: (2,1) -> (3,1) 吃子
visits=128, score=0.42, wins=51, losses=70, draws=7
```

测试：

- `choose_move()` 不污染输入 `state`。
- 有合法走法时，`len(last_root_stats) == len(legal_moves)`。
- 每个 stats 的 move 与合法走法一一对应。
- `visits == wins + losses + draws`。
- `score` / `winrate` / `avg` 公式正确。
- 无合法走法时返回 `None` 且 stats 为空。

验收：

- GUI 能解释截图局面每个候选的根统计。
- 不改变默认 AI 参数。
- `pytest`、`smoke_test.py` 通过。

完成记录：

- 新增 canonical `RootMoveStats` 与 `RolloutAI.last_root_stats`。
- `last_diagnostics` 保持兼容别名。
- GUI 优先读取 `last_root_stats`，候选明细显示 visits / score / winrate / wins / losses / draws / avg / 低置信标记。
- 默认 `rollout` 参数、release 默认参数和 core 规则均未变更。
- 验证：`scripts/smoke_test.py` 正常退出；全量 `pytest` 为 `496 passed in 11.29s`。

## 8. 任务组 P2：三个 rollout 候选小样本筛选

状态：已完成实现与 candidate 小样本（2026-05-15）；三者均未过门禁，不晋升默认。

目标：把 playout policy、截断估值和 rollout 数量变成可 bench 的候选。

### P2-A：`rollout_32`

配置：

```text
rollouts_per_move = 32
max_rollout_turns = 80
max_step_time_ms = 750
epsilon = 0.15
```

意图：先只提高根采样量，看稳定性和耗时是否可接受。

### P2-B：`rollout_risk_playout`

配置：

```text
rollouts_per_move = 32
max_rollout_turns = 80
max_step_time_ms = 750
epsilon = 0.10
playout_policy = greedy_risk
```

意图：降低随机 playout 噪声，让模拟更接近合理对弈。

### P2-C：`rollout_cutoff_eval`

配置：

```text
rollouts_per_move = 32
max_rollout_turns = 80
max_step_time_ms = 750
epsilon = 0.10
playout_policy = greedy_risk
cutoff_eval = current evaluator
```

意图：未终局时不再全部记作 0.5，而是用 evaluator 估计叶子价值，降低截断噪声。

实现边界：

- 新增 build_ai kind：
  - `rollout_32`
  - `rollout_risk_playout`
  - `rollout_cutoff_eval`
- 或者先用 `rollout` + kwargs 实现，但最终必须给 `bench_ai.py` profile 一个稳定 kind。
- `ai_version_signature()` 必须记录 playout policy、cutoff eval、rollout 参数。
- `scripts/bench_ai.py` 的 `CANDIDATE_PROFILES` 增加三个 candidate 默认：

```text
candidate stage: opponent=rollout, games_per_side=100
promotion stage: opponent=rollout, games_per_side=400
```

命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_32 --opponent rollout --games-per-side 100 --stage candidate
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_risk_playout --opponent rollout --games-per-side 100 --stage candidate
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_cutoff_eval --opponent rollout --games-per-side 100 --stage candidate
```

过小样本后扩大：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate <候选> --opponent rollout --games-per-side 400 --stage promotion
```

验收：

- 每个候选都有 JSON + MD 报告。
- 候选不过门禁时不接 GUI 默认。
- 至少保留一个最强候选进入 P3 组合验证。

完成记录：

| 候选 | 合并局数 | 胜率 | timeouts | 门禁 |
|---|---:|---:|---:|---|
| `rollout_32` | 200 | 54.5% | 4 | 失败：胜率低于 55%，timeouts > 0 |
| `rollout_risk_playout` | 200 | 57.0% | 10 | 失败：timeouts > 0 |
| `rollout_cutoff_eval` | 200 | 57.5% | 11 | 失败：timeouts > 0 |

报告：

- `reports/p2_candidate_rollout_32_20260515.json` / `.md`
- `reports/p2_candidate_rollout_risk_playout_20260515.json` / `.md`
- `reports/p2_candidate_rollout_cutoff_eval_20260515.json` / `.md`

结论：

- `rollout_risk_playout` 与 `rollout_cutoff_eval` 胜率有正向信号，但真实 timeout 门禁失败，不能进入默认 AI 或 promotion。
- 后续若继续 P2 分支，应优先降低 step timeout（例如减少 rollout 数、降低 cutoff 深度或优化 playout），再重跑 candidate。
- 默认 `rollout`、release 默认参数和 GUI 默认推荐均保持不变。

## 9. 任务组 P2.5：Rollout deadline safety

状态：已完成（2026-05-15）。

目标：只修复 P2 正向候选的边界超时，不直接进入大规模 P3，不改 GUI/release 默认。

实现：

- `RolloutAI.__init__()` 新增 `deadline_safety_ms: float = 0.0`，默认不改变旧 `rollout` 行为。
- `choose_move()` 内部采样 deadline 使用 `max_step_time_ms - deadline_safety_ms`，并用 `max(0.0, ...)` 防御负预算。
- `ai_version_signature()` 记录 `deadline_safety_ms`。
- `scripts/bench_ai.py` 支持 profile-level `candidate_kwargs`，且只给 `rollout_risk_playout` / `rollout_cutoff_eval` 的 candidate/promotion profile 传 `deadline_safety_ms=30.0`。
- 未复验 `rollout_32`。

复验：

| 候选 | 合并局数 | 胜率 | timeouts | 结论 |
|---|---:|---:|---:|---|
| `rollout_risk_playout` | 200 | 58.5% | 1 | 未过总门禁 |
| `rollout_cutoff_eval` | 200 | 57.0% | 0 | **P2.5 survives** |

报告：

- `reports/p25_candidate_rollout_risk_playout_20260515.json` / `.md`
- `reports/p25_candidate_rollout_cutoff_eval_20260515.json` / `.md`

结论：

- `rollout_cutoff_eval` 是 P2.5 survivor，可作为 P3 组合验证的候选基础。
- 这不是默认晋升；默认 `rollout`、GUI 默认推荐和 `release/v1.0/default_params.json` 均保持不变。
- P2.5 结束后进入 P3 Zweistein-lite。

## 10. 任务组 P3：Zweistein-lite evaluator

状态：已完成基础实现与 candidate 小样本（2026-05-15）；未晋升默认。

目标：实现一个本项目内可测试、可解释的估值函数，不追求论文 100% 复刻。

新增 API：

```python
def zweistein_lite_score(state: GameState, perspective: Player) -> float:
    ...
```

建议特征：

```text
terminal_score:
  perspective 已胜：+1_000_000
  opponent 已胜：-1_000_000

progress_score:
  己方棋子越接近目标角越高
  对方棋子越接近其目标角越低

material_score:
  己方活子数越多越高
  对方活子数越少越高

mobility_score:
  己方未来骰子平均可走数越多越高
  对方未来骰子平均可走数越少越高

risk_score:
  避免对手下一步直接到角或吃光
```

测试：

- 越接近目标角分越高。
- 己方已到角直接极高。
- 对方已到角直接极低。
- 红蓝镜像局面分数相反。
- 死子数量影响合理。
- 空局面 / 单子局面不崩溃。

派生 AI：

- `greedy_zweistein`
- `rollout_zweistein_cutoff`
- `expectimax_zweistein_d1`

预期：

最可能过门禁的是：

```text
rollout + Zweistein cutoff + risk-aware playout
```

而不是裸 expectimax。

验收：

- Zweistein-lite 单元测试通过。
- 三个派生 AI 能构造、能返回合法走法、不污染 state。
- 至少 `rollout_zweistein_cutoff` 进入 P2 同等 bench 流程。

完成记录：

- 新增 `ai/zweistein.py`，提供 `zweistein_lite_score(state, perspective)`。
- 特征覆盖终局、推进距离、子力、期望机动性、距离加权被吃风险、直接到角风险。
- 新增 `ZweisteinGreedyAI`，注册 `greedy_zweistein`。
- `RolloutAI.cutoff_eval` 支持 `zweistein`，注册 `rollout_zweistein_cutoff`。
- `ExpectimaxAI` 支持 `leaf_evaluator=current|zweistein`，注册 `expectimax_zweistein_d1`。
- `ai_version_signature()` 记录 `leaf_evaluator`。
- `scripts/bench_ai.py` 为 `rollout_zweistein_cutoff` candidate/promotion profile 注入 `deadline_safety_ms=30.0`。

P3 candidate 结果：

| 候选 | 合并局数 | 胜率 | timeouts | 门禁 |
|---|---:|---:|---:|---|
| `rollout_zweistein_cutoff` | 200 | 58.0% | 0 | 通过 candidate |

报告：

- `reports/p3_candidate_rollout_zweistein_cutoff_20260515.json` / `.md`

结论：

- `rollout_zweistein_cutoff` 可进入后续 promotion 400+400 复验。
- 未跑 promotion，不能替换默认 AI。
- 默认 `rollout`、GUI 默认推荐和 `release/v1.0/default_params.json` 均保持不变。

## 11. 任务组 P4：MCTS opponent node 修复

目标：先证明对手节点方向正确，再考虑大样本。

小局面测试设计：

```text
我方某步后，对手有两个合法走法：
A：不防守，让我方下一手直接胜
B：防守，阻止我方下一手直接胜

正确 MCTS / Minimax：应假设对手会选 B。
错误方向：若把对手当成会选 A，则 MCTS 会高估我方当前步。
```

任务：

- 构造一个 deterministic 小局面，固定骰子或控制随机流。
- 给 MCTS / Minimax opponent node 写回归测试。
- 明确 opponent node 回传值应从 perspective 视角取最小或选择最坏响应。
- 修复后只跑 smoke/candidate，不直接大样本。

验收：

- 小局面测试能在修复前失败、修复后通过。
- `mcts_eval_v1` 不返回非法走法。
- 先跑：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate mcts_eval_v1 --stage smoke
```

- smoke 通过后才考虑 candidate。

## 12. 任务组 P5：开局搜索

状态：P5.0 entry guard、P5.1 strata/seed-pool smoke 与 P5.2 small-scale gate 已完成（2026-05-16）；未晋升布局。

目标：等 AI 策略稳定后再搜开局，避免旧策略布局失效。

前置条件：

- P2/P3/P4 至少确定一个 working default candidate。
- 该 candidate 通过 400+400 或更高门禁。
- release 默认 AI 参数冻结。

搜索策略：

- 枚举或采样己方 720 种布局。
- 对手布局池包括：
  - 当前 default
  - balanced
  - aggressive
  - defensive
  - mirror / anti-mirror
- 小样本训练筛选，验证集扩大复验。

产物：

- `reports/opening_search_after_ai_stabilized.md`
- 若过门禁，新增或更新 `ai/opening_layouts.py` 预设：
  - balanced candidate
  - aggressive candidate
  - defensive candidate

验收：

- 不修改 core。
- 不把单一布局称为最优。
- GUI 默认布局变更必须有独立报告。

P5.0 完成记录：

- `scripts/search_openings.py` 主评测入口不再使用旧 `greedy_risk` self-play。
- 脚本读取 `release/v1.0/default_params.json`，校验 `ai == "rollout"`，剔除 metadata 后把当前 release 默认 rollout kwargs 传给红蓝双方 AI。
- stats 聚合真实 `timeouts`，报告中记录 `ai_kind`、`ai_kwargs_source` 和完整 kwargs。
- 小样本 smoke：`sample_size=5`、train/validation 每 opponent 各 2 局，validation top 两个红方布局分别为 5/8 和 6/8，0 illegal/crash/timeout。
- 报告：`reports/p5_opening_entry_guard_20260516.md` / `.json`。
- 结论：entry guard 通过；样本不足以晋升布局，GUI/release 默认布局不变。

P5.1 完成记录：

- `scripts/search_openings.py` 支持 `candidate_mode=sample|stratified`；stratified 模式按 aggressive / balanced / defensive 三类各取 `per_style` 个候选。
- 支持 `seed_pool` 聚合跨 seed stats，并在 Markdown / JSON 报告中记录 `style`、`seed_count`、`seeds`、`candidate_count`、`train_rows`、`decision` 和真实 `timeouts`。
- 小样本 smoke：`--candidate-mode stratified --per-style 1 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027`。三类各 1 个候选，validation 结果 aggressive 1/8、defensive 4/8、balanced 2/8，0 illegal/crash/timeout。
- 报告：`reports/p51_opening_strata_seed_smoke_20260516.md` / `.json`。
- 结论：分层和 seed 池流程通过；样本不足以晋升布局，GUI/release 默认布局不变。

P5.2 完成记录：

- 复用 P5.1 分层与 seed pool 流程，只扩大到 smoke 级别：`--candidate-mode stratified --per-style 2 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027`。
- 训练集共 6 个候选，结果依次为 5/8、4/8、3/8、3/8、3/8、2/8；validation top3 为 3/8、4/8、4/8。
- 全部 train / validation stats 均为 `illegal_moves=0`、`crashes=0`、`timeouts=0`，当前 release 默认 rollout kwargs 已记录在报告中。
- 报告：`reports/p52_opening_small_scale_gate_20260516.md` / `.json`。
- 结论：P5.2 仅证明小规模扩大样本门禁可运行；样本仍远小于布局晋升门禁，GUI/release 默认布局不变。

## 13. 推荐执行顺序

```text
P1 Rollout 根节点诊断收敛（已完成）
  -> P2 三个 rollout 候选小样本筛选（已完成，未晋升）
  -> P2.5 Rollout deadline safety（已完成，rollout_cutoff_eval survives）
  -> P3 Zweistein-lite evaluator（已完成 candidate，rollout_zweistein_cutoff 通过）
  -> P3 promotion（可选：rollout_zweistein_cutoff 400+400）
  -> P4 MCTS opponent node 修复
  -> P5.0 开局搜索 entry guard（已完成）
  -> P5.1 开局候选分层与 seed 池 smoke（已完成）
  -> P5.2 小规模扩大样本门禁（已完成，未晋升）
```

优先级：

1. P1 必做，因为它直接解释怪棋。
2. P2 必做，因为它把 rollout 变化变成可 bench 候选。
3. P2.5 只处理 deadline safety，避免把边界 timeout 问题拖入大规模 P3。
4. P3 已完成 candidate；若目标是默认晋升，先跑 400+400 promotion，否则进入 P4。
5. P4 在 P3 后做，避免在弱 leaf eval 上过度优化树搜索。
6. P5 最后做，因为开局布局依赖最终 AI 风格。

## 14. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| rollout 采样变慢 | 现场每步等待变长 | 保留 `max_step_time_ms` 和 fallback；门禁监控 avg/max step |
| cutoff evaluator 偏置 | 模拟未终局时系统性误判 | 先单元测试再 bench；不过门禁不晋升 |
| Zweistein-lite 过拟合内部对手 | 对外部程序收益不稳定 | 使用 `rollout`、`greedy_risk`、MCTS 候选多对手评测 |
| MCTS bug 被大样本掩盖 | 浪费评测时间 | 先小局面方向性测试 |
| 开局搜索过拟合旧 AI | 换策略后布局失效 | AI 默认冻结后再搜 |

## 15. 下一步产物

本 spec 通过后，按任务组分别写 implementation plan：

1. `docs/superpowers/plans/2026-05-15-rollout-root-stats-plan.md`
2. `docs/superpowers/plans/2026-05-15-rollout-candidates-plan.md`
3. `docs/superpowers/plans/2026-05-15-rollout-deadline-safety-plan.md`
4. `docs/superpowers/plans/2026-05-15-zweistein-lite-plan.md`
5. `docs/superpowers/plans/2026-05-15-mcts-opponent-node-plan.md`
6. `docs/superpowers/plans/2026-05-15-opening-search-after-ai-plan.md`

每个 plan 独立执行、独立测试、独立报告；不把五个方向揉成一次大改。

## 16. Spec 自检

- 无规则语义变更。
- 无外部依赖。
- 每个任务组都有明确目标、边界、测试和验收。
- P1/P2/P3/P4/P5 有顺序依赖，避免开局搜索过早。
- 默认 AI / release 变更必须经过报告门禁。
