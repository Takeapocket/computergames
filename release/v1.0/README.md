# 爱恩斯坦棋参赛程序 v1.0

2026 年辽宁省大学生计算机博弈大赛校内选拔赛参赛版本。

## 运行环境

- Python 3.11（仓库根 `.venv/` 已就绪）
- Windows + Tkinter（系统自带，无额外依赖）
- 离线运行，**不需要网络**

## 启动

优先双击仓库根目录的 `启动项目.cmd` 打开现场菜单。

菜单常用项：

```text
1. 启动 GUI
2. 一键赛前总检查
3. 完整 pytest
4. smoke 测试
5. S2 全流程演练
```

命令行等价入口：

```powershell
& ".venv/Scripts/python.exe" "scripts/launcher.py"
```

赛前主检查命令行方式：

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

成功标准：最后一行必须是 `READY FOR MATCH`。

主程序启动：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

## 比赛模式操作流程

1. 启动 GUI。
2. 菜单 → 模式 → 比赛模式（弹出甲乙身份 + 红蓝颜色 + 计时设置 dialog）。
3. 选择我方甲乙身份和红蓝颜色，核对单方时限；默认不要勾选"程序自动超时判负"，除非裁判明确要求双方程序自行计时判负。
4. 选择我方开局布局（默认 `balanced_v1`，可用 `aggressive_v1` / `defensive_v1` / 自定义）。
5. 录入对方开局，点击"确认开局"进入 playing 阶段。
6. 每回合：先录入骰子，再录入对方走法（若对方先手），或读取我方推荐走法并执行。
7. 我方推荐 AI = `rollout` kind + P14 promotion 显式参数（详见 `default_params.json`）。
8. 单盘结束后 dialog 提示胜方，进入下一盘开局录入。
9. 任一方 4 胜后 dialog 提示整轮胜方，停止开新盘。

## 计时策略

- 默认单方时限 240 秒，可在比赛模式 dialog 中改成 600 秒等现场要求的时长。
- 默认只提示超时，不自动判负；裁判暂停、沟通或设备确认时，程序不会自行结束本盘。
- 默认模式下，裁判确认某方超时负后，点击计时面板对应的"裁判判红方超时负" / "裁判判蓝方超时负"按钮，程序会记为 `reason="timeout"` 并推进七盘制比分。
- 若现场要求程序自行计时判负，进入比赛模式时勾选"程序自动超时判负"。
- 无论是否自动判负，"暂停计时"按钮都可用于裁判宣布暂停的场景。

## 崩溃恢复

- 程序异常终止后，重新执行 `scripts/run_gui.py`。
- 启动时若检测到 `replays/auto_save.json` 或 `replays/auto_save_match.json`，会弹"恢复未完成对局"dialog。
- **接受恢复**：核对棋盘、当前方、骰子阶段、计时、棋谱步数与现场实际情况一致后，继续比赛。
- **拒绝恢复**：若 auto-save 已被现场情况污染（例如换轮但未清理），点击"否"开新一轮。

详见 `docs/EMERGENCY_GUIDE.md` 第 2-4 章。

## 默认 AI

- 名称：`rollout`
- 实现：`ai/rollout_ai.py`（有时间上限的平面 rollout，fallback 为 `greedy_risk`）
- 参数：见 `default_params.json`；v1.0 默认使用 P14 promotion 参数：64 rollout / move、80 half-turn cutoff、2000ms step deadline、epsilon 0.05、close sample 96、risk-aware playout、Zweistein cutoff、80ms deadline safety。
- 晋升状态：已按 `reports/ai_promotion_decision.md` 的 P14 双轮 50+50 复验数据晋升。
- adaptive rollout 是显式实验候选，不是 v1.0 默认参数；它 direct vs old rollout 800 局合并胜率 59.00%，未过 60% 默认晋升线。
- AI 候选实验入口保留在 `scripts/param_sweep.py` / `scripts/search_openings.py` / `scripts/tournament.py`

## 工程化基线

- 现场启动器：根目录 `启动项目.cmd`，内部调用 `scripts/launcher.py`
- 赛前主检查：`scripts/preflight_check.py`，成功必须输出 `READY FOR MATCH`
- 验证脚本：`scripts/smoke_test.py`、`scripts/s2_rehearsal.py`、`scripts/quick_bench.py`、`scripts/tournament.py`
- 应急手册：`docs/EMERGENCY_GUIDE.md`
- 现场清单：`docs/MATCH_CHECKLIST.md`
- 测试报告：`release/v1.0/test_report.md`
- 已知限制：`release/v1.0/known_limitations.md`

## 紧急回滚

- 不要在比赛中直接编辑 `gui/main_window.py` 默认常量。若赛前间隙必须回滚 AI，先记录原因，只做受控修改或切换到已复验备机，然后完整重跑 `scripts/preflight_check.py` 并确认 `READY FOR MATCH`；比赛进行中依赖程序内置 fallback，不临时改源码。
- 若布局录入异常，可切回 `balanced_v1` 默认。
