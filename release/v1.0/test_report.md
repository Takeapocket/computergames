# Test Report

Date: 2026-05-12（自动化基线）/ 2026-05-13（自动化复验 + S2 §4 真实 Tk GUI 手动表填写完成）

## Commands

| command | exit code | result |
|---|---:|---|
| `.venv/Scripts/python.exe -m pytest -q` | 0 | 332 passed, 50 skipped |
| `.venv/Scripts/python.exe scripts/smoke_test.py` | 0 | 合法走法 / undo / winner 全过 |
| `.venv/Scripts/python.exe scripts/s2_rehearsal.py` | 0 | 8/8 scenarios passed |
| `python scripts/quick_bench.py --red greedy_risk --blue greedy --games 200 --seed 2026` | 0 | red_win_rate=0.58 |
| `python scripts/quick_bench.py --red greedy --blue greedy_risk --games 200 --seed 2026` | 0 | blue_win_rate=0.535 |
| `python scripts/quick_bench.py --red rollout --blue greedy_risk --games 400 --seed 2026` | 0 | red_win_rate=0.605 |
| `python scripts/quick_bench.py --red greedy_risk --blue rollout --games 400 --seed 2026` | 0 | blue_win_rate=0.6475 |
| `rg "import socket\|import urllib\|import requests" --glob "*.py"` | 1 | 无生产网络依赖 |
| `rg "stuck_penalty\|STUCK_PIECE_PENALTY\|count_stuck_pieces" --glob "*.py"` | 1 | R-0 followup 清理完成 |

`rg` 在无匹配时返回 exit code 1（这是预期的「无引用」状态）。

## pytest

```
332 passed, 50 skipped
```

0 failed / 0 errors。

## smoke_test

```
dice: 3
selected pieces: [3]
legal moves:
  1. red 3: Position(row=2, col=2) -> Position(row=3, col=2)
  2. red 3: Position(row=2, col=2) -> Position(row=2, col=3)
  3. red 3: Position(row=2, col=2) -> Position(row=3, col=3) capture
applied: Move(player=Player.RED, piece_id=3, ...)
winner: None
undo restored: True
```

## s2_rehearsal

```
[1/8] 4:0 整轮: PASS
[2/8] 4:3 整轮: PASS
[3/8] 先手序列: PASS
[4/8] 超时判负: PASS
[5/8] 盘间恢复: PASS
[6/8] 盘中恢复: PASS
[7/8] 悔棋边界: PASS
[8/8] 整轮结束后行为: PASS
----------------------------------------------------------------------
Total: 8/8 scenarios passed
```

## GUI manual rehearsal

`reports/gui-rehearsal.md` §4 真实 Tk GUI 手动表 2026-05-13 由操作员现场填表完成，21 项全"正常"：

- §4.1 启动到 4:0 整轮（8 步）：全部正常
- §4.2 4:3 决胜（3 步）：全部正常
- §4.3 盘内崩溃恢复（2 步）：全部正常
- §4.4 盘间崩溃恢复（2 步）：全部正常
- §4.5 误操作恢复（3 步）：全部正常
- §4.6 整轮结束后操作（3 步）：全部正常

S2 完整闭环（headless 自动 8/8 + 真实 GUI 手动 21/21）。

## AI baseline

### greedy_risk (red) vs greedy (blue), 200 局, seed=2026

```text
red_win_rate:       0.58
blue_win_rate:      0.42
red_win_ci95:       [0.5107, 0.6463]
blue_win_ci95:      [0.3537, 0.4893]
illegal_moves:      0
crashes:            0
timeouts:           0
average_step_time_ms: 0.309
max_step_time_ms:     1.332
report_path:        reports/release_greedy_risk_vs_greedy.json
```

### greedy (red) vs greedy_risk (blue), 200 局, seed=2026

```text
red_win_rate:       0.465
blue_win_rate:      0.535
red_win_ci95:       [0.3972, 0.5341]
blue_win_ci95:      [0.4659, 0.6028]
illegal_moves:      0
crashes:            0
timeouts:           0
average_step_time_ms: 0.333
max_step_time_ms:     6.841
report_path:        reports/release_greedy_vs_greedy_risk.json
```

### 合并

```text
greedy_risk 合并胜率：(116 + 107) / 400 = 55.75%
greedy 合并胜率：       (84 + 93) / 400  = 44.25%
greedy_risk 双侧 Wilson CI 下界均 > 50% / > 47%（红方下界 0.51，蓝方下界 0.47）
```

`greedy_risk` 在两侧均击败 `greedy`，红方略强（先手 / 短盘特性）。所有局合法、零崩溃、零超时；最大单步耗时 6.84 ms，远低于 5000 ms 上限。

### rollout promotion vs greedy_risk, 800 局, seed=2026

```text
rollout red win rate:  60.50% (242 / 400), Wilson lower 55.63%
rollout blue win rate: 64.75% (259 / 400), Wilson lower 59.95%
combined win rate:     62.62% (501 / 800), Wilson lower 59.22%
illegal_moves:         0
crashes:               0
timeouts:              0
max_step_time_ms:      469.14
report_paths:
  reports/rollout_vs_greedy_risk_red.json
  reports/greedy_risk_vs_rollout_blue.json
```

## Promotion decisions

参见 `reports/ai_promotion_decision.md`：

- **AI 默认**：`rollout` 晋升为 GUI/release 默认；`greedy_risk` 保留为应急回退。
- **开局默认**：保持 `balanced_v1`，未做候选晋升。

参数搜索 / 开局搜索 / pairwise tournament 流水线均已落地为 `scripts/param_sweep.py`、`scripts/search_openings.py`、`scripts/tournament.py`；本 release 未替换默认布局。

## Known limitations

参见 `release/v1.0/known_limitations.md`。本次验证未发现新已知项。
