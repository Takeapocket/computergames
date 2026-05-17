# P7.0 Rollout Failure Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Generate a reproducible report that categorizes losses by the current release default `rollout` against `greedy_risk`.

**Architecture:** Implement a standalone analyzer script with its own instrumented game loop instead of changing `ai.match.play_one_game()`. The analyzer reads release default rollout kwargs, records per-step root diagnostics and tactical facts, writes JSON/Markdown reports, and explicitly states that labels are attribution clues rather than causal proof.

**Tech Stack:** Python 3.11, argparse, json, random, pathlib, existing `ai.match.build_ai`, existing `ai.match.starting_state_for`, existing `ai.tactical.find_winning_moves`, existing `GameState.apply_move()` / `undo_move()`.

---

## File Structure

- Create: `scripts/analyze_rollout_failures.py`
  - Release default loader.
  - Tactical helper functions.
  - Instrumented game loop.
  - Failure bucket aggregation.
  - JSON and Markdown report writers.
- Create: `tests/test_analyze_rollout_failures.py`
  - Unit tests for helper functions and report writer.
- Generate when running manually: `reports/p7_rollout_failure_analysis_YYYYMMDD.json`
- Generate when running manually: `reports/p7_rollout_failure_analysis_YYYYMMDD.md`

## Task 1: Helper Tests

**Files:**
- Create: `tests/test_analyze_rollout_failures.py`
- Create later: `scripts/analyze_rollout_failures.py`

- [ ] **Step 1: Add failing tests for tactical helper classification**

Create `tests/test_analyze_rollout_failures.py`:

```python
from __future__ import annotations

import json

from core.game_state import GameState
from core.types import Player, Position
from scripts import analyze_rollout_failures


def test_move_wins_immediately_detects_goal_corner() -> None:
    state = GameState.from_layout(
        red={6: Position(3, 3)},
        blue={1: Position(0, 4)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]

    assert analyze_rollout_failures.move_wins_immediately(state, move, 6) is True


def test_opponent_direct_win_dice_after_move_detects_allowed_loss() -> None:
    state = GameState.from_layout(
        red={6: Position(2, 2)},
        blue={1: Position(1, 1)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]

    dice_set = analyze_rollout_failures.opponent_direct_win_dice_after_move(state, move, 6)

    assert isinstance(dice_set, list)


def test_bucket_loss_tags_counts_known_labels() -> None:
    steps = [
        {
            "subject_player": "red",
            "subject_to_move": True,
            "exists_direct_win": True,
            "chosen_direct_win": False,
            "allowed_direct_loss_dice": [],
            "low_confidence": False,
            "timed_out": False,
            "used_fallback": False,
            "self_capture": False,
            "score_margin": 0.2,
        }
    ]

    buckets = analyze_rollout_failures.bucket_loss_tags(steps, subject_player=Player.RED)

    assert buckets["missed_direct_win"] == 1
    assert buckets["unclassified"] == 0


def test_write_reports_mentions_attribution_not_causation(tmp_path) -> None:
    payload = {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": "greedy_risk",
        "games": 1,
        "seed_pool": [27016],
        "summary": {"subject_wins": 0, "subject_losses": 1, "illegal_moves": 0, "crashes": 0, "timeouts": 0},
        "failure_buckets": {
            "missed_direct_win": 1,
            "allowed_direct_loss": 0,
            "low_confidence_loss": 0,
            "timeout_or_fallback": 0,
            "bad_self_capture": 0,
            "opening_side_bias": 0,
            "material_race_loss": 0,
            "unclassified": 0,
        },
        "examples": [],
        "command": "python scripts/analyze_rollout_failures.py --games 1",
        "default_layout": "balanced_v1",
    }
    md_path = tmp_path / "analysis.md"
    json_path = tmp_path / "analysis.json"

    analyze_rollout_failures.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["games"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "标签是归因线索，不是因果证明" in markdown
    assert "默认 AI、默认布局、release 配置未变" in markdown
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_rollout_failures.py
```

Expected: FAIL because `scripts/analyze_rollout_failures.py` does not exist.

## Task 2: Implement Analyzer Helpers

**Files:**
- Create: `scripts/analyze_rollout_failures.py`

- [ ] **Step 1: Create imports and constants**

Create `scripts/analyze_rollout_failures.py` with:

```python
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, starting_state_for
from ai.tactical import find_winning_moves
from core.move import Move
from core.types import Player


BUCKETS = (
    "missed_direct_win",
    "allowed_direct_loss",
    "low_confidence_loss",
    "timeout_or_fallback",
    "bad_self_capture",
    "opening_side_bias",
    "material_race_loss",
    "unclassified",
)
```

- [ ] **Step 2: Add release loader and tactical helpers**

Add:

```python
def load_release_default_ai_config(
    path: str | Path = ROOT / "release" / "v1.0" / "default_params.json",
) -> tuple[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")
    metadata_keys = {"ai", "fallback_ai", "promotion_report"}
    return "rollout", {key: value for key, value in data.items() if key not in metadata_keys}


def board_key(state) -> str:
    return repr(state.serialize(include_history=False))


def move_wins_immediately(state, move: Move, dice: int) -> bool:
    state.apply_move(move, dice=dice)
    try:
        return state.get_winner() is move.player
    finally:
        state.undo_move()


def direct_winning_moves(state, dice: int) -> list[Move]:
    return find_winning_moves(state, dice, state.current_player)


def opponent_direct_win_dice_after_move(state, move: Move, dice: int) -> list[int]:
    state.apply_move(move, dice=dice)
    try:
        opponent = state.current_player
        winning_dice = []
        for next_dice in range(1, 7):
            if find_winning_moves(state, next_dice, opponent):
                winning_dice.append(next_dice)
        return winning_dice
    finally:
        state.undo_move()


def is_self_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player
```

- [ ] **Step 3: Add bucket classification**

Add:

```python
def _empty_buckets() -> dict[str, int]:
    return {bucket: 0 for bucket in BUCKETS}


def bucket_loss_tags(steps: list[dict], *, subject_player: Player) -> dict[str, int]:
    buckets = _empty_buckets()
    matched = False
    subject_steps = [step for step in steps if step["subject_to_move"]]

    for step in subject_steps:
        if step["exists_direct_win"] and not step["chosen_direct_win"]:
            buckets["missed_direct_win"] += 1
            matched = True
        if step["allowed_direct_loss_dice"]:
            buckets["allowed_direct_loss"] += 1
            matched = True
        if step["low_confidence"]:
            buckets["low_confidence_loss"] += 1
            matched = True
        if step["timed_out"] or step["used_fallback"]:
            buckets["timeout_or_fallback"] += 1
            matched = True
        if step["self_capture"] and float(step.get("score_margin") or 0.0) < 0.08:
            buckets["bad_self_capture"] += 1
            matched = True

    if not matched:
        buckets["unclassified"] += 1
    return buckets
```

- [ ] **Step 4: Run helper tests and verify GREEN for helpers**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_rollout_failures.py
```

Expected: helper tests pass after report writer is added in Task 4.

## Task 3: Implement Instrumented Game Loop

**Files:**
- Modify: `scripts/analyze_rollout_failures.py`

- [ ] **Step 1: Add one-game analyzer**

Add:

```python
def analyze_one_game(
    *,
    subject_player: Player,
    subject_ai,
    opponent_ai,
    dice_rng: random.Random,
    layout: str,
    max_turns: int,
) -> dict:
    state = starting_state_for(layout)
    steps: list[dict] = []
    illegal_moves = 0
    crashes = 0
    timeouts = 0

    for turn in range(max_turns):
        winner = state.get_winner()
        if winner is not None:
            return {
                "winner": winner.value,
                "subject_won": winner is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "steps": steps,
                "termination_reason": "winner",
            }

        active = state.current_player
        ai = subject_ai if active is subject_player else opponent_ai
        dice = dice_rng.randint(1, 6)
        legal = state.legal_moves(active, dice)
        if not legal:
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "steps": steps,
                "termination_reason": "no_move",
            }

        exists_direct_win = bool(direct_winning_moves(state, dice))
        started = time.perf_counter()
        try:
            move = ai.choose_move(state, dice)
        except Exception as exc:  # noqa: BLE001 - analysis records crashes
            crashes += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "steps": steps,
                "termination_reason": f"crash:{type(exc).__name__}",
            }
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms > float(getattr(ai, "max_step_time_ms", 10**9)):
            timeouts += 1

        if move not in legal:
            illegal_moves += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "steps": steps,
                "termination_reason": "illegal_move",
            }

        chosen_direct_win = move_wins_immediately(state, move, dice)
        allowed_direct_loss_dice = [] if chosen_direct_win else opponent_direct_win_dice_after_move(state, move, dice)
        root_stats = getattr(ai, "last_root_stats", [])
        steps.append(
            {
                "turn": turn,
                "board": board_key(state),
                "player": active.value,
                "subject_player": subject_player.value,
                "subject_to_move": active is subject_player,
                "dice": dice,
                "legal_move_count": len(legal),
                "move": {
                    "piece_id": move.piece_id,
                    "from": [move.from_pos.row, move.from_pos.col],
                    "to": [move.to_pos.row, move.to_pos.col],
                },
                "root_stats_count": len(root_stats),
                "low_confidence": bool(getattr(ai, "last_low_confidence", False)),
                "timed_out": bool(getattr(ai, "last_timed_out", False)),
                "used_fallback": bool(getattr(ai, "last_used_fallback", False)),
                "score_margin": getattr(ai, "last_score_margin", None),
                "exists_direct_win": exists_direct_win,
                "chosen_direct_win": chosen_direct_win,
                "allowed_direct_loss_dice": allowed_direct_loss_dice,
                "self_capture": is_self_capture(move),
                "elapsed_ms": elapsed_ms,
            }
        )
        state.apply_move(move, dice=dice)

    return {
        "winner": None,
        "subject_won": False,
        "turns": max_turns,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "steps": steps,
        "termination_reason": "draw_max_turns",
    }
```

- [ ] **Step 2: Add multi-game aggregation**

Add:

```python
def analyze_games(*, games: int, seed_pool: list[int], opponent: str, layout: str, max_turns: int) -> dict:
    subject_kind, subject_kwargs = load_release_default_ai_config()
    summary = {"subject_wins": 0, "subject_losses": 0, "illegal_moves": 0, "crashes": 0, "timeouts": 0}
    buckets = _empty_buckets()
    examples: list[dict] = []

    for game_index in range(games):
        seed = seed_pool[game_index % len(seed_pool)] * 100_000 + game_index
        subject_player = Player.RED if game_index % 2 == 0 else Player.BLUE
        subject_ai = build_ai(subject_kind, seed=seed * 3 + 1, **subject_kwargs)
        opponent_ai = build_ai(opponent, seed=seed * 3 + 2)
        result = analyze_one_game(
            subject_player=subject_player,
            subject_ai=subject_ai,
            opponent_ai=opponent_ai,
            dice_rng=random.Random(seed * 3),
            layout=layout,
            max_turns=max_turns,
        )
        summary["illegal_moves"] += int(result["illegal_moves"])
        summary["crashes"] += int(result["crashes"])
        summary["timeouts"] += int(result["timeouts"])
        if result["subject_won"]:
            summary["subject_wins"] += 1
        else:
            summary["subject_losses"] += 1
            game_buckets = bucket_loss_tags(result["steps"], subject_player=subject_player)
            for key, value in game_buckets.items():
                buckets[key] += value
            examples.append(
                {
                    "game_index": game_index,
                    "subject_player": subject_player.value,
                    "termination_reason": result["termination_reason"],
                    "buckets": game_buckets,
                    "last_steps": result["steps"][-6:],
                }
            )

    return {
        "subject": {"ai": subject_kind, "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": opponent,
        "games": games,
        "seed_pool": seed_pool,
        "default_layout": layout,
        "summary": summary,
        "failure_buckets": buckets,
        "examples": examples[:20],
    }
```

## Task 4: Report Writer and CLI

**Files:**
- Modify: `scripts/analyze_rollout_failures.py`

- [ ] **Step 1: Add report writer**

Add:

```python
def write_reports(payload: dict, output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# P7 Rollout Failure Analysis",
        "",
        "默认 AI、默认布局、release 配置未变。",
        "",
        "标签是归因线索，不是因果证明。",
        "",
        f"- subject: `{payload['subject']['ai']}`",
        f"- opponent: `{payload['opponent']}`",
        f"- games: `{payload['games']}`",
        f"- seed_pool: `{payload['seed_pool']}`",
        f"- default_layout: `{payload['default_layout']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failure Buckets", ""])
    for key, value in payload["failure_buckets"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Reproduce", "", "```powershell", payload["command"], "```"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 2: Add CLI**

Add:

```python
def _parse_seed_pool(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze release default rollout losses.")
    parser.add_argument("--games", type=int, default=120)
    parser.add_argument("--seed-pool", default="27016,27017,27018")
    parser.add_argument("--opponent", default="greedy_risk")
    parser.add_argument("--starting-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "p7_rollout_failure_analysis.md")
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "p7_rollout_failure_analysis.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seed_pool = _parse_seed_pool(args.seed_pool)
    payload = analyze_games(
        games=args.games,
        seed_pool=seed_pool,
        opponent=args.opponent,
        layout=args.starting_layout,
        max_turns=args.max_turns,
    )
    payload["command"] = (
        f'& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" '
        f'--games {args.games} --seed-pool {args.seed_pool} --opponent {args.opponent} '
        f'--starting-layout {args.starting_layout} --max-turns {args.max_turns} '
        f'--output "{args.output}" --json-output "{args.json_output}"'
    )
    write_reports(payload, args.output, args.json_output)
    print(f"wrote {args.output}")
    print(f"wrote {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_rollout_failures.py
```

Expected: PASS.

## Task 5: Script Smoke and Full P7.0 Report

**Files:**
- Verify: `scripts/analyze_rollout_failures.py`
- Generate: `reports/p7_rollout_failure_analysis_20260516.md`
- Generate: `reports/p7_rollout_failure_analysis_20260516.json`

- [ ] **Step 1: Run a small smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" --games 2 --seed-pool 27016 --opponent greedy_risk --starting-layout balanced_v1 --output "reports/p7_rollout_failure_analysis_smoke.md" --json-output "reports/p7_rollout_failure_analysis_smoke.json"
```

Expected: exit code 0 and both smoke files written.

- [ ] **Step 2: Run full P7.0 analysis**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" --games 120 --seed-pool 27016,27017,27018 --opponent greedy_risk --starting-layout balanced_v1 --output "reports/p7_rollout_failure_analysis_20260516.md" --json-output "reports/p7_rollout_failure_analysis_20260516.json"
```

Expected: exit code 0 and both P7.0 files written.

## Task 6: P7.0 Verification

**Files:**
- Verify: `tests/test_analyze_rollout_failures.py`
- Verify: `scripts/analyze_rollout_failures.py`

- [ ] **Step 1: Run analyzer tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_rollout_failures.py
```

Expected: PASS.

- [ ] **Step 2: Run preflight**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

Expected: output ends with `READY FOR MATCH`.

## Self-Review

- Spec coverage: Covers P7.0 script, report fields, attribution disclaimer, and no-default-change constraint.
- Placeholder scan: No placeholder tokens or omitted helper names.
- Boundary check: The analyzer only writes reports and does not modify GUI/release defaults.
