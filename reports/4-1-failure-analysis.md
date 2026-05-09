# 阶段 4.1 验收 GreedyAI vs RandomAI 失败分析

更新时间：2026-05-09  
对应任务：`docs/superpowers/plans/2026-05-09-phase-4-basic-ai.md` Task 10  
对应报告：`reports/bench_20260509_081311_greedy_vs_random.json`（红=greedy 200 局）

## 数据

| 指标 | 数值 | 阶段 4.1 门槛 |
|---|---|---|
| 总局数 | 200 | — |
| GreedyAI（红方）胜率 | 0.59 | ≥ 0.95 ❌ |
| 平均步数 | 11.56 | — |
| illegal_moves / crashes / timeouts | 0 / 0 / 0 | 全 0 ✓ |

## 失败模式分类（200 局中红方输 82 局）

| 失败模式 | 局数 | 占输局比例 | 占总局比例 |
|---|---|---|---|
| Red 无合法走法 → forfeit | 48 | 58.5% | **24.0%** |
| Blue 到达 (0,0) | 34 | 41.5% | 17.0% |
| Red 被吃光 | 0 | 0% | 0% |

## 根因

**dice=1 时强制选中 Red 1 号棋子，但 1 号在初始局面被自己人围死。**

默认开局 Red 1 在 (0,0)，三个走法方向 (1,0)/(0,1)/(1,1) 分别被 Red 4/2/5 占据 → `legal_moves_for_piece(piece 1)` 永远返回 `[]`。任何回合掷出 `dice=1`：
- `legal_piece_ids_for_dice(dice=1)` 因 piece 1 alive 直接返回 `[1]`（不会 fallback 到最近存活）；
- `legal_moves(player, dice=1)` 返回 `[]`；
- `play_one_game` 把"AI 返回 None"判为当前方负。

每回合 1/6 概率触发，开局后大约 4-5 回合内必然命中。RandomAI 因为每步都随机移动任意子，反而经常意外松开 piece 4/2/5 解放 piece 1；GreedyAI 一直按距离贪心走最优子，piece 1 周围长期不松，被 forfeit 概率反而更高。

蓝方完全对称（Blue 1 在 (4,4) 同样被围），所以 RandomAI vs RandomAI 仍然是约 50/50（实测 49/51），双方对称受害。但 GreedyAI vs RandomAI 这种不对称对局里，"会贪心解放角子"才是关键能力，目前的评估函数完全没看到。

`docs/RULE_ASSUMPTIONS.md` 第 11 / 23 条已经标记过"无合法走法的裁定方式未确认"——这次我们确认了它在 harness 里就是 forfeit。

## 候选方案

| 方案 | 影响范围 | 工作量 | 风险 |
|---|---|---|---|
| A. 在 evaluator 加 stuck_penalty（扫每枚己方子，无 legal_moves 即罚分） | `ai/evaluator.py` + 测试 | 1-2 task | 在 4.1 范围内可控；权重需要小心，过大可能让 AI 不敢推进 |
| B. 改规则：dice 选中棋子无法走时，fallback 到下一近存活子 | `core/rules.py` + `core/game_state.py` + 全量测试 | 中等 | **改 core 规则**，需先确认是否符合 2026 校赛/省赛官方规则 |
| C. 改规则：dice 选中棋子无法走时，本回合判 pass（不动子） | `core/rules.py` + `play_one_game` 处理 None 的语义 | 中等 | 同上 |
| D. 把阶段 4.1 门槛从 ≥95% 下调到 ≥70%，把"角子风险"留给 4.2 Expected Risk | `PROJECT_PHASES.md` | 1 行改动 | 推迟问题，不解决；但 4.2 本就要做风险评估 |
| E. 改默认开局：让角子初始就有合法走法（例如把 piece 1 放到三角形外缘而不是顶角） | `ai/match.py:default_starting_state` + 测试 | 1 task | 避开问题，但仍然承认任何"角子被围"的开局都会同病；阶段 7 开局库的研究本来就要做 |

## 建议

**首选 A（evaluator 加 stuck penalty）**：保持规则不变（不冒规则与官方解读不一致的险）、保持开局是标准三角形（与阶段 7 衔接）、在 4.1 范围内闭环。stuck penalty 的本质就是简化版的"expected risk for self-forfeit"，方向上和 4.2 兼容，将来 4.2 的 expected risk 更精细时可以替换或合并。

如果选 D，需要在 PROJECT_PHASES.md 同步注明 4.1 门槛下调的理由，并把"为什么 ≥95% 在当前规则下不可达"写进决策记录。
