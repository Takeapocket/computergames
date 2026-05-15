# 爱恩斯坦棋参赛程序项目简介

更新时间：2026-05-15（code review follow-up 后同步默认 AI 参数和候选状态）

## 项目定位

本项目用于 2026 年辽宁省大学生计算机博弈大赛校内选拔赛，方向为爱恩斯坦棋离线 GUI 参赛程序。

程序目标不是命令行工具，而是比赛现场可操作的软件：操作员录入骰子和对方走法，程序校验合法性、维护局面，并逐步加入 AI 推荐、棋谱、计时和评测能力。

## 当前阶段判断（2026-05-15，S2/S3/S4 全部闭环）

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
- **2026-05-15 code review follow-up 已完成**：默认 `rollout` 参数保持旧 flat release 形态（16 rollout / move、80 half-turn cutoff、500ms step deadline、epsilon 0.15）。adaptive rollout 仅作为显式实验候选；direct vs old rollout 800 局合并胜率 59.00%，未过 60% 默认晋升线，不写入 release 默认参数。`RolloutAI` 诊断现区分 score / winrate / cutoffs / avg；bench 脚本已聚合真实 `timeouts`。

下一会话优先级：
1. **release/v1.0 归档与赛前核对**：sign-off 复验已记录；下一步是备份正式提交物和现场启动包。
2. 如时间允许：跑 `scripts/param_sweep.py` / `scripts/search_openings.py` 大样本，按门禁决定是否替换默认布局或继续优化 rollout 参数；adaptive rollout 未过默认晋升线前不得写入 release 默认。
3. 比赛后再回到 Expectimax 强化 / 开局库 / rollout 参数实验主线。

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
- 最小随机 AI、GreedyAI、greedy_risk（带 distance-weighted capture risk）、RolloutAI（默认推荐，release 参数为旧 flat rollout）、ExpectimaxAI（实验性）。
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
2. **可选**：跑大样本 `scripts/param_sweep.py` / `scripts/search_openings.py`，按门禁更新 `reports/ai_promotion_decision.md` 与 `release/v1.0/default_params.json`。adaptive rollout 当前只是显式候选，不是 release 默认。
3. 比赛后再回到 Expectimax 强化 / 开局库 / rollout 参数实验主线。
