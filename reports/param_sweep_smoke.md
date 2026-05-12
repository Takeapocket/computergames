# Param Sweep Report

generated_at: 2026-05-12T20:48:05
sample_size: 3
games_per_train: 10
validation_games: 10
seed_train: 2026 / seed_validation: 12026
layout: default_no_stuck_corner_v1
top_k: 2
wall_seconds: 0.69

Baseline = `greedy_risk` 默认权重；candidate = `greedy_risk` 透传被采样权重。
胜率视角：red = candidate。

## Train pass (top to bottom)

- 50.0% (wins=5/10) illegal=0 crashes=0 max_step_ms=3.7 | distance_weight=1.0, material_weight=5.0, expected_risk_weight=5.0, expected_win_risk_weight=100.0, self_capture_weight=0.5
- 50.0% (wins=5/10) illegal=0 crashes=0 max_step_ms=3.8 | distance_weight=1.0, material_weight=20.0, expected_risk_weight=3.0, expected_win_risk_weight=100.0, self_capture_weight=0.5
- 50.0% (wins=5/10) illegal=0 crashes=0 max_step_ms=2.9 | distance_weight=3.0, material_weight=5.0, expected_risk_weight=1.0, expected_win_risk_weight=1000.0, self_capture_weight=0.5

## Validation (top 2)

- 30.0% (wins=3/10) illegal=0 crashes=0 max_step_ms=3.3 | distance_weight=1.0, material_weight=5.0, expected_risk_weight=5.0, expected_win_risk_weight=100.0, self_capture_weight=0.5
- 30.0% (wins=3/10) illegal=0 crashes=0 max_step_ms=2.7 | distance_weight=1.0, material_weight=20.0, expected_risk_weight=3.0, expected_win_risk_weight=100.0, self_capture_weight=0.5

## Promotion gate

候选晋升判断由 `reports/ai_promotion_decision.md` 单独决定，并需通过：

- candidate vs greedy_risk 双边各 200 局合并胜率 > 55%
- Wilson 95% CI 下界 >= 50%
- illegal_moves = 0, crashes = 0, timeouts = 0
- avg_step_time_ms < 1000, max_step_time_ms < 5000
