# 爱恩斯坦棋参赛程序阶段目标文档

更新时间：2026-05-09  
项目目标：2026 年辽宁省大学生计算机博弈大赛校内选拔赛  
项目方向：爱恩斯坦棋离线 GUI 参赛程序  
建议文件位置：项目根目录 `PROJECT_PHASES.md`

---

## 一、项目总目标

在校内选拔赛前，做出一个：

- 离线可运行；
- 规则正确；
- 现场可操作；
- 有 GUI；
- 支持骰子录入、对方走法录入、建议走法输出；
- 支持棋谱保存、悔棋、计时；
- 具备一定博弈强度；
- 可通过本地 harness 持续迭代优化的爱恩斯坦棋参赛程序。

优先级排序：

```text
规则正确 > 现场稳定 > GUI 可操作 > 基础 AI 强度 > Expectimax 强化 > 开局库与参数优化 > 界面美观
```

---

## 二、核心工程原则

### 1. Harness-first

不要靠主观感觉判断 AI 是否变强。  
每次 AI 优化都必须通过本地对战 harness 验证。

必须统计：

- 胜率；
- 平均步数；
- 平均单步耗时；
- 最大单步耗时；
- 非法走法次数；
- 崩溃次数；
- 超时次数；
- replay 棋谱。

### 2. Core-first

先做规则引擎，再做 GUI。  
规则逻辑不能写进界面层。

### 3. 小步迭代

每次只优化一个明确目标：

- 评估函数；
- 走法排序；
- 时间管理；
- Expectimax 深度；
- 局面缓存；
- 开局库；
- 参数权重。

禁止一次性大改多个模块。

### 4. 不优先深度学习

首版 AI 不使用深度学习。  
优先采用：

- 规则评估；
- 概率风险评估；
- Expectimax；
- 局面缓存；
- 开局库；
- 批量对战调参。

---

# 阶段 0：项目初始化与规则固化

## 目标

建立项目骨架，固化当前规则假设，避免 Codex 或其他 AI 工具自行脑补规则。

## 输出物

```text
README.md
AGENTS.md
docs/PROJECT_BRIEF.md
docs/RULE_ASSUMPTIONS.md
PROJECT_PHASES.md
core/
ai/
gui/
record/
tests/
scripts/
adapters/
reports/
replays/
```

## 必须完成

1. 创建项目目录。
2. 写清当前比赛目标。
3. 写清当前采用的爱恩斯坦棋规则假设。
4. 写清 Codex 开发约束。
5. 明确第一阶段不做 GUI、不做复杂 AI。
6. 明确所有核心规则必须有 pytest 测试。

## 验收标准

Codex 进入项目后能明确知道：

- 这是爱恩斯坦棋参赛程序；
- 当前优先实现 core；
- 规则逻辑不能写进 GUI；
- 所有改动必须可测试；
- 不允许无依据修改规则；
- 不允许没有评测就宣称 AI 变强。

---

# 阶段 1：核心规则引擎 Core

## 目标

实现一个完全脱离 GUI 的爱恩斯坦棋规则引擎。

这是整个项目的地基。

## 输出物

```text
core/types.py
core/board.py
core/move.py
core/game_state.py
core/rules.py
record/serializer.py
tests/test_rules.py
tests/test_game_state.py
tests/test_serializer.py
scripts/smoke_test.py
```

## 必须实现

1. 5x5 棋盘。
2. 双方棋子编号 1-6。
3. 棋子位置与存活状态。
4. 根据骰子点数选择可走棋子。
5. 生成合法走法。
6. 执行走子。
7. 吃子。
8. 悔棋 / 撤销走子。
9. 胜负判断。
10. 局面序列化与反序列化。

## 必须测试

1. 棋盘边界。
2. 红方合法方向。
3. 蓝方合法方向。
4. 不能移动到己方棋子上。
5. 可以吃掉对方棋子。
6. 吃子后对方棋子状态正确。
7. undo 后局面完全恢复。
8. 骰子点数对应棋子存在时必须选择该棋子。
9. 对应棋子死亡时选择最近存活棋子。
10. 左右距离相同时允许二选一。
11. 到达目标角判胜。
12. 吃光对方棋子判胜。
13. serialize / deserialize 后局面一致。

## 验收标准

```text
pytest 全部通过。
scripts/smoke_test.py 能跑通。
规则逻辑不依赖 GUI。
undo_move 能完整恢复局面。
```

---

# 阶段 2：最小可用 GUI

## 目标

做出一个现场能用的离线 GUI 雏形。

不追求漂亮，先保证可操作。

## 输出物

```text
gui/main_window.py
gui/board_widget.py
gui/control_panel.py
gui/app.py
scripts/run_gui.py
```

## 必须实现

1. 显示 5x5 棋盘。
2. 显示双方棋子编号。
3. 显示当前行动方。
4. 输入骰子点数。
5. 显示当前骰子对应的可走棋子。
6. 点击或选择合法走法。
7. 执行走子并刷新棋盘。
8. 显示胜负结果。
9. 支持悔棋按钮。
10. 支持重置棋局。

## 暂不追求

- 不追求复杂动画。
- 不追求界面美观。
- 不做复杂 AI。
- 不做平台 API。
- 不做联网功能。

## 验收标准

```text
可以完整手动下一盘棋。
非法走法不能执行。
悔棋后棋盘恢复正确。
GUI 不直接改规则，只调用 core。
```

---

# 阶段 3：棋谱、计时、比赛模式

## 目标

把程序从“能玩”升级为“能上场”。

## 输出物

```text
record/game_record.py
record/exporter.py
gui/timer_panel.py
gui/match_mode.py
records/
```

## 必须实现

### 1. 棋谱记录

每步记录：

- 回合数；
- 当前方；
- 骰子点数；
- 移动棋子；
- 起点；
- 终点；
- 是否吃子；
- 被吃棋子；
- 当前局面；
- 单步用时；
- 双方剩余时间。

### 2. 棋谱保存与加载

支持：

- 保存为 JSON；
- 从 JSON 恢复；
- 回放棋谱；
- 悔棋时同步回退棋谱。

### 3. 计时功能

支持：

- 单方总时间；
- 每步耗时；
- 当前方计时；
- 暂停 / 恢复；
- 超时提示。

### 4. 比赛模式提示

GUI 应明确显示：

- 当前该谁操作；
- 是否需要录入骰子；
- 是否需要录入对方走法；
- 当前可走棋子；
- 当前推荐走法；
- 是否可以悔棋；
- 当前棋谱是否已保存。

## 验收标准

```text
一局棋结束后能生成完整棋谱。
程序关闭后可以重新加载棋谱。
计时不影响规则逻辑。
悔棋时棋谱和局面同步回退。
```

---

# 阶段 4：基础 AI 与启发式评估函数

## 目标

实现第一版能稳定下棋的 AI，并建立可解释的局面评估函数。

本阶段重点不是搜索深度，而是让 AI 具备基本棋感，并且永远不走非法步。

## 输出物

```text
ai/random_ai.py
ai/greedy_ai.py
ai/evaluator.py
ai/threat.py
ai/risk.py
tests/test_ai_basic.py
tests/test_evaluator.py
```

## 必须实现

1. RandomAI：随机选择一个合法走法。
2. GreedyAI：根据评估函数选择当前骰子下的最优走法。
3. 基础评估函数。
4. 概率风险评估。
5. 威胁地图 threat map。
6. GUI 中支持“建议走法”。
7. 显示 AI 推荐：
   - 移动棋子；
   - 起点；
   - 终点；
   - 是否吃子；
   - 推荐理由简述。

---

## 4.1 基础评估函数

评估函数至少包含：

1. 我方棋子距离目标角越近越好。
2. 对方棋子距离目标角越远越好。
3. 我方存活棋子越多越好。
4. 对方存活棋子越少越好。
5. 能直接获胜的走法最高优先级。
6. 能吃子的走法加分。
7. 被对方威胁的棋子减分。
8. 能阻止对方下一步获胜的走法加分。

示例结构：

```text
score =
  distance_score
+ material_score
+ capture_score
+ win_score
+ block_opponent_score
- threat_penalty
```

---

## 4.2 概率风险评估 Expected Risk

爱恩斯坦棋不是普通确定性棋类。  
对手下一步能走哪枚棋子，取决于骰子点数。

因此 AI 不能只判断“某个棋子是否被威胁”，还要估计：

```text
这个棋子在对方下一轮被吃掉的概率是多少？
```

必须实现：

1. 枚举对方下一轮骰子 1-6。
2. 对每个骰子点数，计算对方可选择棋子。
3. 对每个可选择棋子，生成对方合法走法。
4. 判断哪些走法可以吃掉我方棋子。
5. 估算我方每个棋子的被吃风险。
6. 对关键棋子的高风险暴露进行惩罚。

示例：

```text
如果我方 3 号棋子处于位置 A。
对方掷出 1 或 2 时，都可能移动对应棋子吃掉我方 3 号。
那么我方 3 号棋子的 expected capture risk 至少包含：
P(dice=1) + P(dice=2) = 2/6
```

注意：如果某个骰子点数对应的棋子已死亡，需要按照爱恩斯坦棋规则映射到最近存活棋子，因此风险评估必须复用 core 的骰子选择逻辑，不能单独写一套。

---

## 4.3 边缘保护 Edge Safety

贴边棋子通常更安全，因为被攻击方向更少。  
中心区域棋子更容易暴露在多路夹击中。

评估函数应加入边缘保护因素：

- 棋子贴边：适度加分；
- 棋子在中心且被多个方向威胁：减分；
- 靠近目标角但暴露风险高：需要综合判断；
- 不能为了贴边而完全放弃进攻速度。

示例结构：

```text
risk_penalty =
  expected_capture_risk * piece_importance_weight

edge_bonus =
  edge_safety_weight * edge_safety_score
```

---

## 4.4 棋子重要性 Piece Importance

不同棋子的价值不完全一样。  
评估时可以根据局面动态调整棋子重要性：

- 离目标角最近的棋子更重要；
- 唯一有冲线机会的棋子更重要；
- 能阻挡对方关键棋子的棋子更重要；
- 已经暴露且无进攻价值的棋子重要性较低。

---

## 阶段 4 验收标准

```text
AI 永远只输出合法走法。
AI 能识别一步获胜。
AI 能识别对方一步获胜威胁。
AI 能明显强于 RandomAI。
评估函数有单元测试。
概率风险评估复用 core 的骰子选择逻辑。
GUI 能显示建议走法，但不强制自动执行。
```

---

# 阶段 5：对战 Harness

## 目标

建立本地自动对战评测系统，用数据判断 AI 改动到底变强还是变弱。

这是后续优化的核心。

## 输出物

```text
scripts/run_match.py
scripts/tournament.py
scripts/benchmark.py
scripts/analyze_logs.py
reports/
replays/
tests/test_tournament.py
```

## 必须实现

1. AI vs AI 自动对战。
2. 支持固定随机种子。
3. 支持批量对战。
4. 支持保存 replay。
5. 支持 baseline 和 candidate 对比。
6. 输出胜率统计。
7. 输出非法走法次数。
8. 输出崩溃次数。
9. 输出平均步数。
10. 输出平均单步耗时。
11. 输出最大单步耗时。
12. 输出 reports/latest.md。
13. 输出 reports/latest.json。

## 推荐命令

```bash
python scripts/tournament.py --black greedy --white random --games 100 --seed 2026
python scripts/tournament.py --black candidate --white baseline --games 200 --seed 2026
python scripts/benchmark.py
```

## 报告至少包含

```text
games
seed
black_ai
white_ai
black_win_rate
white_win_rate
draw_rate
average_turns
illegal_moves
crashes
timeouts
average_step_time_ms
max_step_time_ms
```

## 验收标准

```text
能自动跑 100 局以上。
非法走法为 0。
崩溃次数为 0。
结果生成 reports/latest.md 和 reports/latest.json。
每次 AI 优化都有数据对比。
```

---

# 阶段 6：Expectimax 主线强化

## 目标

将 AI 从“贪心评估”升级为“考虑骰子概率和对手回应的搜索型 AI”。

本阶段核心方向固定为：

```text
Expectimax / 期望极小极大
```

MCTS、rollout、自对弈可以作为后续补充，但本阶段不要分散精力。

---

## 为什么选择 Expectimax

普通 Minimax 假设双方每一步都能自由选择最优行动。  
但爱恩斯坦棋中，行动受骰子限制。

因此搜索树中除了我方决策节点和对方决策节点，还存在骰子概率节点：

```text
我方选择走法
→ 对方骰子为 1/2/3/4/5/6 的概率节点
→ 对方在对应骰子下选择最优回应
→ 我方下一轮骰子概率节点
```

Expectimax 更适合这种带随机骰子的完全信息博弈。

---

## 输出物

```text
ai/expectimax_ai.py
ai/search.py
ai/transposition.py
ai/move_ordering.py
ai/time_control.py
tests/test_expectimax.py
tests/test_transposition.py
```

---

## 必须实现

### 1. Expectimax 搜索

至少支持：

- 固定深度搜索；
- 最大搜索时间限制；
- 终局立即返回极大值 / 极小值；
- 到达深度限制时调用 evaluator；
- 枚举骰子 1-6 的概率节点；
- 对同一骰子下的多个可选棋子和走法进行最优选择。

### 2. 搜索深度配置

支持：

```text
depth = 1
depth = 2
depth = 3
```

初期不要盲目追求深度。  
应优先保证：

- 不超时；
- 不非法；
- 搜索结果稳定；
- 对战胜率提升。

### 3. 时间管理

必须支持：

- 每步最大思考时间；
- 接近超时时提前返回当前最佳走法；
- 超时保护 fallback；
- 没有搜索结果时回退到 GreedyAI；
- GreedyAI 也没有结果时回退到 RandomAI。

### 4. 局面哈希表 Transposition Table

Expectimax 会重复计算大量局面，必须加入局面缓存。

缓存 key 至少包含：

- 当前棋盘；
- 双方棋子状态；
- 当前行动方；
- 当前搜索深度；
- 当前骰子或概率节点信息。

缓存 value 至少包含：

- 局面分数；
- 最佳走法；
- 搜索深度；
- 是否精确值。

### 5. 走法排序 Move Ordering

优先搜索：

1. 直接获胜走法；
2. 阻止对方直接获胜的走法；
3. 吃子走法；
4. 降低自身 expected risk 的走法；
5. 推进关键棋子的走法；
6. 其他普通走法。

### 6. 剪枝与降级搜索

Expectimax 不像 Alpha-Beta 那样容易直接剪枝，但仍可做工程级优化：

- 到达必胜局面立即返回；
- 到达必败局面立即返回；
- 某分支已明显低于当前候选时，降低搜索深度；
- 对低价值走法只做浅层评估；
- 对高风险走法提前惩罚；
- 当剩余时间不足时，只搜索排序靠前的候选走法；
- 使用 transposition table 避免重复计算。

注意：剪枝不能破坏规则正确性。  
宁可少剪枝，也不能因为错误剪枝导致明显漏算一步胜利或一步防守。

---

## 阶段 6 验收标准

```text
ExpectimaxAI 永远只输出合法走法。
ExpectimaxAI 支持固定深度和时间限制。
ExpectimaxAI 超时时能安全 fallback。
Transposition Table 有单元测试。
ExpectimaxAI vs GreedyAI 胜率明显提升。
Candidate vs Baseline 胜率超过 55% 才保留。
非法走法为 0。
崩溃次数为 0。
平均单步耗时在比赛可接受范围内。
```

---

# 阶段 7：开局库与参数优化

## 目标

优化开局布阵和前几步决策，提高整体胜率。

爱恩斯坦棋的初始阵型非常重要。  
很多程序中后盘搜索不错，但开局布局差，会导致前期直接陷入劣势。

---

## 重要原则

不要直接声称某个阵型是“数学最优”。  
除非有可靠资料或自己完成充分验证，否则统一称为：

```text
候选开局阵型
经过 harness 初步验证的推荐阵型
当前默认开局
```

---

## 输出物

```text
ai/opening_book.py
ai/opening_layouts.py
scripts/search_openings.py
scripts/tune_params.py
reports/opening_report.md
reports/params_report.md
```

---

## 7.1 开局布局库 Opening Layouts

至少维护几类候选布局：

### 1. 均衡型布局

目标：

- 不明显暴露关键棋子；
- 进攻和防守兼顾；
- 适合作为默认稳定布局。

### 2. 速攻型布局

目标：

- 让部分棋子更快接近目标角；
- 提高早期冲线概率；
- 风险是容易被针对吃子。

### 3. 防守型布局

目标：

- 减少早期被吃概率；
- 保持棋子结构稳定；
- 适合对手攻击性较强时使用。

### 4. 反制型布局

目标：

- 针对常见布局；
- 提前占据关键防守位置；
- 用于对抗特定风格 AI。

---

## 7.2 Opening Book 前几步查表

前 3-5 步可以考虑使用 Opening Book。

目的：

- 减少开局阶段搜索耗时；
- 避免 AI 在开局走出明显坏棋；
- 固化经过验证的高胜率开局策略；
- 保证前几步稳定可解释。

Opening Book 条目应包含：

```text
局面哈希
当前方
骰子点数
推荐走法
候选备选走法
使用次数
历史胜率
备注
```

---

## 7.3 开局库验证方法

每套布局必须通过 tournament 验证。

至少统计：

- 红方胜率；
- 蓝方胜率；
- 总胜率；
- 平均步数；
- 早期被吃子次数；
- 早期冲线次数；
- 对 RandomAI 胜率；
- 对 GreedyAI 胜率；
- 对当前 Baseline 胜率；
- 对 Candidate 胜率。

推荐命令：

```bash
python scripts/search_openings.py --games 200 --seed 2026
python scripts/tournament.py --black expectimax --white baseline --games 300 --seed 2026
```

---

## 7.4 参数优化

可调参数包括：

```text
distance_weight
material_weight
capture_weight
win_weight
block_opponent_weight
expected_risk_weight
edge_safety_weight
piece_importance_weight
center_exposure_penalty
rollout_weight
search_depth
max_step_time_ms
```

调参原则：

1. 每次只调整少量参数。
2. 每组参数必须保存。
3. 每次参数变化必须跑 tournament。
4. 胜率没有提升的参数不进入默认配置。
5. 不要过拟合某一个固定对手。

---

## 阶段 7 验收标准

```text
至少有 3 套候选开局布局。
确定 1 套默认布局。
至少完成 1 份 opening_report.md。
至少完成 1 份 params_report.md。
默认开局和默认参数有 tournament 数据支撑。
Opening Book 不影响 core 规则正确性。
```

---

# 阶段 8：现场比赛打磨

## 目标

把程序打磨成比赛当天能放心使用的状态。

## 输出物

```text
dist/
release/
docs/USER_MANUAL.md
docs/MATCH_CHECKLIST.md
docs/EMERGENCY_GUIDE.md
```

## 必须实现

1. 一键启动程序。
2. 默认进入比赛模式。
3. 字体和棋子编号显示清楚。
4. 操作按钮不容易误点。
5. 关键操作需要确认。
6. 悔棋入口明显。
7. 当前状态提示明显。
8. 保存棋谱路径明确。
9. 程序异常时尽量保留当前棋谱。
10. 支持离线运行。
11. 支持比赛前快速自检。

## 现场检查清单

```text
1. 电脑电量 / 电源正常。
2. 程序可离线启动。
3. 鼠标键盘正常。
4. 屏幕亮度合适。
5. 棋盘显示清楚。
6. 骰子录入正常。
7. 对方走法录入正常。
8. AI 建议走法正常。
9. 悔棋可用。
10. 计时可用。
11. 棋谱保存可用。
12. 随机测试一局不崩。
```

## 验收标准

```text
连续模拟比赛 3 局不崩。
手动录入对方走法流程顺畅。
出现误操作可以恢复。
程序不依赖网络。
比赛模式下不会意外修改规则或参数。
```

---

# 阶段 9：封版与参赛材料

## 目标

冻结比赛版本，避免赛前乱改引入 bug。

## 输出物

```text
release/v1.0/
release/v1.0/README.md
release/v1.0/config.json
release/v1.0/default_params.json
release/v1.0/user_manual.md
release/v1.0/test_report.md
release/v1.0/opening_report.md
release/v1.0/sample_records/
```

## 必须完成

1. 标记稳定版本。
2. 固定默认参数。
3. 固定默认开局。
4. 固定默认 AI。
5. 保留源码备份。
6. 保留可运行版本备份。
7. 保留测试报告。
8. 保留典型棋谱。
9. 保留比赛当天操作手册。
10. 保留应急处理说明。

## 封版原则

```text
赛前最后阶段只修 bug，不做大改。
不临时换 AI 框架。
不临时换 GUI 框架。
不临时引入新依赖。
不在比赛电脑上做未经测试的修改。
不因为单局输赢临时大调参数。
```

## 验收标准

```text
稳定版能运行。
pytest 全部通过。
GUI 正常。
棋谱正常。
计时正常。
AI 建议正常。
Expectimax 不超时。
无非法走法。
有备份。
```

---

# 三、总体路线压缩版

```text
阶段 0：项目初始化
输出：README、AGENTS、规则假设文档、目录结构

阶段 1：规则引擎
输出：core、serializer、pytest、smoke_test

阶段 2：最小 GUI
输出：棋盘显示、骰子输入、手动走子、悔棋

阶段 3：比赛功能
输出：棋谱、计时、比赛模式

阶段 4：基础 AI + 评估函数
输出：RandomAI、GreedyAI、Evaluator、Expected Risk、Edge Safety

阶段 5：对战 Harness
输出：自动对战、胜率统计、replay、benchmark、reports

阶段 6：Expectimax 主线强化
输出：ExpectimaxAI、Transposition Table、Move Ordering、Time Control

阶段 7：开局库与参数优化
输出：候选开局、Opening Book、默认布局、默认参数、调参报告

阶段 8：现场打磨
输出：一键启动、比赛模式、操作手册、应急指南

阶段 9：封版
输出：release 稳定版、测试报告、备份
```

---

# 四、当前最应该做的前三步

## 第一步：阶段 0 + 阶段 1

先让 Codex 完成：

- 项目骨架；
- core 规则引擎；
- pytest 测试；
- smoke_test。

不要做 GUI，不要做复杂 AI。

## 第二步：阶段 2

做最小 GUI：

- 显示棋盘；
- 输入骰子；
- 手动走子；
- 悔棋；
- 胜负判断。

## 第三步：阶段 4 + 阶段 5

做基础 AI 和 harness：

- RandomAI；
- GreedyAI；
- Evaluator；
- Expected Risk；
- tournament；
- reports。

---

# 五、AI 优化主线

最终 AI 强化路线固定为：

```text
RandomAI
→ GreedyAI
→ GreedyAI + Expected Risk
→ GreedyAI + Edge Safety
→ Expectimax depth=1
→ Expectimax depth=2
→ Expectimax + Transposition Table
→ Expectimax + Move Ordering
→ Expectimax + Time Control
→ Opening Book + Expectimax
→ 参数调优版本
```

不要一开始就做 MCTS。  
MCTS 可以作为后续备选，但当前主线应死磕 Expectimax。

---

# 六、最终判断标准

一个版本是否值得保留，不看主观感觉，只看数据。

候选版本必须满足：

```text
pytest 全部通过。
非法走法 = 0。
崩溃次数 = 0。
超时次数 = 0。
Candidate vs Baseline 胜率 > 55%。
平均单步耗时在比赛限制内。
GUI 可正常操作。
棋谱可保存。
悔棋可恢复。
```

如果胜率提升但稳定性下降，不保留。  
如果单局表现很好但批量对战变差，不保留。  
如果算法更复杂但没有数据提升，不保留。

---

# 七、一句话总路线

先保证规则能跑，  
再保证现场能用，  
再用 harness 验证 AI 是否真的变强，  
最后用 Expectimax、概率风险评估和开局库把强度一点点堆上去。
