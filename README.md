# 爱恩斯坦棋参赛程序

本项目面向 2026 年辽宁省大学生计算机博弈大赛校内选拔赛。第一阶段只搭建离线可测试的核心规则引擎，不实现 GUI、复杂 AI、统一平台 API 或数据库。

## 项目结构

```text
core/      核心类型、棋盘、规则、状态和走子撤销
ai/        最小随机 AI
record/    JSON 友好的棋谱/状态序列化封装
tests/     pytest 自动测试
scripts/   本地 smoke test
docs/      规则假设和项目文档
```

## 当前能力

- 5x5 棋盘边界判断。
- 红方和蓝方目标方向合法走法生成。
- 骰子点数对应棋子选择。
- 吃子、己方阻挡、目标角胜利和吃光胜利。
- 走子和撤销。
- 状态序列化与反序列化。
- 最小随机 AI 从当前合法走法中选一步。

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

本阶段采用的临时规则记录在 `docs/RULE_ASSUMPTIONS.md`。后续如果比赛附件或统一平台协议确认，应优先更新 `core/` 和测试，再接入 GUI 或 AI。
