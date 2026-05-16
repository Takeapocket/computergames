# 爱恩斯坦棋参赛程序项目简介

更新时间：2026-05-16（P5.5 opening duel 60-game expansion 后同步候选状态）

## 项目定位

本项目用于 2026 年辽宁省大学生计算机博弈大赛校内选拔赛，方向为爱恩斯坦棋离线 GUI 参赛程序。

程序目标不是命令行工具，而是比赛现场可操作的软件：操作员录入骰子和对方走法，程序校验合法性、维护局面，并逐步加入 AI 推荐、棋谱、计时和评测能力。

## 当前阶段判断（2026-05-16，S2/S3/S4 全部闭环）

- 阶段 0：项目初始化与规则固化已基本补齐。
- 阶段 1：核心规则引擎已完成，**R-0 已合规修复**（允许吃本方棋子）。**R-0 followup 已清理 `stuck_penalty` 准死代码**（grep 已无残留）。
- 阶段 2：Tkinter GUI 已实现（棋盘显示、开局录入、骰子录入、合法走法选择、执行、悔棋、重置、AI 推荐）。
- 阶段 3：棋谱、计时、比赛模式已完成主链路。R-1 开局录入、R-2 七盘制、R-3 崩溃自救均已实现；S2 headless 自动演练 + 真实 Tk GUI 手动表（2026-05-13，`reports/gui-rehearsal.md` §4，21/21 正常）均已完成，S2 完整闭环。
- 阶段 4.0 / 4.1 / 4.2：基础对战 harness、GreedyAI、greedy_risk 已完成；**R-0 合规重跑后**门槛全部通过：
  - 4.1 GreedyAI vs RandomAI 合并 63.75% ≥ 60%（详见 `reports/4-1-rebench.md`）
  - 4.2 greedy_risk vs greedy 合并 55.75%，2026-05-12 release 验证仍为 55.75%（详见 `release/v1.0/test_report.md`）
- 阶段 4.4：ExpectimaxAI 在 R-0 合规重跑后仍弱（合并 45.0%），保留为研究/实验代码。
- **S3 完成（2026-05-12）**：`scripts/quick_bench.py` 新增 Wilson 95% CI；`scripts/tournament.py` pairwise matrix 落地；`stuck_penalty` 死代码清理完毕；`ai/self_capture.py`（默认关闭）/ `scripts/param_sweep.py` / `scripts/search_openings.py` 候选实验流水线建立。
- **S4 已完成（2026-05-13）**：`release/v1.0/` 目录 README + config + default_params + known_limitations + test_report 已完整落地；`rollout` 已按 harness 门禁晋升为默认 AI，`greedy_risk` 保留为应急回退，默认布局保持 `balanced_v1`，决策见 `reports/ai_promotion_decision.md`。
- **2026-05-15 code review follow-up 已完成**：当时默认 `rollout` 参数保持旧 flat release 形态（16 rollout / move、80 half-turn cutoff、500ms step deadline、epsilon 0.15）。该默认参数已被 2026-05-16 P3 受控默认替换 supersede；当前以 `gui/main_window.py` 与 `release/v1.0/default_params.json` 为准。adaptive rollout 仅作为显式实验候选；direct vs old rollout 800 局合并胜率 59.00%，未过 60% 默认晋升线。`RolloutAI` 诊断现区分 score / winrate / cutoffs / avg；bench 脚本已聚合真实 `timeouts`。
- **2026-05-15 P1 / P2 / P2.5 已完成**：`RolloutAI.last_root_stats` 成为 canonical 诊断接口；新增 `rollout_32`、`rollout_risk_playout`、`rollout_cutoff_eval` 三个 benchable 候选。P2 三者均未过门禁；P2.5 只给 `rollout_risk_playout` / `rollout_cutoff_eval` 的 bench profile 注入 `deadline_safety_ms=30.0`，其中仅 `rollout_cutoff_eval` 以 57.0% 胜率、0 timeout 标记为 survivor。默认 AI 和 release 配置不变。
- **2026-05-15 P3 Zweistein-lite promotion 已通过，2026-05-16 已受控替换默认**：新增 `zweistein_lite_score()` 与 `greedy_zweistein`、`rollout_zweistein_cutoff`、`expectimax_zweistein_d1` 实验 kind。`rollout_zweistein_cutoff` vs 当前默认旧 flat `rollout` 的 candidate 双边 100+100 合并胜率 58.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`；promotion 双边 400+400 合并胜率 56.75%，Wilson lower 53.29%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，working-baseline promotion 门禁通过。用户已批准替换 GUI/release 工作默认；实现仍使用 `kind="rollout"` + 显式 P3 kwargs，不依赖 `rollout_zweistein_cutoff` factory。
- **2026-05-16 P4/P4.1 已停止，转 P5**：修复 / 验证 `MCTSAI` opponent DecisionNode 语义；对手节点现在按 root-player 视角最小化，避免把对手当合作方。P4.1 新增最小真实局面测试，并让 MCTS leaf 支持 `current|zweistein` evaluator，默认仍为 `current`。`mcts_eval_v1(leaf_evaluator=zweistein)` 对当前 release 默认 rollout kwargs 双边 10+10，合并胜率 25.0%，0 illegal/crash/timeout，低于用户指定 45% 停止线。未跑正式 200+200 candidate，未改 GUI/release 默认；下一步转 P5。
- **2026-05-16 P5.0 opening entry guard 已完成**：`scripts/search_openings.py` 已改为使用当前 release 默认 `rollout` 显式 kwargs 评测布局候选，且统计真实 `timeouts`。仅跑小样本 smoke，生成 `reports/p5_opening_entry_guard_20260516.md` / `.json`；未改 GUI/release 默认布局。
- **2026-05-16 P5.1 opening strata + seed pool 已完成**：`scripts/search_openings.py` 支持 stratified 候选分层和 seed-pool 聚合；P5.1 smoke 三类各 1 个候选、seed pool 2026/2027，validation 结果为 aggressive 1/8、defensive 4/8、balanced 2/8，0 illegal/crash/timeout。报告见 `reports/p51_opening_strata_seed_smoke_20260516.md` / `.json`；样本不足以晋升布局，未改 GUI/release 默认布局。
- **2026-05-16 P5.2 opening small-scale gate 已完成**：复用当前 release 默认 `rollout` 显式 kwargs，分层候选扩大到每类 2 个、seed pool 2026/2027，train 6 个候选结果为 5/8、4/8、3/8、3/8、3/8、2/8；validation top3 为 3/8、4/8、4/8，0 illegal/crash/timeout。报告见 `reports/p52_opening_small_scale_gate_20260516.md` / `.json`；仍不是布局晋升证据，未改 GUI/release 默认布局。
- **2026-05-16 P5.3 opening seed3 validation2 gate 已完成**：继续使用当前 release 默认 `rollout` 显式 kwargs，分层候选保持每类 2 个，seed pool 扩到 2026/2027/2028，validation games 提高到每 opponent 2 局；train top3 均为 6/12，validation top3 为 10/24、10/24、11/24，0 illegal/crash/timeout。报告见 `reports/p53_opening_seed3_validation2_20260516.md` / `.json`；当前候选没有布局晋升信号，未改 GUI/release 默认布局。
- **2026-05-16 P5.4 opening layout duel precheck 已完成**：新增 `scripts/compare_opening_layouts.py`，取 P5.3 validation 最好的 balanced 候选直接对当前默认 `balanced_v1` 做红蓝双边小样本验证。结果：合并 14/24 = 58.3%，Wilson CI [38.8%, 75.5%]；candidate as red 9/12，candidate as blue 5/12，0 illegal/crash/timeout。报告见 `reports/p54_opening_duel_best_balanced_20260516.md` / `.json`；这是前置正信号，但不足以晋升默认布局。
- **2026-05-16 P5.5 opening duel 60-game expansion 已完成**：复用 P5.4 同一 balanced 候选，扩到 60 局双边复验。结果：合并 23/60 = 38.3%，Wilson CI [27.1%, 51.0%]；candidate as red 13/30，candidate as blue 10/30，0 illegal/crash/timeout。报告见 `reports/p55_opening_duel_best_balanced_60g_20260516.md` / `.json`；P5.4 小样本正信号未复现，停止该候选晋升路线，未改 GUI/release 默认布局。

下一会话优先级：
1. **release/v1.0 归档与赛前核对**：sign-off 复验已记录；下一步是备份正式提交物和现场启动包。
2. AI 研究若继续推进，当前默认基线已是 `rollout` kind + P3 promotion 显式参数；后续候选必须直接对这个配置过门禁。
3. P5.5 已完成同一候选的 60 局扩样复验；后续 P5 候选仍必须直接对当前 release 默认 rollout kwargs 验证，且 P5.0/P5.1/P5.2/P5.3/P5.4/P5.5 报告都不能作为默认布局晋升证据。

## 当前技术栈

- Python 3.11
- pytest
- tkinter 标准库 GUI
- 当前不依赖网络服务、数据库或统一平台 API

## 已有能力

- 5×5 棋盘。
- 双方 1-6 号棋子。
- 骰子点数到可动棋子的选择规则（含距离最近映射、双向并列）。
- 合法走法生成（含吃本方棋子，R-0 已合规）。
- 吃对方/本方子、胜负判断、走子和撤销。
- 状态序列化和反序列化。
- 最小随机 AI、GreedyAI、greedy_risk（带 distance-weighted capture risk）、RolloutAI（默认推荐，release 参数为 P3 promotion 显式 kwargs）、P2/P3 rollout/Zweistein 显式实验候选、MCTSAI（实验性，P4.1 已停止，不进入 promotion）、ExpectimaxAI（实验性）。
- Tkinter GUI（含开局录入、骰子录入、推荐走法 by rollout）。
- 对战 harness（`scripts/quick_bench.py`，slim JSON 默认）+ 验证脚本（`scripts/_grid_validate_4_2.py`）。
- 棋谱 JSON 保存 / 加载 / 回放 / 悔棋。
- 单方计时（4 分钟包干）。

## 当前规则假设

完整规则细节以 `docs/RULE_ASSUMPTIONS.md` 为准（已与国赛官网规则对齐）。当前关键事实：

- 红方目标角为右下角 (4, 4)。
- 蓝方目标角为左上角 (0, 0)。
- 红方可向下、右、右下移动；蓝方可向上、左、左上移动。
- 到达目标角或吃光对方棋子立即获胜，**没有和棋**。
- **开局可任意摆放**（赛事规则明确允许，无组委会强制布局）。
- 单方时限 4 分钟包干。
- 7 盘制，先胜 4 盘为胜方，轮流先手。
- **吃本方棋子是合法走法**（赛事规则明确，core/rules.py R-0 已实现）。

## 开发边界

短期内不要做：

- 深度学习训练。
- 未确认协议的平台适配。
- 联网功能。
- 正式 release 打包（等阶段 8/9）。
- 没有 harness 数据支撑的 AI 强度结论。

新增功能应优先保持分层：

- 规则改动先进入 `core/` 并补测试。
- GUI 只展示状态和转发操作。
- 棋谱和计时进入 `record/` 与 `gui/` 的明确边界。
- 平台适配只放入 `adapters/`。

## 常用命令

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026
```

## 下一步建议（下一会话）

详见 `PROJECT_PHASES.md` §S4 与 `docs/superpowers/plans/2026-05-12-final-sprint-plan.md`。简版顺序：

1. **release/v1.0 归档**：把 release/v1.0 当作正式提交物备份；准备现场启动包。
2. **可选 AI 研究**：当前默认已替换为 P3 promotion 参数，P4.1 已停止 MCTS，P5.5 已证明当前 balanced 候选小样本正信号不可复现。任何再次默认变更都必须直接对当前默认配置复验，并保持可回退到 `greedy_risk` 或旧 flat `rollout` 参数。
3. 比赛后再回到 Expectimax 强化 / 开局库 / rollout 参数实验主线。
