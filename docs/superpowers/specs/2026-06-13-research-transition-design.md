# 爱恩斯坦棋 AI 长期研究转型设计

日期：2026-06-13
状态：已批准（用户确认定位、路线、依赖边界与迁移目标）

## 1. 背景与目标

2026 赛季已结束。项目从"参赛程序"转型为**纯研究项目**，目标是提升爱恩斯坦棋 AI 的棋力上限。比赛约束（4 分钟包干、离线部署、封版纪律）解除；可运行的 GUI 程序与 release/v1.0 锁定配置保留为历史基线和评测锚点。

转型时基线：默认 AI 为 `rollout` + P14 参数（对旧 P3 默认 59.0%）；除 P14 受控默认替换外，其余未晋升路线与重开条件见 `reports/ai_experiment_stop_list_20260518.md`；全量 pytest 862 passed（2026-06-13 复验）。

实战暴露的典型输法——己方先进子距目标角一步时被对方掷中可吃子点数——转化为两个研究项：真实棋谱骰子公平性取证、终局竞速局面精确求解。

## 2. 已确认决策

| 决策点 | 结论 |
|---|---|
| 定位 | 纯研究，不保留比赛可部署约束 |
| 路线 | 先地基后双线（经典搜索线 + 自对弈学习线并行） |
| 硬件/依赖 | 有 NVIDIA GPU；接受 numpy/torch；必要时接受 Rust/C 扩展 |
| 迁移 | 项目本体迁至 `E:\computergame`（E 盘剩 97GB） |

## 3. 硬约束

- **C 盘红线**：C 盘仅剩 ~53GB。训练数据、模型权重、自对弈棋谱、pip/torch 缓存一律放 E 盘。
- **README 红线**：README 及对外文档不写比赛结果信息；复盘内容只进 PROJECT_MEMORY / reports，措辞中性。
- **纪律保留**：harness-first、core-first、pytest 全绿；旧路线重开必须有新技术假设（stop list 重开条件有效）。

## 4. 代码摸底结论（设计依据）

- `core/game_state.py` `apply_move`：原地变更 + `history` + `undo_move`，make/undo 已存在；但每次 apply 都经 `_find_matching_legal_move` 重新生成合法步校验，热循环存在双倍合法步生成开销。
- `ai/rollout_ai.py` `_sample_move_score` / `_playout`：每个 root rollout 通过 `GameState.serialize()` / `deserialize()` 克隆局面，每个 playout 新建 `GreedyAI` + `random.Random`，每 ply 跑一次 greedy_risk 评估，分配与复制开销显著。`GreedyAI` 持有 RNG 并用随机打破并列，任何对象复用都必须证明固定 seed 行为等价，或明确标记为行为变化候选。
- `ai/expectimax_v2.py`：朴素 expectimax，无置换表、无 move ordering、无 Star1/Star2 机会节点剪枝、无迭代加深。
- `ai/mcts.py` `_iterate`：UCT + 显式 ChanceNode 结构正确，但叶子仅做静态评估（无 playout 阶段）——这是 MCTS 历史上 25-30% 弱于 RolloutAI 的最可能结构性原因；该骨架适合日后接价值网络。
- `record/game_record.py` `MoveRecord`：含 `turn / player / dice / move / state_after / step_seconds / remaining_seconds / source(self|opponent|unknown)`，基础复盘所需数据已齐。`source` 当前表示走子来源，不是独立骰子来源字段；骰子取证脚本必须在报告中声明样本来源语义，不能把 `source="opponent"` 直接当作外部骰子来源的强证据。
- `scripts/tournament.py`：仅胜率矩阵，无 Elo、无持久化。

## 5. 路线图

### R-P0 搬家与转型

1. PR 合并当前文档转型改动到 main（用户要求先 PR 再迁移）。
2. robocopy 迁移到 `E:\computergame`（排除 `.venv/`），`git fsck` 校验，重建 `.venv`，全量 pytest + preflight 验证迁移无损。
3. pip 缓存指向 E 盘；建 `data/`（训练数据/天梯结果）与 `models/`（权重）目录约定，两者已加入 `.gitignore`。缓存配置优先用单次命令环境变量或 `--cache-dir`，不默认修改全局环境变量或用户级 pip 配置；如需持久配置，先单独确认。
4. C 盘旧目录保留，由用户验证后自行处置。

执行边界：R-P0 涉及 PR、迁移、重建虚拟环境和缓存配置，均属于需要用户确认的操作；本文只定义顺序和验收，不授权自动执行 `git commit`、`git push`、目录删除、全局配置修改或依赖安装。

### R-P1 地基

1. **性能基线与纯 Python 提速**：`scripts/perf_probe.py` 建立 playouts/sec、每步 clone 次数、合法步生成次数、GreedyAI/RNG 构造次数等基线；优化 `GameState` 内部信任快路径、rollout 局面复制/复用、`_playout` 对象复用、合法步生成分配削减；固定 seed 等价性回归保证行为不变；目标 playouts/sec ≥5x。`apply_move` 继续保持公开校验语义，快路径只能作为内部受控 API 使用。若对象复用改变 RNG 消耗顺序或并列打破结果，该改动不得归类为“行为不变性能优化”，必须作为新 AI 候选进入天梯验证。Rust 扩展此阶段不做（等天梯证明算力是瓶颈）。
2. **持久 Elo 天梯**：`scripts/ladder.py`——选手注册（kind + kwargs + 签名）、增量赛程、Elo±不确定度；P14 默认 = 1500 锚点；对局 JSONL 入 `data/ladder/`，报告入 `reports/ladder/`。研究模式"门禁"重定义为天梯 Elo 显著高于锚点。
3. **真实棋谱复盘 + 骰子取证**：`scripts/replay_analyze.py`（吃 GameRecord/MatchRecord JSON，失败桶标注 + 逐步与默认 AI 推荐对比）；`scripts/dice_forensics.py`（按可证明的样本来源分组做卡方均匀性检验 + "我方有破门威胁时对方掷中吃子点数"的条件巧合度检验，输出样本口径、p 值与效应量）。若现有棋谱缺少独立骰子来源字段，脚本必须降级为“走子来源分组的骰子序列审计”，不得输出超出数据口径的作弊结论。
4. `requirements-research.txt`（numpy 先进，torch 到 R-P2B 再装）；core 保持零依赖，GUI/release 路径不导入研究依赖。

### R-P2A 经典搜索线

新技术假设：depth=1 朴素 expectimax 的历史失败（45%）归因于无深度无剪枝；TT + move ordering + Star1/Star2 + 迭代加深为 EWN 文献标准配置，预期把有效深度推到 4-6。

- E1：`ExpectimaxV2` 加 Zobrist 置换表、move ordering（吃子/进角/威胁削减优先）、迭代加深与时间管理。
- E2：Star1/Star2 机会节点剪枝。前置条件：先定义搜索值域上下界（例如归一化到固定区间，或证明 `WIN_SCORE` 与非终局 eval 的夹逼关系），并用小深度穷举 expectimax 对照测试证明剪枝结果与未剪枝一致。
- E3：终局精确求解器——少子/近终局局面无截断精确 expectimax（TT 缓存）；retrograde 残局库远期再议。
- Zweistein-DP 表（`ai/zweistein_dp.py`，P9 遗产）复用为 eval/ordering 特征。

### R-P2B 自对弈学习线

- L0：`MCTSAI._leaf_score` 加 playout 选项，天梯对照验证"叶子静态评估是 MCTS 弱因"诊断。
- L1：评估权重自动调参（SPSA/CEM，目标=天梯 Elo），先调 `zweistein_lite_score` / greedy_risk 权重。
- L2：价值网络 V(s)（PyTorch + GPU）替换 cutoff_eval / leaf eval；自对弈数据入 `data/selfplay/`。
- L3：AZ-lite：policy+value 双头 + PUCT-MCTS + 自对弈迭代闭环；权重入 `models/`。

### R-P3 可选后续（按天梯数据决定）

Rust core 热路径重写；外部开源 EWN bot 接入对手池（`adapters/` 兑现）；720 布局 × 强 AI 的布局-策略联合研究。

## 6. 验收口径

- 棋力结论一律来自持久天梯（games、seed、Elo±CI 入库）。
- 行为不变的性能优化必须带固定 seed 等价性回归测试；pytest 全绿。
- 每个研究项动手前先写技术假设与判停条件（沿用 stop list 的防再开闸纪律）。

## 7. 用户动作项（非阻塞）

- 省赛比赛机上的真实棋谱 JSON 拷回 `records/`（供 R-P1.3 复盘与取证；该目录已 gitignore，不会入库）。
- 迁移验证通过后自行处置 C 盘旧目录。
