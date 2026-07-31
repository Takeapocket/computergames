# 爱恩斯坦棋（Einstein Chess）

一个用 Python 编写的爱恩斯坦棋程序，包含规则引擎、Tkinter 图形界面、棋谱保存、多种 AI 和本地评测工具。

项目最初用于离线计算机博弈比赛。比赛版本保留在 `release/v1.0/`，主分支则继续用于搜索算法、评估函数和自对弈研究。

## 功能

- 完整的 5x5 爱恩斯坦棋规则、合法步生成、胜负判断和走子撤销
- 可录入布局、骰子和对手走法的桌面 GUI
- 对局计时、七盘制流程、自动保存和崩溃恢复
- Greedy、Rollout、Expectimax、MCTS 和精确残局求解器
- AI 对战、Elo 天梯、性能探测、参数调优和棋谱分析脚本
- 固定随机种子、JSON 报告和 pytest 回归测试

## 游戏规则

棋盘为 5x5，双方各有 6 枚编号棋子。每回合掷一次六面骰，点数决定本回合可移动的棋子；对应编号已经被吃掉时，改走编号最接近的存活棋子。先到达对角目标格或吃光对方棋子的一方获胜。

本项目采用的具体规则和已确认边界见 [docs/RULE_ASSUMPTIONS.md](docs/RULE_ASSUMPTIONS.md)。

## 环境要求

- Python 3.11
- Tkinter（Windows 官方 Python 安装包默认包含）
- pytest（仅测试需要）
- NumPy（仅研究脚本需要）

程序运行时不依赖网络服务或数据库。

## 快速开始

```powershell
git clone https://github.com/Takeapocket/computergames.git
cd computergames

python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

Windows 用户也可以双击根目录的 `启动项目.cmd`，从菜单启动 GUI、测试或赛前检查。

在 Linux 或 macOS 上，Python 命令改为：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python scripts/run_gui.py
```

部分 Linux 发行版需要通过系统包管理器单独安装 Tkinter。

## 运行测试

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

规则变更应先进入 `core/` 并补充测试。GUI 只负责展示和输入，不维护另一套规则实现。

## AI 对战与研究

运行一组不写报告文件的快速对战：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" `
  --red greedy_zweistein `
  --blue greedy_risk `
  --games 20 `
  --no-save-report
```

安装研究脚本依赖：

```powershell
& ".venv/Scripts/python.exe" -m pip install -r requirements-research.txt
```

较大的天梯结果、自对弈数据和模型文件不应写入仓库。相关脚本接受显式输出目录，部分脚本也读取 `CG_RESEARCH_DATA_DIR`：

```powershell
$env:CG_RESEARCH_DATA_DIR = "D:/computergame-data"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --help
& ".venv/Scripts/python.exe" "scripts/tune_eval_weights.py" --help
```

AI 强度结论以批量对战数据为准。报告应保留对局数、随机种子、双方颜色、错误统计和耗时信息。

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
release/v1.0/   保留的比赛版本和默认配置
adapters/       外部平台适配层预留目录
```

## 文档

- [项目简介](docs/PROJECT_BRIEF.md)
- [开发路线](PROJECT_PHASES.md)
- [规则假设](docs/RULE_ASSUMPTIONS.md)
- [比赛版本说明](release/v1.0/README.md)
- [比赛操作清单](docs/MATCH_CHECKLIST.md)
- [实验报告](reports/)

## 参与开发

欢迎提交 issue 或 pull request。提交前请确认：

1. 新行为有对应测试。
2. `python -m pytest -q` 可以通过。
3. 没有把训练数据、模型、缓存或大体积棋谱加入仓库。
4. 涉及 AI 强度的结论附有可复现的批量对战结果。

`release/v1.0/` 是历史基线。实验算法可以继续演进，但不应在没有评测数据时改动该版本的默认配置。

## 许可证

项目原创代码和文档采用 [MIT License](LICENSE)。仓库中的官方赛事通知和规则材料不在 MIT 授权范围内，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
