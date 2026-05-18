# Opening Light Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, deterministic, resumable opening-layout screening script that compares 20-40 curated candidates against `balanced_v1` with current release default rollout kwargs.

**Architecture:** Add a standalone script under `scripts/` with small pure helpers for candidate generation, release config loading, run-limit validation, aggregation, resume IO, markdown formatting, and CLI orchestration. Tests monkeypatch game execution so most coverage is fast and deterministic; only the final smoke runs real games at `4 candidates * 2 sides * 1 game`.

**Tech Stack:** Python 3.11, stdlib `argparse/json/random/itertools/dataclasses/pathlib`, existing `ai.match`, `ai.opening_layouts`, `core.game_state`, `core.types`, pytest.

---

## Scope And Constraints

This plan implements the approved spec in `docs/superpowers/specs/2026-05-18-opening-light-screen-design.md`.

Do not modify these files or semantics:

- `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`
- `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`
- `release/v1.0/default_params.json`
- `release/v1.0/config.json`
- core rule semantics
- GUI default layout

Do not run large samples. The only real-game run in this plan is:

```powershell
& ".venv/Scripts/python.exe" scripts/screen_openings_light.py --max-candidates 4 --games-per-side 1 --output reports/opening_light_screen_smoke.json --summary reports/opening_light_screen_smoke.md
```

Do not commit or push. The user explicitly prohibited commit/push for this task, so this plan uses verification checkpoints instead of git commit steps.

## File Structure

- Create `scripts/screen_openings_light.py`
  - Owns CLI, candidate generation, release AI config loading, game execution, aggregation, resume JSON, atomic writes, dry-run output, and markdown summary.
  - Imports existing project APIs after inserting repo root into `sys.path`, matching current script patterns.
- Create `tests/test_screen_openings_light.py`
  - Fast unit tests for deterministic candidate generation, validation, mirror layout, release config loading, run-limit guard, aggregation, resume skip, dry-run, and summary writing.
  - Uses monkeypatch fake `play_one_game` for orchestration tests.
- Generate during smoke only:
  - `reports/opening_light_screen_smoke.json`
  - `reports/opening_light_screen_smoke.md`

## Task 1: Candidate Generation

**Files:**
- Create: `scripts/screen_openings_light.py`
- Create: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing tests for candidate generation**

Add these tests to `tests/test_screen_openings_light.py`:

```python
from __future__ import annotations

from ai.opening_layouts import mirror_layout, validate_layout

from scripts import screen_openings_light as sol


def _layout_key(candidate: sol.OpeningCandidate) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (piece_id, candidate.red_layout[piece_id].row, candidate.red_layout[piece_id].col)
        for piece_id in sorted(candidate.red_layout)
    )


def test_generate_candidates_is_deterministic() -> None:
    first = sol.generate_candidates(mode="curated", max_candidates=12, seed=2026)
    second = sol.generate_candidates(mode="curated", max_candidates=12, seed=2026)

    assert [candidate.candidate_id for candidate in first] == [candidate.candidate_id for candidate in second]
    assert [_layout_key(candidate) for candidate in first] == [_layout_key(candidate) for candidate in second]


def test_generate_candidates_respects_max_candidates() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=8, seed=2026)

    assert len(candidates) == 8
    assert candidates[0].candidate_id == "curated_000"
    assert candidates[-1].candidate_id == "curated_007"


def test_generate_candidates_are_valid_and_blue_is_mirror() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=20, seed=2026)

    assert candidates
    for candidate in candidates:
        assert validate_layout(candidate.red_layout, candidate.blue_layout) == []
        assert candidate.blue_layout == mirror_layout(candidate.red_layout)


def test_generate_candidates_has_unique_ids_and_layouts() -> None:
    candidates = sol.generate_candidates(mode="curated", max_candidates=32, seed=2026)

    ids = [candidate.candidate_id for candidate in candidates]
    layouts = [_layout_key(candidate) for candidate in candidates]
    assert len(ids) == len(set(ids))
    assert len(layouts) == len(set(layouts))


def test_full_mode_can_be_limited_without_running_all_games() -> None:
    candidates = sol.generate_candidates(mode="full", max_candidates=5, seed=2026)

    assert [candidate.candidate_id for candidate in candidates] == [
        "full_000",
        "full_001",
        "full_002",
        "full_003",
        "full_004",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: collection/import fails because `scripts/screen_openings_light.py` does not exist.

- [ ] **Step 3: Implement candidate generation helpers**

Create `scripts/screen_openings_light.py` with this initial content:

```python
"""Lightweight resumable opening-layout screening.

This script compares small curated opening candidates against the current
release default layout. It never modifies GUI/release defaults.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, play_one_game
from ai.opening_layouts import PRESETS, RED_ZONE, mirror_layout, validate_layout
from core.game_state import GameState
from core.types import Player, Position

Mode = Literal["curated", "full"]
LAYOUT_JSON = dict[str, list[int]]
METADATA_KEYS = {"ai", "fallback_ai", "promotion_report"}
MAX_DEFAULT_PLANNED_GAMES = 160
SCHEMA_VERSION = 1
DEFAULT_OUTPUT = ROOT / "reports" / "opening_light_screen.json"
DEFAULT_SUMMARY = ROOT / "reports" / "opening_light_screen.md"


@dataclass(frozen=True)
class OpeningCandidate:
    candidate_id: str
    source: str
    red_layout: dict[int, Position]
    blue_layout: dict[int, Position]


@dataclass(frozen=True)
class GameSeeds:
    role: str
    game_index: int
    base_seed: int
    dice_seed: int
    red_seed: int
    blue_seed: int


def sorted_red_zone() -> list[Position]:
    return sorted(RED_ZONE, key=lambda pos: (pos.row + pos.col, pos.row, pos.col))


def layout_signature(layout: Mapping[int, Position]) -> tuple[tuple[int, int, int], ...]:
    return tuple((int(piece_id), pos.row, pos.col) for piece_id, pos in sorted(layout.items()))


def copy_layout(layout: Mapping[int, Position]) -> dict[int, Position]:
    return {int(piece_id): pos for piece_id, pos in layout.items()}


def layout_from_order(positions: list[Position], piece_order: list[int]) -> dict[int, Position]:
    return {piece_id: positions[index] for index, piece_id in enumerate(piece_order)}


def swapped_layout(base: Mapping[int, Position], first: int, second: int) -> dict[int, Position]:
    layout = copy_layout(base)
    layout[first], layout[second] = layout[second], layout[first]
    return layout


def reversed_layout(base: Mapping[int, Position]) -> dict[int, Position]:
    positions = [base[piece_id] for piece_id in sorted(base)]
    return {piece_id: position for piece_id, position in zip(sorted(base), reversed(positions))}


def all_permutation_layouts() -> list[dict[int, Position]]:
    positions = sorted_red_zone()
    return [
        {piece_id: position for piece_id, position in zip(range(1, 7), perm)}
        for perm in itertools.permutations(positions, 6)
    ]


def curated_layout_sources(seed: int) -> list[tuple[str, dict[int, Position]]]:
    home = sorted_red_zone()
    forward = sorted(home, key=lambda pos: (-(pos.row + pos.col), pos.row, pos.col))
    center = sorted(home, key=lambda pos: (abs(pos.row - 1) + abs(pos.col - 1), pos.row, pos.col))
    balanced = PRESETS["balanced_v1"].red
    sources: list[tuple[str, dict[int, Position]]] = [
        ("preset:balanced_v1", copy_layout(PRESETS["balanced_v1"].red)),
        ("preset:aggressive_v1", copy_layout(PRESETS["aggressive_v1"].red)),
        ("preset:defensive_v1", copy_layout(PRESETS["defensive_v1"].red)),
        ("heuristic:low_ids_forward", layout_from_order(forward, [1, 2, 3, 4, 5, 6])),
        ("heuristic:high_ids_forward", layout_from_order(forward, [6, 5, 4, 3, 2, 1])),
        ("heuristic:low_ids_center", layout_from_order(center, [1, 2, 3, 4, 5, 6])),
        ("heuristic:high_ids_center", layout_from_order(center, [6, 5, 4, 3, 2, 1])),
        ("swap:balanced_1_6", swapped_layout(balanced, 1, 6)),
        ("swap:balanced_2_5", swapped_layout(balanced, 2, 5)),
        ("swap:balanced_3_4", swapped_layout(balanced, 3, 4)),
        ("heuristic:balanced_reverse", reversed_layout(balanced)),
    ]
    shuffled = all_permutation_layouts()
    random.Random(seed).shuffle(shuffled)
    sources.extend((f"shuffle:{index:03d}", layout) for index, layout in enumerate(shuffled))
    return sources


def generate_candidates(*, mode: Mode, max_candidates: int, seed: int) -> list[OpeningCandidate]:
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    if mode == "curated":
        sources = curated_layout_sources(seed)
    elif mode == "full":
        sources = [(f"full:{index:03d}", layout) for index, layout in enumerate(all_permutation_layouts())]
    else:
        raise ValueError("mode must be 'curated' or 'full'")

    candidates: list[OpeningCandidate] = []
    seen: set[tuple[tuple[int, int, int], ...]] = set()
    for source, red_layout in sources:
        signature = layout_signature(red_layout)
        if signature in seen:
            continue
        blue_layout = mirror_layout(red_layout)
        errors = validate_layout(red_layout, blue_layout)
        if errors:
            continue
        seen.add(signature)
        candidate_id = f"{mode}_{len(candidates):03d}"
        candidates.append(
            OpeningCandidate(
                candidate_id=candidate_id,
                source=source,
                red_layout=copy_layout(red_layout),
                blue_layout=copy_layout(blue_layout),
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: Task 1 tests pass. Later tests do not exist yet.

## Task 2: Release Config Loading And Run Limits

**Files:**
- Modify: `scripts/screen_openings_light.py`
- Modify: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing tests for release kwargs and run limits**

Append to `tests/test_screen_openings_light.py`:

```python
import json

import pytest


def test_load_release_default_ai_config_strips_metadata(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(
        json.dumps(
            {
                "ai": "rollout",
                "rollouts_per_move": 32,
                "fallback_ai": "greedy_risk",
                "promotion_report": "reports/ai_promotion_decision.md",
            }
        ),
        encoding="utf-8",
    )

    kind, kwargs = sol.load_release_default_ai_config(path)

    assert kind == "rollout"
    assert kwargs == {"rollouts_per_move": 32}


def test_load_release_default_ai_config_rejects_non_rollout(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(json.dumps({"ai": "greedy_risk"}), encoding="utf-8")

    with pytest.raises(ValueError, match="must use ai='rollout'"):
        sol.load_release_default_ai_config(path)


def test_validate_run_limits_rejects_large_non_dry_run() -> None:
    with pytest.raises(ValueError, match="planned games"):
        sol.validate_run_limits(candidate_count=81, games_per_side=1, dry_run=False)


def test_validate_run_limits_allows_large_dry_run() -> None:
    sol.validate_run_limits(candidate_count=720, games_per_side=1, dry_run=True)


def test_validate_run_limits_rejects_invalid_games_per_side() -> None:
    with pytest.raises(ValueError, match="games_per_side"):
        sol.validate_run_limits(candidate_count=4, games_per_side=0, dry_run=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: failures for missing `load_release_default_ai_config()` and `validate_run_limits()`.

- [ ] **Step 3: Implement config loading and run-limit guard**

Append these functions to `scripts/screen_openings_light.py`:

```python
def load_release_default_ai_config(
    path: str | Path = ROOT / "release" / "v1.0" / "default_params.json",
) -> tuple[str, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")
    return "rollout", {key: value for key, value in data.items() if key not in METADATA_KEYS}


def validate_run_limits(*, candidate_count: int, games_per_side: int, dry_run: bool) -> None:
    if games_per_side < 1:
        raise ValueError("games_per_side must be >= 1")
    if games_per_side > 500:
        raise ValueError("games_per_side must be <= 500 to keep deterministic seed ranges isolated")
    planned_games = candidate_count * games_per_side * 2
    if not dry_run and planned_games > MAX_DEFAULT_PLANNED_GAMES:
        raise ValueError(
            f"planned games ({planned_games}) exceeds safety limit {MAX_DEFAULT_PLANNED_GAMES}; "
            "reduce --max-candidates or --games-per-side"
        )
```

- [ ] **Step 4: Run tests to verify Task 2 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all current tests pass.

## Task 3: Aggregation And Game Execution

**Files:**
- Modify: `scripts/screen_openings_light.py`
- Modify: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing aggregation and seed tests**

Append to `tests/test_screen_openings_light.py`:

```python
from dataclasses import dataclass

from core.types import Player


@dataclass
class FakeResult:
    winner: Player | None
    turns: int
    illegal_moves: int = 0
    crashes: int = 0
    timeouts: int = 0
    step_times_ms: list[float] | None = None


def test_make_game_seeds_uses_role_offset() -> None:
    red_seed = sol.make_game_seeds(master_seed=2026, candidate_index=3, role="candidate_as_red", local_game_index=1, games_per_side=2)
    blue_seed = sol.make_game_seeds(master_seed=2026, candidate_index=3, role="candidate_as_blue", local_game_index=0, games_per_side=2)

    assert red_seed.base_seed == 2026 * 100000 + 3 * 1000 + 1
    assert blue_seed.base_seed == 2026 * 100000 + 3 * 1000 + 2
    assert red_seed.dice_seed == red_seed.base_seed * 3
    assert blue_seed.red_seed == blue_seed.base_seed * 3 + 1
    assert blue_seed.blue_seed == blue_seed.base_seed * 3 + 2


def test_aggregate_candidate_results_calculates_combined_fields() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]
    red_results = [
        (FakeResult(Player.RED, 10, step_times_ms=[1.0, 3.0]), sol.GameSeeds("candidate_as_red", 0, 1, 3, 4, 5)),
        (FakeResult(Player.BLUE, 12, illegal_moves=1, step_times_ms=[5.0]), sol.GameSeeds("candidate_as_red", 1, 2, 6, 7, 8)),
    ]
    blue_results = [
        (FakeResult(Player.BLUE, 14, crashes=1, timeouts=1, step_times_ms=[2.0, 10.0]), sol.GameSeeds("candidate_as_blue", 0, 3, 9, 10, 11)),
        (FakeResult(None, 20, step_times_ms=[]), sol.GameSeeds("candidate_as_blue", 1, 4, 12, 13, 14)),
    ]

    result = sol.aggregate_candidate_result(
        candidate=candidate,
        games_per_side=2,
        red_results=red_results,
        blue_results=blue_results,
    )

    assert result["candidate_wins_as_red"] == 1
    assert result["candidate_wins_as_blue"] == 1
    assert result["combined_candidate_wins"] == 2
    assert result["combined_games"] == 4
    assert result["combined_win_rate"] == 0.5
    assert result["illegal_moves"] == 1
    assert result["crashes"] == 1
    assert result["timeouts"] == 1
    assert result["average_turns"] == 14.0
    assert result["average_step_time_ms"] == 4.2
    assert result["max_step_time_ms"] == 10.0
    assert len(result["seeds_used"]) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: failures for missing `make_game_seeds()` and `aggregate_candidate_result()`.

- [ ] **Step 3: Implement seed, serialization, aggregation, and game helpers**

Append to `scripts/screen_openings_light.py`:

```python
def make_game_seeds(
    *,
    master_seed: int,
    candidate_index: int,
    role: Literal["candidate_as_red", "candidate_as_blue"],
    local_game_index: int,
    games_per_side: int,
) -> GameSeeds:
    side_game_index = local_game_index if role == "candidate_as_red" else games_per_side + local_game_index
    base_seed = master_seed * 100_000 + candidate_index * 1_000 + side_game_index
    return GameSeeds(
        role=role,
        game_index=local_game_index,
        base_seed=base_seed,
        dice_seed=base_seed * 3,
        red_seed=base_seed * 3 + 1,
        blue_seed=base_seed * 3 + 2,
    )


def layout_to_json(layout: Mapping[int, Position]) -> LAYOUT_JSON:
    return {str(piece_id): [pos.row, pos.col] for piece_id, pos in sorted(layout.items())}


def layout_from_json(data: Mapping[str, list[int]]) -> dict[int, Position]:
    return {int(piece_id): Position(int(pos[0]), int(pos[1])) for piece_id, pos in data.items()}


def seeds_to_json(seeds: GameSeeds) -> dict[str, int | str]:
    return {
        "role": seeds.role,
        "game_index": seeds.game_index,
        "base_seed": seeds.base_seed,
        "dice_seed": seeds.dice_seed,
        "red_seed": seeds.red_seed,
        "blue_seed": seeds.blue_seed,
    }


def role_stats(results: list[tuple[Any, GameSeeds]], candidate_player: Player) -> dict[str, Any]:
    games = len(results)
    wins = sum(1 for result, _ in results if result.winner is candidate_player)
    turns = [int(result.turns) for result, _ in results]
    step_times = [
        float(step_time)
        for result, _ in results
        for step_time in (result.step_times_ms or [])
    ]
    return {
        "wins": wins,
        "games": games,
        "illegal_moves": sum(int(result.illegal_moves) for result, _ in results),
        "crashes": sum(int(result.crashes) for result, _ in results),
        "timeouts": sum(int(getattr(result, "timeouts", 0)) for result, _ in results),
        "average_turns": (sum(turns) / games) if games else 0.0,
        "average_step_time_ms": (sum(step_times) / len(step_times)) if step_times else 0.0,
        "max_step_time_ms": max(step_times) if step_times else 0.0,
        "total_step_time_ms": sum(step_times),
        "step_time_count": len(step_times),
    }


def aggregate_candidate_result(
    *,
    candidate: OpeningCandidate,
    games_per_side: int,
    red_results: list[tuple[Any, GameSeeds]],
    blue_results: list[tuple[Any, GameSeeds]],
) -> dict[str, Any]:
    red_stats = role_stats(red_results, Player.RED)
    blue_stats = role_stats(blue_results, Player.BLUE)
    combined_games = red_stats["games"] + blue_stats["games"]
    combined_wins = red_stats["wins"] + blue_stats["wins"]
    all_turns = [int(result.turns) for result, _ in [*red_results, *blue_results]]
    total_step_time = red_stats["total_step_time_ms"] + blue_stats["total_step_time_ms"]
    step_count = red_stats["step_time_count"] + blue_stats["step_time_count"]
    seeds_used = [seeds_to_json(seeds) for _, seeds in [*red_results, *blue_results]]
    return {
        "candidate_id": candidate.candidate_id,
        "source": candidate.source,
        "red_layout": layout_to_json(candidate.red_layout),
        "blue_layout": layout_to_json(candidate.blue_layout),
        "games_per_side": games_per_side,
        "candidate_wins_as_red": red_stats["wins"],
        "candidate_wins_as_blue": blue_stats["wins"],
        "combined_candidate_wins": combined_wins,
        "combined_games": combined_games,
        "combined_win_rate": (combined_wins / combined_games) if combined_games else 0.0,
        "illegal_moves": red_stats["illegal_moves"] + blue_stats["illegal_moves"],
        "crashes": red_stats["crashes"] + blue_stats["crashes"],
        "timeouts": red_stats["timeouts"] + blue_stats["timeouts"],
        "average_turns": (sum(all_turns) / combined_games) if combined_games else 0.0,
        "average_step_time_ms": (total_step_time / step_count) if step_count else 0.0,
        "max_step_time_ms": max(red_stats["max_step_time_ms"], blue_stats["max_step_time_ms"]),
        "seeds_used": seeds_used,
        "candidate_as_red": {key: value for key, value in red_stats.items() if key not in {"total_step_time_ms", "step_time_count"}},
        "candidate_as_blue": {key: value for key, value in blue_stats.items() if key not in {"total_step_time_ms", "step_time_count"}},
    }


def run_one_direction(
    *,
    red_layout: dict[int, Position],
    blue_layout: dict[int, Position],
    role: Literal["candidate_as_red", "candidate_as_blue"],
    candidate_index: int,
    games_per_side: int,
    master_seed: int,
    max_turns: int,
    ai_kind: str,
    ai_kwargs: dict[str, Any],
) -> list[tuple[Any, GameSeeds]]:
    results: list[tuple[Any, GameSeeds]] = []
    for local_game_index in range(games_per_side):
        seeds = make_game_seeds(
            master_seed=master_seed,
            candidate_index=candidate_index,
            role=role,
            local_game_index=local_game_index,
            games_per_side=games_per_side,
        )
        red_ai = build_ai(ai_kind, seed=seeds.red_seed, **ai_kwargs)
        blue_ai = build_ai(ai_kind, seed=seeds.blue_seed, **ai_kwargs)
        dice_rng = random.Random(seeds.dice_seed)
        state = GameState.from_layout(red=red_layout, blue=blue_layout, current_player=Player.RED)
        result = play_one_game(
            red_ai=red_ai,
            blue_ai=blue_ai,
            dice_rng=dice_rng,
            max_turns=max_turns,
            starting_state=state,
        )
        results.append((result, seeds))
    return results


def run_candidate(
    *,
    candidate: OpeningCandidate,
    candidate_index: int,
    baseline_red: dict[int, Position],
    baseline_blue: dict[int, Position],
    games_per_side: int,
    master_seed: int,
    max_turns: int,
    ai_kind: str,
    ai_kwargs: dict[str, Any],
) -> dict[str, Any]:
    red_results = run_one_direction(
        red_layout=candidate.red_layout,
        blue_layout=baseline_blue,
        role="candidate_as_red",
        candidate_index=candidate_index,
        games_per_side=games_per_side,
        master_seed=master_seed,
        max_turns=max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    blue_results = run_one_direction(
        red_layout=baseline_red,
        blue_layout=candidate.blue_layout,
        role="candidate_as_blue",
        candidate_index=candidate_index,
        games_per_side=games_per_side,
        master_seed=master_seed,
        max_turns=max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    return aggregate_candidate_result(
        candidate=candidate,
        games_per_side=games_per_side,
        red_results=red_results,
        blue_results=blue_results,
    )
```

- [ ] **Step 4: Run tests to verify Task 3 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all current tests pass.

## Task 4: Resume JSON And Atomic Persistence

**Files:**
- Modify: `scripts/screen_openings_light.py`
- Modify: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing resume tests**

Append to `tests/test_screen_openings_light.py`:

```python
def test_is_result_complete_requires_matching_layout_and_game_count() -> None:
    candidate = sol.generate_candidates(mode="curated", max_candidates=1, seed=2026)[0]
    result = {
        "candidate_id": candidate.candidate_id,
        "red_layout": sol.layout_to_json(candidate.red_layout),
        "combined_games": 4,
    }

    assert sol.is_result_complete(result, candidate, expected_games=4) is True
    assert sol.is_result_complete({**result, "combined_games": 2}, candidate, expected_games=4) is False
    assert sol.is_result_complete({**result, "red_layout": {"1": [9, 9]}}, candidate, expected_games=4) is False


def test_load_resume_state_rejects_incompatible_parameters(tmp_path) -> None:
    output = tmp_path / "screen.json"
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps({**payload, "seed": 9999}), encoding="utf-8")

    with pytest.raises(ValueError, match="incompatible resume output"):
        sol.load_resume_payload(
            output,
            expected=payload,
            no_resume=False,
        )


def test_load_resume_state_allows_larger_current_max_candidates(tmp_path) -> None:
    output = tmp_path / "screen.json"
    old_payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=4,
        candidate_count=4,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    output.write_text(json.dumps(old_payload), encoding="utf-8")
    current_payload = {**old_payload, "max_candidates": 8, "candidate_count": 8}

    loaded = sol.load_resume_payload(output, expected=current_payload, no_resume=False)

    assert loaded["max_candidates"] == 4
    assert loaded["results"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: missing resume/payload helper failures.

- [ ] **Step 3: Implement payload, resume, and atomic write helpers**

Append to `scripts/screen_openings_light.py`:

```python
def utc_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_run_payload(
    *,
    argv: list[str],
    mode: Mode,
    max_candidates: int,
    candidate_count: int,
    games_per_side: int,
    seed: int,
    baseline_layout: str,
    max_turns: int,
    ai_kind: str,
    ai_kwargs: dict[str, Any],
) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "updated_at": now,
        "argv": argv,
        "mode": mode,
        "max_candidates": max_candidates,
        "candidate_count": candidate_count,
        "games_per_side": games_per_side,
        "seed": seed,
        "baseline_layout": baseline_layout,
        "max_turns": max_turns,
        "ai_kind": ai_kind,
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "ai_kwargs": ai_kwargs,
        "results": [],
    }


def is_result_complete(result: Mapping[str, Any], candidate: OpeningCandidate, *, expected_games: int) -> bool:
    return (
        result.get("candidate_id") == candidate.candidate_id
        and result.get("combined_games") == expected_games
        and result.get("red_layout") == layout_to_json(candidate.red_layout)
    )


def validate_resume_compatible(existing: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    strict_keys = ("mode", "seed", "baseline_layout", "games_per_side", "max_turns", "ai_kind", "ai_kwargs")
    for key in strict_keys:
        if existing.get(key) != expected.get(key):
            raise ValueError(f"incompatible resume output: {key} differs; use --no-resume or a different --output")
    if int(existing.get("max_candidates", 0)) > int(expected.get("max_candidates", 0)):
        raise ValueError("incompatible resume output: existing max_candidates is larger than current run")


def load_resume_payload(path: str | Path, *, expected: dict[str, Any], no_resume: bool) -> dict[str, Any]:
    output = Path(path)
    if no_resume or not output.exists():
        return expected
    existing = json.loads(output.read_text(encoding="utf-8"))
    validate_resume_compatible(existing, expected)
    return existing


def atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
```

- [ ] **Step 4: Run tests to verify Task 4 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all current tests pass.

## Task 5: Dry-run CLI

**Files:**
- Modify: `scripts/screen_openings_light.py`
- Modify: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing dry-run test**

Append to `tests/test_screen_openings_light.py`:

```python
def test_dry_run_does_not_call_play_one_game_or_write_outputs(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "out.json"
    summary = tmp_path / "out.md"

    def fail_play_one_game(**kwargs):
        raise AssertionError("dry-run must not call play_one_game")

    monkeypatch.setattr(sol, "play_one_game", fail_play_one_game)

    exit_code = sol.main(
        [
            "--dry-run",
            "--max-candidates",
            "4",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "candidate_count: 4" in captured.out
    assert "curated_000" in captured.out
    assert not output.exists()
    assert not summary.exists()
```

- [ ] **Step 2: Run tests to verify it fails**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py::test_dry_run_does_not_call_play_one_game_or_write_outputs -v
```

Expected: failure for missing `main()`.

- [ ] **Step 3: Implement argparse and dry-run flow**

Append to `scripts/screen_openings_light.py`:

```python
def format_layout_label(layout: Mapping[int, Position]) -> str:
    return "/".join(f"{piece_id}:{layout[piece_id].row}{layout[piece_id].col}" for piece_id in sorted(layout))


def print_dry_run(*, mode: Mode, baseline_layout: str, candidates: list[OpeningCandidate], preview_count: int = 8) -> None:
    print(f"mode: {mode}")
    print(f"candidate_count: {len(candidates)}")
    print(f"baseline_layout: {baseline_layout}")
    for candidate in candidates[:preview_count]:
        print(
            f"{candidate.candidate_id} source={candidate.source} "
            f"red={format_layout_label(candidate.red_layout)} "
            f"blue={format_layout_label(candidate.blue_layout)}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight resumable opening layout screening.")
    parser.add_argument("--mode", choices=("curated", "full"), default="curated")
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--games-per-side", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--baseline-layout", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(raw_argv)
    candidates = generate_candidates(mode=args.mode, max_candidates=args.max_candidates, seed=args.seed)
    validate_run_limits(candidate_count=len(candidates), games_per_side=args.games_per_side, dry_run=args.dry_run)
    if args.baseline_layout not in PRESETS:
        raise ValueError(f"unknown baseline layout {args.baseline_layout!r}; expected one of {sorted(PRESETS)}")
    if args.dry_run:
        print_dry_run(mode=args.mode, baseline_layout=args.baseline_layout, candidates=candidates)
        return 0
    raise NotImplementedError("non-dry-run orchestration is implemented in Task 6")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify Task 5 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all current tests pass.

## Task 6: Non-dry-run Orchestration And Markdown Summary

**Files:**
- Modify: `scripts/screen_openings_light.py`
- Modify: `tests/test_screen_openings_light.py`

- [ ] **Step 1: Write failing orchestration and summary tests**

Append to `tests/test_screen_openings_light.py`:

```python
def test_run_screening_resumes_completed_candidate_and_writes_summary(tmp_path, monkeypatch) -> None:
    output = tmp_path / "screen.json"
    summary = tmp_path / "screen.md"
    candidates = sol.generate_candidates(mode="curated", max_candidates=2, seed=2026)
    existing_result = {
        "candidate_id": candidates[0].candidate_id,
        "source": candidates[0].source,
        "red_layout": sol.layout_to_json(candidates[0].red_layout),
        "blue_layout": sol.layout_to_json(candidates[0].blue_layout),
        "games_per_side": 1,
        "candidate_wins_as_red": 1,
        "candidate_wins_as_blue": 0,
        "combined_candidate_wins": 1,
        "combined_games": 2,
        "combined_win_rate": 0.5,
        "illegal_moves": 0,
        "crashes": 0,
        "timeouts": 0,
        "average_turns": 10.0,
        "average_step_time_ms": 1.0,
        "max_step_time_ms": 2.0,
        "seeds_used": [],
        "candidate_as_red": {},
        "candidate_as_blue": {},
    }
    payload = sol.new_run_payload(
        argv=[],
        mode="curated",
        max_candidates=2,
        candidate_count=2,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    payload["results"] = [existing_result]
    output.write_text(json.dumps(payload), encoding="utf-8")
    calls: list[str] = []

    def fake_run_candidate(**kwargs):
        candidate = kwargs["candidate"]
        calls.append(candidate.candidate_id)
        return {
            **existing_result,
            "candidate_id": candidate.candidate_id,
            "source": candidate.source,
            "red_layout": sol.layout_to_json(candidate.red_layout),
            "blue_layout": sol.layout_to_json(candidate.blue_layout),
            "combined_candidate_wins": 2,
            "combined_games": 2,
            "combined_win_rate": 1.0,
        }

    monkeypatch.setattr(sol, "run_candidate", fake_run_candidate)
    monkeypatch.setattr(sol, "load_release_default_ai_config", lambda: ("rollout", {"rollouts_per_move": 32}))

    exit_code = sol.main(
        [
            "--max-candidates",
            "2",
            "--games-per-side",
            "1",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    assert exit_code == 0
    assert calls == ["curated_001"]
    written = json.loads(output.read_text(encoding="utf-8"))
    assert len(written["results"]) == 2
    assert summary.exists()
    assert "这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。" in summary.read_text(encoding="utf-8")


def test_write_summary_sorts_top_candidates(tmp_path) -> None:
    summary = tmp_path / "summary.md"
    payload = sol.new_run_payload(
        argv=["--max-candidates", "2"],
        mode="curated",
        max_candidates=2,
        candidate_count=2,
        games_per_side=1,
        seed=2026,
        baseline_layout="balanced_v1",
        max_turns=200,
        ai_kind="rollout",
        ai_kwargs={"rollouts_per_move": 32},
    )
    payload["results"] = [
        {
            "candidate_id": "curated_000",
            "red_layout": {"1": [0, 0]},
            "combined_win_rate": 0.25,
            "combined_candidate_wins": 1,
            "combined_games": 4,
            "candidate_wins_as_red": 1,
            "candidate_wins_as_blue": 0,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_turns": 10.0,
            "average_step_time_ms": 1.0,
            "max_step_time_ms": 2.0,
        },
        {
            "candidate_id": "curated_001",
            "red_layout": {"1": [1, 1]},
            "combined_win_rate": 0.75,
            "combined_candidate_wins": 3,
            "combined_games": 4,
            "candidate_wins_as_red": 1,
            "candidate_wins_as_blue": 2,
            "illegal_moves": 0,
            "crashes": 0,
            "timeouts": 0,
            "average_turns": 12.0,
            "average_step_time_ms": 1.5,
            "max_step_time_ms": 3.0,
        },
    ]

    sol.write_summary(summary, payload)

    text = summary.read_text(encoding="utf-8")
    assert text.index("curated_001") < text.index("curated_000")
    assert "| rank | candidate_id | win_rate | wins/games |" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: failures for missing `write_summary()` and non-dry-run `NotImplementedError`.

- [ ] **Step 3: Implement summary and orchestration**

Replace the `raise NotImplementedError(...)` branch in `main()` and append helper functions:

```python
def json_layout_label(raw_layout: Mapping[str, list[int]]) -> str:
    return "/".join(f"{piece_id}:{pos[0]}{pos[1]}" for piece_id, pos in sorted(raw_layout.items(), key=lambda item: int(item[0])))


def write_summary(path: str | Path, payload: Mapping[str, Any]) -> None:
    results = sorted(
        payload.get("results", []),
        key=lambda row: float(row.get("combined_win_rate", 0.0)),
        reverse=True,
    )
    total_illegal = sum(int(row.get("illegal_moves", 0)) for row in results)
    total_crashes = sum(int(row.get("crashes", 0)) for row in results)
    total_timeouts = sum(int(row.get("timeouts", 0)) for row in results)
    lines = [
        "# Opening Light Screen Summary",
        "",
        f"generated_at: {payload.get('generated_at', '')}",
        f"updated_at: {payload.get('updated_at', '')}",
        f"argv: {json.dumps(payload.get('argv', []), ensure_ascii=False)}",
        f"mode: {payload.get('mode')}",
        f"candidate_count: {payload.get('candidate_count')}",
        f"games_per_side: {payload.get('games_per_side')}",
        f"seed: {payload.get('seed')}",
        f"baseline_layout: {payload.get('baseline_layout')}",
        f"max_turns: {payload.get('max_turns')}",
        f"ai_kind: {payload.get('ai_kind')}",
        "ai_kwargs_source: release/v1.0/default_params.json",
        f"ai_kwargs: {json.dumps(payload.get('ai_kwargs', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。",
        "",
        f"stability_totals: illegal_moves={total_illegal}, crashes={total_crashes}, timeouts={total_timeouts}",
        "",
        "## Top Candidates",
        "",
        "| rank | candidate_id | win_rate | wins/games | as_red | as_blue | illegal | crashes | timeouts | avg_turns | avg_step_ms | max_step_ms | red_layout |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(results[:10], start=1):
        games = int(row.get("combined_games", 0))
        wins = int(row.get("combined_candidate_wins", 0))
        lines.append(
            f"| {rank} | {row.get('candidate_id', '')} | {100.0 * float(row.get('combined_win_rate', 0.0)):.1f}% "
            f"| {wins}/{games} | {row.get('candidate_wins_as_red', 0)} | {row.get('candidate_wins_as_blue', 0)} "
            f"| {row.get('illegal_moves', 0)} | {row.get('crashes', 0)} | {row.get('timeouts', 0)} "
            f"| {float(row.get('average_turns', 0.0)):.1f} | {float(row.get('average_step_time_ms', 0.0)):.1f} "
            f"| {float(row.get('max_step_time_ms', 0.0)):.1f} | {json_layout_label(row.get('red_layout', {}))} |"
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def result_by_id(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("candidate_id")): dict(row) for row in payload.get("results", [])}
```

Update `main()` non-dry-run branch to:

```python
    ai_kind, ai_kwargs = load_release_default_ai_config()
    expected_payload = new_run_payload(
        argv=raw_argv,
        mode=args.mode,
        max_candidates=args.max_candidates,
        candidate_count=len(candidates),
        games_per_side=args.games_per_side,
        seed=args.seed,
        baseline_layout=args.baseline_layout,
        max_turns=args.max_turns,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    payload = load_resume_payload(args.output, expected=expected_payload, no_resume=args.no_resume)
    existing = result_by_id(payload)
    baseline = PRESETS[args.baseline_layout]
    baseline_red = copy_layout(baseline.red)
    baseline_blue = copy_layout(baseline.blue)
    results: list[dict[str, Any]] = list(payload.get("results", []))

    for candidate_index, candidate in enumerate(candidates):
        previous = existing.get(candidate.candidate_id)
        if previous is not None and is_result_complete(previous, candidate, expected_games=args.games_per_side * 2):
            continue
        result = run_candidate(
            candidate=candidate,
            candidate_index=candidate_index,
            baseline_red=baseline_red,
            baseline_blue=baseline_blue,
            games_per_side=args.games_per_side,
            master_seed=args.seed,
            max_turns=args.max_turns,
            ai_kind=ai_kind,
            ai_kwargs=ai_kwargs,
        )
        results = [row for row in results if row.get("candidate_id") != candidate.candidate_id]
        results.append(result)
        payload = {
            **expected_payload,
            "generated_at": payload.get("generated_at", expected_payload["generated_at"]),
            "updated_at": utc_now(),
            "results": results,
        }
        atomic_write_json(args.output, payload)
        existing[candidate.candidate_id] = result

    payload = {
        **expected_payload,
        "generated_at": payload.get("generated_at", expected_payload["generated_at"]),
        "updated_at": utc_now(),
        "results": results,
    }
    atomic_write_json(args.output, payload)
    write_summary(args.summary, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run tests to verify Task 6 passes**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all tests pass.

## Task 7: Verification Smoke

**Files:**
- Generated: `reports/opening_light_screen_smoke.json`
- Generated: `reports/opening_light_screen_smoke.md`
- Read-only check: protected files listed in scope constraints

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
```

Expected: all `tests/test_screen_openings_light.py` tests pass.

- [ ] **Step 2: Run dry-run smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" scripts/screen_openings_light.py --dry-run --max-candidates 8
```

Expected:

- Exit code 0.
- Output includes `candidate_count: 8`.
- Output includes `curated_000`.
- No `reports/opening_light_screen.json` is created by this dry-run unless it existed before.

- [ ] **Step 3: Run real lightweight smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" scripts/screen_openings_light.py --max-candidates 4 --games-per-side 1 --output reports/opening_light_screen_smoke.json --summary reports/opening_light_screen_smoke.md
```

Expected:

- Exit code 0.
- JSON contains `candidate_count: 4`.
- JSON contains exactly 4 `results`.
- Each result has `combined_games: 2`.
- Markdown contains `这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。`

- [ ] **Step 4: Inspect generated smoke files**

Run:

```powershell
& ".venv/Scripts/python.exe" -c "import json; from pathlib import Path; p=json.loads(Path('reports/opening_light_screen_smoke.json').read_text(encoding='utf-8')); assert p['candidate_count']==4; assert len(p['results'])==4; assert all(r['combined_games']==2 for r in p['results']); print({'candidate_count': p['candidate_count'], 'results': len(p['results']), 'illegal_moves': sum(r['illegal_moves'] for r in p['results']), 'crashes': sum(r['crashes'] for r in p['results']), 'timeouts': sum(r['timeouts'] for r in p['results'])})"
```

Expected: prints aggregate counts and raises no assertion.

- [ ] **Step 5: Confirm protected files were not changed**

Run:

```powershell
git diff -- gui/main_window.py release/v1.0/default_params.json release/v1.0/config.json core
```

Expected: no diff output.

Run:

```powershell
git status --short
```

Expected: only these intentional files are new or modified for this task:

- `docs/superpowers/specs/2026-05-18-opening-light-screen-design.md`
- `docs/superpowers/plans/2026-05-18-opening-light-screen-plan.md`
- `scripts/screen_openings_light.py`
- `tests/test_screen_openings_light.py`
- `reports/opening_light_screen_smoke.json`
- `reports/opening_light_screen_smoke.md`

Existing unrelated user changes, if any, must be left untouched.

## Self-Review Checklist

- Spec coverage:
  - Candidate generation deterministic, limited, valid, mirrored, and de-duplicated: Task 1.
  - Release default rollout kwargs loading and metadata stripping: Task 2.
  - Run-size safety guard: Task 2.
  - Red/blue double-sided game execution with deterministic seeds: Task 3.
  - Required result fields and aggregation: Task 3.
  - Per-candidate JSON persistence and resume: Task 4 and Task 6.
  - Dry-run without games or output writes: Task 5.
  - Markdown top 10 summary and small-sample disclaimer: Task 6.
  - Required smoke commands and protected-file checks: Task 7.
- Placeholder scan:
  - No `TBD`, `TODO`, "implement later", or vague "add tests" steps.
  - Each task has concrete tests, implementation snippets, commands, and expected outcomes.
- Type consistency:
  - `OpeningCandidate`, `GameSeeds`, `layout_to_json()`, `make_game_seeds()`, `aggregate_candidate_result()`, `run_candidate()`, and `write_summary()` names are consistent across tests and implementation steps.
  - Result JSON field names match the approved spec.
- Project constraints:
  - No commit/push steps included.
  - No protected GUI/release/core changes included.
  - No large benchmark command included.
