# Opening Search Report

generated_at: 2026-05-16T16:20:19
sample_size: 5
games_per_train_opponent: 2
validation_games_per_opponent: 2
seed_train: 2026 / seed_validation: 12026
top_k: 2
ai_kind: rollout
ai_kwargs_source: release/v1.0/default_params.json
ai_kwargs: {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}
wall_seconds: 293.51

Train: candidate red layout vs (mirror + balanced + aggressive + defensive) 蓝方布局，双方 AI 均为当前 release 默认 rollout 显式 kwargs。
Validation: 使用同一 4 对手集合，以 validation_games_per_opponent 做更大样本确认。
注意：本脚本仍是红方布局筛选；默认布局晋升还需按门禁补红蓝两侧覆盖。
结论：这是 P5.0 entry guard 小样本 smoke，仅验证 opening-search harness 已对齐当前 release 默认 rollout kwargs；样本不足以晋升布局，GUI/release 默认布局不变。

## Train pass (top to bottom)

- 75.0% (wins=6/8) illegal=0 crashes=0 timeouts=0 max_step_ms=639.2 | red=1:01/2:20/3:00/4:10/5:11/6:02
- 62.5% (wins=5/8) illegal=0 crashes=0 timeouts=0 max_step_ms=720.3 | red=1:10/2:20/3:02/4:01/5:11/6:00
- 62.5% (wins=5/8) illegal=0 crashes=0 timeouts=0 max_step_ms=720.1 | red=1:11/2:20/3:02/4:10/5:00/6:01
- 50.0% (wins=4/8) illegal=0 crashes=0 timeouts=0 max_step_ms=720.4 | red=1:20/2:01/3:02/4:00/5:11/6:10
- 37.5% (wins=3/8) illegal=0 crashes=0 timeouts=0 max_step_ms=712.8 | red=1:20/2:00/3:02/4:10/5:01/6:11

## Validation (top 2 vs same 4 opponents)

- 62.5% (wins=5/8) illegal=0 crashes=0 timeouts=0 max_step_ms=716.5 | red=1:01/2:20/3:00/4:10/5:11/6:02
- 75.0% (wins=6/8) illegal=0 crashes=0 timeouts=0 max_step_ms=720.3 | red=1:10/2:20/3:02/4:01/5:11/6:00

## Promotion gate

候选布局晋升需通过：

- candidate layout vs current default layout 双边合并胜率 >= 55%
- Wilson 95% CI 下界 >= 50%
- 至少 3 个不同 seed 池复验
- illegal_moves = 0, crashes = 0, timeouts = 0
- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
