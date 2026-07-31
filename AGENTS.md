# 项目协作指令

## 语言与沟通

- 始终使用简体中文回复。
- 面向有经验的开发者，保持专业、直接、技术导向。
- 汇报结论时优先说明事实、验证结果和下一步，不做无依据承诺。

## 当前工作区

- 主开发目录：`E:\computergame`
- 研究数据目录：`E:\computergame-data`
- pip 缓存目录：`E:\pip-cache`
- torch 缓存目录：`E:\torch-cache`
- C 盘旧目录 `C:\Users\Takeapocket\Desktop\documents\computergames` 已弃用，仅作为迁移前快照保留；不要在旧目录继续开发、测试、提交或推送。

## 项目目标

本项目已从 2026 年辽宁省大学生计算机博弈大赛校内选拔赛的爱恩斯坦棋离线 GUI 参赛程序，转型为以该程序为基础的长期 AI 棋力研究项目。比赛形态的 GUI、`release/v1.0` 和 P14 默认参数保留为历史基线与天梯锚点。

核心目标优先级：

```text
规则正确 > 可复现实验 > 本地稳定 > GUI 可操作 > 基础 AI 强度 > Expectimax/MCTS 强化 > 开局库与参数优化 > 界面美观
```

当前默认假设：

- 比赛现场不依赖网络。
- 不默认存在统一平台或 API。
- 若后续确认平台协议，只在 `adapters/` 增加适配层，不改 core 规则语义。
- GUI 只调用 core，不复制或改写规则逻辑。
- 长期研究阶段不再受封版纪律约束，但保留 core-first、harness-first、pytest 全绿和数据可复现纪律。
- 训练数据、模型权重、自对弈棋谱、pip/torch 缓存一律放 E 盘；仓库内不得默认写入大体积研究产物。

## 每次接手项目先读

新对话或新任务开始时，先读取这些文件再判断阶段和任务：

1. `PROJECT_MEMORY.md`
2. `PROJECT_PHASES.md`
3. `README.md`
4. `docs/RULE_ASSUMPTIONS.md`
5. `docs/PROJECT_BRIEF.md`
6. `docs/E_DRIVE_HANDOFF_20260614.md`

不要只凭历史印象判断项目状态；以当前仓库文件和测试结果为准。

## 工程原则

- KISS：优先直接、清晰、可验证的实现。
- YAGNI：只做当前阶段明确需要的能力，不提前做平台 API、复杂 AI、深度学习或正式棋谱格式。
- DRY：发现重复逻辑时优先收敛到 core、record、ai 或 gui 的合适边界。
- SOLID：保持 core、ai、gui、record、adapters 分层；规则逻辑不得写入 GUI。
- Harness-first：AI 强弱必须用本地对战 harness 数据证明，不能靠单局主观判断。
- Core-first：任何规则变化必须先改 core 和测试，再接 GUI 或 AI。

## 当前结构约定

- `core/`：棋盘状态、规则、合法步、胜负判断、走子/撤销、序列化。
- `ai/`：随机 AI、贪心 AI、评估函数、后续搜索 AI。
- `gui/`：离线 GUI，只负责展示、输入和调用 core。
- `record/`：状态和后续棋谱保存/加载。
- `tests/`：pytest 自动测试。
- `scripts/`：本地运行、测试、评测脚本。
- `adapters/`：预留统一平台/API 适配层；没有正式协议前保持空骨架。
- `reports/`：后续 harness、参数、开局评测报告。
- `replays/`：后续自动对战或比赛棋谱 replay。

## 命令约定

优先使用项目虚拟环境：

```powershell
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

研究脚本默认使用 E 盘环境变量：

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
```

搜索文件和内容优先使用 `rg`。

## 危险操作约束

未经用户明确要求，不执行：

- `git commit`
- `git push`
- `git reset --hard`
- 删除文件或目录
- 批量移动/重命名文件
- 全局安装或卸载依赖
- 调用生产环境 API 或发送敏感数据

如确需执行高风险操作，必须先说明操作类型、影响范围和风险，并等待用户明确确认。

## 测试与完成标准

代码变更完成前至少运行相关测试；涉及 core、GUI 或公共接口时运行完整 pytest。

不能在没有验证输出的情况下声称“完成”“通过”或“可用”。

阶段性功能必须满足对应文档中的验收标准：

- 阶段计划：`PROJECT_PHASES.md`
- 规则假设：`docs/RULE_ASSUMPTIONS.md`
- 项目摘要：`docs/PROJECT_BRIEF.md`
