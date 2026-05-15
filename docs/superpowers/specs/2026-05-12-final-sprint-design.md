# 赛前收官冲刺 Design Spec

> 历史设计稿（2026-05-12），已被 2026-05-15 状态取代：`release/v1.0` 已生成，S2 真实 GUI 手测已完成，当前默认 AI 为旧 flat `rollout`，adaptive rollout 不是 release 默认。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

Date: 2026-05-12
Status: Review-Ready
Scope: S2 真实 GUI 闭环 -> S3 低风险 AI 与 harness -> S4 封版提交
Deadline: 2026-05-18

---

## 0. 项目全貌快照

### 0.1 项目定位

本项目是面向 2026 年辽宁省大学生计算机博弈大赛校内选拔赛的爱恩斯坦棋离线 GUI 参赛程序。现场默认不联网、不依赖统一平台，由操作员录入骰子点数和对方走法，程序维护局面、校验合法性、计时、保存棋谱，并输出我方推荐走法。

核心价值排序固定为：

```text
规则正确 > 现场稳定 > GUI 可操作 > 默认 AI 强度 > 数据化 AI 增强 > 开局与参数优化 > 界面美观
```

当前策略不是放弃 AI，而是防止赛前把未经验证的 AI 实验塞进比赛默认路径。所有 AI 候选必须用本地 harness 数据证明强于当前默认 `greedy_risk`，否则默认 AI 保持不变。

### 0.2 已确认规则事实

- 棋盘为 5x5。
- 双方各 6 枚棋子，编号 1-6。
- 红方目标角为右下角 `(4, 4)`，蓝方目标角为左上角 `(0, 0)`。
- 红方可向下、右、右下走一格；蓝方可向上、左、左上走一格。
- 目标格有棋子时吃掉该棋子，包含本方棋子。core 已在 R-0 后合规。
- 骰子点数对应编号棋子；若该编号已死，选择编号距离最近的存活棋子；两侧等距时均可选。
- 到达目标角或吃光对手立即获胜；比赛没有和棋。
- 每盘每方 4 分钟包干，超时判负。
- 每轮最多 7 盘，先胜 4 盘为本轮胜方。
- 甲方第 1/4/5 盘先手，乙方第 2/3/6/7 盘先手。
- 程序崩溃判负，所以自动保存和恢复能力比实验性 AI 更重要。
- 比赛过程中不允许联网。

规则真值以 `docs/RULE_ASSUMPTIONS.md` 为准。任何规则变化必须先改 `core/` 和测试，再接 GUI 或 AI。

### 0.3 当前架构

```text
core/       规则引擎：GameState、Move、rules、types；不依赖 GUI/AI
ai/         AI 层：random、greedy、risk、evaluator、expectimax、match harness、opening layouts
gui/        Tkinter GUI：main_window、board_widget、opening_panel、match_mode、timer_panel
record/     棋谱与持久化：game_record、match_record、auto_save、serializer
tests/      pytest 自动测试；数量以最新 pytest 输出为准，不在文档中写死
scripts/    本地入口：run_gui.py、quick_bench.py、smoke_test.py、s2_rehearsal.py
reports/    bench、演练、参数、开局和封版报告
release/    封版产物，当前尚未生成 v1.0
```

分层边界：

- `core/` 只表达规则语义，不知道 GUI、record、AI。
- `gui/` 只展示状态、收集输入、调用 `core/ai/record`，不得复制合法步或胜负逻辑。
- `ai/` 可以模拟和评估，但必须通过 `GameState.legal_moves()` 与 `GameState.apply_move()` 使用规则。
- `record/` 负责持久化和恢复，不决定规则。
- `adapters/` 只在确认统一平台协议后新增适配层，短期不做。

### 0.4 当前状态

| 模块 | 状态 | 结论 |
|---|---|---|
| 规则引擎 | 已完成 | R-0 后允许吃本方子，规则与官方描述对齐。 |
| 开局录入 | 已完成 | GUI 支持预设、自定义、录入对方布局，并写入棋谱 metadata。 |
| 单局 GUI | 已完成 | 棋盘、骰子、合法走法、推荐、悔棋、重置可用。 |
| 棋谱与计时 | 已完成 | JSON 棋谱、加载恢复、4 分钟包干计时可用。 |
| 七盘制比赛 | 已完成 | R-2 主链路完成，甲乙身份、先手序列、比分推进可用。 |
| 崩溃自救 | 已完成 | 盘内与整轮 auto-save 已实现并有测试。 |
| S2 自动演练 | 已完成 | `scripts/s2_rehearsal.py` 8/8 PASS。 |
| S2 真实 GUI 手动演练 | 未完成 | `reports/gui-rehearsal.md` 第 4 节仍待填写。 |
| 默认 AI | 可用 | GUI 默认使用 `greedy_risk`，这是当前参赛基线。 |
| Expectimax | 实验性 | R-0 后合并胜率 45.0%，弱于 `greedy_risk`，不能作为默认 AI。 |

### 0.5 核心判断

担心 AI 太弱是合理的，但直接把主线改成“优先重写 AI”风险更高：

1. 现场一旦 GUI 流程、恢复、计时或开局录入出错，AI 再强也无法发挥。
2. 当前 `greedy_risk` 不是随机 AI，已通过 4.1/4.2 合规重跑门槛，是稳定参赛基线。
3. Expectimax 已有实测负收益，说明赛前盲目加深搜索或换框架不可靠。
4. AI 提升必须避免单 seed、单方向、小样本造成的假阳性。
5. 离比赛截止只剩数天，默认策略应是“稳定版本兜底 + 小时间盒 AI 增强”。

因此本设计采用：先补齐 S2 真实 GUI 闭环，再做 harness 可信度与低风险 AI 优化，最后封版。实验性 AI 只作为候选，不得绕过晋升门禁。

---

## 1. 收官路线

### 1.1 阶段顺序

```text
S0  基线验证
A   S2 真实 GUI 手动演练闭环
B   Harness 工程化 + R-0 followup 清理
C   低风险 AI 增强：参数搜索 + 开局搜索 + self-capture 评估
D   实验性 AI：ExpectimaxV2 / Rollout，严格时间盒
E   Release v1.0 封版与提交检查
```

执行原则：

- A 是 P0，必须先完成。没有真实 GUI 手测记录，不进入“完整 S2 已完成”的结论。
- B 是 AI 工作的前置条件。没有置信区间和 pairwise matrix，参数搜索结果可信度不足。
- C 是主力 AI 增强路径，优先追求确定性、小改动、可回滚。
- D 是实验路径，不能阻塞封版，不能因单局或小样本结果替换默认 AI。
- E 只修 bug、补报告、锁配置，不做大功能。

### 1.2 时间盒建议

| 日期 | 重点 | 产物 | 停止条件 |
|---|---|---|---|
| 5/12 | S2 真实 GUI 手动演练 | `reports/gui-rehearsal.md` 第 4 节填完 | 发现 P0 现场问题则先修 GUI/record。 |
| 5/12-13 | harness 工程化与 stuck 清理 | CI、tournament、无 `stuck_penalty` 准死代码 | pytest 或 smoke 失败必须先修。 |
| 5/13-14 | 参数搜索、开局搜索、self-capture 实验 | 参数报告、开局报告、候选 AI 数据 | 候选未过 gate 不进默认。 |
| 5/14-15 | ExpectimaxV2 或 Rollout 时间盒 | 实验报告 | 半天内无正向数据即停止。 |
| 5/15-17 | release/v1.0 封版 | release 包、测试报告、已知限制 | 不再做新 AI 框架。 |
| 5/18 | 最终检查与提交 | 可运行程序、源码、文档材料 | 只做检查和备份。 |

### 1.3 明确不做

- 不引入 PyTorch、Gymnasium、Stable-Baselines3、OpenSpiel 运行时依赖。
- 不联网下载模型、数据或在线服务。
- 不在 GUI 中复制规则逻辑。
- 不以 OpenSpiel、ewn-gym 或任何外部仓库作为规则真值来源。
- 不用单局胜负决定参数或默认 AI。
- 不在封版阶段做大规模重构。
- 不执行 `git commit`、`git push`、`git reset --hard`，除非用户明确要求。

---

## 2. 质量门禁

### 2.1 通用基线

任何阶段开始前至少确认：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

涉及 GUI 现场流程时还要运行：

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

涉及 AI 默认候选时还要双边 bench：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026
```

### 2.2 AI 晋升门禁

替换 GUI 默认 AI 或 release 默认 AI 前，候选必须同时满足：

1. Candidate vs 当前默认 AI（历史上下文为 `greedy_risk`；2026-05-15 后为旧 flat `rollout`）：红蓝各 200 局，共 400 局。
2. Candidate vs `greedy`：红蓝各 200 局，共 400 局。
3. Candidate 对当前默认 AI 合并胜率 > 55%。
4. Wilson 95% CI 下界不低于 50%，否则视为证据不足。
5. `illegal_moves = 0`。
6. `crashes = 0`。
7. 基于 bench 聚合的真实 `timeouts = 0`；历史 legacy timeout 字段不可单独作为晋升证据。
8. `avg_step_time_ms < 1000`。
9. `max_step_time_ms < 5000`。
10. 报告写入 `reports/`，包含命令、seed、games、布局、AI signature、pytest/smoke 状态。

如果候选只在小样本或单方向胜出，只能保留为实验入口，不进入默认 GUI。

### 2.3 开局晋升门禁

替换 GUI 默认布局或 release 推荐布局前，候选必须满足：

1. 至少对当前默认布局做双边对比。
2. 至少 400 局总样本，红蓝角色都覆盖。
3. 与当前默认相比合并胜率 > 53%，且 Wilson CI 下界不低于 50%。
4. 不增加无合法步、非法走法、崩溃或超时。
5. 能在 GUI `OpeningPanel` 下拉中明确选择。
6. 报告说明布局适用风格：均衡、速攻、防守或实验。

### 2.4 封版门禁

release/v1.0 完成前必须满足：

- pytest 全量通过。
- smoke test 通过。
- S2 headless 演练通过。
- S2 真实 GUI 手动表已填写。
- GUI 可离线启动。
- auto-save 恢复路径可用。
- 默认 AI 为 `greedy_risk` 或通过 AI 晋升门禁的候选。
- release README 写明启动、操作、恢复、已知限制。
- 无网络依赖。
- 无未解释的 `stuck_penalty` 准死代码残留。

---

## 3. Phase A - S2 真实 GUI 手动演练闭环

### 3.1 目标

补齐 headless 自动化无法覆盖的真实 Tk GUI 人工视觉与交互验证，确认现场操作员能按比赛流程使用程序。

### 3.2 要更新的文件

- `reports/gui-rehearsal.md`

### 3.3 必填场景

1. 启动程序，进入比赛模式，选择我方甲乙身份和红蓝颜色。
2. 完整跑通一轮 4:0。
3. 完整跑通一轮 4:3，重点验证第 7 盘先手显示。
4. 盘中崩溃恢复：杀掉 Python，重启，接受恢复，检查局面、计时、棋谱。
5. 盘间崩溃恢复：结束一盘后崩溃，重启，检查比分和下一盘状态。
6. 误操作恢复：悔棋、加载棋谱、拒绝错误恢复。
7. 整轮结束后操作：保存、重置、进入下一轮或 debug 模式。

### 3.4 验收

`reports/gui-rehearsal.md` 第 4 节所有表格必须填具体结果。发现问题时不要只写“失败”，要记录：

```text
复现步骤
实际结果
期望结果
影响等级：P0/P1/P2/P3
是否阻塞封版
建议修复文件
```

---

## 4. Phase B - Harness 工程化与 R-0 followup

### 4.1 为什么先做 harness

参数搜索和 AI 实验如果没有置信区间、AI signature、双边对战矩阵，很容易把随机波动误判为提升。赛前 AI 增强必须先把评测工具做可信。

### 4.2 需要补齐的能力

- `scripts/quick_bench.py` 输出 Wilson 95% CI。
- `scripts/tournament.py` 输出 pairwise matrix。
- bench JSON 包含 seed、games、layout、AI signature、illegal/crash/timeout、step time。
- `reports/tournament_matrix.md` 可作为后续实验基线。

### 4.3 R-0 followup

R-0 后允许吃本方子，`stuck_penalty` 基本成为准死代码。应在 AI 大量实验前清理，避免后续参数、报告和 CLI 继续围绕无效权重展开。

清理范围：

- `ai/evaluator.py` 删除 `STUCK_PIECE_PENALTY` 和 `count_stuck_pieces()`。
- `evaluate()` 删除 `stuck_penalty` 参数。
- `ai/greedy_ai.py` 删除 `stuck_penalty` 属性和转发。
- `ai/match.py` 删除 signature 中的 `stuck_penalty`。
- `scripts/quick_bench.py`、`scripts/run_match.py`、`scripts/_bench_meta.py` 删除对应 CLI 与 metadata。
- 测试同步更新。

注意：这是有回归风险的 API 清理，不要放到 release freeze 最后一天。

### 4.4 self-capture 评估

允许吃本方子后，评估函数缺少“主动自残换取机动性或胜率”的建模。建议作为低风险实验，不直接进入默认：

- 新增独立 helper，先返回可解释的 mobility gain 分数。
- 默认权重保持 0，避免未验证逻辑影响当前 `greedy_risk`。
- 用 candidate AI 显式启用权重进行 harness 对比。
- 只有过 AI 晋升门禁才允许调整默认权重。

---

## 5. Phase C - 低风险 AI 增强

### 5.1 参数搜索

目标是调优现有 `GreedyAI` 和 `evaluate()` 权重，不改搜索框架，不改 core，不引入依赖。

候选参数：

```text
distance_weight
material_weight
expected_risk_weight
expected_win_risk_weight
self_capture_weight（若 Phase B 实现，默认 0）
```

搜索纪律：

- 训练 seed 与验证 seed 分离。
- 小样本用于筛选，大样本用于确认。
- 不用单 seed 结果改默认。
- 每个候选写入报告，包含参数、seed、games、CI、稳定性字段。
- 最终只保留少数有证据的候选，避免 release 配置混乱。

### 5.2 开局搜索

当前 `ai/match.py` 的 `STARTING_LAYOUT_ID` 只影响 harness 默认开局；真实 GUI 默认下拉是 `OpeningPanel.layout_var = "balanced_v1"`。因此开局搜索的落地必须同时考虑：

- harness 默认布局。
- `ai/opening_layouts.py` 的 `PRESETS`。
- GUI 开局下拉默认值。
- release README 对推荐布局的说明。

推荐策略：

1. 先枚举或采样红方 720 种出发区排列。
2. 蓝方先用镜像布局和现有三类预设作为对手。
3. 小样本筛选 top 10。
4. 用独立 seed 扩大样本复验。
5. 只把通过门禁的布局加入 `PRESETS`，命名如 `balanced_tuned_v1`、`aggressive_tuned_v1`。
6. 是否改 GUI 默认必须另走开局晋升门禁。

### 5.3 默认 AI 变更策略

优先选项：

- 如果无候选过 gate，release 保持 `greedy_risk`。
- 如果参数候选过 gate，新增 `greedy_risk_tuned` 或更新 `greedy_risk` 默认，但必须同步 GUI 和 release 配置。
- 如果只有开局候选过 gate，默认 AI 不变，只更新推荐布局。
- 如果 AI 和开局都过 gate，先分别验证，再做组合验证，避免无法归因。

---

## 6. Phase D - 实验性 AI

### 6.1 ExpectimaxV2

现有 `ExpectimaxAI(depth=1)` 已实测弱于 `greedy_risk`。后续不能写成“已确认 chance node 错误”，而应作为实验假设处理。

实验假设：

- H1：当前 risk evaluator 与 lookahead 语义错位，关闭 leaf risk 后提升。
- H2：显式区分 player node 与 chance node 后更容易控制 depth 和风险项。
- H3：turn-aware risk 比默认“总是假设对手下一手”更适合搜索。
- H4：depth=2/3 只有在 H1-H3 正向且 step time 合格后才值得尝试。

实现边界：

- 新建 `ai/expectimax_v2.py`，不破坏 `ai/expectimax_ai.py`。
- 先注册 `build_ai("expectimax_v2")`，再跑 quick_bench。
- quick_bench 需要先支持传递 depth、heuristic、risk 参数，否则实验命令不可执行。
- `GameState` 当前没有 `clone()`；模拟必须使用 `apply_move()/undo_move()` 或 `serialize()/deserialize()`。
- depth=0 必须与同 evaluator 的 Greedy 选择一致。
- timeout 必须返回合法 move 或 fallback 到 greedy/random legal move，不得崩溃。

晋升策略：

- ExpectimaxV2 默认只是候选。
- 未过 AI 晋升门禁时，不接 GUI 默认。
- 即使 E0/E1 小样本好看，也必须完成双边 400+400 gate。

### 6.2 RolloutAI

Rollout 是兜底实验，不是 MCTS。它适合做小时间盒对比，但风险是耗时和随机性。

实现边界：

- 新建 `ai/rollout_ai.py`。
- 每个候选 move 做有限随机 rollout。
- 必须有 `max_turns` 和 `time_limit_ms`。
- 必须支持 seed，保证可复现。
- 必须有 greedy fallback。
- 未过 AI 晋升门禁时只作为实验入口。

---

## 7. Phase E - Release v1.0

### 7.1 release 目录

```text
release/v1.0/
├── README.md
├── config.json
├── default_params.json
├── test_report.md
├── sample_records/
└── known_limitations.md
```

如果复制源码快照，必须说明来源和生成方式；不要手工复制一半源码造成不一致。更稳妥的做法是在 release README 中说明从项目根目录运行，并把 `release/v1.0/` 作为配置、报告和操作说明目录。

### 7.2 release README 必须包含

- Python 版本。
- 如何启动 GUI。
- 如何进入比赛模式。
- 如何选择甲乙身份和开局。
- 如何录入骰子和对方走法。
- 如何读取推荐走法。
- 如何保存棋谱。
- 如何处理崩溃恢复。
- 如何处理误操作。
- 如何验证离线运行。
- 默认 AI 和默认布局说明。
- 已知限制。

### 7.3 最终检查

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026
rg "import socket|import urllib|import requests" --glob "*.py"
rg "stuck_penalty" --glob "*.py"
```

`rg stuck_penalty` 的目标是 Python 文件为 0。历史报告或说明文档中可以出现，但必须注明是已删除的历史概念。

---

## 8. 外部参考使用边界

### 8.1 ewn-gym

可借鉴：

- 显式 chance node 的组织方式。
- 简单 rollout 结构。
- 一些 heuristic idea。

不可照搬：

- Gymnasium API。
- Stable-Baselines3 或深度学习部分。
- evaluator 细节。
- 任何与本项目 core 规则冲突的规则实现。

### 8.2 OpenSpiel

可借鉴：

- chance node 建模思路。
- 720 种开局排列搜索思路。
- 对外部 benchmark 的报告结构。

不可照搬：

- OpenSpiel 依赖。
- C++ 规则代码。
- OpenSpiel 作为规则真值。

---

## 9. 给后续 AI 工作者的交接提示

接手前必须先读：

1. `PROJECT_MEMORY.md`
2. `PROJECT_PHASES.md`
3. `README.md`
4. `docs/RULE_ASSUMPTIONS.md`
5. `docs/PROJECT_BRIEF.md`
6. 本 design spec
7. `docs/superpowers/plans/2026-05-12-final-sprint-plan.md`

执行时必须遵守：

- 先读后写。
- 先测试后修改默认 AI。
- 修改规则先 core + tests，不能在 GUI 或 AI 里补规则。
- AI 候选必须有 reports 数据。
- GUI 默认路径宁可稳定，不要为了小样本 AI 收益冒现场风险。
- 不执行 git commit/push/reset，除非用户明确要求。

---

## 10. 交付清单

- [ ] `reports/gui-rehearsal.md` 第 4 节真实 GUI 手动表填写完成。
- [ ] `scripts/quick_bench.py` 输出 Wilson CI。
- [ ] `scripts/tournament.py` 输出 pairwise matrix。
- [ ] `reports/tournament_matrix.md` 生成。
- [ ] `stuck_penalty` 已从 Python 代码中清理，或明确记录为未完成且不阻塞。
- [ ] self-capture 评估有实验报告，若未过 gate 不进入默认。
- [ ] 参数搜索报告生成。
- [ ] 开局搜索报告生成。
- [ ] 默认 AI 仍为 `greedy_risk`，或候选已完整通过 AI 晋升门禁。
- [ ] 默认布局仍为稳定布局，或候选已完整通过开局晋升门禁。
- [ ] `release/v1.0/` 完整。
- [ ] pytest、smoke、S2 rehearsal、GUI 手测均有记录。
- [ ] 无网络依赖。
- [ ] 已知限制写入 release 文档。
