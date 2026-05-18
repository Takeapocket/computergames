# Opening Light Screen Summary

- generated_at: 2026-05-18T05:38:11+00:00
- updated_at: 2026-05-18T05:47:36+00:00
- argv: `["--max-candidates", "16", "--games-per-side", "1"]`
- mode: curated
- candidate_count: 16
- games_per_side: 1
- max_planned_games: 32
- compact: True
- wall_seconds: 88.983
- seed: 2026
- baseline_layout: balanced_v1
- max_turns: 200
- ai_kind: rollout
- ai_kwargs_source: release/v1.0/default_params.json
- ai_kwargs: `{"close_sample_margin": 0.08, "close_sample_rollouts_per_move": 32, "cutoff_eval": "zweistein", "deadline_safety_ms": 30.0, "epsilon": 0.1, "low_confidence_margin": 0.08, "max_rollout_turns": 80, "max_step_time_ms": 750.0, "playout_policy": "greedy_risk", "rollouts_per_move": 32}`

这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。

## Stability Totals

- combined_games: 32
- illegal_moves: 0
- crashes: 0
- timeouts: 0

## Top Candidates

| rank | candidate_id | win_rate | wins/games | red_wins | blue_wins | illegal | crashes | timeouts | avg_turns | avg_step_ms | max_step_ms | red_layout |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | curated_003 | 1.000 | 2/2 | 1 | 1 | 0 | 0 | 0 | 18.50 | 286.16 | 613.33 | 1:20/2:11/3:02/4:10/5:01/6:00 |
| 2 | curated_008 | 1.000 | 2/2 | 1 | 1 | 0 | 0 | 0 | 11.50 | 401.42 | 720.12 | 1:00/2:11/3:02/4:10/5:01/6:20 |
| 3 | curated_001 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 21.00 | 294.84 | 679.51 | 1:11/2:02/3:20/4:01/5:10/6:00 |
| 4 | curated_004 | 0.500 | 1/2 | 1 | 0 | 0 | 0 | 0 | 21.00 | 293.78 | 618.54 | 1:00/2:01/3:10/4:11/5:02/6:20 |
| 5 | curated_006 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 21.00 | 280.94 | 642.41 | 1:00/2:01/3:02/4:20/5:11/6:10 |
| 6 | curated_007 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 19.00 | 286.34 | 636.05 | 1:20/2:01/3:02/4:10/5:11/6:00 |
| 7 | curated_010 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 21.00 | 295.54 | 720.37 | 1:20/2:11/3:10/4:02/5:01/6:00 |
| 8 | curated_012 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 17.00 | 336.44 | 720.31 | 1:11/2:20/3:10/4:02/5:00/6:01 |
| 9 | curated_013 | 0.500 | 1/2 | 0 | 1 | 0 | 0 | 0 | 20.00 | 286.98 | 626.11 | 1:20/2:00/3:10/4:02/5:01/6:11 |
| 10 | curated_014 | 0.500 | 1/2 | 1 | 0 | 0 | 0 | 0 | 17.00 | 302.23 | 616.76 | 1:20/2:01/3:10/4:00/5:11/6:02 |
