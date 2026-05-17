# 爱恩斯坦棋离线 GUI 参赛程序

面向 2026 年辽宁省大学生计算机博弈大赛的爱恩斯坦棋程序。

项目当前重心已经从"继续堆功能"转到"赛前冻结与现场可用"：规则引擎、Tkinter GUI、七盘制比赛流程、计时提示、棋谱与崩溃恢复、默认 AI、赛前检查脚本和 Windows 双击启动器都已落地。比赛现场默认离线运行，不依赖网络、数据库或统一平台 API。

如果后续确认统一平台协议，只在 `adapters/` 增加适配层；`core/` 的规则语义不跟着平台输入输出格式摇摆。

## 当前状态

| 项目 | 当前结论 |
|---|---|
| 参赛版本 | `release/v1.0/` 已作为比赛版本目录维护 |
| 现场入口 | 根目录 `启动项目.cmd` 可双击打开菜单 |
| GUI | 支持开局录入、骰子录入、程序掷骰、走法执行、AI 推荐、悔棋、恢复 |
| 比赛流程 | 支持每轮最多 7 盘、先胜 4 盘、甲乙身份和固定先手序列 |
| 计时判负 | 默认只提示超时，以裁判判定为准；裁判要求时可开启程序自动超时判负 |
| 规则实现 | 已对齐国赛规则，包含"目标格有棋子即吃掉"，本方棋子也可被吃 |
| 默认 AI | `rollout` kind + P3 promotion 显式参数 |
| 应急回退 | `greedy_risk`，再退到第一条合法步 |
| 默认布局 | `balanced_v1`，P5 系列候选未晋升 |
| 当前主线 | 赛前冻结、现场启动包核对、只修现场风险 bug |

最近项目记录显示：R-4 GUI 程序掷骰、现场一键启动器、P6 鲁棒性锁定、P7/P8/P9 候选审计都已闭环。P7.2、P8、P9 的实验候选没有进入默认配置。

## 现场最快启动

比赛电脑上优先用双击入口：

```text
启动项目.cmd
```

菜单里已经包含这些入口：

- 启动 GUI
- 一键赛前总检查
- 完整 pytest
- smoke 测试
- S2 七盘制演练
- timing probe
- release/default 状态显示

命令行等价入口：

```powershell
& ".venv/Scripts/python.exe" "scripts/launcher.py"
```

直接打开 GUI：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

赛前总检查：

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

成功时应输出：

```text
READY FOR MATCH
```

## 运行环境

- Python 3.11
- Windows
- Tkinter 标准库 GUI
- pytest
- 项目本身不依赖网络服务、数据库或生产 API

优先使用仓库内 `.venv/`。如需重建虚拟环境：

```powershell
python -m venv ".venv"
& ".venv/Scripts/python.exe" -m pip install pytest
```

## 现场操作链路

程序按"操作员辅助参赛"设计，而不是命令行自走程序：

1. 启动 GUI。
2. 选择我方甲乙身份、单方时限，并确认是否开启"程序自动超时判负"。
3. 录入或选择双方开局。
4. 按裁判或双方约定录入骰子，也可以在双方同意时点击"程序掷骰"。
5. 录入对方走法。
6. 查看我方推荐走法和候选诊断。
7. 执行我方走法。
8. 单盘结束后进入下一盘，任一方 4 胜后结束本轮。

现场细节见：

- `docs/MATCH_CHECKLIST.md`
- `docs/EMERGENCY_GUIDE.md`
- `release/v1.0/README.md`

## 已实现能力

### 规则与状态

- 5x5 棋盘，双方各 6 子，编号 1-6。
- 红方目标角为右下角 `(4, 4)`，蓝方目标角为左上角 `(0, 0)`。
- 红方向下、右、右下移动；蓝方向上、左、左上移动。
- 骰子点数映射到存活棋子；编号棋子已死时选择最近编号，双向等距时两个都可选。
- 目标格有棋子即吃掉，包括本方棋子。
- 到达目标角或吃光对方棋子立即获胜，没有和棋。
- 支持走子、撤销、序列化和反序列化。

### GUI 与比赛

- Tkinter 离线 GUI。
- 开局录入：预设布局、自定义布局、对方布局录入。
- 骰子录入：手动录入外部骰子结果，或使用 GUI 内"程序掷骰"。
- 单方时限计时显示，默认 240 秒；比赛模式弹窗可改时限。
- 超时默认只提示，不自动判负；裁判确认超时判负后可用计时面板按钮记分；裁判要求双方程序自行计时时，可在比赛模式弹窗开启自动超时判负。
- 七盘制比赛模式：甲乙身份、先手序列、比分推进、先胜 4 盘。
- JSON 棋谱保存与加载。
- 盘内 auto-save、整轮 auto-save、崩溃后恢复。
- 损坏 auto-save 启动时自动清理，不阻塞 GUI。

### AI 与评测

- 默认推荐：`rollout` kind + P3 promotion 参数。
- 当前默认参数：32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、risk-aware playout、Zweistein cutoff、30ms deadline safety。
- 应急 AI：`greedy_risk`。
- 实验 AI：`expectimax`、`expectimax_v2`、`mcts`、Zweistein / DP / adaptive rollout 系列候选。
- 评测脚本覆盖 quick bench、candidate/promotion bench、tournament、参数搜索、开局搜索、布局对比和失败归因。

默认 AI 或默认布局的变更必须由 harness 数据支撑。单局输赢不能作为改默认配置的理由。

## 常用命令

完整测试：

```powershell
& ".venv/Scripts/python.exe" -m pytest
```

GUI smoke：

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

七盘制自动演练：

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

查看启动器菜单：

```powershell
& ".venv/Scripts/python.exe" "scripts/launcher.py" --list
```

查看当前 release/default 状态：

```powershell
& ".venv/Scripts/python.exe" "scripts/launcher.py" --run status
```

AI candidate bench 示例：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate rollout_adaptive_close_sample --stage candidate --report-name p72_candidate_rollout_adaptive_close_sample
```

## 项目结构

```text
core/          棋盘、规则、合法步、胜负判断、走子/撤销、序列化
ai/            random、greedy、greedy_risk、rollout、expectimax、mcts、
               Zweistein、risk、opening_layouts、match
gui/           Tkinter GUI：棋盘、控制面板、开局录入、计时、七盘制流程
record/        JSON 棋谱、状态序列化、auto-save、整轮记录
scripts/       启动、测试、评测、搜索、赛前检查和现场菜单
tests/         pytest 自动测试
docs/          规则记录、项目摘要、现场清单、应急手册
reports/       AI、harness、演练和默认决策报告
release/v1.0/  比赛版本目录
replays/       自动保存和对战 replay
adapters/      平台/API 适配层预留，目前不实现具体协议
```

## 关键文档

- `PROJECT_MEMORY.md`：当前事实快照和历史决策。
- `PROJECT_PHASES.md`：阶段规划、验收门槛和 AI 研究路线。
- `docs/RULE_ASSUMPTIONS.md`：规则假设与国赛规则对齐记录。
- `docs/PROJECT_BRIEF.md`：项目定位、当前阶段和边界。
- `release/v1.0/test_report.md`：封版测试与默认 AI 晋升依据。
- `reports/ai_promotion_decision.md`：默认 AI 决策记录。
- `docs/MATCH_CHECKLIST.md`：现场操作检查清单。
- `docs/EMERGENCY_GUIDE.md`：误操作、崩溃、超时等现场处理说明。

## 规则边界

完整规则以 `docs/RULE_ASSUMPTIONS.md` 为准。当前已确认：

- 开局棋位可以任意摆放，没有组委会强制布局。
- 吃本方棋子是合法走法。
- 每盘单方 4 分钟包干，超时判负；程序默认只做超时提示，现场判罚以裁判为准。
- 每轮最多 7 盘，先胜 4 盘。
- 甲方第 1/4/5 盘先手，乙方第 2/3/6/7 盘先手。
- 比赛中禁止联网，统一平台不是默认假设。

如果赛前附件与当前实现冲突，处理顺序固定为：

```text
先改 core 与测试，再接 GUI、AI 或 adapters。
```

## AI 晋升纪律

当前默认基线是 release 默认 `rollout` 显式 kwargs，不是旧 flat rollout，也不是 `greedy_risk`。

任何默认 AI、参数或默认布局变更都必须满足：

- 直接对当前 release 默认配置评测。
- 使用红蓝双边对战数据。
- 报告写入 `reports/`，包含 games、seed、胜率、Wilson CI、非法走法、崩溃、真实 timeout、平均步时和最大步时。
- `illegal_moves = 0`、`crashes = 0`、真实 `timeouts = 0`。
- 胜率没有过门禁时只保留为实验候选，不进入 GUI/release 默认。

已关闭或未晋升的近期路线：

- P5.5 默认布局候选 60 局复验失败，`balanced_v1` 不变。
- P7.2 `rollout_adaptive_close_sample` 合并胜率 50.0%，未过 candidate 门槛。
- P8 threat defense audit 不支持实现 `rollout_threat_rerank`。
- P9.1 / P9.2 均未过 55% candidate 门槛，P9.3 不启动。
- MCTS P4.1 probe 低于停止线，赛前不继续。

## 开发纪律

- Core-first：规则变化先进入 `core/` 并补测试。
- Harness-first：AI 强弱只认本地批量对战数据。
- GUI 不复制规则：界面只展示状态、收集输入并调用 `core/ai/record`。
- YAGNI：没有正式平台协议前，不实现平台适配细节。
- KISS：赛前只修现场风险 bug，不引入新框架。
- DRY：重复规则逻辑收敛到 `core/`，重复评测口径收敛到 scripts/harness。
- 比赛版本不临时联网、不临时换 AI 框架、不因单局输赢改默认参数。
