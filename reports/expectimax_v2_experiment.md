# ExpectimaxV2 Experiment

## Candidate

- kind: `expectimax_v2`
- depth: 1
- leaf risk: disabled (expected_risk_weight=0.0, expected_win_risk_weight=0.0)
- default AI unchanged: `greedy_risk`

## Smoke Commands

```bash
cd C:/tmp/computergames-ai-strengthening && PYTHONPATH=. python scripts/quick_bench.py --red expectimax_v2 --blue greedy --games 50 --seed 2026 --report-name expectimax_v2_vs_greedy_smoke
cd C:/tmp/computergames-ai-strengthening && PYTHONPATH=. python scripts/quick_bench.py --red greedy --blue expectimax_v2 --games 50 --seed 2026 --report-name greedy_vs_expectimax_v2_smoke
```

## Smoke Results

| Match                     | Games | Red Wins | Blue Wins | Draws | Illegal | Crashes | Max Step (ms) |
|---------------------------|-------|----------|-----------|-------|---------|---------|---------------|
| expectimax_v2 vs greedy   | 50    | 28       | 22        | 0     | 0       | 0       | 0.88          |
| greedy vs expectimax_v2   | 50    | 28       | 22        | 0     | 0       | 0       | 0.86          |

- Both benches: exit 0, illegal_moves=0, crashes=0, max_step_time_ms < 1ms (well under 5000ms).
- expectimax_v2 wins 56% as red, 44% as blue against plain greedy (no risk). Red-side advantage is consistent.

## Decision

- Default AI: keep `greedy_risk`
- Promotion: not decided by smoke; run Task 6 promotion gate if smoke is stable and stronger than baseline
