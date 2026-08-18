# 爱恩斯坦棋 / Einstein Chess

用 Python 3.11 编写的爱恩斯坦棋实现，包含离线 Tkinter GUI、规则引擎、AI 对战接口和可复现实验工具。

项目最初用于离线计算机博弈比赛，现在作为长期 AI 棋力研究平台维护。`release/v1.0/` 保存比赛基线的配置、说明和验收材料；主分支继续开发搜索算法、评估函数与自对弈研究工具。

[快速开始](#快速开始) · [常用命令](#常用命令) · [项目状态](#项目状态) · [研究与复现](#研究与复现) · [文档](#文档)

## 功能

- 实现 5×5 棋盘、骰子映射、合法自吃、胜负判断、走子撤销和状态序列化
- 提供开局录入、手动或程序掷骰、对手走法录入和 AI 推荐界面
- 支持单方计时、七盘制流程、JSON 棋谱、自动保存和崩溃恢复
- GUI 默认使用 P14 Rollout，并在异常时回退到 `greedy_risk`
- 提供 ExpectimaxV2、MCTS 和受局面门限约束的精确残局求解器作为实验入口
- 提供 AI 对战、Elo 天梯、性能探针、CEM 调参、棋谱复盘和骰子审计脚本

程序运行时不依赖网络服务或数据库。所有规则判断都来自 `core/`，GUI 和 AI 不维护各自的规则副本。

## 快速开始

项目主要在 Windows 上开发和验证。使用 PowerShell：

```powershell
git clone https://github.com/Takeapocket/computergames.git
cd computergames

python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

也可以双击根目录的 `启动项目.cmd`，从菜单启动 GUI、运行测试或查看当前 release 配置。

Linux 或 macOS 可使用下列命令形式。部分 Linux 发行版需要单独安装 Tkinter，当前仓库没有跨平台 CI：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python scripts/run_gui.py
```

## 常用命令

运行全量测试和规则 smoke：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

运行一组不写报告文件的快速对战：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" `
  --red greedy_zweistein `
  --blue greedy_risk `
  --games 20 `
  --starting-layout balanced_v1 `
  --no-save-report
```

根目录启动器还提供赛前检查、S2 演练和 timing probe。使用 `scripts/launcher.py --list` 可以查看全部入口。

## 项目状态

| 部分 | 当前状态 |
|---|---|
| 规则、GUI 与棋谱 | 比赛主链路已经完成，`release/v1.0/` 保留配置和验收材料。 |
| 默认 AI | GUI/release 使用 P14 Rollout：初始采样 64 次，接近候选最多采样 96 次；默认布局是 `balanced_v1`，回退 AI 是 `greedy_risk`。完整参数见 `release/v1.0/default_params.json`。 |
| 搜索研究 | ExpectimaxV2、MCTS 和精确残局求解器均可独立评测，目前没有替换 P14，也没有棋力晋升结论。 |
| 学习研究 | 自动调参工具已经可复现运行。价值网络只有待确认的设计稿，仓库中尚无自对弈生成、PyTorch 训练、checkpoint 或神经评估适配器。 |

当前回归快照来自 2026-08-18：`1071 passed in 74.51s`，`scripts/smoke_test.py` 通过。P14 在本地 Elo 报告中固定为 1500 锚点，这个数字是比较起点，不是外部等级分。

## 项目结构

```text
core/           棋盘状态、规则、合法步和序列化
ai/             评估函数、搜索算法和 AI 对战接口
gui/            Tkinter 桌面界面
record/         棋谱、自动保存和恢复
scripts/        启动、测试、评测和研究工具
tests/          pytest 测试
docs/           规则说明、设计文档和开发计划
reports/        可提交的小型实验报告
release/v1.0/   历史比赛基线的配置、说明和验收材料
adapters/       外部平台适配层预留目录
```

`core/` 是规则事实源。`gui/` 只处理显示和输入，`ai/` 通过公开状态与合法步接口搜索，`record/` 负责保存和恢复。`adapters/` 目前没有平台实现，只有确认正式协议后才会增加适配层。

## 研究与复现

安装现有研究依赖：

```powershell
& ".venv/Scripts/python.exe" -m pip install -r requirements-research.txt
```

`requirements-research.txt` 目前只有 NumPy。L2 尚未实施，因此仓库没有固定 PyTorch 版本，默认 GUI、core 和 release 也不导入 PyTorch。

训练数据、模型、天梯记录、缓存和大体积棋谱必须放在仓库外。下面使用 E 盘作为示例，请替换成自己的绝对路径：

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/einstein-chess-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --help
& ".venv/Scripts/python.exe" "scripts/tune_eval_weights.py" --help
```

主要研究入口：

| 脚本 | 用途 |
|---|---|
| `scripts/quick_bench.py` | 固定种子的双 AI 快速对战与 JSON 汇总 |
| `scripts/ladder.py` | 双人或 round-robin Elo 评测，记录对局和不确定度 |
| `scripts/perf_probe.py` | 对局耗时、Rollout visits 和热路径计数 |
| `scripts/replay_analyze.py` | 分析 GameRecord 或 MatchRecord，并可对照 P14 推荐 |
| `scripts/dice_forensics.py` | 骰子分布、卡方统计和条件巧合度审计 |
| `scripts/tune_eval_weights.py` | 可恢复的 CEM 评估权重搜索 |

天梯会拒绝复用已有的非空 `games.jsonl`；CEM 调参会校验新目录和 `--resume` 配置。每次实验应保留对局数、随机种子、双方颜色、AI 签名、错误统计、耗时和置信区间。

本项目维护者当前使用的目录映射见 [E 盘开发交接](docs/E_DRIVE_HANDOFF_20260614.md)。

单局、少量 smoke、训练损失和一次性能探针只说明程序可以运行或结果符合局部预期。AI、布局或 release 参数发生变化前，需要单独设计足够样本的对照实验。

## 规则摘要

双方在 5×5 棋盘上各有 6 枚编号棋子。每回合的六面骰决定可移动棋子；对应编号已经被吃掉时，改走编号最接近的存活棋子，两侧等距时可以二选一。目标格上的棋子会被吃掉，包括本方棋子。任意棋子到达对角目标格，或一方吃光对方棋子，立即获胜。

正式规则没有和棋。研究 harness 的 `max_turns` 平局只用于限制实验长度。完整规则和赛事边界见 [规则记录](docs/RULE_ASSUMPTIONS.md)。

## 文档

- [项目简介](docs/PROJECT_BRIEF.md)
- [研究路线与阶段](PROJECT_PHASES.md)
- [规则记录](docs/RULE_ASSUMPTIONS.md)
- [E 盘开发交接](docs/E_DRIVE_HANDOFF_20260614.md)
- [研究转型设计](docs/superpowers/specs/2026-06-13-research-transition-design.md)
- [R-P2A 精确残局报告](reports/rp2a_exact_endgame_20260731.md)
- [R-P2B L1 CEM 报告](reports/rp2b_l1_cem_tuning_20260803.md)
- [R-P2B L2 价值网络设计](docs/superpowers/specs/2026-08-03-rp2b-l2-value-network-design.md)
- [比赛基线说明](release/v1.0/README.md)
- [比赛操作清单](docs/MATCH_CHECKLIST.md)
- [实验报告目录](reports/)

## 参与开发

提交 issue 或 pull request 前，请确认：

1. 规则改动先进入 `core/`，并有对应测试。
2. `python -m pytest -q` 可以通过。
3. 训练数据、模型、缓存和大体积棋谱没有进入仓库。
4. AI 强度结论附有可复现的批量对战结果。
5. 默认配置变化直接对 P14 基线做过门禁验证。

`release/v1.0/` 是历史基线。没有充分评测证据时，不修改该目录的默认配置。

## 许可证

项目原创代码和文档采用 [MIT License](LICENSE)。仓库中的官方赛事通知和规则材料不在 MIT 授权范围内，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
