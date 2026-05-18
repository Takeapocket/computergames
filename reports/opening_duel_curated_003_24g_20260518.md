# Opening Layout Duel Report

generated_at: 2026-05-18T13:52:53
argv: ["--candidate-report", "reports/opening_light_screen.json", "--candidate-section", "results", "--candidate-index", "3", "--games-per-side", "4", "--seed-pool", "25026,25027,25028", "--output", "reports/opening_duel_curated_003_24g_20260518.md", "--json-output", "reports/opening_duel_curated_003_24g_20260518.json", "--decision-reason", "curated_003 survived 16x1 and 8-game expansion; 24-game seed-pool probe only, not promotion evidence."]
candidate_source: reports/opening_light_screen.json::results[3]
candidate_style: unknown
baseline_layout_id: balanced_v1
games_per_side_per_seed: 4
seed_pool: [25026, 25027, 25028]
max_turns: 200
ai_kind: rollout
ai_kwargs_source: release/v1.0/default_params.json
ai_kwargs: {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}
wall_seconds: 126.56

Candidate layout vs current default layout, with both red and blue roles covered.
This layout duel is a pre-check, not a promotion gate. GUI/release defaults remain unchanged.

## Candidate

- red=1:20/2:11/3:02/4:10/5:01/6:00
- blue=1:24/2:33/3:42/4:34/5:43/6:44

## Results

- combined: 50.0% (wins=12/24), CI95=[31.4%, 68.6%], illegal=0, crashes=0, timeouts=0, max_step_ms=720.4
- candidate as red: 58.3% (wins=7/12), illegal=0, crashes=0, timeouts=0, max_step_ms=720.3
- candidate as blue: 41.7% (wins=5/12), illegal=0, crashes=0, timeouts=0, max_step_ms=720.4

## Decision

Do not promote layout from this report.
Reason: curated_003 survived 16x1 and 8-game expansion; 24-game seed-pool probe only, not promotion evidence.

Full promotion still requires:

候选布局晋升需通过：

- candidate layout vs current default layout 双边合并胜率 >= 55%
- Wilson 95% CI 下界 >= 50%
- 至少 3 个不同 seed 池复验
- illegal_moves = 0, crashes = 0, timeouts = 0
- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
