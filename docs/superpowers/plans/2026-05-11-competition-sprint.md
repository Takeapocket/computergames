# 赛前冲刺 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or equivalent task-by-task execution. This repository forbids implicit git commit/reset/branch operations unless the user explicitly requests them, so checklist steps use tests and diffs as checkpoints instead of commits.

**Goal:** 在校内报名截止前先补齐赛场必需能力，再用数据决定是否推进 AI 强化。

**Architecture:** 赛场功能按 `record` / `gui` 分层推进：棋谱和恢复数据进入 `record`，Tkinter 只负责提示、展示和调用 core 状态。AI 实验保持在 `ai` 与 harness 内，不影响 `greedy_risk` 默认路径。

**Tech Stack:** Python 3.11、pytest、tkinter、项目现有 `GameState` / `GameRecord` / `MatchTimer`。

---

## 修订后的阶段顺序

1. **S0 基线验证**
   - 运行 `& ".venv/Scripts/python.exe" -m pytest`。
   - 如果失败，先按系统化调试定位根因，不叠加新功能。

2. **S1 R-3 崩溃自救**
   - 新建 `record/auto_save.py`，负责自动保存文件路径、保存、检测、加载、清理。
   - 修改 `gui/main_window.py`：走子、悔棋后自动保存；启动后检测可恢复棋谱；重置后清理自动保存。
   - 自动保存 metadata 只存可 JSON 序列化数据：timer 当前行动方、双方剩余时间、暂停状态。
   - 先测 `record/auto_save.py` 的序列化与清理，再测 `MainWindow` 调用路径。

3. **S2 R-1 完整灵活开局录入**
   - 最终验收目标：可视化编辑器支持点击/拖拽放置棋子、校验双方 1-6 号布局、保存/加载自定义布局，并在开局时选择使用。
   - 实现顺序分两步：先交付比赛可用闭环（选择我方预设布局、录入对方 6 子布局、开始对局），随后在同一阶段补齐完整编辑器与自定义布局持久化。
   - 自定义布局文件放在 `layouts/`，记录布局 id、红方 1-6 坐标、蓝方 1-6 坐标。
   - `GameState.from_layout()` 是唯一创建局面入口；GUI 不复制走法规则。

4. **S3 R-2 七局四胜**
   - 优先扩展现有 `gui/match_mode.py`，必要时新增 `record/match_record.py`。
   - 数据模型显式区分：我方/对方、红方/蓝方、甲方/乙方。
   - 先用单元测试覆盖 1/4/5 与 2/3/6/7 先手序列、先到 4 胜、下一局编号。

5. **S4 GUI 全流程演练**
   - 手动跑：开局录入 → 走子 → 悔棋 → 自动保存恢复 → 七局四胜推进。
   - 运行完整 pytest。

6. **S5 低风险 AI followup**
   - 只在 S1-S4 完成后处理。
   - 可选项：删除 stuck penalty 死代码、自吃策略评估、Expectimax leaf 关闭风险项实验。
   - AI 变更必须用 `scripts/quick_bench.py` 数据证明；没有数据不替换默认 AI。

7. **S6 赛前冻结**
   - 不晚于 2026-05-16 冻结。
   - 冻结后只修 bug，不做新功能、不换 AI 主线。

## S1 R-3 任务清单

### Task 1: 自动保存记录层

**Files:**
- Create: `record/auto_save.py`
- Test: `tests/test_auto_save.py`

- [ ] 写失败测试：保存 `GameRecord` 与 timer metadata 后，`has_auto_save()` 为真，`load_auto_save()` 能恢复棋谱和 metadata。
- [ ] 写失败测试：空文件或不存在文件不应被视为可恢复。
- [ ] 写失败测试：`clear_auto_save()` 清理后 `has_auto_save()` 为假。
- [ ] 实现最小 `record/auto_save.py`。
- [ ] 运行 `& ".venv/Scripts/python.exe" -m pytest tests/test_auto_save.py -v`。

### Task 2: GUI 自动保存调用

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_main_window.py`

- [ ] 写失败测试：执行一步合法走法后会调用自动保存。
- [ ] 写失败测试：悔棋成功后会调用自动保存。
- [ ] 写失败测试：重置棋局会清理自动保存。
- [ ] 在 `MainWindow` 增加 `_auto_save_current_game()` 和 `_clear_auto_save()` 小方法。
- [ ] 在 `_apply_selected_move()`、`_undo_move()`、`_reset_game()` 接入对应调用。
- [ ] 运行 `& ".venv/Scripts/python.exe" -m pytest tests/test_main_window.py tests/test_auto_save.py -v`。

### Task 3: 启动恢复入口

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_main_window.py`

- [ ] 写失败测试：存在自动保存时，确认恢复后 `state`、`record`、`timer` 使用保存内容。
- [ ] 写失败测试：拒绝恢复时保留新局，并清理旧自动保存。
- [ ] 在初始化完成控件后调用恢复检查，避免恢复前刷新引用不存在的 widget。
- [ ] 恢复失败时显示错误并保留新局，不让 GUI 崩溃。
- [ ] 运行 `& ".venv/Scripts/python.exe" -m pytest tests/test_main_window.py tests/test_auto_save.py -v`。

### Task 4: 阶段验证

- [ ] 运行完整测试：`& ".venv/Scripts/python.exe" -m pytest`。
- [ ] 运行 GUI 冒烟入口：`& ".venv/Scripts/python.exe" "scripts/run_gui.py"`，手动确认自动保存恢复弹窗。
- [ ] 记录实际验证结果；不提交、不打 tag，除非用户明确要求。

## S2 R-1 任务边界

S2 不再定义为“最小开局录入”阶段；最小闭环只是降低风险的第一批提交粒度。S2 完成前必须包含：

- 可视化布局编辑器：5×5 棋盘上点击/拖拽放置、移动、清除棋子。
- 合法区域校验：红方只能在左上出发区 6 格，蓝方只能在右下出发区 6 格；双方各 1-6 号齐全且无重叠。
- 自定义布局保存/加载：布局 JSON 保存在 `layouts/`，下次启动可选择。
- 开局流程集成：比赛模式开始前可选择我方布局、录入或加载对方布局，并将实际开局写入棋谱 metadata。
- 测试覆盖：布局数据解析/校验、保存/加载、GUI 开局状态转换。
