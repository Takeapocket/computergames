# P9 Zweistein-DP Smoke

日期：2026-05-17

## 结论

- 新增 `ai/zweistein_dp.py` 概率估值表。
- DP 表尺寸：`15625 x 20`，`PDF_VAL` 与 `CDF_VAL` 均为 15625 行。
- 本机一次冷导入含表构建耗时：`706.560ms`。
- `zweistein_dp_win_prob(default_starting_state(), Player.RED)` 1000 次平均调用耗时：`0.010691ms`。
- GUI/release 默认 AI、默认布局、`release/v1.0/default_params.json` 和 core 规则均未修改。

## 验证命令

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein_dp.py"
```

结果：

```text
11 passed in 0.72s
```

相关组合测试：

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_zweistein_dp.py" "tests/test_chance_rerank.py"
& ".venv/Scripts/python.exe" -m pytest "tests/test_rollout_ai.py"
& ".venv/Scripts/python.exe" -m pytest "tests/test_ai_basic.py" "tests/test_ai_match.py"
& ".venv/Scripts/python.exe" -m pytest "tests/test_bench_ai.py"
```

结果：

```text
18 passed in 0.73s
16 passed in 0.84s
48 passed in 0.86s
39 passed in 1.20s
```
