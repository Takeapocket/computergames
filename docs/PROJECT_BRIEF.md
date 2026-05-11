# 爱恩斯坦棋参赛程序项目简介

更新时间：2026-05-11

## 项目定位

本项目用于 2026 年辽宁省大学生计算机博弈大赛校内选拔赛，方向为爱恩斯坦棋离线 GUI 参赛程序。

程序目标不是命令行工具，而是比赛现场可操作的软件：操作员录入骰子和对方走法，程序校验合法性、维护局面，并逐步加入 AI 推荐、棋谱、计时和评测能力。

## 当前阶段判断（2026-05-11，R-0 完成后）

- 阶段 0：项目初始化与规则固化已基本补齐。
- 阶段 1：核心规则引擎已完成，**R-0 已合规修复**（允许吃本方棋子）；pytest 207 passed。
- 阶段 2：最小 Tkinter GUI 已实现（棋盘显示、骰子录入、合法走法选择、执行、悔棋、重置）。
- 阶段 3：棋谱、计时、比赛模式 — **部分完成**。GUI 比赛模式只支持单局；7 盘制 / 自动轮换先后手 / 比分显示尚未实现。
- 阶段 4.0 / 4.1 / 4.2：基础对战 harness、GreedyAI、greedy_risk 已完成；**R-0 合规重跑后**门槛全部通过：
  - 4.1 GreedyAI vs RandomAI 合并 63.75% ≥ 60%（详见 `reports/4-1-rebench.md`）
  - 4.2 greedy_risk vs greedy 合并 55.75%，与 n=2000 真值 53.8% 差 +2pp（详见 `reports/4-2-rebench.md`）
- 阶段 4.4：ExpectimaxAI 在 R-0 合规重跑后仍弱（合并 45.0% vs 旧 46.5%），保留为研究/实验代码（详见 `reports/4-4-rebench.md`）。

下一会话优先级：
1. R-1（开局录入 GUI）
2. R-2（7 盘制比赛模式）
3. R-3（崩溃自救）
4. R-0-followup（与 R-1/R-2/R-3 并行）：删 stuck_penalty 死代码 + ai/risk.py 加 self-capture 战略评估

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
- 最小随机 AI、GreedyAI、greedy_risk（带 distance-weighted capture risk）、ExpectimaxAI（实验性）。
- 最小 Tkinter GUI（含骰子录入、推荐走法 by greedy_risk）。
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

详见 `PROJECT_PHASES.md` 顶部"赛事规则对齐补丁"章节。简版顺序：

1. **R-1 开局录入 GUI**：支持比赛现场录入对方布局 + 自己布局多候选
2. **R-2 7 盘制比赛模式**：盘数计数、自动先后手轮换、比分显示
3. **R-3 崩溃自救**：每步保存到 `replays/auto_save.json`
4. **R-0-followup**（可与上述并行）：删 stuck_penalty 死代码 + ai/risk.py self-capture 扩展
5. 之后才回到原阶段 6（Expectimax 强化）/ 阶段 7（开局库与参数）的主线


