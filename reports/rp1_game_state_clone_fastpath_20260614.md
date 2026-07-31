# R-P1 GameState Clone Fast Path

Date: 2026-06-14

## Scope

This slice adds an in-memory `GameState.clone()` API and uses it in rollout root simulation hot paths instead of `GameState.serialize()` / `GameState.deserialize()`.

The change is intended as a behavior-equivalent performance cleanup for internal rollout simulations. Public serialization, replay format, core rule semantics, GUI defaults, release/v1.0, and P14 rollout parameters are unchanged.

## Implementation

Changed files:

```text
core/game_state.py
ai/rollout_ai.py
tests/test_game_state.py
tests/test_perf_probe.py
tests/test_rollout_paired.py
docs/superpowers/plans/2026-06-14-rp1-game-state-clone-plan.md
```

`GameState.clone(include_history=True)` deep-copies pieces and move history using existing `Piece.copy()` and `Move.copy()`. Rollout hot paths use `clone(include_history=False)` because playout simulations do not inspect historical moves or call `undo_move()`.

Updated clone sites:

```text
RolloutAI._sample_move_score()
RolloutPairedAI.choose_move()
```

`tests/test_rollout_paired.py::test_rollout_paired_uses_clone_without_serialize_round_trip` monkeypatches `GameState.serialize()` and `GameState.deserialize()` and verifies the paired root simulation path no longer calls either method.

## Verification

TDD red checks:

```text
tests/test_game_state.py::test_clone_matches_serialize_round_trip_and_is_independent: failed with AttributeError before implementation
tests/test_game_state.py::test_clone_can_omit_history_for_rollout_simulations: failed with AttributeError before implementation
```

Targeted verification:

```text
tests/test_game_state.py tests/test_rollout_ai.py tests/test_rollout_paired.py tests/test_perf_probe.py: 59 passed in 1.03s
```

Full regression:

```text
pytest -q: 941 passed in 73.09s
```

Whitespace check:

```text
git diff --check: no whitespace errors; only existing LF/CRLF working-copy warnings in documentation files
```

## Perf Probe

Command:

```powershell
$env:CG_RESEARCH_DATA_DIR = "E:/computergame-data"
$env:PIP_CACHE_DIR = "E:/pip-cache"
$env:TORCH_HOME = "E:/torch-cache"
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 1 --samples 8 --seed 62014 --output "reports/rp1_game_state_clone_fastpath_probe_20260614.json"
```

Output:

```text
reports/rp1_game_state_clone_fastpath_probe_20260614.json
```

Observed:

```text
match_probe.games=1
match_probe.turns=17
match_probe.steps=17
match_probe.average_step_time_ms=96.75301176471027
match_probe.max_step_time_ms=294.23989999850164
match_probe.illegal_moves=0
match_probe.crashes=0
match_probe.timeouts=0
rollout_decision_probe.samples=8
rollout_decision_probe.root_visits=1833
rollout_decision_probe.root_visits_per_second=133.42274865435257
rollout_decision_probe.instrumentation.game_state_clone_calls=1836
rollout_decision_probe.instrumentation.game_state_serialize_calls=0
rollout_decision_probe.instrumentation.game_state_deserialize_calls=0
```

This run confirms the rollout decision hot path no longer uses serialize/deserialize cloning. It does not claim an overall 5x speedup, because this plan did not preserve a same-parameter pre-change baseline.

## Decision

R-P1 clone fast path is landed as an internal performance cleanup. It changes no default AI, GUI, release, P14 parameter, or core public rule behavior.
