# 爱恩斯坦棋离线 GUI 参赛程序

本项目面向 2026 年辽宁省大学生计算机博弈大赛校内选拔赛，目标是交付一个比赛现场可离线运行、可操作、可解释的爱恩斯坦棋程序。

当前版本不依赖网络，不假定存在统一平台或 API。现场默认流程是：操作员录入骰子和对方走法，程序维护局面、校验合法性，并给出我方推荐走法。若赛前确认统一平台协议，只在 `adapters/` 增加适配层，不修改 `core/` 规则语义。

## 当前结论

- 比赛版本已封版至 `release/v1.0/`，包含运行说明、配置、默认参数、已知限制、测试报告和样例棋谱。
- 规则、GUI、棋谱、计时、七盘制比赛流程、崩溃自救、AI harness 均已闭环。
- 当前默认参赛 AI 是 `rollout` kind + P3 promotion 显式参数：32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、risk-aware playout、Zweistein cutoff、30ms deadline safety。
- `greedy_risk` 保留为应急回退；`expectimax`、`expectimax_v2`、`mcts` 和其他 rollout/Zweistein 变体均为实验候选。
- P5.0/P5.1/P5.2 只验证开局搜索 harness、分层候选和小规模 seed pool 流程，没有晋升默认布局。

## 快速启动

优先使用仓库内 `.venv/`：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

现场操作流程见：

- `release/v1.0/README.md`
- `docs/MATCH_CHECKLIST.md`
- `docs/EMERGENCY_GUIDE.md`

## 运行环境

- Python 3.11
- Windows + 标准库 Tkinter
- pytest
- 离线运行，无数据库、网络服务或生产 API 依赖

如需重建虚拟环境：

```powershell
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
```

## 常用验证

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

GUI、core、record 或公共接口变更后，应运行完整 pytest。文档-only 变更至少检查 Markdown diff 和命令示例是否仍与项目现状一致。

## 核心能力

- 规则引擎：5x5 棋盘、红/蓝目标角、合法步生成、骰子映射、吃子、吃本方子、胜负判断、走子/撤销、序列化。
- GUI：开局录入、对方布局录入、骰子录入、合法走法执行、悔棋、AI 推荐、推荐候选诊断。
- 比赛流程：单方 4 分钟包干计时、七盘制、甲乙身份、先手序列、比分推进、先胜 4 盘判定。
- 棋谱与恢复：JSON 棋谱保存/加载、盘内 auto-save、整轮 auto-save、崩溃后恢复。
- AI 与 harness：`quick_bench`、`bench_ai`、`tournament`、`param_sweep`、`search_openings`，报告写入 `reports/`。

## 项目结构

```text
core/          棋盘、规则、合法步、胜负判断、走子/撤销、序列化
ai/            random / greedy / greedy_risk / rollout / expectimax / mcts /
               tactical / risk / evaluator / opening_layouts / match
gui/           Tkinter 离线 GUI：main_window / board_widget / control_panel /
               match_mode / opening_panel / timer_panel
record/        JSON 棋谱、状态序列化、auto_save、match_record
adapters/      统一平台/API 适配层预留，目前无正式实现
scripts/       run_gui / smoke_test / quick_bench / bench_ai / tournament /
               param_sweep / search_openings / s2_rehearsal
tests/         pytest 自动测试
docs/          规则、项目摘要、现场操作清单、应急手册
release/v1.0/  封版比赛产物
reports/       AI、harness、演练和决策报告
replays/       auto_save 与对战 replay
```

顶层关键文档：

- `PROJECT_MEMORY.md`：项目事实快照
- `PROJECT_PHASES.md`：阶段规划与 AI 研究路线
- `AGENTS.md`：协作约束

## AI 评测

常用命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy_risk --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue rollout --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/tournament.py" --help
```

默认 AI、参数或开局布局变更必须满足以下条件：

- 直接对当前 release 默认 `rollout` 显式 kwargs 评测。
- 使用双边对战数据，而不是单局印象。
- 胜率、Wilson CI、非法走法、崩溃、真实 timeout telemetry、平均步时、最大步时均写入报告。
- `illegal_moves = 0`、`crashes = 0`、真实 `timeouts = 0` 是晋升前置条件。
- 2026-05-15 前部分历史报告的 legacy `timeouts=0` 不能单独作为新候选晋升证据。

`greedy_risk` 可以作为辅助诊断和应急回退，但不能替代当前默认基线。

## 规则边界

当前规则以 `docs/RULE_ASSUMPTIONS.md` 为准，已与国赛规则对齐：

- 棋盘为 5x5，双方各 6 子，编号 1-6。
- 红方向下、右、右下；蓝方向上、左、左上。
- 目标格有棋子即吃掉，包含本方棋子。
- 骰子点数对应棋子死亡时，选择编号距离最近的存活棋子；双向等距时两个都可选。
- 到达目标角或吃光对方棋子立即获胜，没有和棋。
- 每盘单方 4 分钟包干；每轮最多 7 盘，先胜 4 盘。

如赛事附件与现有规则冲突，处理顺序固定为：先改 `core/` 与测试，再接 GUI、AI 或 `adapters/`。

## 文档索引

- `docs/RULE_ASSUMPTIONS.md`：规则假设和官方规则对齐记录
- `docs/PROJECT_BRIEF.md`：项目定位、当前阶段和边界
- `PROJECT_PHASES.md`：阶段规划、AI 路线和验收门槛
- `PROJECT_MEMORY.md`：当前事实快照和历史决策
- `release/v1.0/test_report.md`：封版测试和默认 AI 晋升依据
- `reports/ai_promotion_decision.md`：默认 AI 决策记录
- `reports/p52_opening_small_scale_gate_20260516.md`：最新 P5 开局搜索小规模门禁报告

## 开发纪律

- Core-first：规则变化必须先落到 `core/` 和测试。
- Harness-first：AI 强弱必须用本地对战数据证明。
- GUI 不复制规则：GUI 只展示状态、收集输入并调用 core/ai/record。
- YAGNI：没有正式平台协议前，不实现平台适配细节。
- 比赛版本不引入联网依赖，不临时更换 AI 框架，不因单局输赢改默认参数。
