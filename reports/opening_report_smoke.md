# Opening Search Report

generated_at: 2026-05-12T20:51:09
sample_size: 5
games_per_train_opponent: 10
validation_games: 10
seed_train: 2026 / seed_validation: 12026
top_k: 3
wall_seconds: 1.66

Train: candidate(red, greedy_risk) vs (mirror + balanced + aggressive + defensive) 蓝方布局
Validation: candidate(red) vs mirror(red) 镜像。

## Train pass (top to bottom)

- 55.0% (wins=22/40) max_step_ms=1.1 | red=1:11/2:20/3:02/4:10/5:00/6:01
- 52.5% (wins=21/40) max_step_ms=1.1 | red=1:10/2:20/3:02/4:01/5:11/6:00
- 50.0% (wins=20/40) max_step_ms=1.0 | red=1:20/2:00/3:02/4:10/5:01/6:11
- 45.0% (wins=18/40) max_step_ms=1.2 | red=1:01/2:20/3:00/4:10/5:11/6:02
- 40.0% (wins=16/40) max_step_ms=1.0 | red=1:20/2:01/3:02/4:00/5:11/6:10

## Validation (top 3 vs mirror)

- 40.0% (wins=4/10) illegal=0 crashes=0 max_step_ms=0.7 | red=1:11/2:20/3:02/4:10/5:00/6:01
- 40.0% (wins=4/10) illegal=0 crashes=0 max_step_ms=1.1 | red=1:10/2:20/3:02/4:01/5:11/6:00
- 60.0% (wins=6/10) illegal=0 crashes=0 max_step_ms=1.1 | red=1:20/2:00/3:02/4:10/5:01/6:11

## Promotion gate

候选布局晋升需通过：

- candidate vs current default 至少 400 总局，红蓝两侧覆盖
- 合并胜率 > 53%
- Wilson 95% CI 下界 >= 50%
- illegal_moves = 0, crashes = 0, timeouts = 0
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
