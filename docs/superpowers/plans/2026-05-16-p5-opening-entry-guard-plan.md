# P5 Opening Entry Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make opening search evaluate candidates against the current release default rollout configuration before any larger P5 layout search.

**Architecture:** Keep opening search as a script-level harness. Load `release/v1.0/default_params.json`, strip metadata fields, and use the resulting `kind="rollout"` plus explicit kwargs for both sides of the opening candidate matchup.

**Tech Stack:** Python 3.11, pytest, existing `ai.match.build_ai()` / `play_one_game()` harness.

---

### Task 1: Release Default AI Entry Guard

**Files:**
- Modify: `scripts/search_openings.py`
- Modify: `tests/test_search_openings.py`
- Create: `reports/p5_opening_entry_guard_20260516.md`
- Create: `reports/p5_opening_entry_guard_20260516.json`

- [x] **Step 1: Write failing tests**

Add tests that import `load_release_default_ai_config`, assert it reads rollout kwargs from a JSON file, assert `_run_candidate()` builds both red and blue AI with those kwargs, and assert `_combine_stats()` aggregates `timeouts`.

- [x] **Step 2: Verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" -q
```

Expected before implementation: import or assertion failure because `load_release_default_ai_config` and timeout aggregation do not exist yet.

- [x] **Step 3: Implement minimal script changes**

In `scripts/search_openings.py`, add:

```python
def load_release_default_ai_config(path: str | Path = ROOT / "release" / "v1.0" / "default_params.json") -> tuple[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout' for P5 opening baselines")
    metadata_keys = {"ai", "fallback_ai", "promotion_report"}
    return "rollout", {key: value for key, value in data.items() if key not in metadata_keys}
```

Then update `_run_candidate()` and `_run_against_opponents()` to use this config, pass kwargs to `build_ai()`, and include `result.timeouts` in stats.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/test_search_openings.py" -q
```

Expected: all `test_search_openings.py` tests pass.

- [x] **Step 5: Smoke P5.0 without expanding sample**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --sample-size 5 --games 2 --validation-games 2 --top-k 2 --seed 2026 --output "reports/p5_opening_entry_guard_20260516.md"
```

Expected: Markdown report is generated, stdout JSON identifies the same report path, and report text states that the current release default rollout kwargs were used.

- [x] **Step 6: Synchronize status docs**

Update `PROJECT_MEMORY.md`, `PROJECT_PHASES.md`, and `docs/superpowers/specs/2026-05-15-ai-next-stage-roadmap-design.md` with P5.0 result. Explicitly state no GUI/release default layout changed.
