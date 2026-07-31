# 爱恩斯坦棋离线 GUI 参赛程序

面向 2026 年辽宁省大学生计算机博弈大赛（暨中国大学生计算机博弈大赛辽宁选拔赛）的爱恩斯坦棋程序：Python + Tkinter 离线 GUI，按"操作员辅助参赛"设计。比赛现场默认离线运行，不依赖网络、数据库或统一平台 API；若后续确认统一平台协议，只在 `adapters/` 增加适配层，`core/` 规则语义不变。

仓库已完成 v1.0 封版：规则引擎、GUI、七盘制比赛流程、计时提示、棋谱与崩溃恢复、默认 AI、赛前检查脚本和 Windows 双击启动器全部落地。项目当前已转入**长期研究模式**（2026-06 起）：以这套可运行程序为基础研究爱恩斯坦棋 AI 棋力，v1.0 锁定配置保留为历史基线与评测锚点；研究路线图见 `PROJECT_PHASES.md` §2.5。当前主开发目录为 `E:\computergame`，C 盘旧目录已弃用。

## 当前状态

| 项目 | 当前结论 |
|---|---|
| 主开发目录 | `E:\computergame` |
| C 盘旧目录 | 已弃用，仅作为迁移前快照保留，不再开发/测试/提交 |
| 研究数据/cache | `E:\computergame-data`、`E:\pip-cache`、`E:\torch-cache` |
| 当前提交 | `4b8b10910502fc9473c28e35c9128c65fafbe45e` |
| 参赛版本 | `release/v1.0/`，P14 默认参数已锁定（2026-05-18） |
| 现场入口 | 根目录 `启动项目.cmd` 双击打开菜单 |
| 默认 AI | `rollout` kind + P14 promotion 显式参数（明细见下） |
| 应急回退 | `greedy_risk`，再退到第一条合法步 |
| 默认布局 | `balanced_v1`，全部布局候选均未过晋升门禁 |
| 计时判负 | 默认只提示超时，以裁判判定为准；裁判要求时可开启程序自动超时判负 |
| 规则实现 | 已对齐国赛规则：目标格有棋子即吃掉（含本方子）、无和棋 |
| 测试基线 | 全量 pytest 933 passed（2026-06-14 复验）；preflight 成功输出 `READY FOR MATCH` |
| 赛程背景 | 省赛正式比赛日 2026-06-07（沈阳航空航天大学），通知 PDF 在仓库根目录 |

注意：`release/archives/` 下的 zip 归档生成于 2026-05-15，内含的 `default_params.json` 仍是 P3 之前的旧 flat 参数，早于 P14 锁定。现场和备机一律以当前仓库 `release/v1.0/` 目录为准，不要直接使用旧 zip。

## 现场最快启动

比赛电脑上优先用双击入口：

```text
启动项目.cmd
```

菜单包含 7 个入口：

1. 启动 GUI
2. 一键赛前总检查
3. 完整 pytest
4. smoke 测试
5. S2 七盘制演练
6. timing budget probe（16 样本，刷新 preflight timing 报告）
7. release/default 状态显示

命令行等价入口：

```powershell
& ".venv/Scripts/python.exe" "scripts/launcher.py"          # 菜单
& ".venv/Scripts/python.exe" "scripts/run_gui.py"           # 直接打开 GUI
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"   # 赛前总检查
```

赛前总检查成功时最后输出：

```text
READY FOR MATCH
```

## 运行环境

- Windows + Python 3.11，Tkinter 标准库 GUI
- 测试框架 pytest
- 不依赖网络服务、数据库或生产 API
- 长期研究数据、模型权重、自对弈棋谱和 pip/torch 缓存放 E 盘，不写入 C 盘旧仓库

优先使用仓库内 `.venv/`。如需重建虚拟环境：

```powershell
python -m venv ".venv"
& ".venv/Scripts/python.exe" -m pip install pytest
```

E 盘研究环境建议：

```powershell
cd E:\computergame
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" -m pytest -q
```

当前 E 盘交接验证结果：`933 passed in 79.08s`。详细交接记录见 `docs/E_DRIVE_HANDOFF_20260614.md`。

## 锁定的默认配置

默认 AI 实现为 `kind="rollout"` + P14 promotion 显式参数：

| 参数 | 值 |
|---|---|
| rollouts_per_move | 64 |
| max_rollout_turns | 80 |
| max_step_time_ms | 2000.0 |
| epsilon | 0.05 |
| close_sample_margin / rollouts | 0.08 / 96 |
| low_confidence_margin | 0.08 |
| playout_policy | greedy_risk |
| cutoff_eval | zweistein |
| deadline_safety_ms | 80.0 |

- 配置真值来源：`release/v1.0/default_params.json`；`tests/test_release_consistency.py` 锁定 GUI/release 默认一致性。
- GUI 推荐兜底链固定为：默认 rollout → `greedy_risk` → 第一条合法步 → 无合法步提示。
- 默认开局布局 `balanced_v1`。
- P14 晋升依据：两轮 50+50 合并 118/200 = 59.0%，Wilson CI [52.1%, 65.6%]，0 illegal/crash/timeout；决策记录见 `reports/ai_promotion_decision.md` 与 `release/v1.0/test_report.md`。

## 已实现能力

### 规则与状态（core/）

- 5x5 棋盘，双方各 6 子（编号 1-6）；红方目标角 `(4, 4)`，蓝方目标角 `(0, 0)`。
- 红方向下、右、右下移动；蓝方向上、左、左上移动。
- 骰子点数映射存活棋子；编号已死时选最近编号，双向等距时两个都可选。
- 目标格有棋子即吃掉，包括本方棋子；到达目标角或吃光对方立即获胜，无和棋。
- 走子、撤销、序列化/反序列化；程序掷骰使用 `secrets.randbelow`。

### GUI 与比赛流程（gui/）

- 开局录入：预设布局、自定义布局、对方布局录入。
- 骰子录入：手动录入外部骰子结果，或在双方同意时点击"程序掷骰"。
- 单方时限计时显示，默认 240 秒，比赛模式弹窗可改（决赛加赛可改 600）。
- 超时默认只提示；裁判确认后可用计时面板按钮记分；裁判要求时可开启自动超时判负。
- 七盘制比赛模式：甲乙身份、先手序列、比分推进、先胜 4 盘。
- AI 推荐显示候选诊断（visits / score / winrate / 低置信标记）与推荐来源。

### 棋谱与恢复（record/）

- JSON 棋谱保存与加载；盘内 auto-save、整轮 auto-save、崩溃后恢复。
- 损坏 auto-save 启动时自动清理，不阻塞 GUI。
- 计时数据拒绝 `nan/inf/负数` 等损坏值。

### AI 与评测（ai/ + scripts/）

- 默认推荐：上表 P14 参数的 rollout；应急 AI：`greedy_risk`。
- 实验 AI（均未过门禁，仅保留为研究代码）：`expectimax` / `expectimax_v2`、`mcts`、Zweistein / Zweistein-DP 系列、root racing、material/self-capture guard、paired 系列。
- 评测工具链：`quick_bench.py`（快速对战）、`bench_ai.py`（candidate/promotion 门禁）、`tournament.py`（多 AI 矩阵）、`param_sweep.py`（参数搜索）、`search_openings.py` / `screen_openings_light.py` / `compare_opening_layouts.py`（开局搜索、轻量筛查与布局对比）、`analyze_rollout_failures.py` / `analyze_threat_defense.py`（失败归因与审计）、`timing_budget_probe.py`（步时预算探测）。

默认 AI 或默认布局的变更必须由 harness 数据支撑，单局输赢不构成变更理由。

## 现场操作链路

1. 启动 GUI，进入比赛模式：选我方颜色、甲乙身份、单方时限，确认是否开启自动超时判负。
2. 录入或选择双方开局。
3. 按裁判或双方约定录入骰子，或点击"程序掷骰"。
4. 录入对方走法；查看我方推荐与候选诊断；执行我方走法。
5. 单盘结束自动推进比分，任一方 4 胜后结束本轮。

现场细节、应急处理和逐步检查表见：

- `docs/MATCH_CHECKLIST.md`（赛前 24 小时 / 赛前 30 分钟 / 每盘 / 盘间 / 赛后）
- `docs/EMERGENCY_GUIDE.md`（崩溃、误操作、超时处理）
- `release/v1.0/README.md` 与 `release/v1.0/known_limitations.md`

## 常用命令

```powershell
& ".venv/Scripts/python.exe" -m pytest                       # 完整测试
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"         # GUI smoke
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"       # 七盘制自动演练
& ".venv/Scripts/python.exe" "scripts/launcher.py" --list    # 启动器菜单一览
& ".venv/Scripts/python.exe" "scripts/launcher.py" --run status   # release/default 状态
```

AI candidate bench 示例（候选必须直接对当前 release 默认配置）：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" --candidate <kind> --stage candidate --report-name <报告名>
```

## 项目结构

```text
core/             棋盘、规则、合法步、胜负判断、走子/撤销、序列化、程序掷骰
ai/               random、greedy、greedy_risk、rollout、expectimax、mcts、
                  Zweistein/Zweistein-DP、risk、opening_layouts、match
gui/              Tkinter GUI：棋盘、控制面板、开局录入、计时、七盘制流程
record/           JSON 棋谱、auto-save、整轮记录
scripts/          启动器、GUI 入口、赛前检查、测试与评测/搜索/归因脚本
tests/            pytest 自动测试（933 条）
docs/             规则假设、项目摘要、现场清单、应急手册、设计/计划文档
reports/          AI 评测、开局搜索、审计与默认决策报告
release/v1.0/     比赛版本目录（配置真值）
release/archives/ 历史打包（2026-05-15，内含旧参数，勿直接使用）
records/          现场棋谱归档目录
replays/          auto-save 与对战 replay
output/           参赛提交物（程序设计说明书等）
adapters/         平台/API 适配层预留，未实现具体协议
启动项目.cmd       现场双击入口
```

## 关键文档

- `PROJECT_MEMORY.md`：当前事实快照和历史决策。
- `PROJECT_PHASES.md`：阶段规划、验收门槛和 AI 研究路线。
- `docs/E_DRIVE_HANDOFF_20260614.md`：E 盘迁移、虚拟环境、数据/cache 目录和新对话接手说明。
- `docs/RULE_ASSUMPTIONS.md`：规则假设与国赛规则对齐记录。
- `docs/PROJECT_BRIEF.md`：项目定位、当前阶段和边界。
- `reports/ai_promotion_decision.md`：默认 AI 决策记录。
- `reports/ai_experiment_stop_list_20260518.md`：全部未晋升路线总表与重开条件。
- `release/v1.0/test_report.md`：封版测试与默认 AI 晋升依据。
- 根目录《全国计算机博弈竞赛总则.md》《爱恩斯坦棋项目规则.md》：规则原文。

## 规则边界

完整规则以 `docs/RULE_ASSUMPTIONS.md` 为准。当前已确认：

- 开局棋位可以任意摆放，没有组委会强制布局。
- 吃本方棋子是合法走法。
- 每盘单方 4 分钟包干，超时判负；程序默认只提示，现场判罚以裁判为准。
- 每轮最多 7 盘，先胜 4 盘；甲方第 1/4/5 盘先手，乙方第 2/3/6/7 盘先手。
- 比赛中禁止联网；统一平台不是默认假设。
- 程序崩溃 = 该方判负（因此兜底链和 auto-save 是硬要求）。

如果赛事附件与当前实现冲突，处理顺序固定为：先改 `core/` 与测试，再接 GUI、AI 或 adapters。

## AI 晋升纪律

当前基线是 release 默认 `rollout` 显式 kwargs（P14），不是旧 flat rollout，也不是 `greedy_risk`。任何默认 AI、参数或默认布局变更必须满足：

- 直接对当前 release 默认配置评测，红蓝双边对战。
- 报告写入 `reports/`，包含 games、seed、胜率、Wilson CI、illegal、crashes、真实 timeouts、平均/最大步时。
- `illegal_moves = 0`、`crashes = 0`、真实 `timeouts = 0`。
- 胜率未过门禁只保留为实验候选，不进入 GUI/release 默认。

未晋升路线（MCTS、Zweistein-DP、threat rerank、root racing、guard/paired 系列、P5.x 与 curated 开局等）统一见 `reports/ai_experiment_stop_list_20260518.md`；重开任何路线需先写清楚新技术假设与门禁，并满足该报告的"重新打开条件"。唯一一个过初筛但未扩样确认的配置是 `rollout_strong_96`（25+25 初筛 60.0%，未做 50+50 确认，未晋升）。

## 开发纪律

- Core-first：规则变化先进入 `core/` 并补测试。
- Harness-first：AI 强弱只认本地批量对战数据。
- GUI 不复制规则：界面只展示状态、收集输入并调用 `core/ai/record`。
- YAGNI / KISS / DRY：没有正式平台协议不实现适配细节；封版期只修现场风险 bug；重复逻辑收敛到 `core/` 与评测 harness。
- 比赛版本不临时联网、不临时换 AI 框架、不因单局输赢改默认参数。
