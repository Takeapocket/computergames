# Opening Search Report

generated_at: 2026-05-13T09:19:48
sample_size: 5
games_per_train_opponent: 10
validation_games_per_opponent: 10
seed_train: 2026 / seed_validation: 12026
top_k: 10
wall_seconds: 2.75

Train: candidate(red, greedy_risk) vs (mirror + balanced + aggressive + defensive) 蓝方布局，双方 AI 均为 greedy_risk。
Validation: 使用同一 4 对手集合，以 validation_games_per_opponent 做更大样本确认。
注意：本脚本仍是红方布局筛选；默认布局晋升还需按门禁补红蓝两侧覆盖。

## Train pass (top to bottom)

- 60.0% (wins=24/40) max_step_ms=1.1 | red=1:11/2:20/3:02/4:10/5:00/6:01
- 60.0% (wins=24/40) max_step_ms=1.1 | red=1:20/2:00/3:02/4:10/5:01/6:11
- 45.0% (wins=18/40) max_step_ms=1.1 | red=1:10/2:20/3:02/4:01/5:11/6:00
- 45.0% (wins=18/40) max_step_ms=0.7 | red=1:20/2:01/3:02/4:00/5:11/6:10
- 37.5% (wins=15/40) max_step_ms=0.9 | red=1:01/2:20/3:00/4:10/5:11/6:02

## Validation (top 5 vs same 4 opponents)

- 55.0% (wins=22/40) illegal=0 crashes=0 max_step_ms=0.8 | red=1:11/2:20/3:02/4:10/5:00/6:01
- 55.0% (wins=22/40) illegal=0 crashes=0 max_step_ms=1.3 | red=1:20/2:00/3:02/4:10/5:01/6:11
- 37.5% (wins=15/40) illegal=0 crashes=0 max_step_ms=1.0 | red=1:10/2:20/3:02/4:01/5:11/6:00
- 42.5% (wins=17/40) illegal=0 crashes=0 max_step_ms=0.8 | red=1:20/2:01/3:02/4:00/5:11/6:10
- 50.0% (wins=20/40) illegal=0 crashes=0 max_step_ms=0.8 | red=1:01/2:20/3:00/4:10/5:11/6:02

## Promotion gate

候选布局晋升需通过：

- candidate layout vs current default layout 双边合并胜率 >= 55%
- Wilson 95% CI 下界 >= 50%
- 至少 3 个不同 seed 池复验
- illegal_moves = 0, crashes = 0, timeouts = 0
- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
