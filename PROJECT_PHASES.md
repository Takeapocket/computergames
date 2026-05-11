# 爱恩斯坦棋参赛程序阶段目标文档

更新时间：2026-05-10  
项目目标：2026 年辽宁省大学生计算机博弈大赛校内选拔赛  
项目方向：爱恩斯坦棋离线 GUI 参赛程序  
建议文件位置：项目根目录 `PROJECT_PHASES.md`

---

## ⚠️ 赛事规则对齐补丁（2026-05-10 新增，优先级最高）

2026-05-10 通过国赛官网原文（`全国计算机博弈竞赛总则.md` + `爱恩斯坦棋项目规则.md`）核对，发现项目当前实现与赛事规则有以下出入。**这些补丁的优先级高于阶段 6/7 的主线推进**，必须在继续 AI 强化之前完成。

### 阶段 R-0：吃本方棋子合规修复（P0，必须首先做）✅ 已完成 (2026-05-11)

**修复 commit**：core/rules.py 删除 `if occupant.player is piece.player: continue` 分支；tests/test_rules.py 改 `test_piece_can_capture_own_piece`；tests/test_game_state.py 加 `test_apply_self_capture_marks_own_piece_dead`；tests/test_evaluator.py + test_evaluator_injection.py 修破测试。pytest 207 passed。

**bench 重跑**：详见 `reports/4-1-rebench.md` / `reports/4-2-rebench.md` / `reports/4-4-rebench.md`，全部门槛通过。所有 bench JSON 已转为 slim 格式（无 `per_game[]`，~1.2KB / 份）。

**R-0-followup（不在 R-0 范围）**：
- 删除 `STUCK_PIECE_PENALTY` / `count_stuck_pieces` 死代码（含 evaluator/greedy_ai/CLI flag/_bench_meta 引用 + 7 个测试）
- `ai/risk.py` 加入 `expected_self_capture_risk` 或在 evaluator 加 self-capture 战略价值项
- 4-x-failure-analysis 全文重写（如果做时间预算允许）

**问题**：`core/rules.py:52-54` 不允许走到本方棋子位置；规则原文："如果在棋子走动的目标棋位上有棋子，则要将该棋子从棋盘上移出（吃掉）。**有时吃掉本方棋子也是一种策略**。"

**输出物**：

```text
core/rules.py             # 移除"跳过本方棋子"分支，统一捕获 occupant
tests/test_rules.py        # test_piece_cannot_move_to_own_piece_square → test_piece_can_capture_own_piece
tests/test_game_state.py   # 验证 apply_move 在自残时正确把本方子标 alive=False
ai/risk.py                 # 评估"被自家吃掉"是否计入 expected_capture_risk
ai/evaluator.py            # 评估 stuck_penalty 是否还需要（自残后被围死场景应大幅减少）
reports/4-1-rebench.md     # 重跑 4.1 GreedyAI vs RandomAI bench
reports/4-2-rebench.md     # 重跑 4.2 greedy_risk vs greedy grid（基于合规规则）
reports/4-4-rebench.md     # 重跑 4.4 ExpectimaxAI bench；可能结论翻盘
```

**验收标准**：

```text
test_piece_can_capture_own_piece 通过（自残后本方子 alive=False，move.is_capture=True）。
全量 pytest 通过。
4.1 GreedyAI vs RandomAI 在合规规则下合并胜率 ≥ 60%（沿用原门槛）。
4.2 greedy_risk vs greedy 在合规规则下合并胜率与之前 53.8% 对比，差异 ≤ 5pp。
4.4 ExpectimaxAI vs greedy_risk 重跑数据更新到 4-4-failure-analysis.md。
```

**预估工时**：core+tests 0.5h；bench 重跑 + 报告 1h。

---

### 阶段 R-1：开局录入 GUI（P1）

**问题**：赛事规则第 1 条 "开局时双方棋子在出发区的棋位可以随意摆放"；项目当前 `STARTING_LAYOUT_ID` 只是 self-play 默认布局，比赛中两边可任意摆放。GUI 缺少"录入对方布局 + 选择我方布局"功能。

**输出物**：

```text
ai/match.py                # LAYOUTS 字典扩展为 dict[id, callable]，支持多候选
ai/opening_layouts.py      # 至少 3 套候选布局（均衡 / 速攻 / 防守），从阶段 7 提前到这里
gui/opening_panel.py       # 新建：(a) 选择我方候选布局，(b) 拖放或网格点击录入对方布局
gui/main_window.py         # 集成 opening_panel；开局阶段显示"录入对方布局"提示
tests/test_opening_panel.py
tests/test_opening_layouts.py
```

**验收标准**：

```text
GUI 启动后默认进入"开局录入"阶段。
我方布局可从下拉框选择 ≥ 3 个候选布局之一。
对方布局可通过点击 5×5 棋盘出发区录入（红方左上 / 蓝方右下三角形）。
录入完成后可点击"开始对局"进入正常比赛流程。
保存的棋谱包含双方实际开局布局。
```

**预估工时**：4-6h（GUI 改动较多）。

---

### 阶段 R-2：7 盘制比赛模式（P1）

**问题**：赛事规则第 7 条 "每轮双方对阵最多 7 盘，轮流先手（甲方一四五盘先手，乙方二三六七盘先手），两盘中间不休息，先胜 4 盘为胜方"；项目 `gui/match_mode.py` 只支持单局。

**输出物**：

```text
gui/match_mode.py          # 增加 round_state: pieces_won_us / pieces_won_them / current_game_index
gui/main_window.py         # 显示当前盘数 / 比分 / 谁先手
record/match_record.py     # 新建：聚合 7 盘 GameRecord 为一轮 MatchRecord
tests/test_match_mode.py   # 验证盘数判定 / 先后手轮换 / 先胜 4 盘判胜
```

**验收标准**：

```text
GUI 显示 "本轮第 X 盘 / 比分 a:b / 我方/对方先手"。
某一方累计胜 4 盘时弹出"本轮胜方"对话框。
盘 1/4/5 我方先手；盘 2/3/6/7 对方先手（开始时由 GUI 询问哪方是甲方）。
两盘之间不休息，自动重置棋盘并提示对方先后手。
```

**预估工时**：3-4h。

---

### 阶段 R-3：崩溃自救（P1）

**输出物**：

```text
record/auto_save.py        # 每步保存到 replays/auto_save.json
gui/main_window.py         # 启动时检测 auto_save.json，提示"上次未保存的对局，是否恢复？"
```

**验收标准**：

```text
每步走完自动写 replays/auto_save.json（含 GameRecord serialize）。
程序异常退出后再启动，弹出"恢复上次对局" Yes/No 对话框。
对方走法和我方走法都触发 auto_save。
```

**预估工时**：1-2h。

---

### 阶段 R-4：决赛快棋（P3，赛前一周做）

10 分钟快棋包干，复用 `--total-seconds 600` 启动参数；如需 GUI 切换按钮，再加。

---

## 进度评估（2026-05-11，R-0 完成后）

| 阶段 | 状态 | 备注 |
|---|---|---|
| 0 项目初始化 | ✓ 完成 | |
| 1 规则引擎 | ✓ **完成（R-0 已合规修复）** | 详见 `reports/4-1-rebench.md` |
| 2 最小 GUI | ✓ 完成 | |
| 3 棋谱/计时/比赛模式 | ⚠️ **部分完成** | 阶段 R-1 / R-2 / R-3 补完 |
| 4.0 最小 harness | ✓ 完成 | bench 已按 R-0 合规规则重跑（slim 格式） |
| 4.1 GreedyAI | ✓ 完成 | R-0 合规重跑后合并 63.75% ≥ 60% 门槛 |
| 4.2 Expected Risk | ✓ 完成 | R-0 合规重跑后合并 55.75%（旧 53.8% 差 +2pp，<5pp 门槛） |
| 4.3 Edge Safety | ❌ **跳过** | 1-ply 下 count_edge_pieces 无效，已回退（详见 review history） |
| 4.4 Piece Importance | ⚠️ **改实现成 ExpectimaxAI** | R-0 合规重跑后合并 45.0%（旧 46.5%），仍弱于 greedy_risk，保留为研究代码 |
| 5 Harness 工程化 | 部分完成（quick_bench 已有） | tournament 多 AI 循环赛、reports/latest.md 自动生成尚未做 |
| 6 Expectimax 主线 | ❌ 未开始（depth=1 已尝试但弱） | R-0 重跑数据未否定 4-4-rebench 的 4 个改进方向，但未执行 |
| 7 开局库与参数 | 部分提前到 R-1 | |
| 8 现场打磨 | ❌ 未开始 | 含 R-3 |
| 9 封版 | ❌ 未开始 | |

**主线调整建议**：
- ~~R-0~~ 已完成（2026-05-11），bench 已重跑并入库
- R-1 / R-2 / R-3 是赛前必须，估时合计 8-11h
- R-0-followup（stuck_penalty 死代码清理 + ai/risk.py self-capture 扩展）可以与 R-1/R-2/R-3 并行，不阻塞主线
- 阶段 7 的开局库优先级被 R-1 提前消化了一部分，剩余的"开局库参数调优"可以推迟
- 阶段 6 Expectimax 主线：R-0 重跑后 depth=1 仍弱（45.0%），是否继续做需要先实验 reports/4-4-rebench.md 列出的 4 个方向

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
record/exporter.py        # 暂合并到 record/game_record.py：仅 JSON 一种导出格式时无需独立模块。待出现 PGN-like 等第二种格式再拆分（YAGNI）。
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

> ⚠️ **强制顺序：先做 4.0 最小 harness，再做 4.1-4.4 任何 AI 改进。**
> 否则违反"Harness-first"原则——每加一个 AI 特性必须有数据证明它确实变强了，而不是"看上去像在赢"。

0. **最小对战 harness**（见下文 4.0）——必须最先完成。
1. RandomAI：随机选择一个合法走法。
2. GreedyAI：根据评估函数选择当前骰子下的最优走法。
3. 基础评估函数。
4. 概率风险评估。
5. 威胁地图 threat map。
6. GUI 中支持"建议走法"。
7. 显示 AI 推荐：
   - 移动棋子；
   - 起点；
   - 终点；
   - 是否吃子；
   - 推荐理由简述。

---

## 4.0 最小对战 harness（**先于一切 AI 改进**）

**目标：** 提供"两个 AI 自动对战 N 局并输出胜率/平均步数/非法步数/崩溃数"的最小能力，让后续每个 AI 改进都能立即用数据验证。

阶段 5 是 harness 的**工程化扩展**（多 AI tournament、replay 管理、参数对比报告）；阶段 4.0 只要"能跑能出数"。

**输出物：**

```text
scripts/run_match.py    # AI vs AI 单次对战，输出 winner/turns/illegal/crash
scripts/quick_bench.py  # 批量对战 100 局，输出胜率/平均步数等汇总
ai/__init__.py          # AI 协议：play(state, dice) -> Move
```

**验收标准：**

```text
python scripts/quick_bench.py --red random --blue random --games 100 --seed 2026
能在 30 秒内跑完 100 局，输出：
  red_win_rate / blue_win_rate / draw_rate
  avg_turns / illegal_moves / crashes
非法走法 = 0，崩溃 = 0。
```

完成 4.0 之后，4.1-4.4 每个里程碑都按以下"评测门槛"模式执行：
1. 改进一个 AI 特性
2. quick_bench 跑 200 局：candidate vs baseline
3. 胜率门槛达标且无非法/崩溃 → 进入下一里程碑；否则回退或调试

**里程碑评测门槛（建议值，不是绝对值）：**

| 里程碑 | candidate | baseline | 胜率门槛 |
|---|---|---|---|
| 4.1 完成 | GreedyAI（基础评估 + stuck_penalty） | RandomAI | ≥ 60% |
| 4.2 完成 | Greedy + Expected Risk | GreedyAI | ≥ 55% |
| 4.3 完成 | Greedy + Risk + Edge Safety | Greedy + Risk | ≥ 53% |
| 4.4 完成 | Greedy + Risk + Edge + Piece Importance | Greedy + Risk + Edge | ≥ 53% |

胜率达不到说明：(a) 新特性实现有 bug；(b) 新特性方向错误；(c) 调参未优化。无论哪种都不应进入下一里程碑。

> **2026-05-09 修订（4.1 门槛）**：原门槛 ≥ 95% 在 1-ply greedy + 仅"距离 + 子力 + stuck"
> 评估的组合下不可达。诊断详见 `reports/4-1-decision-record.md`。结论是把 95% 这个"接近无敌"
> 的预期推迟到 4.2/4.3/4.4 三个评估扩展叠加之后再考评，4.1 的合格线下调到 ≥ 60%（实测红
> 65%、蓝 71.5%，明显强于 RandomAI）。同时把"AI 能识别对方一步获胜威胁"也延到 4.2，因为
> 那本质上就是 Expected Risk 在做的事。

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
4.0 最小 harness 跑通（100 局 random vs random，非法=0，崩溃=0）。
4.1 GreedyAI vs RandomAI 胜率 ≥ 60%（200 局，固定 seed，reports/ 留档；红蓝两边都跑过）。
4.2 Greedy+Risk vs Greedy 胜率 ≥ 55%。
4.3 Greedy+Risk+Edge vs Greedy+Risk 胜率 ≥ 53%。
4.4 加 Piece Importance 后 vs 4.3 胜率 ≥ 53%。
所有里程碑：AI 永远只输出合法走法；非法走法=0、崩溃=0、超时=0。
AI 能识别一步获胜（4.1 已支持，evaluator 终局检查直接给 +WIN_SCORE）。
对方一步获胜威胁的识别延到 4.2 Expected Risk（1-ply greedy 看不到，需要枚举对方下回合骰子）。
评估函数有单元测试。
概率风险评估复用 core 的骰子选择逻辑。
GUI 能显示建议走法，但不强制自动执行。
```

胜率门槛是建议值，第一次跑达不到不代表方向错——但需要在 reports/ 里写清楚"低于门槛的原因分析"，不能不达标就直接进下一里程碑。

---

# 阶段 5：对战 Harness 工程化

## 目标

将阶段 4.0 的最小 harness 扩展为正式评测系统：多 AI tournament、批量参数对比、replay 管理、reports 自动生成。

阶段 4.0 已经有"两个 AI 跑 N 局出胜率"的基础能力；阶段 5 的工作是让它支持：

- 任意多个 AI 之间的循环赛
- baseline vs candidate 的标准化参数对比报告
- 可视化的 replay 加载（便于调参时分析单局）
- benchmark：固定 baseline 测当前 AI 的稳定基线性能

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

## 7.4.1 自动化调参 workflow

本项目不做强化学习、不做神经网络。"训练"的本质 = **自动化调参**。
首选方法：(1+λ) **演化策略** —— 比 grid search 高效，比 Bayesian 优化好上手。

**算法（伪代码）：**

```text
baseline = 当前默认参数集（reports/params_report.md 里的最新一组）
for generation in 1..N:
    # 1. 生成 λ 个候选（建议 λ=5-8）
    candidates = []
    for i in 1..λ:
        c = baseline 的副本
        随机选 1-2 个权重，按 ±20% 高斯扰动
        candidates.append(c)

    # 2. 每个候选 vs baseline 跑 200 局（固定 seed 池保证可重复）
    results = []
    for c in candidates:
        win_rate, illegal, crash, timeouts = tournament(c, baseline, games=200, seed_pool=...)
        results.append((c, win_rate, illegal, crash, timeouts))

    # 3. 筛选：必须 illegal=0、crash=0、timeouts=0，且胜率 > 55%
    survivors = [r for r in results if r.illegal==0 and r.crash==0 and r.timeouts==0 and r.win_rate > 0.55]

    # 4. 采纳最强候选作为新 baseline；如果无人达标，baseline 不变
    if survivors:
        best = max(survivors, key=lambda r: r.win_rate)
        baseline = best.params
        记录到 reports/params_history.md

    # 5. 早停：连续 3 代无候选达标 → 收敛或局部最优，停止
    if 连续 3 代无 survivor:
        break
```

**关键纪律：**

- **种子池固定**：每代用同一组 seeds（比如 [2026, 2027, ..., 2225] 共 200 个），不同代之间换种子是噪声源
- **样本量 200 局**：胜率差 5% 时统计置信区间约 ±7%，足够辨别真改进 vs 噪声
- **每代只动 1-2 个参数**：动太多无法归因哪个参数有效
- **每组参数 commit 到 git**：rollback 方便
- **避免过拟合**：终选 baseline 必须再 vs RandomAI 和 GreedyAI 各跑 100 局确认没退化

**预算估计：** 单局耗时 1-2 秒（Expectimax depth=2），200 局约 5-7 分钟。每代 5 个候选 × 200 局 ≈ 30 分钟。10 代 ≈ 5 小时。能在一晚跑完。

如果时间允许，可以加 **简单 grid search** 作为补充：选 2-3 个最关键的参数（如 `expected_risk_weight`、`edge_safety_weight`），每个 3-5 个离散值，全组合跑一次（~30 分钟），找出局部最优起点，再用演化策略细调。

**输出：** `scripts/tune_params.py` 实现上述算法，运行后产出 `reports/tune_log_YYYYMMDD.md`（每代候选 + 胜率），以及最终入库参数 `release/v*/default_params.json`。

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
