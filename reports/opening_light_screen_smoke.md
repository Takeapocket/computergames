# Opening Light Screen Summary

- generated_at: 2026-05-18T01:42:16+00:00
- updated_at: 2026-05-18T01:48:05+00:00
- argv: `["--max-candidates", "4", "--games-per-side", "1", "--output", "reports/opening_light_screen_smoke.json", "--summary", "reports/opening_light_screen_smoke.md"]`
- mode: curated
- candidate_count: 4
- games_per_side: 1
- seed: 2026
- baseline_layout: balanced_v1
- max_turns: 200
- ai_kind: rollout
- ai_kwargs_source: release/v1.0/default_params.json
- ai_kwargs: `{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`

这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。

## Stability Totals

- combined_games: 8
- illegal_moves: 0
- crashes: 0
- timeouts: 0

## Top Candidates

| rank | candidate_id | win_rate | wins/games | red_wins | blue_wins | illegal | crashes | timeouts | avg_turns | avg_step_ms | max_step_ms | red_layout |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | curated_003 | 1.000 | 2/2 | 1 | 1 | 0 | 0 | 0 | 18.50 | 285.08 | 610.17 | 1:20/2:11/3:02/4:10/5:01/6:00 |
| 2 | curated_000 | 0.500 | 1/2 | 1 | 0 | 0 | 0 | 0 | 24.00 | 289.85 | 720.07 | 1:00/2:01/3:02/4:10/5:11/6:20 |
| 3 | curated_001 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 21.00 | 293.79 | 680.11 | 1:11/2:02/3:20/4:01/5:10/6:00 |
| 4 | curated_002 | 0.000 | 0/2 | 0 | 0 | 0 | 0 | 0 | 18.50 | 270.91 | 592.00 | 1:01/2:10/3:00/4:02/5:20/6:11 |
