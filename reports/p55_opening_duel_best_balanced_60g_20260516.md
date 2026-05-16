# Opening Layout Duel Report

generated_at: 2026-05-16T18:38:30
argv: ["--candidate-report", "reports/p53_opening_seed3_validation2_20260516.json", "--candidate-section", "validation_top", "--candidate-index", "2", "--baseline-layout", "balanced_v1", "--games-per-side", "10", "--seed-pool", "23026,23027,23028", "--max-turns", "200", "--output", "reports/p55_opening_duel_best_balanced_60g_20260516.md", "--json-output", "reports/p55_opening_duel_best_balanced_60g_20260516.json"]
candidate_source: reports/p53_opening_seed3_validation2_20260516.json::validation_top[2]
candidate_style: balanced
baseline_layout_id: balanced_v1
games_per_side_per_seed: 10
seed_pool: [23026, 23027, 23028]
max_turns: 200
ai_kind: rollout
ai_kwargs_source: release/v1.0/default_params.json
ai_kwargs: {"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}
wall_seconds: 320.06

Candidate layout vs current default layout, with both red and blue roles covered.
This layout duel is a pre-check, not a promotion gate. GUI/release defaults remain unchanged.

## Candidate

- red=1:00/2:10/3:11/4:20/5:02/6:01
- blue=1:44/2:34/3:33/4:24/5:42/6:43

## Results

- combined: 38.3% (wins=23/60), CI95=[27.1%, 51.0%], illegal=0, crashes=0, timeouts=0, max_step_ms=720.7
- candidate as red: 43.3% (wins=13/30), illegal=0, crashes=0, timeouts=0, max_step_ms=720.5
- candidate as blue: 33.3% (wins=10/30), illegal=0, crashes=0, timeouts=0, max_step_ms=720.7

## Decision

Do not promote layout from this report.
Reason: 60-game expansion failed: candidate scored 23/60 (38.3%), CI95 upper=51.0% < 55.0%; stop this candidate route; defaults unchanged.

Full promotion still requires:

候选布局晋升需通过：

- candidate layout vs current default layout 双边合并胜率 >= 55%
- Wilson 95% CI 下界 >= 50%
- 至少 3 个不同 seed 池复验
- illegal_moves = 0, crashes = 0, timeouts = 0
- 保留均衡 / 速攻 / 防守三类候选，不声称最优布局
- 必须落地到 GUI OpeningPanel preset 才能成为默认；report 仅记录候选
