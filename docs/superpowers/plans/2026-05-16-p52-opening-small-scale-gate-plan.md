# P5.2 Opening Small Scale Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a small-scale expanded opening-layout gate on top of P5.1 strata/seed-pool support without promoting any layout or changing GUI/release defaults.

**Architecture:** Reuse `scripts/search_openings.py` exactly as built in P5.1. Increase candidate breadth from one layout per style to two layouts per style, keep a two-seed pool, write `reports/p52_opening_small_scale_gate_20260516.md/json`, then synchronize status docs with the measured result.

**Tech Stack:** Python 3.11, pytest, existing `scripts/search_openings.py`, current release default `rollout` kwargs from `release/v1.0/default_params.json`.

---

### Task 1: Run P5.2 Small-Scale Gate

**Files:**
- Create: `reports/p52_opening_small_scale_gate_20260516.md`
- Create: `reports/p52_opening_small_scale_gate_20260516.json`

- [x] **Step 1: Confirm CLI supports P5.2 inputs**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --help
```

Expected: help text lists `--candidate-mode`, `--per-style`, `--seed-pool`, and `--json-output`.

- [x] **Step 2: Run expanded smoke gate**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --candidate-mode stratified --per-style 2 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027 --output "reports/p52_opening_small_scale_gate_20260516.md" --json-output "reports/p52_opening_small_scale_gate_20260516.json"
```

Expected: six stratified train candidates, top three validation candidates, current release default `rollout` kwargs recorded, and 0 illegal/crash/timeout required for considering P5.2 harness healthy. This is not a layout-promotion run.

- [x] **Step 3: Validate JSON shape**

Run:

```powershell
& ".venv/Scripts/python.exe" -m json.tool "reports/p52_opening_small_scale_gate_20260516.json"
```

Expected: valid JSON containing `candidate_mode`, `candidate_count`, `seed_pool`, `validation_seed_pool`, `train_rows`, `validation_top`, and `decision`.

### Task 2: Documentation Sync

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`
- Modify: `docs/PROJECT_BRIEF.md`
- Modify: `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md`

- [x] **Step 1: Record P5.2 measured outcome**

Update all four status docs with the exact P5.2 command, train/validation headline result, telemetry, report paths, and explicit decision:

```text
P5.2 only expands the smoke gate. It does not promote or change the default layout.
```

- [x] **Step 2: Preserve default constraints**

Confirm the docs still state that future layout promotion must benchmark against the current release default rollout kwargs and must not use old flat rollout or greedy_risk as the promotion baseline.

### Task 3: Verification

**Files:**
- Read-only verification only.

- [x] **Step 1: Run focused tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" "tests/test_bench_ai.py" -q
```

Expected: all selected tests pass.

- [x] **Step 2: Confirm protected defaults unchanged**

Run:

```powershell
git diff --name-only -- "gui/main_window.py" "gui/opening_panel.py" "release/v1.0/default_params.json" "release/v1.0/config.json"
```

Expected: no output.

- [x] **Step 3: Run full regression and smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
git diff --check
```

Expected: pytest passes, smoke exits normally, and diff check has no whitespace errors other than existing line-ending warnings if reported by Git.

---

## Completion Rule

P5.2 is complete only after the report exists, status docs are synchronized, focused and full verification have fresh passing output, and protected GUI/release default files remain unchanged. No git commit is part of this plan unless the user explicitly asks.
