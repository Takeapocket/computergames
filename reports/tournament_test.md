# AI Tournament Matrix

generated_at: 2026-05-13T10:53:37
seed: 2026
games_per_orientation: 5
layout: default_no_stuck_corner_v1
wall_seconds: 36.701
illegal_moves_total: 0
crashes_total: 0

行 = Red 方 AI；列 = Blue 方 AI；值 = Red 视角胜率（按对应有序对 `--games` 局）。

| AI | random | greedy | greedy_risk | rollout |
|---|---:|---:|---:|---:|
| random | - | 40.0% | 20.0% | 20.0% |
| greedy | 60.0% | - | 40.0% | 20.0% |
| greedy_risk | 80.0% | 80.0% | - | 60.0% |
| rollout | 80.0% | 60.0% | 60.0% | - |

## Per-pair metadata

```json
{
  "ais": [
    "random",
    "greedy",
    "greedy_risk",
    "rollout"
  ],
  "games_per_orientation": 5,
  "seed": 2026,
  "layout_id": "default_no_stuck_corner_v1",
  "max_turns": 200,
  "illegal_moves_total": 0,
  "crashes_total": 0,
  "pairs": [
    {
      "red": "random",
      "blue": "greedy",
      "games": 5,
      "red_wins": 2,
      "blue_wins": 3,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.16318369513180148,
      "max_step_time_ms": 0.802999988081865
    },
    {
      "red": "random",
      "blue": "greedy_risk",
      "games": 5,
      "red_wins": 1,
      "blue_wins": 4,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.16150842083765096,
      "max_step_time_ms": 0.7980999944265932
    },
    {
      "red": "random",
      "blue": "rollout",
      "games": 5,
      "red_wins": 1,
      "blue_wins": 4,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 54.28642222206249,
      "max_step_time_ms": 390.723300006357
    },
    {
      "red": "greedy",
      "blue": "random",
      "games": 5,
      "red_wins": 3,
      "blue_wins": 2,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.1820473677454222,
      "max_step_time_ms": 0.9358999959658831
    },
    {
      "red": "greedy",
      "blue": "greedy_risk",
      "games": 5,
      "red_wins": 2,
      "blue_wins": 3,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.30115729153597687,
      "max_step_time_ms": 0.6587000098079443
    },
    {
      "red": "greedy",
      "blue": "rollout",
      "games": 5,
      "red_wins": 1,
      "blue_wins": 4,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 60.10573516439283,
      "max_step_time_ms": 316.71249998908024
    },
    {
      "red": "greedy_risk",
      "blue": "random",
      "games": 5,
      "red_wins": 4,
      "blue_wins": 1,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.16655348820698468,
      "max_step_time_ms": 0.6552999984705821
    },
    {
      "red": "greedy_risk",
      "blue": "greedy",
      "games": 5,
      "red_wins": 4,
      "blue_wins": 1,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 0.316242683322521,
      "max_step_time_ms": 0.6934999983059242
    },
    {
      "red": "greedy_risk",
      "blue": "rollout",
      "games": 5,
      "red_wins": 3,
      "blue_wins": 2,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 62.09370967686697,
      "max_step_time_ms": 323.5599000036018
    },
    {
      "red": "rollout",
      "blue": "random",
      "games": 5,
      "red_wins": 4,
      "blue_wins": 1,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 83.24961770813388,
      "max_step_time_ms": 477.6106999925105
    },
    {
      "red": "rollout",
      "blue": "greedy",
      "games": 5,
      "red_wins": 3,
      "blue_wins": 2,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 63.70090315819988,
      "max_step_time_ms": 396.2418000010075
    },
    {
      "red": "rollout",
      "blue": "greedy_risk",
      "games": 5,
      "red_wins": 3,
      "blue_wins": 2,
      "draws": 0,
      "illegal_moves": 0,
      "crashes": 0,
      "average_step_time_ms": 61.930095789935685,
      "max_step_time_ms": 381.9633000093745
    }
  ],
  "wall_seconds": 36.701,
  "generated_at": "2026-05-13T10:53:37"
}
```
