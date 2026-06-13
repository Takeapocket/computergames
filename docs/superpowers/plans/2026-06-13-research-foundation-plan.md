# Research Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the safe local R-P1 foundation for long-term Einstein chess AI research while preserving release/v1.0 as a historical baseline.

**Architecture:** Keep `core/`, GUI, and release defaults unchanged. Add research-only scripts under `scripts/`, non-versioned large outputs under `data/`, and concise evidence under `reports/`.

**Tech Stack:** Python 3.11, pytest, existing `ai.match` harness, JSON/JSONL; research dependencies declared in `requirements-research.txt`.

---

### Task 1: Replay And Dice Audit Bootstrap

**Files:**
- Create: `scripts/replay_analyze.py`
- Create: `scripts/dice_forensics.py`
- Test: `tests/test_replay_analyze.py`
- Test: `tests/test_dice_forensics.py`

- [x] **Step 1: Write failing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_replay_analyze.py" "tests/test_dice_forensics.py" -q
```

Expected before implementation: import failures for `scripts.replay_analyze` and `scripts.dice_forensics`.

- [x] **Step 2: Implement minimal replay and dice audit APIs**

Implemented:

```text
load_records(paths)
classify_step(state_before, dice, move)
summarize_records(records)
count_dice_by_source(records)
chi_square_uniform(counts)
threat_coincidence_summary(records)
summarize_forensics(records)
```

- [x] **Step 3: Verify tests pass**

Observed:

```text
10 passed
```

### Task 2: Ladder And Perf Bootstrap

**Files:**
- Create: `scripts/ladder.py`
- Create: `scripts/perf_probe.py`
- Test: `tests/test_ladder.py`
- Test: `tests/test_perf_probe.py`

- [x] **Step 1: Write failing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_ladder.py" "tests/test_perf_probe.py" -q
```

Expected before implementation: import failures for `scripts.ladder` and `scripts.perf_probe`.

- [x] **Step 2: Implement minimal ladder and perf APIs**

Implemented:

```text
LadderPlayer
expected_score(rating, opponent_rating)
update_ratings(red_rating, blue_rating, red_score, k_factor)
register_player(player_id, kind, kwargs, rating)
default_anchor_player()
append_jsonl_result(path, row)
run_ladder_games(red, blue, games, seed, output_dir, layout_id, max_turns, k_factor)
run_probe(...)
run_rollout_decision_probe(...)
```

- [x] **Step 3: Verify tests pass**

Observed:

```text
7 passed
```

### Task 3: Research Dependency And Evidence

**Files:**
- Create: `requirements-research.txt`
- Create: `reports/rp1_foundation_bootstrap_20260613.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [x] **Step 1: Add research-only dependency declaration**

`requirements-research.txt` contains `numpy` only. `torch` remains deferred to R-P2B.

- [x] **Step 2: Record implementation evidence**

`reports/rp1_foundation_bootstrap_20260613.md` records scope, execution boundary, and targeted pytest results.

- [x] **Step 3: Sync project status docs**

Update `PROJECT_MEMORY.md` and `PROJECT_PHASES.md` with the R-P1 bootstrap fact once targeted tests and diff review are complete.

- [x] **Step 4: Run full regression**

Observed:

```text
886 passed in 71.78s
```

### Task 4: Next R-P1 Expansion

**Files:**
- Modify: `scripts/perf_probe.py`
- Modify: `scripts/ladder.py`
- Test: targeted tests under `tests/`

- [x] **Step 1: Add micro-instrumentation**

Add explicit counters for clone count, legal move generation count, and GreedyAI/RNG construction count before attempting performance optimization.

Observed:

```text
tests/test_perf_probe.py: 4 passed
```

- [x] **Step 2: Add stronger ladder scheduling**

Add multi-player round-robin scheduling, report markdown output, and uncertainty model once the JSONL baseline is stable.

Implemented:

```text
schedule_round_robin(...)
estimate_rating_uncertainty(...)
run_ladder_round_robin(...)
render_markdown_report(...)
CLI --players / --games-per-pair
```

Observed:

```text
tests/test_ladder.py: 10 passed
tests/test_ladder.py + tests/test_perf_probe.py: 14 passed
R-P1 test group: 24 passed
ladder round-robin CLI smoke OK
```

- [x] **Step 3: Add AI recommendation replay comparison**

Extend `scripts/replay_analyze.py` to compare recorded moves against current P14 recommendations after real records are copied into `records/`.

Implemented:

```text
default_recommender_factory(...)
compare_record_recommendations(...)
summarize_recommendation_comparison(..., include_rows=True)
CLI --compare-recommendations / --include-recommendation-rows / --source
```

Observed:

```text
tests/test_replay_analyze.py: 7 passed
tests/test_replay_analyze.py + tests/test_dice_forensics.py: 10 passed
R-P1 test group: 24 passed
replay recommendation comparison CLI smoke OK
```
