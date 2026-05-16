# Opening Search Report

generated_at: 2026-05-16T17:13:25
sample_size: 100
candidate_mode: stratified
per_style: 2
candidate_count: 6
games_per_train_opponent: 1
validation_games_per_opponent: 1
seed_pool_train: [2026, 2027]
seed_pool_validation: [12026, 12027]
top_k: 3
ai_kind: rollout
ai_kwargs_source: release/v1.0/default_params.json
ai_kwargs: {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}
wall_seconds: 364.74

Train: candidate red layout vs (mirror + balanced + aggressive + defensive) 蓝方布局，双方 AI 均为当前 release 默认 rollout 显式 kwargs。
Validation: 使用同一 4 对手集合，以 validation_games_per_opponent 做更大样本确认。
注意：本脚本仍是红方布局筛选；默认布局晋升还需按门禁补红蓝两侧覆盖。
candidate_mode=stratified 时按 aggressive/balanced/defensive 分层采样；seed_pool 只用于复现实验组织，不代表晋升样本。
结论：这是 P5.2 opening-search sample gate，样本不足以晋升布局，GUI/release 默认布局不变。

## Train pass (top to bottom)

- 62.5% (wins=5/8) style=aggressive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=668.8 | red=1:20/2:11/3:02/4:00/5:10/6:01
- 50.0% (wins=4/8) style=defensive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.4 | red=1:00/2:10/3:01/4:20/5:11/6:02
- 37.5% (wins=3/8) style=aggressive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.1 | red=1:02/2:20/3:11/4:10/5:00/6:01
- 37.5% (wins=3/8) style=balanced seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.4 | red=1:00/2:10/3:11/4:20/5:02/6:01
- 37.5% (wins=3/8) style=defensive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=555.0 | red=1:10/2:01/3:00/4:20/5:02/6:11
- 25.0% (wins=2/8) style=balanced seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.3 | red=1:11/2:01/3:20/4:10/5:02/6:00

## Validation (top 3 vs same 4 opponents)

- 37.5% (wins=3/8) style=aggressive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.2 | red=1:20/2:11/3:02/4:00/5:10/6:01
- 50.0% (wins=4/8) style=defensive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=720.3 | red=1:00/2:10/3:01/4:20/5:11/6:02
- 50.0% (wins=4/8) style=aggressive seeds=2 illegal=0 crashes=0 timeouts=0 max_step_ms=604.6 | red=1:02/2:20/3:11/4:10/5:00/6:01

## Promotion gate

候选布局晋升需通过：

- candidate layout vs current default layout 双边合并胜率 >= 55%
- Wilson 95% CI 下界 >= 50%
- 至少 3 个不同 seed 池复验
- illegal_moves = 0, crashes = 0, timeouts = 0
- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
