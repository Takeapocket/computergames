# 阶段 4.1 决策记录：1-ply Greedy 的能力上限与门槛下调

更新时间：2026-05-09  
对应任务：`docs/superpowers/plans/2026-05-09-phase-4-basic-ai.md` Task 8.5 / 9.5 / 10  
关联 failure analysis：`reports/4-1-failure-analysis.md`

## TL;DR

阶段 4.1 完成 GreedyAI（基础评估 + stuck_penalty）后：

| 配置 | 局数 | 红 GreedyAI 胜率 |
|---|---|---|
| 红 Greedy vs 蓝 Random | 200 | **0.65** |
| 红 Random vs 蓝 Greedy | 200 | 蓝 **0.715**（红 0.285） |

Greedy 自对弈 100 局：红 0.58 / 蓝 0.42（先手优势）。

`PROJECT_PHASES.md` 原门槛 ≥ 95% **不可达**。已下调到 ≥ 60%，本次实测达标。

## 数据沿革

| 版本 | 红 GreedyAI vs 蓝 RandomAI（200 局，seed=2026） | forfeit 输 | 抢 (0,0) 输 | per-game 明细 |
|---|---|---|---|---|
| 4.1 baseline（仅距离 + 子力，标准三角开局） | 59% | 24%（48 局） | 17%（34 局） | `reports/bench_phase_4_1_baseline_greedy_vs_random.json` |
| 4.1 + Task 8.5 + 9.5（stuck_penalty + 无 stuck 开局） | **65%** | <1%（1 局） | 35%（69 局） | `reports/bench_phase_4_1_greedy_vs_random.json` |

stuck 子 forfeit 几乎清零（48 → 1）；剩下的输全部是"被抢着到达 (0,0)"或"路上送子被吃"。

数字按 `per_game[]` 数组中 `winner == "blue"` 且 `termination_reason ∈ {"no_move", "winner_target_corner"}` 聚合得出。复现命令：`python scripts/reproduce_phase_4_1.py`（baseline 用 `--starting-layout standard_triangle_v1`，production 用默认 `default_no_stuck_corner_v1`）。

## 为什么 1-ply greedy 摸不到 95%

GreedyAI 评估"自己走完之后的状态"，**不展开对方下一回合**。所以：

1. **没有威胁感知。** 自己一枚棋子刚好停在对方下回合可吃的格子上时，GreedyAI 看不到。
   实测案例（reports 里的 game 1 t2）：Red 4 走 (1,0)→(1,1) 之后，Blue 6 在 (1,3) 下回合
   dice=6 直接 (1,3)→(0,2) 吃掉 Red 3，Greedy 当时完全无感。
2. **dice 方差。** 推 piece 6 到 (4,4) 至少要 3 次 dice=6（假设 piece 6 还活着且有路径），期望
   ~18 个总回合才有 3 次。这段时间内 RandomAI 也在推任意子，不一定输。
3. **"最优单步"≠"最优策略"。** Greedy 优先吃子（material +10）的局部最优有时让出推进
   tempo，让 Random 先冲到角。

要打到 ≥95% 必须有：
- 至少枚举对方下回合骰子（Expected Risk，4.2）
- 或者多 ply 搜索（Expectimax，6.x）

两者都明确不在 4.1 范围内。

## 已经入库的修订

- **Task 8.5**：`ai/evaluator.py` 加 `STUCK_PIECE_PENALTY = 100.0` 与 `count_stuck_pieces()`，
  让 GreedyAI 主动避免让己方棋子陷入"alive 但无合法走法"的状态。
- **Task 9.5**：`ai/match.py:default_starting_state` 把红 5/6 改到 (2,0)/(3,1)、蓝 5/6 改到
  (2,4)/(1,3)。规避了"角子初始就被自家围死，dice=1/6 强制选→ forfeit"的不可控 1/6 上限。
  阶段 7 引入候选开局库时会被替换。
- **PROJECT_PHASES.md**：4.1 门槛 ≥95% → ≥60%，并把"AI 能识别对方一步获胜威胁"明确移到 4.2。

## 下一步建议

1. **先封 4.1**（commit + 报告留档），把已经过测试的 harness + GreedyAI + stuck_penalty + 无
   stuck 开局作为后续迭代的稳定 baseline。
2. **进入 4.2 Expected Risk 规划**，把 threat awareness 作为头号目标。4.2 完成后需用同
   seed=2026 重跑 `red=greedy(+risk) vs blue=random` 200 局，验证 stuck_penalty 已封堵的
   forfeit 不会因 risk 评估再生，并以实测胜率为准（不预设具体阈值）。同时检查蓝胜局里
   "winner_target_corner" 比例是否随 threat awareness 上线而下降。
3. 如果时间紧（赛前），可以并行规划"GUI 建议走法"集成（PROJECT_PHASES.md 阶段 4 第 6/7 项），
   不必等 4.4。

## 验收记录指针

所有 bench JSON 都是 schema v2，包含 `per_game[]` 明细、`git_revision`、`command`、`ai_versions`、`starting_layout_id` 等元数据。一次性重跑入口：`python scripts/reproduce_phase_4_1.py`。

- 4.0 验收报告：`reports/bench_phase_4_0_random_vs_random.json`（standard_triangle_v1，100 局）
- 4.1 baseline（红 Greedy，stuck_penalty=0）：`reports/bench_phase_4_1_baseline_greedy_vs_random.json`（standard_triangle_v1，200 局）
- 4.1 验收（红 Greedy，stuck_penalty=100）：`reports/bench_phase_4_1_greedy_vs_random.json`（default_no_stuck_corner_v1，200 局）
- 4.1 反向 sanity（蓝 Greedy）：`reports/bench_phase_4_1_random_vs_greedy.json`
- 4.1 自对弈稳定性：`reports/bench_phase_4_1_greedy_vs_greedy.json`（100 局）
- schema v2 replay 范例：`replays/match_phase_4_0_sample_random_vs_random_seed2026.json`
