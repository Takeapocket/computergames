# 爱恩斯坦棋参赛程序

本项目面向 2026 年辽宁省大学生计算机博弈大赛校内选拔赛，目标是离线可运行的爱恩斯坦棋 GUI 参赛程序。当前已具备核心规则、Tkinter GUI、棋谱、计时、自动保存恢复、七盘制比赛流程和基础 AI；不默认实现联网平台 API 或数据库。

## 项目结构

```text
core/      核心类型、棋盘、规则、状态和走子撤销
ai/        随机 AI、贪心 AI、风险评估 AI 和实验性搜索 AI
record/    JSON 友好的棋谱、状态序列化、自动保存和比赛记录封装
gui/       Tkinter 离线 GUI
tests/     pytest 自动测试
scripts/   本地 smoke test
docs/      规则假设和项目文档
```

## 当前能力

- 5x5 棋盘边界判断。
- 红方和蓝方目标方向合法走法生成。
- 骰子点数对应棋子选择。
- 吃子（含吃本方棋子）、目标角胜利和吃光胜利。
- 走子和撤销。
- 状态序列化与反序列化。
- Tkinter GUI：开局录入、骰子录入、合法走法执行、悔棋、AI 推荐。
- JSON 棋谱保存 / 加载、单方 4 分钟包干计时、自动保存恢复。
- 七盘制比赛流程：甲乙身份、先手序列、比分推进、先胜 4 盘。
- 随机 AI、贪心 AI、`greedy_risk` 回退 AI、`rollout` 默认参赛推荐 AI、实验性 Expectimax。

## 运行测试

```powershell
python -m pytest
python scripts/smoke_test.py
```

如果全局没有安装 pytest，可以使用项目本地虚拟环境：

```powershell
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
& ".venv/Scripts/python.exe" -m pytest
& ".venv/Scripts/python.exe" scripts/smoke_test.py
```

## 规则假设

当前规则记录在 `docs/RULE_ASSUMPTIONS.md`。后续如果比赛附件或统一平台协议确认，应优先更新 `core/` 和测试，再接入 GUI、AI 或 `adapters/`。
