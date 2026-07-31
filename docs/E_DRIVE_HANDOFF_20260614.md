# E 盘开发交接说明

更新时间：2026-06-14

## 当前结论

`E:\computergame` 是后续唯一主开发目录。C 盘旧仓库
`C:\Users\Takeapocket\Desktop\documents\computergames` 已弃用，仅作为迁移前快照保留，不再用于开发、测试、提交或推送。

本次交接已经完成从 GitHub 干净 clone 到 E 盘，而不是复制旧目录：

```text
GitHub 仓库：https://github.com/Takeapocket/computergames.git
当前分支：main
当前提交：4b8b10910502fc9473c28e35c9128c65fafbe45e
E 盘项目：E:\computergame
E 盘研究数据：E:\computergame-data
pip 缓存：E:\pip-cache
torch 缓存：E:\torch-cache
```

## 已完成动作

- 修复 `scripts/ladder.py` 的 C 盘默认输出问题：CLI 不再默认写仓库内 `data/ladder`，必须显式传 `--output-dir` 或设置 `CG_RESEARCH_DATA_DIR`。
- 修复代码审查 Important 及以下问题：ladder JSONL 元数据、非空 `games.jsonl` 混写保护、dice forensics 威胁巧合度语义、chi-square 统计输出、fast path stale guard、MCTS helper 参数透传、RolloutPairedAI characterization、研究缓存/权重 `.gitignore` 防线和相关文档口径。
- 当前修复已提交并推送到 GitHub `main`：`4b8b109 Add research scaffolding and review fixes`。
- 已从 GitHub clone 到 `E:\computergame`。
- 已在 `E:\computergame` 重建 `.venv`。
- 已用 `E:\pip-cache` 安装测试依赖和 `requirements-research.txt`；当前研究依赖只有 `numpy`，`torch` 延后到 R-P2B 需要时再引入。
- 已创建 `E:\computergame-data`、`E:\pip-cache`、`E:\torch-cache`。
- C 盘旧目录未删除；其中 ignored 的旧 `data/ladder` 产物也未删除。

## 已验证状态

在 `E:\computergame` 中验证：

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" -m pytest -q
```

结果：

```text
933 passed in 79.08s
```

ladder smoke：

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --red p14_default --blue random --games 0
```

结果确认 `report.json` 写入：

```text
E:\computergame-data\ladder\report.json
```

`games=0` 不生成 `games.jsonl` 是预期行为；报告内的 `games_jsonl` 路径指向
`E:\computergame-data\ladder\games.jsonl`。

## 后续新对话接手步骤

1. 工作目录使用 `E:\computergame`，不要回到 C 盘旧目录。
2. 先读：
   - `PROJECT_MEMORY.md`
   - `PROJECT_PHASES.md`
   - `README.md`
   - `docs/RULE_ASSUMPTIONS.md`
   - `docs/PROJECT_BRIEF.md`
   - `docs/E_DRIVE_HANDOFF_20260614.md`
3. 开始前运行：

```powershell
cd E:\computergame
git status --short
git rev-parse --short HEAD
```

4. 研究脚本默认使用 E 盘环境变量：

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
```

5. 常用验证：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/ladder.py" --red p14_default --blue random --games 0
```

## 当前研究状态

项目已从比赛交付转入长期 AI 棋力研究。`release/v1.0` 和 P14 默认 rollout 参数保留为历史基线与天梯 1500 锚点。

当前可继续推进的主线：

- R-P1：性能基线、fast path 后续优化、持久 Elo 天梯、真实棋谱复盘、骰子取证。
- R-P2A：ExpectimaxV2 经典搜索线。当前已到 Star1 root chance pruning 入口，完整递归 Star1/Star2 interval pruning 尚未实现。
- R-P2B：MCTS / learning 线。当前仅完成 leaf playout L0 入口和小样本 smoke，暂无棋力提升结论。

研究纪律：

- AI 棋力结论只认持久天梯或批量 harness 数据。
- 默认 AI、默认布局、release 配置不得因单局结果变更。
- 训练数据、模型权重、自对弈棋谱、pip/torch cache 一律放 E 盘。
- README 及对外文档不写比赛结果信息。
- 旧失败路线重开必须先写新技术假设和门禁，参考 `reports/ai_experiment_stop_list_20260518.md`。
