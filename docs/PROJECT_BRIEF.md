# 爱恩斯坦棋 AI 研究项目简介

更新时间：2026-10-18

## 当前审查结论

新版 PySide6 0.2 已迁移自定义开局、七盘制、完整计时及自动保存恢复，入口和验证见 [桌面比赛流程报告](../reports/desktop_match_20261018.md)。它与旧 Tk 界面并存，复用相同规则、P14 和旧棋谱格式。当前开发机的测试与独立干净 Windows 验收分开记录，后者尚未完成。

2026-10-18 已修正核心骰子映射：对应编号缺失时分别允许低侧最大号与高侧最小号，不要求两侧等距。当前规则版本为 `einstein-nearest-sides-v2`。此前胜率、Elo、布局和调参结果只能说明旧规则下的表现，不能用于当前棋力晋升。

本轮还加固了棋谱快照隔离、实验版本边界、计时校验和开局保存错误提示；实施见 [全项目审查报告](../reports/project_review_20261018.md)。随后完成新规则下 P14 对历史 Rollout 参数的固定种子换色评测：200 局 104 胜，52%，pair bootstrap 95% 区间 45%–59%，尚不能确认优势；非法步/崩溃/截断/真实越限均为 0。默认参数保留，下一步同时间上限对照与单因素消融，详见 [P14 基线报告](../reports/p14_rebaseline_v2_20261018.md)。学习线 L2 尚未实施。

赛事合规不能只看软件功能或测试数。具体赛事、现场人机操作、设计文档、AI 辅助披露与个人贡献的核查见 [赛事要求与合规证据](COMPETITION_COMPLIANCE.md)。当前未形成完整参赛合格结论。

## 项目定位

本项目是一个以爱恩斯坦棋离线 GUI 为基础的长期 AI 棋力研究平台。规则引擎、桌面程序、棋谱与比赛流程已经完成；当前开发重点是搜索算法、评估函数、实验基础设施和后续学习管线。

`release/v1.0/` 保存历史比赛基线的配置、说明和验收材料。GUI/release 的默认 AI、默认布局和 core 规则不会因单局结果或小样本 smoke 改动。

当前唯一主开发目录是 `E:\computergame`。C 盘旧目录仅保留为迁移前快照，不再用于开发、测试、提交或推送。

## 当前基线

| 项目 | 当前配置 |
|---|---|
| GUI/release 默认 AI | `kind="rollout"`，使用 P14 显式参数 |
| P14 参数 | 64 rollout / move、80 half-turn cutoff、2000ms step deadline、epsilon 0.05、close sample 96、`greedy_risk` playout、Zweistein cutoff、`deadline_safety_ms=80.0` |
| 回退 AI | `greedy_risk` |
| GUI/release 默认布局 | `balanced_v1` |
| 天梯锚点 | P14 固定为 1500；这是本地比较起点，不是外部等级分 |
| 当前回归 | 见桌面比赛流程报告中的全量、Qt 专项及 EXE 验证；P14 200 局基线证据保持独立，不用 UI 测试推导棋力结论 |

比赛主链路包括开局录入、手动或程序掷骰、对手走法录入、AI 推荐、单方计时、七盘制、JSON 棋谱、自动保存和崩溃恢复。详细操作见 `docs/MATCH_CHECKLIST.md` 与 `docs/EMERGENCY_GUIDE.md`。

## 研究进度

### R-P1：研究地基

已经实现：

- `scripts/perf_probe.py`：对局耗时、Rollout visits 和热路径计数
- `scripts/ladder.py`：双人或 round-robin Elo 评测与不确定度
- `scripts/replay_analyze.py`：GameRecord/MatchRecord 复盘和 P14 推荐对照
- `scripts/dice_forensics.py`：骰子分布、卡方统计和条件巧合度审计
- `GameState._apply_known_legal_move()` 与 `GameState.clone(include_history=False)` 两项内部快路径

现有性能报告没有保存同参数修改前基线，因此不能声称达到研究设计中的 5 倍提速目标。真实棋谱复盘和骰子取证也仍需要外部棋谱输入。

### R-P2A：经典搜索

当前定义的 E1 至 E3 已实现：

- ExpectimaxV2 的稳定状态键、值域门禁和 exact-only TT
- 走法排序与迭代加深
- 递归 Star1 上下界剪枝
- `star2` frontier probe 与独立的 `star2_recursive` exact-probe 模式
- 受局面门限约束的精确残局求解器

精确残局求解器只接受总活子不超过 3，或所有活子到目标角的 Manhattan 总距离不超过 6 的非终局。它没有 deadline，也尚未并入完整对局混合 AI。

这些历史结果记录组件实现及当时的测试边界，没有证明 ExpectimaxV2、Star2 或残局求解器强于当前 P14。本轮 core 规则已经修正，需重新评测；默认 AI 参数与 release 配置仍保留。

### R-P2B：MCTS 与学习线

- L0 已接通 MCTS static leaf 与 playout leaf。6 局 smoke 为 `illegal_moves=0`、`crashes=0`、`timeouts=0`，样本不支持 playout leaf 更强的结论。
- L1 已完成确定性、可恢复的 CEM 评估权重调参 harness。E 盘 smoke 为 1 代、2 个候选、4 局；它只验证优化器、Elo 证据链和恢复逻辑，没有晋升默认权重。
- L2 价值网络设计已经形成，当前等待书面确认。确认后才能编写实施计划；自对弈数据生成、PyTorch 训练、checkpoint 和神经 Rollout/MCTS 适配器尚未实现，`requirements-research.txt` 仍只有 NumPy。

L2 的首版教师固定为 P14 rollout self-play。设计使用绝对方向的 `13×5×5 float32` 特征、RED 视角 `+1/-1/0` 标签，并按 game ID 切分训练集和验证集。PyTorch 必须保持研究路径惰性导入，不能成为 core、GUI、release 或默认 AI 的依赖。

## 技术栈与分层

- Python 3.11
- PySide6 桌面 GUI（独立 `.venv-desktop`）与保留的 Tkinter GUI
- pytest
- NumPy，当前仅用于研究脚本
- PyTorch 尚未加入依赖；L2 实施时再固定兼容版本和 CUDA 来源

目录职责：

- `core/`：棋盘状态、规则、合法步、胜负、走子/撤销和序列化
- `ai/`：评估函数、搜索算法和 AI 构造入口
- `gui/`：显示、输入和 core/AI 调用，不复制规则
- `record/`：棋谱、自动保存和恢复
- `scripts/`：启动、测试、评测和研究工具
- `adapters/`：外部平台协议预留；当前没有实现

## 数据与存储边界

```text
仓库：E:\computergame
研究数据、天梯、调参、自对弈和模型：E:\computergame-data
pip 缓存：E:\pip-cache
torch 缓存：E:\torch-cache
C 盘旧目录：仅迁移前快照
```

研究脚本必须接收显式输出目录，或从 `CG_RESEARCH_DATA_DIR` 派生目录。训练数据、模型、checkpoint、缓存和大体积棋谱不得默认写入仓库。

## 工程与证据约束

- 规则变化先改 `core/` 和测试，再接 GUI 或 AI。
- AI 强弱只由可复现的批量对战或带完整证据的 Elo 实验判断。
- 固定 seed、AI 签名、双方颜色、错误统计、耗时和置信区间必须随报告保存。
- 单局、少量 smoke、训练损失或一次性能探针不能作为棋力晋升证据。
- 默认 AI、布局或 release 参数变更前，候选必须直接对 P14 基线通过单独设计的门禁。
- 未确认平台协议前，不在 core 或 GUI 预写平台逻辑。

## 当前未闭环事项

1. P14 对历史参数的当前规则基线已完成；尚需同时间上限和单因素对照，区分约 2.59 倍耗时与未证实的胜率收益。旧规则结果不能混用，旧 CEM 目录不能直接 resume。
2. R-P1 的性能优化缺少同参数修改前后对照；真实棋谱分析仍缺输入数据。
3. R-P2A 已完成算法组件，但没有当前规则下相对 P14 的持久天梯结论，也没有完整对局混合 AI；精确残局仍无 deadline。
4. R-P2B L0/L1 的历史 smoke 只说明接线；L2 仍需确认设计和实施范围，规则与数据证据先于训练。
5. 现存设计说明书仍有未填内容；AI 辅助范围、个人贡献、签字材料、正式规则及平台要求待核实。

## 常用命令

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --help
& ".venv/Scripts/python.exe" "scripts/tune_eval_weights.py" --help
```

## 相关文档

- `README.md`：仓库入口、安装与使用
- `PROJECT_PHASES.md`：阶段顺序、门禁和历史实验路线
- `PROJECT_MEMORY.md`：按日期保存的项目事实记录
- `docs/RULE_ASSUMPTIONS.md`：规则依据与实现边界
- `docs/E_DRIVE_HANDOFF_20260614.md`：迁移事实和当前接手步骤
- `docs/superpowers/specs/2026-06-13-research-transition-design.md`：长期研究总体设计
- `docs/superpowers/specs/2026-08-03-rp2b-l2-value-network-design.md`：L2 价值网络设计
- `reports/rp2b_l1_cem_tuning_20260803.md`：L1 CEM 实现与验证报告
- `reports/rp2a_exact_endgame_20260731.md`：精确残局求解器报告

赛前实验和比赛基线的完整历史保留在 `PROJECT_PHASES.md`、`PROJECT_MEMORY.md`、`reports/` 与 `release/v1.0/`，不在本简介重复展开。
