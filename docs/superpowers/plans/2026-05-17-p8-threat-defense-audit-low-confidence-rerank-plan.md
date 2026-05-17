# P8 Threat Defense Audit + Low-confidence Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests, generated reports, and diff review instead of commits.

**Goal:** Build a reproducible P8 audit that determines whether default rollout losses contain safer threat-reducing alternatives, then conditionally evaluate a narrow low-confidence threat rerank candidate without changing GUI/release defaults.

**Architecture:** Add a standalone threat-defense analyzer that reuses existing core rules, release-default rollout config, and rollout root diagnostics. Keep the audit and candidate paths separate: P8.0-P8.3 generate reports; P8.4/P8.5 are only implemented when report gates support them.

**Tech Stack:** Python 3.11, argparse, json, pathlib, random, existing `ai.match.build_ai`, `ai.match.starting_state_for`, `ai.release_defaults.load_release_default_rollout_kwargs`, `ai.rollout_ai.RootMoveStats`, `ai.tactical.find_winning_moves`, `GameState.legal_moves()` / `apply_move()` / `undo_move()` / `get_winner()`, pytest.

---

## File Structure

- Create: `scripts/analyze_threat_defense.py`
  - Release default loader.
  - Move serialization and root-stat indexing helpers.
  - `opponent_winning_dice_set` per candidate move.
  - Instrumented game loop for subject losses.
  - Threat-defense aggregation, low-confidence ratios, self-capture correlation.
  - JSON and Markdown report writers.
- Create: `tests/test_analyze_threat_defense.py`
  - Helper behavior tests.
  - Position audit tests.
  - Aggregation/report writer tests.
- Generate when running P8.1: `reports/p8_threat_defense_audit_20260517.json`
- Generate when running P8.1: `reports/p8_threat_defense_audit_20260517.md`
- Optional create after audit gate passes: `ai/threat_rerank.py`
  - `ThreatRerankAI` wrapper around release-default rollout.
- Optional create after audit gate passes: `tests/test_threat_rerank.py`
  - Wrapper routing and telemetry tests.
- Optional modify after audit gate passes: `ai/match.py`
  - Register `rollout_threat_rerank`.
  - Register `rollout_safe_timing_profile` only if P8.5 gate is needed.
  - Extend `ai_version_signature()` for `ThreatRerankAI`.
- Optional modify after audit gate passes and user approval: `scripts/bench_ai.py`
  - Register P8 candidate profiles with `opponent_kwargs=RELEASE_DEFAULT_ROLLOUT_KWARGS`.
- Optional generate: `reports/p84_candidate_rollout_threat_rerank_20260517.{json,md}`
- Optional generate: `reports/p85_candidate_rollout_safe_timing_profile_20260517.{json,md}`
- Modify after execution results are known: `PROJECT_MEMORY.md`
  - Add P8 audit/candidate result.
- Modify after execution results are known: `PROJECT_PHASES.md`
  - Add P8 status and preserve default AI/default layout constraints.

## Guardrails

- Do not modify `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`.
- Do not modify `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`.
- Do not modify `release/v1.0/default_params.json`.
- Do not modify `release/v1.0/config.json`.
- Do not modify `core/` rules.
- Do not change default layout from `balanced_v1`.
- Do not connect any P8 candidate to GUI/release default.
- Do not add a direct-win guard in P8; P7 had `missed_direct_win=0`.
- Do not ban self-capture.
- Do not use full `TacticalAI`.

## Task 1: Baseline Guard Check

**Files:**
- Read-only: `release/v1.0/default_params.json`
- Read-only: `release/v1.0/config.json`
- Read-only: `gui/main_window.py`
- Read-only: `ai/match.py`

- [ ] **Step 1: Confirm release default AI is still P3 rollout**

Run:

```powershell
@'
import json
from pathlib import Path

params = json.loads(Path("release/v1.0/default_params.json").read_text(encoding="utf-8"))
assert params["ai"] == "rollout"
assert params["rollouts_per_move"] == 32
assert params["max_step_time_ms"] == 750.0
assert params["epsilon"] == 0.1
assert params["playout_policy"] == "greedy_risk"
assert params["cutoff_eval"] == "zweistein"
assert params["deadline_safety_ms"] == 30.0
assert params["fallback_ai"] == "greedy_risk"
print("release default rollout locked")
'@ | & ".venv/Scripts/python.exe" -
```

Expected: prints `release default rollout locked`.

- [ ] **Step 2: Confirm default layout remains balanced_v1**

Run:

```powershell
@'
import json
from pathlib import Path

config = json.loads(Path("release/v1.0/config.json").read_text(encoding="utf-8"))
assert config["default_layout"] == "balanced_v1"
print("release default layout locked")
'@ | & ".venv/Scripts/python.exe" -
```

Expected: prints `release default layout locked`.

- [ ] **Step 3: Run the release lock tests before editing**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py
```

Expected: PASS. If this fails, stop P8 and fix the release lock regression first.

## Task 2: Threat Defense Helper Tests

**Files:**
- Create: `tests/test_analyze_threat_defense.py`
- Create later: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Add failing helper tests**

Create `tests/test_analyze_threat_defense.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace

from ai.rollout_ai import RootMoveStats
from core.game_state import GameState
from core.types import Player, Position
from scripts import analyze_threat_defense


def test_opponent_winning_dice_after_move_detects_goal_threat() -> None:
    state = GameState.from_layout(
        red={6: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    move = state.legal_moves(Player.RED, 6)[0]

    dice_set = analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert dice_set == [1]


def test_opponent_winning_dice_after_move_restores_state() -> None:
    state = GameState.from_layout(
        red={6: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    before = state.serialize()
    move = state.legal_moves(Player.RED, 6)[0]

    analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert state.serialize() == before


def test_opponent_winning_dice_after_move_terminal_win_has_no_opponent_turn() -> None:
    state = GameState.from_layout(
        red={6: Position(3, 4)},
        blue={1: Position(0, 1)},
        current_player=Player.RED,
    )
    move = next(move for move in state.legal_moves(Player.RED, 6) if move.to_pos == Position(4, 4))

    dice_set = analyze_threat_defense.opponent_winning_dice_after_move(state, move, 6)

    assert dice_set == []


def test_move_identity_is_stable_for_equivalent_moves() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={6: Position(4, 4)},
        current_player=Player.RED,
    )
    first = state.legal_moves(Player.RED, 1)[0]
    second = replace(first)

    assert analyze_threat_defense.move_identity(first) == analyze_threat_defense.move_identity(second)


def test_root_stats_index_uses_sorted_rank_by_score() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={6: Position(4, 4)},
        current_player=Player.RED,
    )
    moves = state.legal_moves(Player.RED, 1)
    stats = [
        RootMoveStats(moves[0], visits=4, wins=1, losses=3, draws=0, cutoffs=0, score=-0.2, winrate=0.25, avg=-0.2),
        RootMoveStats(moves[1], visits=4, wins=3, losses=1, draws=0, cutoffs=0, score=0.5, winrate=0.75, avg=0.5),
    ]

    index = analyze_threat_defense.root_stats_index(stats)

    assert index[analyze_threat_defense.move_identity(moves[1])]["rank"] == 1
    assert index[analyze_threat_defense.move_identity(moves[0])]["rank"] == 2


def test_score_margin_bucket_boundaries() -> None:
    assert analyze_threat_defense.score_margin_bucket(None) == ">0.08_or_null"
    assert analyze_threat_defense.score_margin_bucket(0.01) == "<=0.02"
    assert analyze_threat_defense.score_margin_bucket(0.03) == "(0.02,0.04]"
    assert analyze_threat_defense.score_margin_bucket(0.08) == "(0.04,0.08]"
    assert analyze_threat_defense.score_margin_bucket(0.09) == ">0.08_or_null"
```

- [ ] **Step 2: Run helper tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: FAIL because `scripts/analyze_threat_defense.py` does not exist or lacks the tested functions.

## Task 3: Implement Audit Helper Layer

**Files:**
- Create: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Create script imports and constants**

Create `scripts/analyze_threat_defense.py` with:

```python
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, starting_state_for
from ai.release_defaults import load_release_default_rollout_kwargs
from ai.tactical import find_winning_moves
from core.move import Move
from core.types import Player


MARGIN_BUCKETS = ("<=0.02", "(0.02,0.04]", "(0.04,0.08]", ">0.08_or_null")
```

- [ ] **Step 2: Add move and root-stat helpers**

Add below constants:

```python
def move_identity(move: Move) -> tuple[str, int, int, int, int, int]:
    return (
        move.player.value,
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def move_sort_key(move: Move) -> tuple[int, int, int, int, int]:
    return (
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def move_to_dict(move: Move) -> dict[str, Any]:
    return {
        "piece_id": move.piece_id,
        "from": [move.from_pos.row, move.from_pos.col],
        "to": [move.to_pos.row, move.to_pos.col],
    }


def is_self_capture(move: Move) -> bool:
    return move.captured_piece is not None and move.captured_piece.player is move.player


def board_key(state) -> str:
    return json.dumps(state.serialize(include_history=False), ensure_ascii=False, sort_keys=True)


def root_stats_index(root_stats: list[Any]) -> dict[tuple[str, int, int, int, int, int], dict[str, Any]]:
    ranked = sorted(
        root_stats,
        key=lambda item: (-float(getattr(item, "score", 0.0)), move_sort_key(item.move)),
    )
    index: dict[tuple[str, int, int, int, int, int], dict[str, Any]] = {}
    for rank, item in enumerate(ranked, start=1):
        index[move_identity(item.move)] = {
            "rank": rank,
            "score": float(getattr(item, "score", 0.0)),
            "winrate": float(getattr(item, "winrate", 0.0)),
        }
    return index


def score_margin_bucket(value: float | None) -> str:
    if value is None:
        return ">0.08_or_null"
    value = float(value)
    if value <= 0.02:
        return "<=0.02"
    if value <= 0.04:
        return "(0.02,0.04]"
    if value <= 0.08:
        return "(0.04,0.08]"
    return ">0.08_or_null"


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
```

- [ ] **Step 3: Add opponent winning dice helper**

Add:

```python
def opponent_winning_dice_after_move(state, move: Move, dice: int) -> list[int]:
    state.apply_move(move, dice=dice)
    try:
        if state.get_winner() is move.player:
            return []
        opponent = state.current_player
        winning_dice: list[int] = []
        for next_dice in range(1, 7):
            if find_winning_moves(state, next_dice, opponent):
                winning_dice.append(next_dice)
        return winning_dice
    finally:
        state.undo_move()
```

- [ ] **Step 4: Run helper tests and verify GREEN for Task 2**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: tests from Task 2 PASS or fail only because later aggregation functions are not present yet.

## Task 4: Position Audit Tests

**Files:**
- Modify: `tests/test_analyze_threat_defense.py`
- Modify later: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Add tests for one audited position**

Append to `tests/test_analyze_threat_defense.py`:

```python
def test_audit_position_finds_full_block_alternative() -> None:
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )
    legal = state.legal_moves(Player.RED, 1)
    chosen = next(move for move in legal if (move.to_pos.row, move.to_pos.col) == (1, 0))
    root_stats = [
        RootMoveStats(move, visits=4, wins=2, losses=2, draws=0, cutoffs=0, score=0.1 - index * 0.01, winrate=0.5, avg=0.0)
        for index, move in enumerate(legal)
    ]

    position = analyze_threat_defense.audit_position(
        state=state,
        dice=1,
        chosen=chosen,
        root_stats=root_stats,
        low_confidence=True,
        score_margin=0.03,
        game_index=0,
        turn=3,
        subject_player=Player.RED,
        failure_tags=["allowed_direct_loss", "low_confidence_loss"],
        top_k=5,
    )

    assert position["chosen"]["opponent_winning_dice_count"] >= 1
    assert position["threat_reducing_alternative_exists"] is True
    assert position["best_threat_count"] == 0
    assert position["full_block_alternative_exists"] is True
    assert position["score_margin_bucket"] == "(0.02,0.04]"
```

- [ ] **Step 2: Run position test and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py::test_audit_position_finds_full_block_alternative
```

Expected: FAIL because `audit_position()` is not implemented.

## Task 5: Implement Position Audit

**Files:**
- Modify: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Add root entry and move entry helpers**

Add:

```python
def _root_entry(
    move: Move,
    stats: dict[tuple[str, int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    entry = stats.get(move_identity(move))
    if entry is None:
        return {"rank": None, "score": None, "winrate": None}
    return entry


def _candidate_entry(
    *,
    state,
    dice: int,
    move: Move,
    chosen_threat_count: int | None,
    chosen_score: float | None,
    stats: dict[tuple[str, int, int, int, int, int], dict[str, Any]],
) -> dict[str, Any]:
    root = _root_entry(move, stats)
    winning_dice = opponent_winning_dice_after_move(state, move, dice)
    score = root["score"]
    return {
        **move_to_dict(move),
        "root_rank": root["rank"],
        "root_score": score,
        "root_winrate": root["winrate"],
        "score_delta_from_chosen": None if score is None or chosen_score is None else score - chosen_score,
        "opponent_winning_dice_set": winning_dice,
        "opponent_winning_dice_count": len(winning_dice),
        "threat_delta_from_chosen": None if chosen_threat_count is None else len(winning_dice) - chosen_threat_count,
        "self_capture": is_self_capture(move),
    }
```

- [ ] **Step 2: Add `audit_position()`**

Add:

```python
def audit_position(
    *,
    state,
    dice: int,
    chosen: Move,
    root_stats: list[Any],
    low_confidence: bool,
    score_margin: float | None,
    game_index: int,
    turn: int,
    subject_player: Player,
    failure_tags: list[str],
    top_k: int,
) -> dict[str, Any]:
    legal = state.legal_moves(state.current_player, dice)
    if chosen not in legal:
        raise ValueError("chosen move must be legal in audited position")

    stats = root_stats_index(root_stats)
    chosen_root = _root_entry(chosen, stats)
    chosen_winning_dice = opponent_winning_dice_after_move(state, chosen, dice)
    chosen_threat_count = len(chosen_winning_dice)
    chosen_score = chosen_root["score"]
    chosen_payload = {
        **move_to_dict(chosen),
        "root_rank": chosen_root["rank"],
        "root_score": chosen_score,
        "root_winrate": chosen_root["winrate"],
        "opponent_winning_dice_set": chosen_winning_dice,
        "opponent_winning_dice_count": chosen_threat_count,
        "self_capture": is_self_capture(chosen),
    }

    alternatives = [
        _candidate_entry(
            state=state,
            dice=dice,
            move=move,
            chosen_threat_count=chosen_threat_count,
            chosen_score=chosen_score,
            stats=stats,
        )
        for move in legal
        if move != chosen
    ]
    alternatives.sort(
        key=lambda item: (
            item["opponent_winning_dice_count"],
            999999 if item["root_rank"] is None else item["root_rank"],
            item["piece_id"],
            item["from"][0],
            item["from"][1],
            item["to"][0],
            item["to"][1],
        )
    )
    best_threat_count = min([chosen_threat_count] + [item["opponent_winning_dice_count"] for item in alternatives])
    reducing = [item for item in alternatives if item["opponent_winning_dice_count"] < chosen_threat_count]
    full_blocks = [item for item in reducing if item["opponent_winning_dice_count"] == 0]
    ranked_reducing = [item for item in reducing if item["root_rank"] is not None and item["root_rank"] <= top_k]

    return {
        "game_index": game_index,
        "turn": turn,
        "board": board_key(state),
        "subject_player": subject_player.value,
        "player": state.current_player.value,
        "dice": dice,
        "low_confidence": bool(low_confidence),
        "score_margin": score_margin,
        "score_margin_bucket": score_margin_bucket(score_margin),
        "failure_tags": list(failure_tags),
        "chosen": chosen_payload,
        "alternatives": alternatives,
        "best_threat_count": best_threat_count,
        "threat_reducing_alternative_exists": bool(reducing),
        "full_block_alternative_exists": bool(full_blocks),
        "best_threat_reducing_rank": min((item["root_rank"] for item in ranked_reducing), default=None),
    }
```

- [ ] **Step 3: Run position tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: PASS for helper and position tests.

## Task 6: Aggregation and Decision Tests

**Files:**
- Modify: `tests/test_analyze_threat_defense.py`
- Modify later: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Add tests for summary aggregation**

Append:

```python
def test_summarize_positions_counts_low_confidence_and_self_capture() -> None:
    positions = [
        {
            "low_confidence": True,
            "score_margin_bucket": "<=0.02",
            "threat_reducing_alternative_exists": True,
            "full_block_alternative_exists": True,
            "best_threat_reducing_rank": 2,
            "chosen": {"opponent_winning_dice_count": 2, "self_capture": True},
            "best_threat_count": 0,
        },
        {
            "low_confidence": False,
            "score_margin_bucket": ">0.08_or_null",
            "threat_reducing_alternative_exists": False,
            "full_block_alternative_exists": False,
            "best_threat_reducing_rank": None,
            "chosen": {"opponent_winning_dice_count": 0, "self_capture": False},
            "best_threat_count": 0,
        },
    ]

    summary = analyze_threat_defense.summarize_positions(positions, top_k=5)

    assert summary["threat_defense"]["chosen_allowed_direct_loss_positions"] == 1
    assert summary["threat_defense"]["threat_reducing_alternative_positions"] == 1
    assert summary["low_confidence"]["positions"] == 1
    assert summary["low_confidence"]["with_threat_reducing_alternative"] == 1
    assert summary["low_confidence"]["threat_reducing_ratio"] == 1.0
    assert summary["self_capture_correlation"]["self_capture_and_allowed_direct_loss"] == 1
    assert summary["score_margin_buckets"]["<=0.02"]["positions"] == 1
    assert summary["top_k"]["best_threat_reducing_in_top_k"] == 1
```

- [ ] **Step 2: Add tests for decision gate**

Append:

```python
def test_decide_supports_threat_rerank_when_ratios_are_strong() -> None:
    summary = {
        "low_confidence": {
            "positions": 40,
            "with_threat_reducing_alternative": 12,
            "threat_reducing_ratio": 0.30,
        },
        "top_k": {
            "threat_reducing_positions": 12,
            "best_threat_reducing_in_top_k": 8,
            "best_threat_reducing_in_top_k_ratio": 8 / 12,
        },
    }

    decision = analyze_threat_defense.decide_supports_threat_rerank(summary)

    assert decision["supports_threat_rerank_candidate"] is True


def test_decide_rejects_threat_rerank_when_low_confidence_sample_is_small() -> None:
    summary = {
        "low_confidence": {
            "positions": 10,
            "with_threat_reducing_alternative": 8,
            "threat_reducing_ratio": 0.80,
        },
        "top_k": {
            "threat_reducing_positions": 8,
            "best_threat_reducing_in_top_k": 8,
            "best_threat_reducing_in_top_k_ratio": 1.0,
        },
    }

    decision = analyze_threat_defense.decide_supports_threat_rerank(summary)

    assert decision["supports_threat_rerank_candidate"] is False
    assert any("low_confidence positions" in reason for reason in decision["reasons"])
```

- [ ] **Step 3: Add tests for report writer**

Append:

```python
def test_write_reports_mentions_defaults_unchanged(tmp_path) -> None:
    payload = {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": "greedy_risk",
        "games": 1,
        "seed_pool": [28016],
        "default_layout": "balanced_v1",
        "analysis_window": {"subject_losses_only": True, "subject_to_move_only": True, "score_margin": 0.08, "top_k": 5},
        "summary": {"subject_wins": 0, "subject_losses": 1, "illegal_moves": 0, "crashes": 0, "timeouts": 0, "audited_positions": 0},
        "threat_defense": {
            "chosen_allowed_direct_loss_positions": 0,
            "threat_reducing_alternative_positions": 0,
            "full_block_alternative_positions": 0,
            "partial_reduction_alternative_positions": 0,
            "average_chosen_threat_count": 0.0,
            "average_best_alternative_threat_count": 0.0,
            "average_reduction_when_available": 0.0,
        },
        "low_confidence": {
            "positions": 0,
            "with_allowed_direct_loss": 0,
            "with_threat_reducing_alternative": 0,
            "with_full_block_alternative": 0,
            "threat_reducing_ratio": 0.0,
            "full_block_ratio": 0.0,
        },
        "self_capture_correlation": {
            "self_capture_positions": 0,
            "self_capture_and_allowed_direct_loss": 0,
            "non_self_capture_positions": 0,
            "non_self_capture_and_allowed_direct_loss": 0,
            "allowed_direct_loss_rate_given_self_capture": 0.0,
            "allowed_direct_loss_rate_given_non_self_capture": 0.0,
            "self_capture_with_threat_reducing_alternative": 0,
            "self_capture_with_full_block_alternative": 0,
        },
        "score_margin_buckets": {bucket: {"positions": 0, "with_threat_reducing_alternative": 0} for bucket in analyze_threat_defense.MARGIN_BUCKETS},
        "top_k": {"threat_reducing_positions": 0, "best_threat_reducing_in_top_k": 0, "best_threat_reducing_in_top_k_ratio": 0.0},
        "positions": [],
        "decision": {"supports_threat_rerank_candidate": False, "reasons": ["low_confidence positions 0 < 30"]},
        "command": "python scripts/analyze_threat_defense.py --games 1",
    }
    md_path = tmp_path / "p8.md"
    json_path = tmp_path / "p8.json"

    analyze_threat_defense.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["games"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "默认 AI、默认布局、release 配置未变" in markdown
    assert "threat-reducing alternative" in markdown
    assert "rollout_threat_rerank" in markdown
```

- [ ] **Step 4: Run aggregation tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: FAIL because `summarize_positions()`, `decide_supports_threat_rerank()`, and `write_reports()` are not implemented.

## Task 7: Implement Aggregation, Decision, and Report Writer

**Files:**
- Modify: `scripts/analyze_threat_defense.py`

- [ ] **Step 1: Add `summarize_positions()`**

Add:

```python
def summarize_positions(positions: list[dict[str, Any]], *, top_k: int) -> dict[str, Any]:
    audited = len(positions)
    chosen_allowed = [item for item in positions if item["chosen"]["opponent_winning_dice_count"] > 0]
    reducing = [item for item in positions if item["threat_reducing_alternative_exists"]]
    full_blocks = [item for item in positions if item["full_block_alternative_exists"]]
    partial_reductions = [
        item
        for item in reducing
        if item["best_threat_count"] > 0
    ]
    reduction_amounts = [
        item["chosen"]["opponent_winning_dice_count"] - item["best_threat_count"]
        for item in reducing
    ]

    low_confidence = [item for item in positions if item["low_confidence"]]
    low_confidence_allowed = [item for item in low_confidence if item["chosen"]["opponent_winning_dice_count"] > 0]
    low_confidence_reducing = [item for item in low_confidence if item["threat_reducing_alternative_exists"]]
    low_confidence_full_blocks = [item for item in low_confidence if item["full_block_alternative_exists"]]
    low_confidence_top_k_hits = [
        item
        for item in low_confidence_reducing
        if item["best_threat_reducing_rank"] is not None and item["best_threat_reducing_rank"] <= top_k
    ]

    self_capture = [item for item in positions if item["chosen"]["self_capture"]]
    non_self_capture = [item for item in positions if not item["chosen"]["self_capture"]]
    self_capture_allowed = [item for item in self_capture if item["chosen"]["opponent_winning_dice_count"] > 0]
    non_self_capture_allowed = [item for item in non_self_capture if item["chosen"]["opponent_winning_dice_count"] > 0]

    score_margin_buckets = {
        bucket: {"positions": 0, "with_threat_reducing_alternative": 0}
        for bucket in MARGIN_BUCKETS
    }
    for item in positions:
        bucket = item["score_margin_bucket"]
        score_margin_buckets[bucket]["positions"] += 1
        if item["threat_reducing_alternative_exists"]:
            score_margin_buckets[bucket]["with_threat_reducing_alternative"] += 1

    top_k_hits = [
        item
        for item in reducing
        if item["best_threat_reducing_rank"] is not None and item["best_threat_reducing_rank"] <= top_k
    ]

    return {
        "threat_defense": {
            "chosen_allowed_direct_loss_positions": len(chosen_allowed),
            "threat_reducing_alternative_positions": len(reducing),
            "full_block_alternative_positions": len(full_blocks),
            "partial_reduction_alternative_positions": len(partial_reductions),
            "average_chosen_threat_count": safe_ratio(
                sum(item["chosen"]["opponent_winning_dice_count"] for item in positions),
                audited,
            ),
            "average_best_alternative_threat_count": safe_ratio(
                sum(item["best_threat_count"] for item in positions),
                audited,
            ),
            "average_reduction_when_available": safe_ratio(sum(reduction_amounts), len(reduction_amounts)),
        },
        "low_confidence": {
            "positions": len(low_confidence),
            "with_allowed_direct_loss": len(low_confidence_allowed),
            "with_threat_reducing_alternative": len(low_confidence_reducing),
            "with_full_block_alternative": len(low_confidence_full_blocks),
            "threat_reducing_ratio": safe_ratio(len(low_confidence_reducing), len(low_confidence)),
            "full_block_ratio": safe_ratio(len(low_confidence_full_blocks), len(low_confidence)),
            "best_threat_reducing_in_top_k": len(low_confidence_top_k_hits),
            "best_threat_reducing_in_top_k_ratio": safe_ratio(
                len(low_confidence_top_k_hits),
                len(low_confidence_reducing),
            ),
        },
        "self_capture_correlation": {
            "self_capture_positions": len(self_capture),
            "self_capture_and_allowed_direct_loss": len(self_capture_allowed),
            "non_self_capture_positions": len(non_self_capture),
            "non_self_capture_and_allowed_direct_loss": len(non_self_capture_allowed),
            "allowed_direct_loss_rate_given_self_capture": safe_ratio(len(self_capture_allowed), len(self_capture)),
            "allowed_direct_loss_rate_given_non_self_capture": safe_ratio(len(non_self_capture_allowed), len(non_self_capture)),
            "self_capture_with_threat_reducing_alternative": sum(1 for item in self_capture if item["threat_reducing_alternative_exists"]),
            "self_capture_with_full_block_alternative": sum(1 for item in self_capture if item["full_block_alternative_exists"]),
        },
        "score_margin_buckets": score_margin_buckets,
        "top_k": {
            "threat_reducing_positions": len(reducing),
            "best_threat_reducing_in_top_k": len(top_k_hits),
            "best_threat_reducing_in_top_k_ratio": safe_ratio(len(top_k_hits), len(reducing)),
        },
    }
```

- [ ] **Step 2: Add `decide_supports_threat_rerank()`**

Add:

```python
def decide_supports_threat_rerank(summary: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    low_confidence_positions = int(summary["low_confidence"]["positions"])
    threat_ratio = float(summary["low_confidence"]["threat_reducing_ratio"])
    top_k_ratio = float(summary["low_confidence"]["best_threat_reducing_in_top_k_ratio"])

    if low_confidence_positions < 30:
        reasons.append(f"low_confidence positions {low_confidence_positions} < 30")
    if threat_ratio < 0.25:
        reasons.append(f"low_confidence threat_reducing_ratio {threat_ratio:.3f} < 0.250")
    if top_k_ratio < 0.60:
        reasons.append(f"low-confidence best threat-reducing in top_k ratio {top_k_ratio:.3f} < 0.600")

    return {
        "supports_threat_rerank_candidate": not reasons,
        "reasons": reasons or [
            "low-confidence threat-reducing alternatives are frequent enough for a rollout_threat_rerank candidate"
        ],
    }
```

- [ ] **Step 3: Add report writer**

Add:

```python
def write_reports(payload: dict[str, Any], output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# P8 Threat Defense Audit",
        "",
        "默认 AI、默认布局、release 配置未变。",
        "",
        "本报告只审计 threat-reducing alternative 是否存在；它不是默认 AI 晋升证据。",
        "",
        f"- subject: `{payload['subject']['ai']}`",
        f"- opponent: `{payload['opponent']}`",
        f"- games: `{payload['games']}`",
        f"- seed_pool: `{payload['seed_pool']}`",
        f"- default_layout: `{payload['default_layout']}`",
        f"- audited_positions: `{payload['summary']['audited_positions']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Threat Defense", ""])
    for key, value in payload["threat_defense"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Low Confidence", ""])
    for key, value in payload["low_confidence"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Self-capture Correlation", ""])
    for key, value in payload["self_capture_correlation"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Score Margin Buckets", ""])
    for bucket, values in payload["score_margin_buckets"].items():
        lines.append(
            f"- {bucket}: positions=`{values['positions']}`, "
            f"with_threat_reducing_alternative=`{values['with_threat_reducing_alternative']}`"
        )

    lines.extend(["", "## Top-k Coverage", ""])
    for key, value in payload["top_k"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Decision", ""])
    lines.append(
        f"- supports_threat_rerank_candidate: "
        f"`{payload['decision']['supports_threat_rerank_candidate']}`"
    )
    for reason in payload["decision"]["reasons"]:
        lines.append(f"- reason: `{reason}`")

    lines.extend(["", "## Examples", ""])
    for item in payload["positions"][:5]:
        lines.append(
            "- "
            f"game={item['game_index']} turn={item['turn']} dice={item['dice']} "
            f"chosen_threat={item['chosen']['opponent_winning_dice_count']} "
            f"best_threat={item['best_threat_count']} "
            f"low_confidence={item['low_confidence']}"
        )

    lines.extend(["", "## Reproduce", "", "```powershell", payload["command"], "```"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run aggregation/report tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: PASS for helper, position, aggregation, and report writer tests.

## Task 8: Instrumented Game Loop and CLI

**Files:**
- Modify: `scripts/analyze_threat_defense.py`
- Modify: `tests/test_analyze_threat_defense.py`

- [ ] **Step 1: Add loss tag helper**

Add:

```python
def step_failure_tags(step: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if step["chosen_allowed_direct_loss"]:
        tags.append("allowed_direct_loss")
    if step["low_confidence"]:
        tags.append("low_confidence_loss")
    if step["timed_out"] or step["used_fallback"]:
        tags.append("timeout_or_fallback")
    if step["self_capture"] and float(step.get("score_margin") or 0.0) < 0.08:
        tags.append("bad_self_capture")
    return tags
```

- [ ] **Step 2: Add `analyze_one_game()`**

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
    top_k: int,
) -> dict[str, Any]:
    state = starting_state_for(layout)
    subject_steps: list[dict[str, Any]] = []
    illegal_moves = 0
    crashes = 0
    timeouts = 0

    for turn in range(max_turns):
        winner = state.get_winner()
        if winner is not None:
            return {
                "winner": winner.value,
                "subject_won": winner is subject_player,
                "subject_lost": winner is subject_player.opponent,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "winner",
            }

        active = state.current_player
        ai = subject_ai if active is subject_player else opponent_ai
        dice = dice_rng.randint(1, 6)
        legal = state.legal_moves(active, dice)
        if not legal:
            winner = active.opponent
            return {
                "winner": winner.value,
                "subject_won": winner is subject_player,
                "subject_lost": winner is subject_player.opponent,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "no_move",
            }

        started = time.perf_counter()
        try:
            move = ai.choose_move(state, dice)
        except Exception as exc:  # noqa: BLE001 - audit records crash class.
            crashes += 1
            return {
                "winner": active.opponent.value,
                "subject_won": active.opponent is subject_player,
                "subject_lost": active is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
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
                "subject_lost": active is subject_player,
                "turns": turn,
                "illegal_moves": illegal_moves,
                "crashes": crashes,
                "timeouts": timeouts,
                "subject_steps": subject_steps,
                "termination_reason": "illegal_move",
            }

        if active is subject_player:
            snapshot = state.serialize(include_history=True)
            allowed_direct_loss_dice = opponent_winning_dice_after_move(state, move, dice)
            step = {
                "turn": turn,
                "snapshot": snapshot,
                "dice": dice,
                "move": move.to_dict(),
                "root_stats": list(getattr(ai, "last_root_stats", [])),
                "low_confidence": bool(getattr(ai, "last_low_confidence", False)),
                "timed_out": bool(getattr(ai, "last_timed_out", False)),
                "used_fallback": bool(getattr(ai, "last_used_fallback", False)),
                "score_margin": getattr(ai, "last_score_margin", None),
                "chosen_allowed_direct_loss": bool(allowed_direct_loss_dice),
                "self_capture": is_self_capture(move),
            }
            step["failure_tags"] = step_failure_tags(step)
            subject_steps.append(step)

        state.apply_move(move, dice=dice)

    return {
        "winner": None,
        "subject_won": False,
        "subject_lost": False,
        "turns": max_turns,
        "illegal_moves": illegal_moves,
        "crashes": crashes,
        "timeouts": timeouts,
        "subject_steps": subject_steps,
        "termination_reason": "draw_max_turns",
    }
```

- [ ] **Step 3: Add `analyze_games()`**

Add:

```python
def analyze_games(
    *,
    games: int,
    seed_pool: list[int],
    opponent: str,
    starting_layout: str,
    max_turns: int,
    top_k: int,
    max_examples: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    kwargs = load_release_default_rollout_kwargs()
    summary = {
        "subject_wins": 0,
        "subject_losses": 0,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "draw_max_turns": 0,
        "audited_positions": 0,
    }
    positions: list[dict[str, Any]] = []

    for game_index in range(games):
        subject_player = Player.RED if game_index % 2 == 0 else Player.BLUE
        seed = seed_pool[game_index % len(seed_pool)] + game_index * 9973
        subject_ai = build_ai("rollout", seed=seed, **kwargs)
        opponent_ai = build_ai(opponent, seed=seed ^ 0xA5A5A5)
        result = analyze_one_game(
            subject_player=subject_player,
            subject_ai=subject_ai,
            opponent_ai=opponent_ai,
            dice_rng=random.Random(seed ^ 0xC0FFEE),
            layout=starting_layout,
            max_turns=max_turns,
            top_k=top_k,
        )
        summary["illegal_moves"] += int(result["illegal_moves"])
        summary["crashes"] += int(result["crashes"])
        summary["timeouts"] += int(result["timeouts"])
        if result["subject_won"]:
            summary["subject_wins"] += 1
            continue
        if result["termination_reason"] == "draw_max_turns":
            summary["draw_max_turns"] += 1
        if not result["subject_lost"]:
            continue
        summary["subject_losses"] += 1

        for step in result["subject_steps"]:
            state = starting_state_for(starting_layout)
            from core.game_state import GameState
            from core.move import Move

            state = GameState.deserialize(step["snapshot"])
            chosen = Move.from_dict(step["move"])
            position = audit_position(
                state=state,
                dice=int(step["dice"]),
                chosen=chosen,
                root_stats=step["root_stats"],
                low_confidence=bool(step["low_confidence"]),
                score_margin=step["score_margin"],
                game_index=game_index,
                turn=int(step["turn"]),
                subject_player=subject_player,
                failure_tags=list(step["failure_tags"]),
                top_k=top_k,
            )
            positions.append(position)

    summary["audited_positions"] = len(positions)
    return summary, positions[:max_examples] if max_examples else positions
```

After adding this code, immediately remove the unused `state = starting_state_for(starting_layout)` line inside the step loop if the editor shows it remains unused. The loop must deserialize the saved snapshot before auditing each position.

- [ ] **Step 4: Add parser, seed parser, payload builder, and main**

Add:

```python
def parse_seed_pool(value: str) -> list[int]:
    seeds = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("seed pool must contain at least one integer")
    return seeds


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    summary, positions = analyze_games(
        games=args.games,
        seed_pool=args.seed_pool,
        opponent=args.opponent,
        starting_layout=args.starting_layout,
        max_turns=args.max_turns,
        top_k=args.top_k,
        max_examples=0,
    )
    aggregate = summarize_positions(positions, top_k=args.top_k)
    decision = decide_supports_threat_rerank(aggregate)
    limited_positions = positions[: args.max_examples]
    command = (
        f'& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" '
        f"--games {args.games} --seed-pool {','.join(str(seed) for seed in args.seed_pool)} "
        f"--opponent {args.opponent} --starting-layout {args.starting_layout} "
        f"--max-turns {args.max_turns} --score-margin {args.score_margin} --top-k {args.top_k} "
        f'--max-examples {args.max_examples} --output "{args.output}" --json-output "{args.json_output}"'
    )
    return {
        "subject": {"ai": "rollout", "ai_kwargs_source": "release/v1.0/default_params.json"},
        "opponent": args.opponent,
        "games": args.games,
        "seed_pool": args.seed_pool,
        "default_layout": args.starting_layout,
        "analysis_window": {
            "subject_losses_only": True,
            "subject_to_move_only": True,
            "score_margin": args.score_margin,
            "top_k": args.top_k,
        },
        "summary": summary,
        **aggregate,
        "positions": limited_positions,
        "decision": decision,
        "command": command,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit rollout threat-defense alternatives.")
    parser.add_argument("--games", type=int, default=120)
    parser.add_argument("--seed-pool", type=parse_seed_pool, default=parse_seed_pool("28016,28017,28018"))
    parser.add_argument("--opponent", default="greedy_risk")
    parser.add_argument("--starting-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--score-margin", type=float, default=0.08)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("reports/p8_threat_defense_audit_20260517.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/p8_threat_defense_audit_20260517.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_payload(args)
    write_reports(payload, args.output, args.json_output)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.json_output}")
    print(f"supports_threat_rerank_candidate={payload['decision']['supports_threat_rerank_candidate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Add a CLI smoke test**

Append to `tests/test_analyze_threat_defense.py`:

```python
def test_main_writes_smoke_reports(tmp_path) -> None:
    md_path = tmp_path / "p8_smoke.md"
    json_path = tmp_path / "p8_smoke.json"

    exit_code = analyze_threat_defense.main(
        [
            "--games",
            "2",
            "--seed-pool",
            "28016",
            "--opponent",
            "greedy_risk",
            "--starting-layout",
            "balanced_v1",
            "--max-turns",
            "30",
            "--max-examples",
            "3",
            "--output",
            str(md_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert md_path.exists()
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["subject"]["ai"] == "rollout"
    assert payload["default_layout"] == "balanced_v1"
    assert "decision" in payload
```

- [ ] **Step 6: Run analyzer tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: PASS.

## Task 9: P8.1-P8.3 Full Audit Report

**Files:**
- Generate: `reports/p8_threat_defense_audit_20260517.md`
- Generate: `reports/p8_threat_defense_audit_20260517.json`

- [ ] **Step 1: Run a small manual smoke report**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" `
  --games 6 `
  --seed-pool 28016 `
  --opponent greedy_risk `
  --starting-layout balanced_v1 `
  --max-turns 80 `
  --score-margin 0.08 `
  --top-k 5 `
  --max-examples 5 `
  --output "reports/p8_threat_defense_audit_smoke.md" `
  --json-output "reports/p8_threat_defense_audit_smoke.json"
```

Expected:

```text
Wrote reports/p8_threat_defense_audit_smoke.md
Wrote reports/p8_threat_defense_audit_smoke.json
supports_threat_rerank_candidate=<true or false>
```

- [ ] **Step 2: Inspect smoke JSON shape**

Run:

```powershell
@'
import json
from pathlib import Path

payload = json.loads(Path("reports/p8_threat_defense_audit_smoke.json").read_text(encoding="utf-8"))
for key in ("summary", "threat_defense", "low_confidence", "self_capture_correlation", "score_margin_buckets", "top_k", "decision"):
    assert key in payload, key
assert payload["subject"]["ai"] == "rollout"
assert payload["default_layout"] == "balanced_v1"
print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
print(json.dumps(payload["decision"], ensure_ascii=False, indent=2))
'@ | & ".venv/Scripts/python.exe" -
```

Expected: prints summary and decision JSON without assertion failure.

- [ ] **Step 3: Run the full P8 audit**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" `
  --games 120 `
  --seed-pool 28016,28017,28018 `
  --opponent greedy_risk `
  --starting-layout balanced_v1 `
  --max-turns 200 `
  --score-margin 0.08 `
  --top-k 5 `
  --max-examples 20 `
  --output "reports/p8_threat_defense_audit_20260517.md" `
  --json-output "reports/p8_threat_defense_audit_20260517.json"
```

Expected: script exits 0 and writes both report files.

- [ ] **Step 4: Inspect full audit gate fields**

Run:

```powershell
@'
import json
from pathlib import Path

payload = json.loads(Path("reports/p8_threat_defense_audit_20260517.json").read_text(encoding="utf-8"))
print("summary", json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
print("threat_defense", json.dumps(payload["threat_defense"], ensure_ascii=False, sort_keys=True))
print("low_confidence", json.dumps(payload["low_confidence"], ensure_ascii=False, sort_keys=True))
print("self_capture_correlation", json.dumps(payload["self_capture_correlation"], ensure_ascii=False, sort_keys=True))
print("top_k", json.dumps(payload["top_k"], ensure_ascii=False, sort_keys=True))
print("decision", json.dumps(payload["decision"], ensure_ascii=False, sort_keys=True))
assert payload["summary"]["illegal_moves"] == 0
assert payload["summary"]["crashes"] == 0
assert payload["summary"]["timeouts"] == 0
'@ | & ".venv/Scripts/python.exe" -
```

Expected: prints all required fields and asserts no illegal/crash/timeout in the audit run.

## Task 10: P8.4 Decision Checkpoint

**Files:**
- Read: `reports/p8_threat_defense_audit_20260517.json`
- No edits if gate fails.

- [ ] **Step 1: Read the decision object**

Run:

```powershell
@'
import json
from pathlib import Path

payload = json.loads(Path("reports/p8_threat_defense_audit_20260517.json").read_text(encoding="utf-8"))
decision = payload["decision"]
print(json.dumps(decision, ensure_ascii=False, indent=2))
'@ | & ".venv/Scripts/python.exe" -
```

Expected: decision clearly states whether `rollout_threat_rerank` is supported.

- [ ] **Step 2: Stop candidate work if the gate is false**

If `supports_threat_rerank_candidate` is `false`, do not create `ai/threat_rerank.py` and do not modify `ai/match.py` for P8.4. Record in the final implementation summary:

```text
P8 audit generated. The P8.4 threat rerank candidate was not implemented because the audit gate did not support it: <decision reasons>.
```

- [ ] **Step 3: Continue to Task 11 only if the gate is true**

If `supports_threat_rerank_candidate` is `true`, stop after writing the audit report and implementation summary. Ask the user for explicit approval before continuing to Task 11. Even after approval, the candidate must remain report-only and must not touch GUI/release defaults.

## Task 11: Optional Threat Rerank Tests

**Files:**
- Create: `tests/test_threat_rerank.py`
- Create later: `ai/threat_rerank.py`

- [ ] **Step 1: Add failing wrapper tests**

Create `tests/test_threat_rerank.py`:

```python
from __future__ import annotations

from collections import Counter

from ai.rollout_ai import RootMoveStats
from ai.threat_rerank import ThreatRerankAI
from core.game_state import GameState
from core.types import Player, Position


class FakeBaseAI:
    name = "fake_base"

    def __init__(self, move_index: int, *, low_confidence: bool, score_margin: float | None) -> None:
        self.move_index = move_index
        self.last_low_confidence = low_confidence
        self.last_score_margin = score_margin
        self.last_root_stats = []

    def choose_move(self, state, dice):
        legal = state.legal_moves(state.current_player, dice)
        self.last_root_stats = [
            RootMoveStats(move, visits=8, wins=4, losses=4, draws=0, cutoffs=0, score=1.0 - index * 0.01, winrate=0.5, avg=0.0)
            for index, move in enumerate(legal)
        ]
        return legal[self.move_index]


def make_state() -> GameState:
    return GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(1, 1), 6: Position(4, 4)},
        current_player=Player.RED,
    )


def test_passthrough_when_not_low_confidence() -> None:
    state = make_state()
    base = FakeBaseAI(0, low_confidence=False, score_margin=0.01)
    ai = ThreatRerankAI(base=base)

    move = ai.choose_move(state, 1)

    assert move == state.legal_moves(Player.RED, 1)[0]
    assert ai.fire_counts["threat_rerank_passthrough_not_low_confidence"] == 1


def test_passthrough_when_margin_too_large() -> None:
    state = make_state()
    base = FakeBaseAI(0, low_confidence=True, score_margin=0.20)
    ai = ThreatRerankAI(base=base, threat_rerank_score_margin=0.04)

    move = ai.choose_move(state, 1)

    assert move == state.legal_moves(Player.RED, 1)[0]
    assert ai.fire_counts["threat_rerank_passthrough_margin"] == 1


def test_rerank_selects_lower_threat_top_k_move() -> None:
    state = make_state()
    legal = state.legal_moves(Player.RED, 1)
    chosen_index = next(index for index, move in enumerate(legal) if (move.to_pos.row, move.to_pos.col) == (1, 0))
    base = FakeBaseAI(chosen_index, low_confidence=True, score_margin=0.01)
    ai = ThreatRerankAI(base=base, threat_rerank_top_k=3, threat_rerank_score_margin=0.50)

    move = ai.choose_move(state, 1)

    assert move in legal
    assert move != legal[chosen_index]
    assert ai.fire_counts["threat_rerank_applied"] == 1


def test_fire_counts_is_counter_for_bench_telemetry() -> None:
    ai = ThreatRerankAI(base=FakeBaseAI(0, low_confidence=False, score_margin=0.01))

    assert isinstance(ai.fire_counts, Counter)
```

- [ ] **Step 2: Run wrapper tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py
```

Expected: FAIL because `ai/threat_rerank.py` is not implemented.

## Task 12: Optional Implement ThreatRerankAI

**Files:**
- Create: `ai/threat_rerank.py`

- [ ] **Step 1: Add wrapper implementation**

Create `ai/threat_rerank.py`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from ai.tactical import opponent_winning_dice_set


def _move_identity(move) -> tuple[str, int, int, int, int, int]:
    return (
        move.player.value,
        int(move.piece_id),
        int(move.from_pos.row),
        int(move.from_pos.col),
        int(move.to_pos.row),
        int(move.to_pos.col),
    )


def _winning_dice_after_move(state, move, dice: int) -> set[int]:
    state.apply_move(move, dice=dice)
    try:
        return opponent_winning_dice_set(state, opponent=state.current_player)
    finally:
        state.undo_move()


class ThreatRerankAI:
    name: str

    def __init__(
        self,
        *,
        base,
        name: str = "rollout_threat_rerank",
        threat_rerank_top_k: int = 3,
        threat_rerank_score_margin: float = 0.04,
        threat_rerank_only_low_confidence: bool = True,
        threat_rerank_min_reduction: int = 1,
    ) -> None:
        self.base = base
        self.name = name
        self.threat_rerank_top_k = int(threat_rerank_top_k)
        self.threat_rerank_score_margin = float(threat_rerank_score_margin)
        self.threat_rerank_only_low_confidence = bool(threat_rerank_only_low_confidence)
        self.threat_rerank_min_reduction = int(threat_rerank_min_reduction)
        self.fire_counts: Counter[str] = Counter()

    def choose_move(self, state, dice):
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            return None

        base_move = self.base.choose_move(state, dice)
        if base_move is None:
            return None
        if base_move not in legal:
            return base_move

        if self.threat_rerank_only_low_confidence and not bool(getattr(self.base, "last_low_confidence", False)):
            self.fire_counts["threat_rerank_passthrough_not_low_confidence"] += 1
            return base_move

        score_margin = getattr(self.base, "last_score_margin", None)
        if score_margin is None or float(score_margin) > self.threat_rerank_score_margin:
            self.fire_counts["threat_rerank_passthrough_margin"] += 1
            return base_move

        root_stats = list(getattr(self.base, "last_root_stats", []))
        ranked = sorted(
            root_stats,
            key=lambda item: (
                -float(getattr(item, "score", 0.0)),
                int(item.move.piece_id),
                int(item.move.from_pos.row),
                int(item.move.from_pos.col),
                int(item.move.to_pos.row),
                int(item.move.to_pos.col),
            ),
        )
        top_stats = ranked[: self.threat_rerank_top_k]
        score_by_move = {_move_identity(item.move): float(getattr(item, "score", 0.0)) for item in top_stats}
        chosen_score = score_by_move.get(_move_identity(base_move))
        if chosen_score is None:
            self.fire_counts["threat_rerank_passthrough_no_reduction"] += 1
            return base_move

        self.fire_counts["threat_rerank_considered"] += 1
        base_threat_count = len(_winning_dice_after_move(state, base_move, dice))
        candidates: list[tuple[int, float, int, Any]] = []
        for rank, item in enumerate(top_stats, start=1):
            move = item.move
            if move not in legal or move == base_move:
                continue
            score = float(getattr(item, "score", 0.0))
            if chosen_score - score > self.threat_rerank_score_margin:
                continue
            threat_count = len(_winning_dice_after_move(state, move, dice))
            if base_threat_count - threat_count < self.threat_rerank_min_reduction:
                continue
            candidates.append((threat_count, -score, rank, move))

        if not candidates:
            self.fire_counts["threat_rerank_passthrough_no_reduction"] += 1
            return base_move

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        self.fire_counts["threat_rerank_applied"] += 1
        return candidates[0][3]
```

- [ ] **Step 2: Run wrapper tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py
```

Expected: PASS.

## Task 13: Optional Register rollout_threat_rerank

**Files:**
- Modify: `ai/match.py`
- Modify: `scripts/bench_ai.py`
- Modify or create: `tests/test_ai_match.py` or `tests/test_threat_rerank.py`

- [ ] **Step 1: Add registration test**

Append to `tests/test_threat_rerank.py`:

```python
def test_build_ai_registers_rollout_threat_rerank() -> None:
    from ai.match import ai_version_signature, build_ai

    ai = build_ai("rollout_threat_rerank", seed=123)
    sig = ai_version_signature(ai)

    assert ai.name == "rollout_threat_rerank"
    assert sig["name"] == "rollout_threat_rerank"
    assert sig["base"]["name"] == "rollout"
    assert sig["base"]["rollouts_per_move"] == 32
    assert sig["base"]["cutoff_eval"] == "zweistein"
    assert sig["base"]["deadline_safety_ms"] == 30.0
    assert sig["threat_rerank_top_k"] == 3
    assert sig["threat_rerank_score_margin"] == 0.04
```

- [ ] **Step 2: Run registration test and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py::test_build_ai_registers_rollout_threat_rerank
```

Expected: FAIL because `build_ai()` does not know `rollout_threat_rerank` or signature lacks wrapper fields.

- [ ] **Step 3: Modify `build_ai()`**

In `ai/match.py`, add this branch after `rollout_adaptive_close_sample` and before expectimax branches:

```python
    if kind == "rollout_threat_rerank":
        from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
        from ai.rollout_ai import RolloutAI
        from ai.threat_rerank import ThreatRerankAI

        rerank_keys = {
            "threat_rerank_top_k",
            "threat_rerank_score_margin",
            "threat_rerank_only_low_confidence",
            "threat_rerank_min_reduction",
        }
        rerank_kwargs = {key: ai_kwargs.pop(key) for key in list(ai_kwargs) if key in rerank_keys}
        base = RolloutAI(
            rng=random.Random(seed),
            name="rollout",
            **_merged({**RELEASE_DEFAULT_ROLLOUT_KWARGS}),
        )
        return ThreatRerankAI(base=base, name="rollout_threat_rerank", **rerank_kwargs)
```

This branch must use `RELEASE_DEFAULT_ROLLOUT_KWARGS` as the base. Do not use old flat rollout defaults.

- [ ] **Step 4: Modify `ai_version_signature()`**

In `ai/match.py`, update the wrapper detection block:

```python
    from ai.tactical import TacticalAI
    try:
        from ai.threat_rerank import ThreatRerankAI
    except ImportError:
        ThreatRerankAI = None

    if ThreatRerankAI is not None and isinstance(ai, ThreatRerankAI):
        return {
            "name": ai.name,
            "base": ai_version_signature(ai.base),
            "threat_rerank_top_k": ai.threat_rerank_top_k,
            "threat_rerank_score_margin": ai.threat_rerank_score_margin,
            "threat_rerank_only_low_confidence": ai.threat_rerank_only_low_confidence,
            "threat_rerank_min_reduction": ai.threat_rerank_min_reduction,
        }
```

Keep the existing `TacticalAI` signature behavior after this new block.

- [ ] **Step 5: Register candidate bench profile**

In `scripts/bench_ai.py`, add `rollout_threat_rerank` to `CANDIDATE_PROFILES`:

```python
    "rollout_threat_rerank": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 100,
        },
        "promotion": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 400,
        },
    },
```

The P8 candidate bench must compare against the current release default rollout kwargs, not a naked `build_ai("rollout")`.

- [ ] **Step 6: Run registration and wrapper tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py
```

Expected: PASS.

## Task 14: Optional Candidate Bench for rollout_threat_rerank

**Files:**
- Generate: `reports/p84_candidate_rollout_threat_rerank_20260517.json`
- Generate: `reports/p84_candidate_rollout_threat_rerank_20260517.md`

- [ ] **Step 1: Run focused tests before bench**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py tests/test_analyze_threat_defense.py tests/test_release_consistency.py
```

Expected: PASS.

- [ ] **Step 2: Run candidate bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_threat_rerank `
  --stage candidate `
  --games-per-side 100 `
  --report-name p84_candidate_rollout_threat_rerank_20260517
```

Expected: script writes `reports/p84_candidate_rollout_threat_rerank_20260517.json` and `.md`.
Before trusting the report, inspect the JSON and verify `opponent_kwargs` exactly matches `RELEASE_DEFAULT_ROLLOUT_KWARGS` from `release/v1.0/default_params.json`.

- [ ] **Step 3: Inspect gate result**

Run:

```powershell
@'
import json
from pathlib import Path

payload = json.loads(Path("reports/p84_candidate_rollout_threat_rerank_20260517.json").read_text(encoding="utf-8"))
print(json.dumps(payload.get("gate", payload.get("decision", {})), ensure_ascii=False, indent=2))
print(json.dumps(payload.get("combined", {}), ensure_ascii=False, indent=2))
'@ | & ".venv/Scripts/python.exe" -
```

Expected: report clearly says candidate PASS or FAIL. Even if PASS, do not modify GUI/release defaults in P8.

## Task 15: Optional rollout_safe_timing_profile

**Files:**
- Modify only if P8.5 gate is needed: `ai/match.py`
- Modify only if P8.5 gate is needed: `scripts/bench_ai.py`
- Modify only if P8.5 gate is needed: `tests/test_threat_rerank.py` or `tests/test_ai_match.py`
- Generate only if implemented: `reports/p85_candidate_rollout_safe_timing_profile_20260517.{json,md}`

- [ ] **Step 1: Decide whether P8.5 is needed**

Run:

```powershell
@'
import json
from pathlib import Path

candidate = Path("reports/p84_candidate_rollout_threat_rerank_20260517.json")
if not candidate.exists():
    print("P8.5 not needed: no P8.4 candidate bench report")
else:
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    print(json.dumps(payload, ensure_ascii=False)[:1000])
'@ | & ".venv/Scripts/python.exe" -
```

If P8.4 was not implemented or has no timing concern, skip the rest of Task 15.

- [ ] **Step 2: Add registration test for safe timing profile**

Append to `tests/test_threat_rerank.py`:

```python
def test_build_ai_registers_rollout_safe_timing_profile() -> None:
    from ai.match import ai_version_signature, build_ai

    ai = build_ai("rollout_safe_timing_profile", seed=123)
    sig = ai_version_signature(ai)

    assert ai.name == "rollout_safe_timing_profile"
    assert sig["rollouts_per_move"] == 24
    assert sig["max_step_time_ms"] == 650.0
    assert sig["close_sample_rollouts_per_move"] == 16
    assert sig["deadline_safety_ms"] == 80.0
```

- [ ] **Step 3: Add `build_ai()` branch for safe timing profile**

In `ai/match.py`, add this branch near rollout profiles:

```python
    if kind == "rollout_safe_timing_profile":
        from ai.rollout_ai import RolloutAI

        return RolloutAI(
            rng=rng,
            name="rollout_safe_timing_profile",
            **_merged({
                "rollouts_per_move": 24,
                "max_rollout_turns": 80,
                "max_step_time_ms": 650.0,
                "epsilon": 0.10,
                "close_sample_margin": 0.08,
                "close_sample_rollouts_per_move": 16,
                "low_confidence_margin": 0.08,
                "playout_policy": "greedy_risk",
                "cutoff_eval": "zweistein",
                "deadline_safety_ms": 80.0,
            }),
        )
```

- [ ] **Step 4: Run profile test**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py::test_build_ai_registers_rollout_safe_timing_profile
```

Expected: PASS.

- [ ] **Step 5: Register safe timing candidate bench profile**

In `scripts/bench_ai.py`, add `rollout_safe_timing_profile` to `CANDIDATE_PROFILES`:

```python
    "rollout_safe_timing_profile": {
        "candidate": {
            "opponent": "rollout",
            "opponent_kwargs": RELEASE_DEFAULT_ROLLOUT_KWARGS,
            "starting_layout": "balanced_v1",
            "games_per_side": 100,
        },
    },
```

This keeps the safe timing candidate compared against the current release default rollout kwargs.

- [ ] **Step 6: Run safe timing profile bench**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_safe_timing_profile `
  --stage candidate `
  --games-per-side 100 `
  --report-name p85_candidate_rollout_safe_timing_profile_20260517
```

Expected: report generated. Do not modify GUI/release defaults even if the profile passes.
Before trusting the report, inspect the JSON and verify `opponent_kwargs` exactly matches `RELEASE_DEFAULT_ROLLOUT_KWARGS` from `release/v1.0/default_params.json`.

## Task 16: Documentation Sync After Results

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [ ] **Step 1: Add P8 result to `PROJECT_MEMORY.md`**

Add one dated bullet near the existing P7 entry. Use the actual measured values from `reports/p8_threat_defense_audit_20260517.json`. The text must preserve these facts:

```markdown
- **2026-05-17 P8 threat defense audit 已完成**：新增 `scripts/analyze_threat_defense.py`，对当前 release 默认 `rollout` + P3 参数在 `balanced_v1` 下审计 chosen move 与 alternatives 的 `opponent_winning_dice_set`。审计结果：`audited_positions=<value>`、`chosen_allowed_direct_loss_positions=<value>`、`threat_reducing_alternative_positions=<value>`、`low_confidence.threat_reducing_ratio=<value>`、`self_capture allowed-direct-loss rate=<value>`。报告见 `reports/p8_threat_defense_audit_20260517.md` / `.json`。默认 AI、默认布局、core 规则和 release 配置未变。`rollout_threat_rerank` <implemented-or-not-and-gate-result>；未过门禁不得晋升。
```

Replace angle-bracket fields with actual report values before saving.

- [ ] **Step 2: Add P8 status row to `PROJECT_PHASES.md`**

In section `## 2. 当前状态快照`, add a row after P7:

```markdown
| P8 threat defense audit | 已完成，候选按报告门禁处理 | `scripts/analyze_threat_defense.py` 生成 P8 审计报告，统计 chosen vs alternatives 的 opponent winning dice、low-confidence threat-reducing ratio 与 self-capture 相关性。默认 AI 仍为 `rollout` kind + P3 promotion 显式参数，默认布局仍为 `balanced_v1`，core/release 未变。 |
```

If `rollout_threat_rerank` was implemented, append:

```markdown
`rollout_threat_rerank` 仅作为 benchable candidate 和报告产物存在，不进入 GUI/release 默认。
```

- [ ] **Step 3: Update current-recent-task paragraph if present**

In `PROJECT_PHASES.md` final current-task paragraph, append a concise P8 sentence:

```markdown
P8 threat defense audit 已生成报告；所有 P8 候选只进入 `reports/`，未获用户明确批准前不得进入 GUI/release 默认。
```

Do not alter release default parameter blocks.

## Task 17: Verification

**Files:**
- All modified code/tests/docs.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_analyze_threat_defense.py
```

Expected: PASS.

If P8.4 or P8.5 was implemented, also run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_threat_rerank.py
```

Expected: PASS.

- [ ] **Step 2: Run full pytest**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run smoke test**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

Expected: exits 0.

- [ ] **Step 4: Run S2 rehearsal**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

Expected: all scenarios PASS.

- [ ] **Step 5: Run preflight**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

Expected: final output includes:

```text
READY FOR MATCH
```

- [ ] **Step 6: Check release defaults were not modified**

Run:

```powershell
git diff -- "release/v1.0/default_params.json" "release/v1.0/config.json" "gui/main_window.py" "core"
```

Expected: no diff for release defaults, GUI default recommender, or core rules.

- [ ] **Step 7: Check diff quality**

Run:

```powershell
git diff --check
```

Expected: no output and exit code 0.

## Task 18: Final Implementation Summary Template

Use this structure in the implementation final response:

```text
完成 P8 threat defense audit：
- 新增/更新文件：<files>
- P8 审计报告：reports/p8_threat_defense_audit_20260517.md / .json
- 审计结论：audited_positions=<n>, low_confidence threat_reducing_ratio=<ratio>, supports_threat_rerank_candidate=<true|false>
- P8.4/P8.5 候选状态：<not implemented because gate failed | implemented and bench PASS/FAIL>
- 默认 AI/默认布局/core/release 配置：未变

验证：
- pytest -q: <result>
- scripts/smoke_test.py: <result>
- scripts/s2_rehearsal.py: <result>
- scripts/preflight_check.py: <READY FOR MATCH or failure>
```

Do not claim candidate promotion. Do not say the default AI changed.
