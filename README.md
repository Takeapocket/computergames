# 爱恩斯坦棋参赛程序

面向 2026 年辽宁省大学生计算机博弈大赛校内选拔赛的离线 Tkinter GUI 参赛程序。规则、GUI、棋谱、计时、七盘制比赛流程、崩溃自救、AI harness 已全部闭环；默认参赛 AI 为 `rollout` kind + P3 promotion 参数（Zweistein cutoff / risk-aware playout），`greedy_risk` 作为应急回退。比赛版本已封版至 `release/v1.0/`。

项目不依赖网络、不假定统一平台/API；如赛前 QQ 群发布统一平台协议，再在 `adapters/` 增加适配层，不修改 `core/` 规则语义。

## 项目结构

```text
core/        棋盘、规则、合法步、胜负判断、走子/撤销、序列化
ai/          random / greedy / greedy_risk / rollout（默认） / expectimax / expectimax_v2 /
             mcts / tactical / risk / evaluator / opening_layouts / self_capture / match
gui/         Tkinter 离线 GUI（main_window / board_widget / control_panel /
             match_mode / opening_panel / timer_panel）
record/      JSON 棋谱、状态序列化、auto_save、match_record（一轮 ≤7 盘）
adapters/    预留统一平台适配层（暂无实现）
scripts/     run_gui / smoke_test / quick_bench / tournament / param_sweep /
             search_openings / s2_rehearsal / bench_ai / bench_mcts 等
tests/       pytest 套件
docs/        RULE_ASSUMPTIONS / PROJECT_BRIEF / MATCH_CHECKLIST / EMERGENCY_GUIDE
release/v1.0/  封版产物（README / config / default_params / known_limitations / test_report / sample_records）
reports/     AI / harness / 演练 / 决策报告
replays/     auto_save 与对战 replay
```

顶层另有 `PROJECT_MEMORY.md`（项目事实快照）、`PROJECT_PHASES.md`（阶段规划与 AI 研究路线）、`AGENTS.md`（协作约束）。

## 当前能力

- 5×5 棋盘、红/蓝目标方向、骰子→棋子映射（含死子最近编号回退）、吃子（含吃本方子，R-0 已合规）、目标角与吃光两种胜利、走子与撤销、状态序列化。
- Tkinter GUI：开局录入（预设 `balanced_v1` / `aggressive_v1` / `defensive_v1` 或自定义、可录入对方布局）、骰子录入、合法走法执行、悔棋、AI 推荐显示。
- JSON 棋谱保存/加载；单方 4 分钟包干计时；盘内/盘间 auto_save 自动恢复。
- 七盘制比赛模式：甲乙身份、先手序列（甲方 1/4/5，乙方 2/3/6/7）、比分推进、先胜 4 盘判本轮胜方。
- AI 体系：`random` / `greedy` / `greedy_risk`（回退）/ `rollout`（**默认**，release 参数为 32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、risk-aware playout、Zweistein cutoff、30ms deadline safety）/ `expectimax` 与 `expectimax_v2`（实验性）/ `mcts`（实验性）/ `tactical`（战术封装）。
- P2/P2.5/P3 的其他 rollout / Zweistein 候选仅为显式实验候选，详见 `PROJECT_PHASES.md`；当前进入 `release/v1.0` 默认配置的是 P3 promotion 通过的 `rollout_zweistein_cutoff` 参数集，实现上仍使用 `kind="rollout"` + 显式 kwargs。
- adaptive rollout（32 初采样、close sample 到 128、低置信提示）是显式实验候选，不是 `release/v1.0` 默认参数；直接对旧 rollout 的 800 局合并胜率为 59.00%，未过 60% 默认晋升线。
- Harness：`quick_bench`（Wilson CI）、`tournament`（pairwise matrix）、`param_sweep`、`search_openings`，slim JSON 报告默认入库。
- `release/v1.0/` 已冻结比赛版本，含运行指引、参数、已知限制和 800 局双边晋升数据测试报告。

## 运行环境

- Python 3.11，仓库根 `.venv/` 已就绪。
- Windows + 系统自带 Tkinter，无额外依赖；离线运行。

如需新建环境：

```powershell
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
```

## 启动 GUI

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

现场操作流程详见 `release/v1.0/README.md` 与 `docs/MATCH_CHECKLIST.md`，应急处理见 `docs/EMERGENCY_GUIDE.md`。

## 测试与演练

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

## AI 评测

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red rollout --blue greedy_risk --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue rollout --games 200 --seed 2026
& ".venv/Scripts/python.exe" "scripts/tournament.py" --help
```

任何默认 AI / 参数 / 开局变更，必须以 candidate vs current default rollout 双边对战、胜率达标且 0 illegal / 0 crash / 真实 timeout telemetry 为前提，并把报告写入 `reports/`。`greedy_risk` 可继续作为辅助对手和应急回退，但不能替代当前默认基线。2026-05-15 前部分历史报告里的 `timeouts=0` 是 legacy 字段，不应单独作为新候选晋升证据。详细路线见 `PROJECT_PHASES.md` 第 5 节。

## 规则与文档

- 规则假设：`docs/RULE_ASSUMPTIONS.md`
- 项目摘要：`docs/PROJECT_BRIEF.md`
- 阶段规划与 AI 研究路线：`PROJECT_PHASES.md`
- 项目事实快照：`PROJECT_MEMORY.md`
- 协作约束：`AGENTS.md`
- 比赛规则原文：`全国计算机博弈竞赛总则.md`、`爱恩斯坦棋项目规则.md`

规则若与赛事附件冲突，优先更新 `core/` 与测试，再接 GUI、AI 或 `adapters/`。
