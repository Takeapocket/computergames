# E 盘开发交接说明

迁移完成：2026-06-14

研究状态复核：2026-08-18

## 不变结论

`E:\computergame` 是唯一主开发目录。C 盘旧仓库 `C:\Users\Takeapocket\Desktop\documents\computergames` 仅作为迁移前快照保留，不再用于开发、测试、提交或推送。

训练数据、模型、checkpoint、自对弈棋谱和缓存不得默认写入仓库或 C 盘。

```text
GitHub 仓库：https://github.com/Takeapocket/computergames.git
当前开发分支：main
E 盘项目：E:\computergame
E 盘研究数据：E:\computergame-data
pip 缓存：E:\pip-cache
torch 缓存：E:\torch-cache
```

## 2026-06-14 迁移记录

迁移使用 GitHub 干净 clone，没有复制 C 盘旧目录。迁移基线提交为：

```text
4b8b10910502fc9473c28e35c9128c65fafbe45e
Add research scaffolding and review fixes
```

当时完成的动作：

- 从 GitHub clone 到 `E:\computergame`
- 在 E 盘重建 `.venv`
- 使用 `E:\pip-cache` 安装 pytest 和研究依赖
- 创建 `E:\computergame-data`、`E:\pip-cache` 与 `E:\torch-cache`
- 修复 ladder 默认写仓库的问题，要求 `--output-dir` 或 `CG_RESEARCH_DATA_DIR`
- 补齐 ladder 元数据与混写保护、dice forensics 统计语义、fast path stale guard、MCTS 参数透传和研究产物 `.gitignore` 防线
- 保留 C 盘旧目录及其中 ignored 产物，没有删除原文件

迁移时的全量验证为：

```text
933 passed in 79.08s
```

迁移时还用 `games=0` 的 ladder smoke 确认 `report.json` 可以写入 `E:\computergame-data\ladder\report.json`。该命令属于历史迁移验证，不作为日常接手步骤，因为它会写共享报告路径。

## 当前回归快照

2026-08-18 在当前工作区重新验证：

```text
1071 passed in 74.51s
scripts/smoke_test.py：通过
```

当前 `requirements-research.txt` 仍只有 NumPy。PyTorch 尚未加入依赖，默认 GUI、core、release 和默认 AI 构造路径均不依赖它。

## 当前研究状态

`release/v1.0`、P14 Rollout 参数和 `balanced_v1` 布局继续作为历史比赛基线。实验能力均未替换 GUI/release 默认配置。

### R-P1

性能探针、可落盘 Elo 天梯、棋谱复盘、骰子审计、trusted apply 和 `GameState.clone(include_history=False)` 两项内部快路径已经实现。

现有性能报告没有同参数修改前基线，因此不能声称达到研究设计中的 5 倍提速。真实棋谱复盘和骰子取证仍需要外部棋谱输入。

### R-P2A

当前定义的 E1 至 E3 已实现：

- ExpectimaxV2 的 TT、走法排序和迭代加深
- 递归 Star1 上下界剪枝
- `star2` frontier probe 与 `star2_recursive` exact-probe 模式
- 受局面门限约束的精确残局求解器

这些结果验证正确性和接线，不构成相对 P14 的棋力结论。残局求解器尚未组成完整对局混合 AI；Star2 也没有实现 Ballard transformed alpha/beta probe window。

### R-P2B

- L0：MCTS static/playout leaf 接线和 6 局 smoke 已完成，样本不支持 playout leaf 更强的结论。
- L1：确定性、可恢复的 CEM 调参 harness 已完成。E 盘 smoke 共 4 局，只验证优化器、Elo 证据链和恢复逻辑，没有晋升默认权重。
- L2：价值网络设计已经形成，当前等待书面确认。确认后才能编写实施计划；自对弈数据生成、PyTorch 训练、checkpoint 和神经 Rollout/MCTS 适配器均尚未实现。

L2 首版教师固定为 P14 rollout self-play。特征为绝对方向的 `13×5×5 float32`，标签为 RED 视角 `+1/-1/0`，训练集与验证集按 game ID 切分。PyTorch 必须保持研究路径惰性导入，不能渗入 core、GUI、release 或默认 AI。

## 新对话接手步骤

1. 确认工作目录为 `E:\computergame`，不要回到 C 盘旧快照。
2. 读取：
   - `PROJECT_MEMORY.md`
   - `PROJECT_PHASES.md`
   - `README.md`
   - `docs/RULE_ASSUMPTIONS.md`
   - `docs/PROJECT_BRIEF.md`
   - `docs/E_DRIVE_HANDOFF_20260614.md`
3. 若继续 L2，再读取 `docs/superpowers/specs/2026-08-03-rp2b-l2-value-network-design.md`。
4. 用只读 Git 命令确认当前分支、提交和工作区状态，不要假设交接文档中的历史提交仍是 HEAD。
5. 设置研究环境变量，再运行验证。

```powershell
cd E:\computergame
git status --short
git rev-parse --short HEAD

$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"

& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --help
& ".venv/Scripts/python.exe" "scripts/tune_eval_weights.py" --help
```

不要把 `ladder.py --games 0` 作为日常接手验证写入共享 ladder 目录。需要运行 ladder 时，为每次实验使用唯一的新输出目录。

## 研究纪律

- AI 棋力结论只认可复现的批量对战或带完整证据的 Elo 实验。
- P14 是默认基线和 1500 锚点；小样本结果不得改动默认 AI、布局或 release 参数。
- 训练数据、模型、checkpoint、自对弈棋谱、pip 缓存和 torch 缓存一律放 E 盘。
- `scripts/ladder.py` 和 `scripts/tune_eval_weights.py` 必须使用显式输出目录，或从 `CG_RESEARCH_DATA_DIR` 派生目录。
- 旧失败路线重开前先写新的技术假设和门禁，参考 `reports/ai_experiment_stop_list_20260518.md`。
- L2 设计稿书面确认后才能编写实施计划；计划批准前不安装 PyTorch、不生成训练数据、不修改生产路径。
- L2 有界 smoke 只能证明 pipeline 与 wiring 可用，不能作为棋力晋升证据。
