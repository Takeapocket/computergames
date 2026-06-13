# R-P1 Foundation Bootstrap Report

日期：2026-06-13

## 结论

R-P1 本地地基脚手架已在当前 C 盘工作区落地，未执行 R-P0 的 PR、迁移、虚拟环境重建、全局 pip 配置或依赖安装。

本次只实现低风险、可测试的研究入口：

- `scripts/perf_probe.py`：性能基线入口，输出 match-level 步时聚合、rollout root visits 基线，以及 rollout 决策窗口内的 clone / legal move / GreedyAI / RNG 微计数。
- `scripts/ladder.py`：Elo 天梯入口，P14 默认以 `kind="rollout"` + `RELEASE_DEFAULT_ROLLOUT_KWARGS` 作为 1500 锚点；支持双人 probe、多人 round-robin 调度、Elo 不确定度估计、`report.json` / `report.md` 输出。审查 follow-up 后，CLI 必须显式传 `--output-dir` 或设置 `CG_RESEARCH_DATA_DIR`，不再默认写入 C 盘仓库内 `data/ladder/games.jsonl`。
- `scripts/replay_analyze.py`：读取 `GameRecord` / `MatchRecord` JSON，输出步数、骰子、source、result 与基础局面标签；支持将记录走法逐步对比当前 P14 默认推荐，并可输出 per-step JSON rows。
- `scripts/dice_forensics.py`：按可证明样本口径做骰子序列审计，明确 `MoveRecord.source` 是走子来源，不是独立骰子来源字段。
- `requirements-research.txt`：研究依赖声明，当前只包含 `numpy`，不包含 `torch`。

## 执行边界

- 未改 `core/` 规则语义。
- 未改 GUI / release 默认 AI、默认布局或 P14 参数。
- 未写入 `data/`，除非用户主动指定输出目录或设置 `CG_RESEARCH_DATA_DIR` 后运行 `scripts/ladder.py`。
- 未安装依赖。
- 未执行 `git commit`、`git push`、PR、迁移或删除 C 盘旧目录。

## 验证

已运行：

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_replay_analyze.py" "tests/test_dice_forensics.py" -q
& ".venv/Scripts/python.exe" -m pytest "tests/test_ladder.py" "tests/test_perf_probe.py" -q
& ".venv/Scripts/python.exe" -m pytest "tests/test_replay_analyze.py" "tests/test_dice_forensics.py" "tests/test_ladder.py" "tests/test_perf_probe.py" -q
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 0 --samples 0
& ".venv/Scripts/python.exe" "scripts/ladder.py" --red p14_default --blue random --games 0 --output-dir "E:/computergame-data/ladder/cg_ladder_smoke"
& ".venv/Scripts/python.exe" "scripts/ladder.py" --players random,greedy --games-per-pair 1 --seed 2026 --output-dir "E:/computergame-data/ladder/cg_ladder_rr_smoke"
& ".venv/Scripts/python.exe" "scripts/replay_analyze.py" "C:/tmp/cg_replay_compare_smoke.json" --compare-recommendations --include-recommendation-rows --json
```

结果：

```text
10 passed
14 passed
24 passed
886 passed in 71.78s
perf_probe CLI smoke OK
ladder CLI smoke OK; P14 anchor signature uses kind="rollout" + release kwargs
ladder round-robin CLI smoke OK; output includes schedule, rating_interval, games.jsonl/report.json/report.md
replay recommendation comparison CLI smoke OK; JSON output includes recommendation rows
```

后续在 R-P0 迁移到 `E:\computergame` 并重建 `.venv` 后，应再运行全量 pytest 和 `scripts/preflight_check.py`。
