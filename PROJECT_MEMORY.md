# 爱恩斯坦棋参赛程序项目记忆

更新时间：2026-05-16（P3 受控默认替换后同步；S2/S3/S4 全部闭环）

## 当前结论

- 目标比赛：2026 年辽宁省大学生计算机博弈大赛校内选拔赛，项目选择为"爱恩斯坦棋"。
- 目标不是做命令行工具，而是构建一个离线可运行的 GUI 程序，用于现场比赛。
- 当前最稳假设：现场不依赖统一 API，不联网；双方各自运行自己的程序，由操作员录入骰子、对方走法，并根据程序输出执行本方走法。若后续 QQ 群发布统一平台/API，再新增适配层，不改核心规则引擎和 AI。
- 爱恩斯坦棋有骰子随机性，但程序仍可通过开局布阵、局面评估、期望搜索、蒙特卡洛模拟等方法显著提升胜率。
- **2026-05-11 R-0 已完成**：core 现已合规允许吃本方棋子；4.1 / 4.2 / 4.4 bench 已用合规规则重跑（slim 格式入库），全部门槛通过。详见 `reports/4-1-rebench.md` / `reports/4-2-rebench.md` / `reports/4-4-rebench.md`。
- **2026-05-11 R-1 / R-2 / R-3 已完成**：开局录入 GUI（R-1）+ 七盘制比赛模式（R-2）+ 崩溃自救（R-3）均已实现并通过 324 条 pytest（含 80 条 R-2 新增）。R-2 详见 `reports/r2-rehearsal.md`；R-1 review followup 决策见 `reports/r1-review-followup.md`。
- **2026-05-13 S2 完整闭环**：操作员现场用真实 Tk GUI 跑完 `reports/gui-rehearsal.md` §4 全部 21 个手测步骤（4.1 启动到 4:0 / 4.2 4:3 决胜 / 4.3 盘内崩溃恢复 / 4.4 盘间崩溃恢复 / 4.5 误操作恢复 / 4.6 整轮结束后操作），全部"正常"。S2 自此不再是"部分完成"，整个 final-sprint 完成定义（plan §9）全部满足，进入 release/v1.0 sign-off 与归档阶段。
- **2026-05-12 S2 headless 自动演练已完成**：`scripts/s2_rehearsal.py` 8 个 scenario 全 PASS（4:0 / 4:3 / 先手序列 / 超时判负 / 盘间恢复 / 盘中恢复 / 悔棋边界 / 整轮结束后行为）；落地 `docs/MATCH_CHECKLIST.md` 现场操作清单 + `docs/EMERGENCY_GUIDE.md` 应急手册；当日全量 pytest 已通过。详见 `reports/gui-rehearsal.md`。最新全量验证见 2026-05-15 Tk fixture follow-up 记录：495 passed in 11.68s。
- **历史记录（2026-05-13，当日快照，非最新验证）**：收官冲刺 Task Group 01-02 + 04 已完成。S3（AI 低风险清理 + harness 工程化）落地 `scripts/quick_bench.py` Wilson CI、新增 `scripts/tournament.py` pairwise matrix、清理 R-0 followup `stuck_penalty` 准死代码（grep 无残留）；S4（封版）落地 `release/v1.0/` 全套文档（README + config + default_params + known_limitations + test_report）。AI / 开局候选流水线（`scripts/param_sweep.py` / `scripts/search_openings.py` / `ai/self_capture.py`）已建立。Review 后 codex 已修复 `param_sweep.py` 双边对战门禁 + `search_openings.py` 训练/验证对手对齐与 AI 对称化，并补回归测试。当日复验：371 pytest passed、smoke OK、s2_rehearsal 8/8 PASS、AI baseline 双向 200 局 `greedy_risk` 合并胜率 55.75%（CI 通过）、max_step 6.84ms。随后 `rollout` 以双边 800 局对 `greedy_risk` 合并胜率 62.62%、Wilson lower 59.22% 晋升为 GUI/release 默认 AI；`greedy_risk` 保留为应急回退。决策详见 `reports/ai_promotion_decision.md` 与 `release/v1.0/test_report.md`。**最新验证与 adaptive/timeout 结论以 2026-05-15 条目和 `release/v1.0/test_report.md` 为准。**
- **2026-05-15 code review follow-up 已完成**：修复 adaptive rollout 误写默认参数的问题。当时 GUI/release 默认 AI 仍是 `rollout`，且默认参数保持旧 flat 形态：`rollouts_per_move=16`、`max_rollout_turns=80`、`max_step_time_ms=500.0`、`epsilon=0.15`。该结论已被 2026-05-16 P3 受控默认替换 supersede；当前默认参数以 `gui/main_window.py` 与 `release/v1.0/default_params.json` 为准。adaptive rollout（32 初采样、close sample 到 128、低置信提示）仅作为显式实验候选保留；其 direct vs old rollout 800 局合并胜率 59.00%，未达 60% 默认晋升线，不进入 release/v1.0 默认参数。`RolloutAI` 诊断现区分 `score / winrate / cutoffs / avg`；`quick_bench.py` / `bench_ai.py` 已开始聚合真实 `timeouts`，历史报告中的 legacy timeout 字段不可单独作为晋升证据。最近一次全量验证见 `release/v1.0/test_report.md`。
- **2026-05-15 P1 Rollout 根节点诊断收敛已完成**：新增 canonical `RootMoveStats` 与 `RolloutAI.last_root_stats`，`last_diagnostics` 保持兼容别名；GUI 推荐区优先读取 root stats，候选明细显示 visits、score、winrate、wins、losses、draws、avg 与低置信标记。默认 `rollout` 参数、`release/v1.0/default_params.json` 和 core 规则均未变更。验证：`scripts/smoke_test.py` 正常退出；全量 `pytest` 为 `496 passed in 11.29s`。
- **2026-05-15 P2 rollout 候选小样本已完成**：新增 benchable AI kind：`rollout_32`、`rollout_risk_playout`、`rollout_cutoff_eval`；`RolloutAI` 支持 `playout_policy=greedy|greedy_risk` 与 `cutoff_eval=draw|current`，`ai_version_signature()` 和 `scripts/bench_ai.py` profile 已记录相关元数据。默认 `rollout`、GUI 默认推荐、`release/v1.0/default_params.json` 和 core 规则均未变更。三组 candidate vs 当前默认 `rollout` 双边各 100 局均未过门禁：`rollout_32` 54.5% 且 timeouts=4；`rollout_risk_playout` 57.0% 但 timeouts=10；`rollout_cutoff_eval` 57.5% 但 timeouts=11。报告见 `reports/p2_candidate_rollout_32_20260515.*`、`reports/p2_candidate_rollout_risk_playout_20260515.*`、`reports/p2_candidate_rollout_cutoff_eval_20260515.*`。实现验证：`pytest` 为 `501 passed in 10.16s`，`scripts/smoke_test.py` 正常退出。
- **2026-05-15 P2.5 rollout deadline safety 已完成**：`RolloutAI` 新增 `deadline_safety_ms`，默认 `0.0`，内部 playout deadline 使用 `max_step_time_ms - deadline_safety_ms`；`ai_version_signature()` 记录该字段；`bench_ai.py` 仅给 `rollout_risk_playout` / `rollout_cutoff_eval` 的 candidate/promotion profile 显式传 `deadline_safety_ms=30.0`，未复验 `rollout_32`。P2.5 正式复验仅跑两个正向候选，各双边 100+100、对手 `rollout`：`rollout_risk_playout` 合并胜率 58.5%，但总 `timeouts=1`，未过总门禁；`rollout_cutoff_eval` 合并胜率 57.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，标记为 **P2.5 survives**。报告见 `reports/p25_candidate_rollout_risk_playout_20260515.*` 与 `reports/p25_candidate_rollout_cutoff_eval_20260515.*`。默认 `rollout`、GUI 默认推荐、`release/v1.0/default_params.json` 和 core 规则均未变更。
- **2026-05-15 P3 Zweistein-lite 已完成基础实现与 candidate 小样本**：新增 `ai/zweistein.py` 的 `zweistein_lite_score()`，特征包括终局、推进、子力、期望机动性、被吃风险和直接到角风险；新增 `greedy_zweistein`、`rollout_zweistein_cutoff`、`expectimax_zweistein_d1` 三个实验 kind。`RolloutAI.cutoff_eval` 支持 `zweistein`；`ExpectimaxAI` 支持 `leaf_evaluator=current|zweistein`；`ai_version_signature()` 记录 `leaf_evaluator`；`bench_ai.py` 为 `rollout_zweistein_cutoff` candidate/promotion profile 注入 `deadline_safety_ms=30.0`。P3 小样本：`rollout_zweistein_cutoff` vs `rollout` 双边 100+100，合并胜率 58.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，candidate 门禁通过。报告见 `reports/p3_candidate_rollout_zweistein_cutoff_20260515.*`。该 candidate 结论已被后续 promotion 和 2026-05-16 默认替换决策 supersede。
- **2026-05-15 P3 promotion 已通过**：按用户要求未进入 P4，先用 `scripts/bench_ai.py --candidate rollout_zweistein_cutoff --stage promotion --report-name p3_promotion_rollout_zweistein_cutoff_20260515` 复验。对手保持 old flat `rollout`，双边 400+400，结果：800 局、454 胜、合并胜率 56.75%，Wilson lower 53.29%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，平均步时 175.75ms，最大步时 720.69ms，promotion 门禁通过。报告见 `reports/p3_promotion_rollout_zweistein_cutoff_20260515.json` / `.md`；该 promotion 已在 2026-05-16 转为正式默认替换 decision。
- **2026-05-16 P3 受控默认替换已完成**：用户明确批准将 P3 promotion 已通过的 `rollout_zweistein_cutoff` 提升为 GUI/release 工作默认 AI。实现上保持 `DEFAULT_RECOMMENDER_KIND = "rollout"`，并从 `reports/p3_promotion_rollout_zweistein_cutoff_20260515.json` 的 `ai_versions.candidate` 复制完整参数到 `DEFAULT_RECOMMENDER_KWARGS` 和 `release/v1.0/default_params.json`：32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、close sample 32、playout_policy=`greedy_risk`、cutoff_eval=`zweistein`、deadline_safety_ms=30.0。`release/v1.0/test_report.md` 已追加 P3 promotion 结果和替换说明，`reports/ai_promotion_decision.md` 已改为正式 decision。`greedy_risk` 仍是应急回退；未进入 P4，未改 MCTS，未额外调参。

## 已确认的比赛事实

### 校内选拔赛
- 校内通知文件：`C:/Users/Takeapocket/Desktop/documents/computergames/通知 _ 关于举办 2026 年辽宁省大学生计算机博弈大赛校内选拔赛的通知.html`
- 本校报名截止时间：2026 年 5 月 18 日。
- 队伍组成：1-3 名学生及 1-2 名指导教师。
- 校赛结束后，每个棋牌类项目最终推荐 2 项参加省级决赛。
- 程序要求：参赛队使用各自研发的计算机博弈程序对弈，不限制编程软件。

### 国赛规则（2026-05-10 通过 `全国计算机博弈竞赛总则.md` + `爱恩斯坦棋项目规则.md` 确认）
- **棋盘**：5×5；红方左上出发区，蓝方右下出发区。
- **棋子**：双方各 6 子，编号 1-6。
- **开局**：可任意摆放（**无组委会强制布局**）。
- **走法**：红向下/右/右下，蓝向上/左/左上，每次一格。
- **吃子**：目标格有棋子（**含本方**）则吃掉；吃本方子是合法策略。✅ R-0 已修复 core 实现。
- **骰子映射**：骰子 d 对应棋子已死时，可走最近编号棋子（双向并列时两个都可选）。
- **胜负**：到达对方出发区角点 OR 吃光对方棋子 = 胜；**只有胜负，没有和棋**。
- **单方时限**：每盘每方 4 分钟包干，超时判负。
- **轮制**：每轮 7 盘，先胜 4 盘为胜方；甲方一四五盘先手，乙方二三六七盘先手；两盘中间不休息。
- **决赛加赛**：积分相等 → 胜负关系 → 10 分钟包干快棋两盘 → 抽签/掷骰只比一局。
- **崩盘**：程序崩溃 = 该方判负。
- **联网**：比赛中禁止任何有线/无线联网（桥牌项目例外）。
- **统一平台**：可申请使用，**不强制**；项目按"无统一平台"假设开发。
- **山寨程序检查**：参赛队需提交程序设计文档与源码，可被现场专家组质询。

### 操作规则（总则）
- 比赛过程中每方仅允许一名队员执行裁判允许的操作，不允许超时、修改程序或介入程序运行。
- 两场比赛间隙可修改或调整程序与参数，但不能更换计算机设备，除非得到裁判许可。
- 双方电脑屏幕摆放须有利于对方观察；双方有义务告知对方本方电脑产生的棋步。

## GUI 程序必须支持

- 离线运行，不依赖网络。
- 可视化 5×5 爱恩斯坦棋棋盘。
- 可录入当前轮骰子点数。
- 可录入对方走法。
- 可输出我方建议走法，并明确显示移动棋子、起点、终点、是否吃子。
- 自动判断胜负。
- 计时功能：单方总时间 + 每步耗时统计（已实现 4 分钟包干）。
- 棋谱保存：JSON 格式（已实现）；后续如有组委会规范再适配。
- 悔棋/恢复局面（已实现）。
- 比赛模式：合法步校验、当前轮状态提示、当前推荐走法（已实现）。
- 7 盘制比赛流程（R-2 已实现）。开局录入 GUI（R-1）与崩溃自救（R-3）已实现。S2 headless 自动演练 + 真实 Tk GUI 手动表（21/21 正常）均已完成，S2 完整闭环。

## 工程约束

- 每次只做一小步，先实现可验证的最小功能，再迭代优化。
- 不凭空假设比赛平台/API；所有现场规则差异都先记录为假设，等 QQ 群或老师发布附件后再适配。
- 先做规则引擎和验证 harness，再做复杂 AI。
- 每个核心规则都要有自动测试：合法步、吃子（含本方子）、到达终点、全灭胜负、骰子对应棋子选择、悔棋恢复。
- AI 优化必须用本地对战 harness 验证：旧版本 vs 新版本、随机 AI vs 当前 AI、固定局面回归测试。
- 不优先做深度学习训练。首版 AI 采用规则评估 + 搜索/模拟，保证稳定、可解释、可答辩。
- 代码结构遵循 KISS、YAGNI、DRY、SOLID：规则引擎、AI、GUI、棋谱、平台适配分层，不把逻辑写死在界面里。

## 建议初始架构

- `core/`：棋盘状态、规则、合法步、胜负判断、走子/撤销、序列化。
- `ai/`：随机 AI、贪心 AI、期望搜索或蒙特卡洛 AI。
- `gui/`：离线 GUI，负责展示棋盘、录入骰子和走法、显示建议。
- `record/`：棋谱记录、保存、加载、导出。
- `tests/`：规则测试和 AI 对战 harness。
- `adapters/`：预留统一平台/API 适配层，只有确认平台协议后再实现。

## 下一次对话建议第一步

1. 先读取本文件 + `PROJECT_PHASES.md` "赛事规则对齐补丁"章节。
2. R-0 / R-1 / R-2 / R-3 / S2 / S3 / S4 全部完成；AI 下一阶段 P1 / P2 / P2.5 / P3 均已完成。当前 GUI/release 默认是 `rollout` kind + P3 promotion 参数，不再是旧 flat rollout。
3. P3 promotion survivor `rollout_zweistein_cutoff` 已于 2026-05-16 受控替换为工作默认；如需回退，使用 `greedy_risk` 或恢复旧 flat rollout 参数。后续不要默认进入 P4，除非用户明确要求；比赛后再回到 Expectimax 主线（合并胜率 45.0% 弱于 baseline，需按 `reports/4-4-rebench.md` 方向实验）。
4. 如有时间，可跑大样本 `scripts/param_sweep.py` 或 `scripts/search_openings.py` 看是否产出能过门禁的候选。

## 待确认事项

- 校赛 QQ 群是否发布了项目附件、棋谱标准或统一平台协议（赛前持续关注）。
- 现场骰子由裁判实体投掷、程序生成，还是由平台提供（默认假设：裁判实物投掷，操作员录入到程序）。
- 校赛与省赛是否使用国赛同套规则（默认假设：是；如果有校赛特殊规则，赛前需重新对齐）。
