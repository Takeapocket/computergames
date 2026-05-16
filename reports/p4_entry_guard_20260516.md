# P4 Entry Guard: MCTS Opponent Node / Release Default Baseline

Date: 2026-05-16

## Scope

This is an entry guard only. It does not run a large MCTS candidate or promotion benchmark, does not change GUI defaults, and does not change `release/v1.0/default_params.json` or `release/v1.0/config.json`.

## Baseline Requirement

All P4 candidate or promotion benchmarks must play against the current GUI/release working default AI:

```json
{
  "kind": "rollout",
  "kwargs": {
    "rollouts_per_move": 32,
    "max_rollout_turns": 80,
    "max_step_time_ms": 750.0,
    "epsilon": 0.1,
    "close_sample_margin": 0.08,
    "close_sample_rollouts_per_move": 32,
    "low_confidence_margin": 0.08,
    "playout_policy": "greedy_risk",
    "cutoff_eval": "zweistein",
    "deadline_safety_ms": 30.0
  }
}
```

Naked `opponent="rollout"` is not valid for P4 candidate/promotion decisions because it resolves to the old flat rollout parameters unless effective kwargs are provided.

## Changes

- `ai/mcts.py`: opponent DecisionNode selection now minimizes root-player value; root-player DecisionNode selection still maximizes root-player value. Backprop remains root-player perspective.
- `scripts/bench_ai.py`: loads `release/v1.0/default_params.json` and injects those rollout kwargs into `mcts_eval_v1` candidate/promotion profiles.
- `tests/test_mcts.py`: adds a regression test for opponent DecisionNode minimization.
- `tests/test_bench_ai.py`: adds guard tests that `mcts_eval_v1` candidate/promotion profiles use the release default rollout kwargs.

## Entry Checks

| Check | Result |
|---|---|
| `pytest tests/test_mcts.py::test_mcts_opponent_decision_node_minimizes_root_player_value -q` | 1 passed |
| `pytest tests/test_bench_ai.py::test_resolve_profile_uses_release_default_rollout_kwargs_for_mcts_p4 tests/test_bench_ai.py::test_merge_profile_kwargs_can_use_opponent_kwargs -q` | 2 passed |
| `pytest tests/test_mcts.py -q` | 15 passed |
| `pytest tests/test_bench_ai.py -q` | 33 passed |
| `pytest -q` | 523 passed in 10.91s |
| `scripts/smoke_test.py` | completed; `undo restored: True` |
| `bench_ai.py --candidate mcts_eval_v1 --stage candidate --games-per-side 1 ... --no-save-report` | CLI ran with release default rollout opponent kwargs; returned 1 only because the tiny 2-game smoke failed strength gates |
| `quick_bench.py --red mcts_eval_v1 --blue rollout --blue-kwargs <release default kwargs> --games 1 ... --no-save-report` | CLI accepted explicit kwargs; opponent signature recorded `cutoff_eval="zweistein"` and `deadline_safety_ms=30.0` |

## Promotion Boundary

P4 can continue to small candidate testing only after this guard. Any promotion discussion requires candidate data against the current release default rollout kwargs, with:

```text
win_rate >= 55%
Wilson lower >= 52%
illegal_moves = 0
crashes = 0
timeouts = 0
avg_step_time_ms <= 500
max_step_time_ms <= 5000
```

No GUI/release default replacement is authorized by this entry guard.
