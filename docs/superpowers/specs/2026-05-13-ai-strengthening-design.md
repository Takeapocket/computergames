# AI 能力提升设计

日期：2026-05-13
范围：封版后 AI 强化路线，参考 OpenSpiel / ewn-gym 思路，但保持本项目离线、可解释、可回滚。

## 1. 背景

当前 GUI、计时、棋谱、自动保存恢复、七盘制流程和 release/v1.0 已完成。默认 AI 仍为
`greedy_risk`，它在 R-0 合规规则下相对 `greedy` 的合并胜率为 55.75%。这个结果只说明
它强于本项目的朴素贪心 baseline，不足以证明比赛强度充分。

下一阶段目标从“现场稳定封版”切换为“在不破坏稳定版本的前提下提高 AI 胜率”。默认路径仍必须
可离线运行，不能引入现场不可控依赖。所有 AI 候选都必须通过本地 harness 数据晋升，不能因单局或
小样本结果替换默认 AI。

## 2. 外部参考边界

### OpenSpiel

参考来源：https://github.com/google-deepmind/open_spiel

可借鉴：

- chance node 建模：骰子是随机节点，走子是决策节点。
- 统一动作接口：`LegalActions` / `ApplyAction` / `UndoAction` 的思路与本项目 `GameState`
  已有边界一致。
- 初始布局搜索：双方出发区 6! = 720 种排列，适合做开局候选搜索。

不可采用：

- 不引入 OpenSpiel 依赖。
- 不照搬 OpenSpiel 规则实现；规则真值仍是 `core/` 和 `docs/RULE_ASSUMPTIONS.md`。
- 不因为外部实现差异修改本项目骰子映射、吃本方子或胜负语义。

### ewn-gym / eopXD

参考来源：https://eopxd.com/2020/08/25/einstein-wurfelt-nicht-agent/

可借鉴：

- baseline agent 之间可能存在相克关系，单一对手胜率不能代表综合强度。
- Monte Carlo 搜索需要额外监控树形、样本回报、深度和回传值，否则很难定位错误。
- 终局模式有实际价值，尤其是棋子少、直接到角或吃光路径明确时。
- 游戏长度、敌方剩余棋子数、自杀步/自吃步都可能影响评估。

不可采用：

- 该资料描述的是规则变体，不能作为本项目规则真值。
- 不引入 Gym / Gymnasium / 强化学习框架。
- 不优先深度学习或训练式策略网络。

## 3. 设计目标

1. 提高默认参赛 AI 的可证明强度。
2. 保持 GUI 和比赛流程稳定，AI 候选失败时可立即回退到 `greedy_risk`。
3. 让每次 AI 改动都有报告、seed、局数、胜率、置信区间、非法走法、崩溃、超时和耗时数据。
4. 先做低风险高收益项：开局搜索、参数搜索、轻量 rollout；再做 Expectimax 修复。
5. 保持规则逻辑只在 `core/`，AI 只调用 core API。

## 4. 非目标

- 不做神经网络训练。
- 不引入 OpenSpiel、Gymnasium、Stable-Baselines3、PyTorch 等新依赖。
- 不重写 GUI 或比赛记录格式。
- 不用外部仓库规则替换本项目规则。
- 不在没有 harness 报告的情况下替换 GUI 默认 AI。

## 5. 总体路线

```text
A0 诊断与评测基线
  -> A1 开局搜索
  -> A2 参数与 evaluator 小步优化
  -> A3 轻量 RolloutAI
  -> A4 ExpectimaxV2 修复
  -> A5 候选组合验证与默认晋升
```

推荐优先级：

1. A0 + A1：成本最低，风险小，可能快速提升胜率。
2. A2：沿用现有 `GreedyAI` / `evaluator`，可解释、易回滚。
3. A3：使用有限 rollout 弥补一层 evaluator 的短视问题，但必须严格限时。
4. A4：现有 Expectimax 已实测弱于 `greedy_risk`，只在前面完成后再修。

## 6. 晋升门禁

替换 GUI 默认 AI 或 release 默认参数前，候选必须满足：

```text
candidate vs greedy_risk 双边合并胜率 >= 60%
Wilson 95% CI 下界 >= 52%
每个方向至少 400 局，合并至少 800 局；若时间不足，最小可接受为双边各 200 局
illegal_moves = 0
crashes = 0
timeouts = 0
avg_step_time_ms < 1000
max_step_time_ms < 5000
报告写入 reports/
```

开局布局候选的门槛略低，但不能直接等同于 AI 晋升：

```text
candidate layout vs current default layout 双边合并胜率 >= 55%
Wilson 95% CI 下界 >= 50%
至少 3 个不同 seed 池复验
保留均衡 / 速攻 / 防守三类候选，不声称“最优布局”
```

组合晋升规则：

- AI 候选和开局候选必须先分别过门禁。
- 分别过门禁后再做组合验证，避免无法归因。
- 组合验证未过时，不合并为默认。

## 7. A0：诊断与评测基线

目标：先搞清 `greedy_risk` 弱在哪里，再决定优化点。

任务：

- 扩展 `scripts/tournament.py` 或新增诊断脚本，输出 pairwise matrix。
- 固定 seed 池，至少覆盖 `random`、`greedy`、`greedy_risk`、`expectimax`。
- 对失败局采样保存 replay，按失败原因分类：
  - 被直接到角。
  - 被吃光。
  - 终局走法保守。
  - 自吃/自堵导致机动性下降。
  - 选择了短期吃子但长期输角。
- 输出 `reports/ai_diagnostics.md`。

验收：

- 不修改默认 AI。
- 有一份诊断报告能解释当前 baseline 的主要失误模式。
- `pytest`、`smoke_test.py`、关键 bench 通过。

## 8. A1：开局搜索

目标：利用 720 布局空间寻找稳定候选，提高不改搜索算法时的胜率。

设计：

- 复用 `scripts/search_openings.py`。
- 先采样或枚举己方 720 布局，对手布局使用当前默认、mirror、balanced、aggressive、defensive。
- 训练集小样本筛选，验证集扩大样本复验。
- 输出候选时记录布局 id、棋子坐标、对手池、seed、胜率、CI、耗时。

产物：

- `reports/opening_search_v2.md`
- 过门禁后更新 `ai/opening_layouts.py` 的 `PRESETS`
- 过门禁后更新 `release/v1.0/default_params.json` 或另建 `release/v1.1/`

约束：

- 不在搜索脚本中复制规则。
- 不把单一布局称为最优。
- 默认 GUI 布局变更必须单独验证。

## 9. A2：参数与 evaluator 小步优化

目标：在现有贪心框架内调整 evaluator，先拿可解释收益。

候选方向：

- 终局优先：直接到角、阻止对手一步到角、吃光路径。
- 材料价值：敌我剩余棋子数、关键编号存活价值。
- 机动性：合法步数量、下一骰可走概率。
- 自吃建模：只奖励能提高胜率或避免更坏局面的自吃，不鼓励无意义自残。
- 风险项语义：区分“对手下一手威胁我方”和“我方下一手行动收益”。

实现原则：

- 每次只改少量参数或一个评估项。
- 每个候选有独立 kind 或参数签名，不覆盖 `greedy_risk`。
- 先小样本筛选，再按晋升门禁复验。

产物：

- `reports/param_sweep_v2.md`
- 必要时新增 evaluator 单元测试。

## 10. A3：轻量 RolloutAI

目标：用有限模拟弥补一层评估的短视问题，重点处理随机骰子和中后盘。

设计：

- 新增 `ai/rollout_ai.py`，注册为 `rollout`，默认不接 GUI。
- 对当前骰子的每个合法走法：
  1. apply 候选走法。
  2. 从该局面开始做 N 次模拟。
  3. 模拟过程中骰子由 seed 派生 RNG 生成。
  4. rollout policy 使用 `greedy_risk`、轻随机或混合策略。
  5. 按胜率或平均回报选最高候选。
- 加全局 `max_step_time_ms`，超时立即 fallback 到 `greedy_risk`。
- 记录每步模拟次数、平均深度、fallback 次数。

默认参数建议：

```text
rollouts_per_move = 16 或 32
max_rollout_turns = 80
max_step_time_ms = 500
policy = greedy_risk_epsilon
epsilon = 0.15
```

测试：

- seed 固定时选择可复现。
- 超时时 fallback 可用。
- 不返回非法走法。
- 与 `greedy_risk` 对局无 crash / timeout。

风险：

- rollout 很容易被随机噪声误导，所以必须双边大样本。
- 如果耗时不可控，不进入默认路径。

## 11. A4：ExpectimaxV2

目标：修复现有 Expectimax 与 evaluator risk 语义错位，而不是盲目加深。

实验顺序：

1. 裸 Expectimax：关闭 `expected_risk_weight` 和 `expected_win_risk_weight`，对比裸 greedy。
2. leaf-only eval：搜索内部只展开规则和骰子，叶子使用简化 evaluator。
3. turn-aware risk：风险函数显式接收下一行动方。
4. move ordering：直接胜利、阻止直接胜利、吃子、推进关键子优先。
5. transposition cache：缓存局面、深度、行动方、骰子。
6. depth=2：只在 depth=1 正收益且耗时稳定后尝试。

约束：

- `ExpectimaxAI(depth=1)` 当前 45.0% 的失败结论保留。
- 新实现注册为 `expectimax_v2`，不覆盖旧实验入口。
- 未过晋升门禁时不接 GUI 默认。

## 12. 数据流与模块边界

```text
core/GameState
  -> ai/* choose_move(state, dice)
  -> ai/match.py play_one_game / play_many
  -> scripts/quick_bench.py / tournament.py / param_sweep.py / search_openings.py
  -> reports/*.md + optional slim JSON
  -> ai_promotion_decision.md
  -> release config / GUI default
```

边界：

- `core/` 不依赖 AI。
- `ai/` 不修改规则，只调用 `legal_moves`、`apply_move`、`undo_move`。
- `scripts/` 负责实验编排，不写比赛规则。
- `gui/` 只读取默认 AI kind 和展示推荐，不包含评估逻辑。

## 13. 验证策略

每个阶段至少运行：

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

AI 候选运行：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red <candidate> --blue greedy_risk --games 400 --seed <seed>
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue <candidate> --games 400 --seed <seed>
```

综合验证：

```powershell
& ".venv/Scripts/python.exe" "scripts/tournament.py" --ais random greedy greedy_risk <candidate> --games 200 --seed <seed>
```

报告必须包含：

- 命令。
- git SHA。
- 是否 dirty。
- seed 和 games。
- AI 参数签名。
- 布局。
- 胜率和 Wilson CI。
- illegal / crash / timeout。
- avg / max step time。
- 是否晋升。

## 14. 默认策略

默认 AI 保持 `greedy_risk`，直到候选完整通过门禁。

如果 A1 只有开局候选通过：

- GUI 默认 AI 不变。
- 新布局作为 preset 加入，默认布局是否替换需单独验证。

如果 A2/A3/A4 有 AI 候选通过：

- 先新增 kind 和 release config。
- GUI 推荐 AI 可切换，但默认只在最终报告通过后改。
- 保留一键回退到 `greedy_risk` 的路径。

## 15. 推荐实施顺序

1. 写 `reports/ai_diagnostics.md`：确认 baseline 失误类型。
2. 跑 A1 开局搜索：先拿低风险收益。
3. 跑 A2 参数搜索：只改 evaluator 候选，不动默认。
4. 实现 A3 RolloutAI：严格限时和 fallback。
5. 只有当前三项收益不足时，进入 A4 ExpectimaxV2。
6. 候选通过门禁后，再更新默认配置和 release 文档。

## 16. 退出条件

若连续两类候选在双边 400+ 局验证中均未超过 `greedy_risk` 55%，停止继续调参，转为：

- 保存当前最佳候选报告。
- 复盘失败 replay。
- 优先做终局 solver 或更强 evaluator，而不是继续随机搜索参数。

若任一候选出现非法走法、崩溃、超时或 max step time 超预算，直接禁止晋升。

