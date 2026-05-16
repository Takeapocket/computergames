# P5.1 Opening Strata Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic opening-candidate strata and seed-pool reporting so P5 can expand samples without mixing layout styles or single-seed noise.

**Architecture:** Keep all P5.1 behavior inside `scripts/search_openings.py`. Add pure helper functions for layout style classification, stratified candidate selection, seed-pool parsing, and multi-seed aggregation; then thread them through the CLI/report path without changing GUI or release defaults.

**Tech Stack:** Python 3.11, pytest, existing `ai.match.build_ai()` / `play_one_game()` harness.

---

### Task 1: Candidate Style Helpers

**Files:**
- Modify: `scripts/search_openings.py`
- Modify: `tests/test_search_openings.py`

- [x] **Step 1: Write failing tests**

Add tests:

```python
def test_classify_layout_style_labels_aggressive_balanced_defensive():
    aggressive = {
        1: Position(1, 1),
        2: Position(2, 0),
        3: Position(1, 0),
        4: Position(0, 2),
        5: Position(0, 1),
        6: Position(0, 0),
    }
    defensive = {
        1: Position(0, 0),
        2: Position(0, 1),
        3: Position(0, 2),
        4: Position(1, 0),
        5: Position(1, 1),
        6: Position(2, 0),
    }
    balanced = {
        1: Position(0, 0),
        2: Position(1, 1),
        3: Position(0, 1),
        4: Position(1, 0),
        5: Position(0, 2),
        6: Position(2, 0),
    }

    assert classify_layout_style(aggressive) == "aggressive"
    assert classify_layout_style(defensive) == "defensive"
    assert classify_layout_style(balanced) == "balanced"
```

```python
def test_generate_stratified_layouts_returns_per_style_limit():
    rows = generate_stratified_layouts(per_style=2, seed=2026)

    assert len(rows) == 6
    assert [style for style, _ in rows].count("aggressive") == 2
    assert [style for style, _ in rows].count("balanced") == 2
    assert [style for style, _ in rows].count("defensive") == 2
```

- [x] **Step 2: Verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" -q
```

Expected: import failure for `classify_layout_style` / `generate_stratified_layouts`.

- [x] **Step 3: Implement helpers**

Add `classify_layout_style()` using average Manhattan distance to red target `(4,4)`:

```text
avg <= 5.0 -> aggressive
avg >= 6.0 -> defensive
otherwise -> balanced
```

Add `generate_stratified_layouts(per_style, seed)` returning `(style, layout)` rows in stable style order.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" -q
```

Expected: all tests pass.

### Task 2: Seed Pool Reporting

**Files:**
- Modify: `scripts/search_openings.py`
- Modify: `tests/test_search_openings.py`
- Create: `reports/p51_opening_strata_seed_smoke_20260516.md`
- Create: `reports/p51_opening_strata_seed_smoke_20260516.json`

- [x] **Step 1: Write failing tests**

Add tests for `parse_seed_pool("2026,2027") == [2026, 2027]` and for `_run_against_seed_pool()` aggregating stats across seeds while preserving `seed_count`.

- [x] **Step 2: Verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" -q
```

Expected: missing helper failure.

- [x] **Step 3: Implement seed-pool path**

Add CLI args:

```text
--candidate-mode sample|stratified
--per-style
--seed-pool
--json-output
```

Use `seed_pool` for train and `seed + 10000` for validation inside each seed pool entry. Report `candidate_mode`, `per_style`, `seed_pool`, `style`, `seed_count`, and full release default kwargs source.

- [x] **Step 4: Smoke without expansion**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --candidate-mode stratified --per-style 1 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027 --output "reports/p51_opening_strata_seed_smoke_20260516.md" --json-output "reports/p51_opening_strata_seed_smoke_20260516.json"
```

Expected: small report only; no GUI/release default layout changes.

### Task 3: Documentation Sync

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`
- Modify: `docs/PROJECT_BRIEF.md`
- Modify: `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md`

- [x] **Step 1: Update status**

Record P5.1 as “candidate strata and seed pool smoke complete, no promotion.”

- [x] **Step 2: Final verification**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
git diff --check
```
