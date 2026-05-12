# 爱恩斯坦棋参赛程序 v1.0

2026 年辽宁省大学生计算机博弈大赛校内选拔赛参赛版本。

## 运行环境

- Python 3.11（仓库根 `.venv/` 已就绪）
- Windows + Tkinter（系统自带，无额外依赖）
- 离线运行，**不需要网络**

## 启动

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

## 比赛模式操作流程

1. 启动 GUI。
2. 菜单 → 模式 → 比赛模式（弹出甲乙身份 + 红蓝颜色 dialog）。
3. 选择我方甲乙身份和红蓝颜色，确认。
4. 选择我方开局布局（默认 `balanced_v1`，可用 `aggressive_v1` / `defensive_v1` / 自定义）。
5. 录入对方开局，点击"确认开局"进入 playing 阶段。
6. 每回合：先录入骰子，再录入对方走法（若对方先手），或读取我方推荐走法并执行。
7. 我方推荐 AI = `greedy_risk`（详见 `default_params.json`）。
8. 单盘结束后 dialog 提示胜方，进入下一盘开局录入。
9. 任一方 4 胜后 dialog 提示整轮胜方，停止开新盘。

## 崩溃恢复

- 程序异常终止后，重新执行 `scripts/run_gui.py`。
- 启动时若检测到 `replays/auto_save.json` 或 `replays/auto_save_match.json`，会弹"恢复未完成对局"dialog。
- **接受恢复**：核对棋盘、当前方、骰子阶段、计时、棋谱步数与现场实际情况一致后，继续比赛。
- **拒绝恢复**：若 auto-save 已被现场情况污染（例如换轮但未清理），点击"否"开新一轮。

详见 `docs/EMERGENCY_GUIDE.md` 第 2-4 章。

## 默认 AI

- 名称：`greedy_risk`
- 实现：`ai/greedy_ai.py` + `ai/evaluator.py`（含 expected capture / win risk 项）
- 参数：见 `default_params.json`
- 晋升状态：**未替换**。详见 `reports/ai_promotion_decision.md`
- AI 候选实验入口保留在 `scripts/param_sweep.py` / `scripts/search_openings.py` / `scripts/tournament.py`

## 工程化基线

- 验证脚本：`scripts/smoke_test.py`、`scripts/s2_rehearsal.py`、`scripts/quick_bench.py`、`scripts/tournament.py`
- 应急手册：`docs/EMERGENCY_GUIDE.md`
- 现场清单：`docs/MATCH_CHECKLIST.md`
- 测试报告：`release/v1.0/test_report.md`
- 已知限制：`release/v1.0/known_limitations.md`

## 紧急回滚

- 若现场 AI 输出异常，可在 `gui/main_window.py` 中临时把 `build_ai("greedy_risk", ...)` 换为 `build_ai("greedy", ...)`（无 risk 项的纯贪心）。
- 若布局录入异常，可切回 `balanced_v1` 默认。
