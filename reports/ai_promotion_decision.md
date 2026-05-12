# AI Promotion Decision

date: 2026-05-12
baseline: `greedy_risk` (默认 evaluator 权重, ai/match.build_ai)
candidate: 无

## 决策

**保持 `greedy_risk` 作为 GUI 默认 AI 和 release/v1.0 推荐 AI。**

## 依据

收官冲刺期间（Task Group 02）已建立两条候选流水线：

1. `scripts/param_sweep.py` — 随机采样 evaluator 权重（distance / material / expected_risk / expected_win_risk / self_capture）做 train + validation。
2. `scripts/search_openings.py` — 在出发区 720 种排列中采样并对比 mirror / balanced / aggressive / defensive 蓝方布局。

两条流水线已通过 smoke 验证，但尚未做大样本 train/validation 跑，因此当前没有任何候选满足 AI 晋升门禁：

```text
candidate vs greedy_risk: red/blue 各 200 局，合并 400 局
candidate vs greedy:       red/blue 各 200 局，合并 400 局
合并胜率 > 55%
Wilson 95% CI 下界 >= 50%
illegal_moves = 0
crashes = 0
timeouts = 0
avg_step_time_ms < 1000
max_step_time_ms < 5000
报告写入 reports/
```

未满足门禁的候选只保留为实验入口，不进入 GUI 或 release 默认。

## 方法学说明

2026-05-13 已收敛实验脚本的方法学边界：

- `scripts/param_sweep.py` 的 train pass 仍保留 candidate=red 的低成本筛选；validation pass 改为 candidate 红/蓝双边各 `--validation-games` 局，并按 candidate 视角合并胜率。
- `scripts/search_openings.py` 双方 AI 统一为 `greedy_risk`，避免把 `greedy_risk` vs `greedy` 的 AI 强度差误记为布局收益。
- `scripts/search_openings.py` train 与 validation 使用同一组 4 个蓝方对手布局（mirror + balanced + aggressive + defensive）；但它仍只是红方布局筛选，默认布局晋升前仍需另跑红蓝两侧覆盖的门禁复验。

## 当前 baseline 验证

`greedy_risk` 自 R-0 合规以来 4.1 / 4.2 门槛已通过；本次 release 验证将由 Task 12 用新鲜 `quick_bench` 输出更新：

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026 --report-name release_greedy_risk_vs_greedy
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk --games 200 --seed 2026 --report-name release_greedy_vs_greedy_risk
```

## 候选回滚路径

如赛前余下时间允许做实测：

1. 运行 `scripts/param_sweep.py --sample-size 20 --games 100 --validation-games 200 --seed 2026 --output reports/param_sweep.md`。
2. 对 validation 前几名以 `scripts/quick_bench.py` 双向 200 局复测对 `greedy_risk` 与 `greedy`。
3. 若某候选满足门禁，将 `gui/main_window.py` 的 `build_ai("greedy_risk", seed=0)` 改为带新参数的构造；同步更新 `release/v1.0/default_params.json` 与本文件。

未来若需引入 `greedy_risk_tuned` 等新 kind，需要先在 `ai/match.build_ai` 注册。

## 开局布局

GUI 默认 `balanced_v1` 保留。开局搜索（`scripts/search_openings.py`）已建立流水线，但同样未跑大样本，无候选进入晋升判断。
