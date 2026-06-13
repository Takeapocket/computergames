# R-P1 Trusted Apply Fast Path

Date: 2026-06-14

## Scope

This is a narrow R-P1 performance slice for rollout/search hot loops.

It adds a private `GameState` fast path for applying a move that was already
generated from the current state's legal move list. Public `apply_move()` keeps
its full validation semantics and remains the only API for GUI, records, replay,
external input, and other untrusted callers.

## Implementation

`GameState.apply_move(move, dice)` still performs:

```text
terminal-state check
current-player check
dice-selected piece check
legal move regeneration and canonical capture snapshot
```

After validation it delegates mutation to:

```text
GameState._apply_known_legal_move(move)
```

The private helper:

```text
requires the game to be unfinished
requires move.player to match current_player
trusts that the move came from legal_moves() for this exact state
updates captured piece liveness
updates moved piece position
copies the move into history
copies the return value
```

`RolloutAI` now uses the helper only at internal points where the move is known
to come from legal enumeration:

```text
RolloutAI._sample_move_score()
RolloutAI._playout()
RolloutPairedAI.choose_move()
RolloutPairedAI._playout_with_rng()
```

No GUI, record, replay, adapter, release config, P14 default parameters, or core
rule semantics were changed.

## Behavior Locks

Added tests cover:

```text
public apply_move still canonicalizes captured_piece from regenerated legal moves
private _apply_known_legal_move matches public apply_move on legal captures
private _apply_known_legal_move rejects wrong current player
private _apply_known_legal_move rejects moves after a terminal state
RolloutAI fixed-seed recommendation, root stats, input-state immutability, and RNG progression remain unchanged
```

Targeted verification:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_game_state.py" "tests/test_rollout_ai.py" -q
```

Observed:

```text
36 passed in 0.97s
```

Full regression:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Observed:

```text
926 passed in 73.99s
```

Whitespace check:

```powershell
git diff --check
```

Observed: no whitespace errors; only existing CRLF/LF working-copy warnings.

## Perf Probe

Command:

```powershell
& ".venv/Scripts/python.exe" "scripts/perf_probe.py" --games 1 --samples 8 --seed 62014 --output "reports/rp1_trusted_apply_fastpath_probe_20260614.json"
```

Observed:

```text
match_probe:
  games=1, turns=17, steps=17
  average_step_time_ms=89.8407
  max_step_time_ms=286.1609
  illegal_moves=0, crashes=0, timeouts=0

rollout_decision_probe:
  samples=8, decisions=8
  root_visits=1900
  root_visits_per_second=143.7636
  average_root_visits=237.5
  game_state_serialize_calls=1902
  game_state_deserialize_calls=1902
  legal_moves_calls=1411197
  greedy_ai_constructs=1910
  rng_constructs=1919
```

This probe is a post-change smoke measurement. It should not be read as a
claimed speedup factor because no same-parameter pre-change baseline was saved
in this session.

## Remaining R-P1 Work

The next low-risk optimization candidate is clone overhead:

```text
use serialize(include_history=False) in rollout clones
hoist the immutable snapshot outside the per-visit loop when safe
keep fixed-seed behavior and RNG state locked by characterization tests
```

GreedyAI object reuse and policy RNG reuse remain unsafe as behavior-preserving
optimizations unless they preserve per-playout policy seed derivation exactly.
