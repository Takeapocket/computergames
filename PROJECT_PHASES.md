# 爱恩斯坦棋参赛程序阶段规划

更新时间：2026-05-16（P3 受控默认替换后同步默认 AI 参数和候选状态）
项目目标：2026 年辽宁省大学生计算机博弈大赛校内选拔赛  
项目方向：离线 GUI 参赛程序

本文件是项目后续规划的唯一主入口：记录阶段顺序、当前优先级、验收门槛和 AI 研究路线。规则细节写入 `docs/RULE_ASSUMPTIONS.md`；项目事实快照写入 `PROJECT_MEMORY.md`；具体任务执行计划写入 `docs/superpowers/plans/`；实验数据写入 `reports/`。

---

## 1. 总目标与优先级

目标是在比赛现场交付一个离线、稳定、可操作、可解释的爱恩斯坦棋程序。现场价值优先于算法复杂度。

```text
规则正确 > 现场稳定 > GUI 可操作 > 默认 AI 强度 > 数据化 AI 增强 > 开局与参数优化 > 界面美观
```

当前默认假设：比赛现场不依赖网络和统一平台。操作员录入骰子、录入对方走法，程序维护局面、校验合法性、输出我方建议走法。若后续确认统一平台或 API，只在 `adapters/` 增加适配层，不修改 core 规则语义。

---

## 2. 当前状态快照

| 模块 | 状态 | 结论 |
|---|---|---|
| 规则引擎 `core/` | 已完成 | 5x5、骰子映射、吃子、吃本方子、胜负、撤销、序列化已实现；R-0 后规则与国赛“目标格有棋子即吃掉”一致。 |
| 最小 GUI | 已完成 | Tkinter 棋盘、骰子录入、合法走法、悔棋、重置、AI 推荐已具备。 |
| 棋谱与计时 | 已完成 | JSON 棋谱、加载恢复、单方 4 分钟包干计时已具备。 |
| 开局录入 R-1 | 已完成 | 支持预设布局、自定义布局、录入对方布局，并写入棋谱 metadata。 |
| 崩溃自救 R-3 | 已完成 | `record/auto_save.py`、启动恢复、走子/悔棋自动保存已实现并有测试。 |
| 七盘制 R-2 | 已完成 | `gui/match_mode.py`、`record/match_record.py`、`auto_save_match` 已落地；R-2 review Critical+Important 修复已合并；甲乙身份选择、先手序列、盘内/整轮 auto-save 全链路打通。 |
| S2 GUI 全流程演练 | 已完成 | `scripts/s2_rehearsal.py` 8/8 PASS；`docs/MATCH_CHECKLIST.md` + `docs/EMERGENCY_GUIDE.md` 落地；2026-05-13 操作员真实 Tk GUI 手动表填写完成（`reports/gui-rehearsal.md` §4，21/21 正常）。 |
| 默认 AI | 已晋升 | `rollout` 作为当前默认参赛 AI；`greedy_risk` 保留为应急回退。2026-05-16 起 release 默认参数为 P3 promotion 通过的显式 rollout kwargs：32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、risk-aware playout、Zweistein cutoff、30ms deadline safety。 |
| Adaptive rollout | 实验候选 | 32 初采样 + close sample 到 128 + 低置信提示已实现为显式参数候选，但 direct vs old rollout 800 局合并胜率 59.00%，未达 60% 默认晋升线，不进入 `release/v1.0/default_params.json`。 |
| Rollout 根节点诊断 P1 | 已完成 | `RolloutAI.last_root_stats` + `RootMoveStats` 已成为 canonical 诊断接口，`last_diagnostics` 保持兼容；GUI 优先显示 root stats，并展示 visits / score / winrate / wins / losses / draws / avg / 低置信标记。默认 AI 参数和 release 配置未变。 |
| Rollout 候选 P2 | 已完成，未晋升 | 已注册 `rollout_32` / `rollout_risk_playout` / `rollout_cutoff_eval` 并生成 candidate 报告。三者均未过门禁：`rollout_32` 胜率 54.5% 且 timeouts=4；`rollout_risk_playout` 胜率 57.0% 但 timeouts=10；`rollout_cutoff_eval` 胜率 57.5% 但 timeouts=11。默认 AI 和 release 配置不变。 |
| Rollout deadline safety P2.5 | 已完成，1 个 survivor | `RolloutAI.deadline_safety_ms` 默认 0.0，不改变旧 rollout；P2.5 profile 仅给 `rollout_risk_playout` / `rollout_cutoff_eval` 传 30.0。复验只跑这两个候选，各双边 100+100、对手 rollout。`rollout_cutoff_eval` 胜率 57.0% 且 timeouts=0，标记为 P2.5 survives；`rollout_risk_playout` 胜率 58.5% 但总 timeouts=1，未过总门禁。默认 GUI/release 不变。 |
| Zweistein-lite P3 | promotion 通过，已替换工作默认 | 新增 `zweistein_lite_score()`，注册 `greedy_zweistein` / `rollout_zweistein_cutoff` / `expectimax_zweistein_d1`。`rollout_zweistein_cutoff` candidate vs rollout 双边 100+100：胜率 58.0%，timeouts=0；promotion vs old rollout 双边 400+400：胜率 56.75%，Wilson lower 53.29%，timeouts=0。2026-05-16 已按用户批准受控替换为 GUI/release 工作默认，但实现仍使用 `kind="rollout"` + 显式 kwargs。 |
| Expectimax | 实验性 | `depth=1` 合并胜率 45.0%，弱于 `greedy_risk`，不能作为默认参赛 AI。 |

下一步主线：**release/v1.0 归档/赛前核对；P3 promotion 参数已受控替换为 GUI/release 工作默认。不要自动进入 P4；只有用户明确要求时再进入 MCTS opponent node -> P5 开局搜索。比赛后再推进 Expectimax 结构修复。**
详细方案见：`docs/superpowers/specs/2026-05-12-final-sprint-design.md`
执行计划见：`docs/superpowers/plans/2026-05-12-final-sprint-plan.md`

---

## 3. 开发纪律

- Core-first：规则变化必须先改 `core/` 和测试，再接 GUI 或 AI。
- Harness-first：AI 强弱必须用批量对战数据证明，不能靠单局印象。
- GUI 不复制规则：GUI 只展示状态、收集输入、调用 core/ai/record。
- 小步迭代：每次只改一个明确能力，输出可运行、可测试的最小结果。
- 不默认执行 `git commit`、`git push`、`git reset --hard`、删除文件、批量移动文件或全局安装依赖。
- 不引入联网依赖；比赛版本必须离线可运行。
- 不优先深度学习；短期采用规则评估、风险枚举、搜索、rollout、开局搜索和参数评测。

---

## 4. 赛前主线阶段

### S0：基线验证

目标：每次进入新功能前确认仓库处于可开发状态。

输出：

```text
pytest 全量或相关测试结果
scripts/smoke_test.py 结果
必要时 quick_bench 基线结果
```

验收：

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

进入下一阶段条件：测试通过；若失败，先定位并修复与当前任务相关的问题。

---

### S1：R-2 七盘制比赛模式

状态：已完成。  
优先级：P1，赛前必须。

目标：把当前单局 GUI 升级为赛事规则要求的“每轮最多 7 盘，先胜 4 盘”的比赛流程。

关键规则：

```text
每轮最多 7 盘
先胜 4 盘为本轮胜方
甲方第 1/4/5 盘先手
乙方第 2/3/6/7 盘先手
甲/乙身份不能等同于红/蓝颜色，GUI 必须显式询问或记录
两盘中间不休息，结束一盘后快速进入下一盘开局录入
```

建议输出物：

```text
gui/match_mode.py          # 显示本轮第几盘、比分、甲乙身份、当前先手
gui/main_window.py         # 对局结束后推进盘数，触发下一盘开局录入
record/match_record.py     # 聚合一轮内最多 7 个 GameRecord
tests/test_match_mode.py   # 先手序列、比分、先胜 4 盘、最多 7 盘
tests/test_match_record.py # 一轮记录序列化/反序列化
```

验收标准：

```text
GUI 显示“第 X 盘 / 比分 a:b / 本盘先手 / 我方甲乙身份”。
开始一轮时可选择我方是甲方还是乙方。
盘 1/4/5 由甲方先手，盘 2/3/6/7 由乙方先手。
单盘结束后可记录胜方并进入下一盘开局录入。
任一方 4 胜后显示本轮胜方并停止继续开新盘。
pytest 通过；GUI 手动演练至少跑通一轮 4:0 和一轮 4:3 的流程。
```

边界：本阶段不优化 AI、不做打包、不新增平台 API。

---

### S2：GUI 全流程演练与现场打磨

状态：已完成（2026-05-13）。
优先级：P1，赛前必须。

完成记录：详见 `reports/gui-rehearsal.md`。`scripts/s2_rehearsal.py` 8/8 PASS；
`docs/MATCH_CHECKLIST.md` 与 `docs/EMERGENCY_GUIDE.md` 已落地；现有 pytest
已实质覆盖 R-2 后 GUI 回归；2026-05-13 操作员真实 Tk GUI 手动表
（`reports/gui-rehearsal.md` §4，21 项）全部"正常"，S2 完整闭环。

目标：验证完整比赛操作链路，而不是单个控件可用。

演练路径：

```text
启动程序
选择甲乙身份
选择/录入双方开局
录入骰子
录入对方走法
查看我方推荐走法
执行我方走法
保存/自动保存棋谱
悔棋/恢复
结束单盘
进入下一盘
结束整轮
重启程序并恢复 auto_save
```

建议输出物：

```text
docs/MATCH_CHECKLIST.md     # 现场操作检查清单
docs/EMERGENCY_GUIDE.md     # 崩溃、误操作、超时的处理说明
tests/test_main_window.py   # 补齐 R-2 后 GUI 状态回归
reports/gui-rehearsal.md    # 手动演练记录
```

验收标准：

```text
连续模拟至少 3 盘不崩溃。
至少手动跑通一轮 4 胜流程。
误操作可通过悔棋或加载棋谱恢复。
auto_save 恢复后局面、棋谱、计时状态一致。
GUI 不依赖网络。
```

---

### S3：AI 低风险清理与 harness 工程化

状态：已完成（2026-05-12 收官冲刺 Task Group 01-02）。
优先级：P2，不能阻塞 S1/S2。

目标：清理 R-0 后的死代码，增强评测可信度，为后续 AI 研究建立更干净的实验基础。

建议任务：

```text
删除或退役 stuck_penalty 相关准死代码
评估 self-capture 的战略价值，决定是否加入 evaluator 或 risk 模块
为 quick_bench 增加胜率置信区间
增加 pairwise tournament，输出多 AI 对战矩阵
保留 slim JSON 默认格式，必要时用 --include-per-game 输出复现细节
```

验收标准：

```text
pytest 通过。
quick_bench 仍可复现 4.1/4.2 基线。
所有 AI 对战报告包含 games、seed、胜率、非法走法、崩溃、真实 timeout telemetry、平均步时、最大步时。2026-05-15 前生成的部分历史报告 timeout 字段为 legacy 常量，不能单独作为新候选晋升证据。
新增评估项必须直接对当前 GUI/release 默认 `rollout` 配置（P3 promotion 显式 kwargs）胜率达标，才允许进入默认 AI。
```

---

### S4：封版准备

状态：已完成（2026-05-13，S2 全部手测项填表完成后整体 sign-off）。
优先级：P1，比赛前最后阶段。

目标：冻结比赛版本，降低现场风险。

输出物：

```text
release/v1.0/
release/v1.0/README.md
release/v1.0/config.json
release/v1.0/default_params.json
release/v1.0/test_report.md
release/v1.0/sample_records/
docs/MATCH_CHECKLIST.md
docs/EMERGENCY_GUIDE.md
```

封版原则：

```text
只修 bug，不做大功能。
不临时换 AI 框架。
不临时引入新依赖。
不在比赛电脑上做未经测试的修改。
不因单局输赢临时大调参数。
```

验收标准：

```text
pytest 全部通过。
GUI 可离线启动。
开局录入、计时、棋谱、auto_save、七盘制流程正常。
当前默认 AI 为 `rollout` kind + P3 promotion 显式参数；`greedy_risk` 仅作为应急回退。后续候选必须直接对当前默认 `rollout` 配置过门禁后才可替换。
无非法走法、无崩溃、无超时。
有源码和可运行版本备份。
```

---

## 5. AI 与开局研究路线

本节是赛场闭环完成后的研究路线。任何 AI 候选进入默认版本前，都必须通过 harness 数据验证。

### A1：Expectimax 修复实验

当前结论：`ExpectimaxAI(depth=1)` 在 R-0 合规规则下合并胜率 45.0%，弱于 `greedy_risk`。问题主要不是性能，而是 evaluator 的风险项与 lookahead 语义错位。

实验顺序：

```text
E0 裸 Expectimax：关闭 expected_risk_weight 和 expected_win_risk_weight，对比裸 greedy。
E1 leaf 关闭 risk：搜索叶子只用零和基础评估，避免双重计算下一轮风险。
E2 turn-aware risk：让风险函数显式接收“下一手行动方”，不默认总是对手。
E3 transposition table：缓存局面、深度、行动方、骰子节点。
E4 move ordering：优先直接胜利、阻止直接胜利、吃子、降低风险、推进关键子。
E5 depth=2/3：只在 E0-E4 数据正向后尝试，并加入单步时间上限。
```

保留条件：

```text
candidate vs current default 合并胜率 > 55%。
illegal_moves = 0，crashes = 0，基于 `quick_bench.py` / `bench_ai.py` 聚合的真实 timeouts = 0。2026-05-15 前 legacy timeout 字段不可单独作为晋升证据。
平均单步耗时和最大单步耗时满足 4 分钟包干预算。
报告写入 reports/，默认 AI 变更必须有复现命令。
```

### A2：Rollout / MCTS 备选实验

外部参考：ewn-gym 的 `MctsAgent` 使用每个候选走法后的随机 rollout 统计胜率，结构简单但不是完整 UCT。当前项目已采用轻量 `RolloutAI` 作为默认推荐 AI，后续只做参数和性能复验，不引入完整 MCTS 框架。

建议实现边界：

```text
RolloutAI 不改 core，只通过 GameState / legal_moves / apply_move 运行模拟。
每个合法走法 rollout N 次，按胜率选。
必须支持时间上限和 greedy fallback。
继续用 random/greedy/greedy_risk 做批量复验；默认变更必须保留报告。
```

不做事项：短期不引入 Gymnasium、Stable-Baselines3、AlphaZero 或神经网络训练。

### A3：开局布局搜索

外部参考：OpenSpiel 将双方初始布局建模为 6! = 720 个出发区排列。这个思路适合本项目做开局候选搜索，但不能把 OpenSpiel 的规则实现当作本项目规则来源。

建议路线：

```text
枚举或采样己方 720 种布局。
对每个布局用 current default rollout 跑固定 seed 小样本；`greedy_risk` 只作为辅助对手或应急回退基线。
筛出候选后扩大样本量复验。
保留均衡、速攻、防守三类候选，而不是声称“最优布局”。
```

建议输出物：

```text
scripts/search_openings.py
reports/opening_report.md
ai/opening_layouts.py
```

验收标准：

```text
至少 3 套候选布局有报告数据支撑。
默认布局变更必须 candidate vs current default 胜率有统计优势。
开局搜索不复制 core 规则逻辑，只调用 GameState 和 legal_moves。
```

### A4：参数优化

参数优化只在 harness 工程化后做。每次只调少量参数，避免无法归因。

候选参数：

```text
distance_weight
material_weight
expected_risk_weight
expected_win_risk_weight
self_capture_weight
search_depth
max_step_time_ms
rollout_count
```

验收标准：

```text
固定 seed 池。
candidate vs current default 至少 200 局。
胜率未达标不进入默认配置。
最终参数写入 release 配置并附报告。
```

---

## 6. 外部仓库参考边界

### OpenSpiel

可借鉴：

```text
显式 chance node 建模。
统一 LegalActions / ApplyAction / UndoAction 接口。
初始布局 720 排列的搜索思路。
非空目标格统一 capture，和本项目 R-0 后规则一致。
```

不可照搬：

```text
不引入 OpenSpiel 依赖。
不以 OpenSpiel 作为规则真值来源。
其骰子映射实现更像“缺失时可选最近低编号和最近高编号”，与国赛“最近编号，等距才二选一”的表述不完全一致。
```

### ewn-gym

可借鉴：

```text
pairwise eval 脚本思路。
Expectiminimax 的 chance node 基本结构。
简单 rollout/MCTS 作为后续实验入口。
board 旋转/取反以复用同一策略视角的工程思路。
```

不可照搬：

```text
不引入 Gymnasium/SB3 作为赛前依赖。
不照搬 evaluator；其右下方玩家目标距离计算疑似有问题。
不采用深度学习训练作为短期主线。
```

---

## 7. 常用命令

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026
```

---

## 8. 完成判定

一个阶段只有满足以下条件才算完成：

```text
相关测试通过。
涉及 core、GUI、record 或公共接口时，全量 pytest 通过。
GUI 相关阶段必须有手动演练记录或对应自动测试。
AI 相关阶段必须有 reports/ 数据和复现命令。
默认 AI 或默认布局变更必须证明 candidate 优于 baseline，且稳定性不下降。
文档同步更新 PROJECT_MEMORY.md 或对应报告。
```

当前最近任务：**S2/S3/S4 全部闭环；2026-05-16 已完成 P3 受控默认替换。`rollout` 仍是 GUI/release 默认 AI kind，但默认参数已改为 P3 promotion 通过的 `rollout_zweistein_cutoff` 参数集；`greedy_risk` 保留为应急回退。下一步：release/v1.0 归档与赛前核对；不要自动进入 P4，除非用户明确要求。**
