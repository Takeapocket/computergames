# AI Tournament Matrix

generated_at: 2026-05-12T19:18:41
seed: 2026
games_per_orientation: 10
layout: default_no_stuck_corner_v1
wall_seconds: 0.375
illegal_moves_total: 0
crashes_total: 0

行 = Red 方 AI；列 = Blue 方 AI；值 = Red 视角胜率（按对应有序对 `--games` 局）。

| AI | random | greedy | greedy_risk |
|---|---:|---:|---:|
| random | - | 30.0% | 20.0% |
| greedy | 50.0% | - | 40.0% |
| greedy_risk | 70.0% | 70.0% | - |

## Per-pair metadata

```json
{
  "ais": [
    "random",
    "greedy",
    "greedy_risk"
  ],
  "games_per_orientation": 10,
  "seed": 2026,
  "layout_id": "default_no_stuck_corner_v1",
  "max_turns": 200,
  "illegal_moves_total": 0,
  "crashes_total": 0,
  "pairs": [
    {
      "red": "random",
      "blue": "greedy",
      "games": 10,
      "red_wins": 3,
      "blue_wins": 7,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.23429365059460647,
      "max_step_time_ms": 1.0267999969073571
    },
    {
      "red": "random",
      "blue": "greedy_risk",
      "games": 10,
      "red_wins": 2,
      "blue_wins": 8,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.22659473704008729,
      "max_step_time_ms": 1.014799992844928
    },
    {
      "red": "greedy",
      "blue": "random",
      "games": 10,
      "red_wins": 5,
      "blue_wins": 5,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.22225728661849178,
      "max_step_time_ms": 1.0907999967457727
    },
    {
      "red": "greedy",
      "blue": "greedy_risk",
      "games": 10,
      "red_wins": 4,
      "blue_wins": 6,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.43474843744206737,
      "max_step_time_ms": 0.9799000035854988
    },
    {
      "red": "greedy_risk",
      "blue": "random",
      "games": 10,
      "red_wins": 7,
      "blue_wins": 3,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.22892380955107955,
      "max_step_time_ms": 1.4897999935783446
    },
    {
      "red": "greedy_risk",
      "blue": "greedy",
      "games": 10,
      "red_wins": 7,
      "blue_wins": 3,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.44870765039556065,
      "max_step_time_ms": 1.0554999971645884
    }
  ],
  "wall_seconds": 0.375,
  "generated_at": "2026-05-12T19:18:41"
}
```
