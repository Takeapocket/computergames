# P6.4 Timing Budget Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit git commits/branches unless the user explicitly asks, so checkpoint steps use tests and diff review instead of commits.

**Goal:** Add a report-only timing probe for the current release default rollout recommender on a deterministic sample set.

**Architecture:** The script reads `release/v1.0/default_params.json`, builds the current default `rollout`, samples reachable positions from `balanced_v1`, times one recommendation per sample, and writes JSON plus Markdown reports. It does not change GUI defaults, release configs, or AI parameters.

**Tech Stack:** Python 3.11, argparse, json, pathlib, random, time, existing `ai.match.build_ai`, existing `ai.match.starting_state_for`, existing `scripts.quick_bench._percentile`.

---

## File Structure

- Create: `scripts/timing_budget_probe.py`
  - CLI entrypoint and report generation.
  - Helper functions for release default loading, percentile summary, sample collection, and report writing.
- Create: `tests/test_timing_budget_probe.py`
  - Unit tests for summary calculation, release config parsing, and report file writing.
- Write when running manually: `reports/p6_timing_budget_probe_YYYYMMDD.json`
- Write when running manually: `reports/p6_timing_budget_probe_YYYYMMDD.md`

## Task 1: Unit Tests for Probe Helpers

**Files:**
- Create: `tests/test_timing_budget_probe.py`
- Create later: `scripts/timing_budget_probe.py`

- [ ] **Step 1: Add failing helper tests**

Create `tests/test_timing_budget_probe.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts import timing_budget_probe


def test_summarize_timings_computes_percentiles() -> None:
    summary = timing_budget_probe.summarize_timings([10.0, 20.0, 30.0, 40.0])

    assert summary["avg_ms"] == 25.0
    assert summary["p50_ms"] == 25.0
    assert summary["max_ms"] == 40.0


def test_load_release_default_ai_config_strips_metadata(tmp_path) -> None:
    path = tmp_path / "default_params.json"
    path.write_text(
        json.dumps(
            {
                "ai": "rollout",
                "rollouts_per_move": 32,
                "max_rollout_turns": 80,
                "fallback_ai": "greedy_risk",
                "promotion_report": "reports/ai_promotion_decision.md",
            }
        ),
        encoding="utf-8",
    )

    kind, kwargs = timing_budget_probe.load_release_default_ai_config(path)

    assert kind == "rollout"
    assert kwargs == {"rollouts_per_move": 32, "max_rollout_turns": 80}


def test_write_reports_writes_json_and_markdown(tmp_path) -> None:
    payload = {
        "ai_kind": "rollout",
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "default_layout": "balanced_v1",
        "sample_count": 1,
        "avg_ms": 10.0,
        "p50_ms": 10.0,
        "p95_ms": 10.0,
        "p99_ms": 10.0,
        "max_ms": 10.0,
        "rollout_timed_out_count": 0,
        "rollout_used_fallback_count": 0,
        "illegal_recommendations": 0,
        "exceptions": 0,
        "samples": [],
        "command": "python scripts/timing_budget_probe.py --samples 1",
    }

    md_path = tmp_path / "probe.md"
    json_path = tmp_path / "probe.json"
    timing_budget_probe.write_reports(payload, md_path, json_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["sample_count"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "P6 Timing Budget Probe" in markdown
    assert "默认 AI、默认布局、release 配置未变" in markdown
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_timing_budget_probe.py
```

Expected: FAIL because `scripts/timing_budget_probe.py` does not exist.

## Task 2: Implement Timing Probe Script

**Files:**
- Create: `scripts/timing_budget_probe.py`

- [ ] **Step 1: Create the script with helper functions**

Create `scripts/timing_budget_probe.py` with these top-level functions:

```python
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import build_ai, starting_state_for


DEFAULT_OUTPUT = ROOT / "reports" / "p6_timing_budget_probe.md"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "p6_timing_budget_probe.json"


def load_release_default_ai_config(
    path: str | Path = ROOT / "release" / "v1.0" / "default_params.json",
) -> tuple[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")
    metadata_keys = {"ai", "fallback_ai", "promotion_report"}
    return "rollout", {key: value for key, value in data.items() if key not in metadata_keys}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_timings(values: list[float]) -> dict[str, float]:
    return {
        "avg_ms": mean(values) if values else 0.0,
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "max_ms": max(values) if values else 0.0,
    }
```

- [ ] **Step 2: Add sample collection and report writers**

Add these functions below `summarize_timings()`:

```python
def _sample_board_key(state) -> str:
    return repr(state.serialize(include_history=False))


def collect_samples(*, samples: int, seed: int, layout: str, ai_kind: str, ai_kwargs: dict) -> dict:
    rng = random.Random(seed)
    state = starting_state_for(layout)
    ai = build_ai(ai_kind, seed=seed, **ai_kwargs)
    timings: list[float] = []
    sample_rows: list[dict] = []
    illegal_recommendations = 0
    exceptions = 0
    timed_out_count = 0
    used_fallback_count = 0

    while len(sample_rows) < samples:
        if state.get_winner() is not None:
            state = starting_state_for(layout)
        dice = rng.randint(1, 6)
        legal = state.legal_moves(state.current_player, dice)
        if not legal:
            state = starting_state_for(layout)
            continue

        start = time.perf_counter()
        try:
            move = ai.choose_move(state, dice)
        except Exception as exc:  # noqa: BLE001 - probe records exceptions
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            timings.append(elapsed_ms)
            exceptions += 1
            sample_rows.append(
                {
                    "index": len(sample_rows),
                    "player": state.current_player.value,
                    "dice": dice,
                    "legal_moves": len(legal),
                    "elapsed_ms": elapsed_ms,
                    "exception": type(exc).__name__,
                    "board": _sample_board_key(state),
                }
            )
            state.apply_move(rng.choice(legal), dice=dice)
            continue

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        timings.append(elapsed_ms)
        if getattr(ai, "last_timed_out", False):
            timed_out_count += 1
        if getattr(ai, "last_used_fallback", False):
            used_fallback_count += 1
        if move not in legal:
            illegal_recommendations += 1

        sample_rows.append(
            {
                "index": len(sample_rows),
                "player": state.current_player.value,
                "dice": dice,
                "legal_moves": len(legal),
                "elapsed_ms": elapsed_ms,
                "timed_out": bool(getattr(ai, "last_timed_out", False)),
                "used_fallback": bool(getattr(ai, "last_used_fallback", False)),
                "illegal": move not in legal,
                "board": _sample_board_key(state),
            }
        )
        state.apply_move(move if move in legal else rng.choice(legal), dice=dice)

    summary = summarize_timings(timings)
    return {
        **summary,
        "sample_count": samples,
        "rollout_timed_out_count": timed_out_count,
        "rollout_used_fallback_count": used_fallback_count,
        "illegal_recommendations": illegal_recommendations,
        "exceptions": exceptions,
        "samples": sample_rows,
    }


def write_reports(payload: dict, output: Path, json_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = [
        "# P6 Timing Budget Probe",
        "",
        "默认 AI、默认布局、release 配置未变。",
        "",
        f"- ai_kind: `{payload['ai_kind']}`",
        f"- default_layout: `{payload['default_layout']}`",
        f"- sample_count: `{payload['sample_count']}`",
        f"- avg_ms: `{payload['avg_ms']:.2f}`",
        f"- p50_ms: `{payload['p50_ms']:.2f}`",
        f"- p95_ms: `{payload['p95_ms']:.2f}`",
        f"- p99_ms: `{payload['p99_ms']:.2f}`",
        f"- max_ms: `{payload['max_ms']:.2f}`",
        f"- rollout_timed_out_count: `{payload['rollout_timed_out_count']}`",
        f"- rollout_used_fallback_count: `{payload['rollout_used_fallback_count']}`",
        f"- illegal_recommendations: `{payload['illegal_recommendations']}`",
        f"- exceptions: `{payload['exceptions']}`",
        "",
        "## Reproduce",
        "",
        "```powershell",
        payload["command"],
        "```",
    ]
    output.write_text("\n".join(markdown) + "\n", encoding="utf-8")
```

- [ ] **Step 3: Add CLI entrypoint**

Add:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe release default rollout timing budget.")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=26016)
    parser.add_argument("--layout", default="balanced_v1")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ai_kind, ai_kwargs = load_release_default_ai_config()
    result = collect_samples(
        samples=args.samples,
        seed=args.seed,
        layout=args.layout,
        ai_kind=ai_kind,
        ai_kwargs=ai_kwargs,
    )
    command = (
        f'& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" '
        f'--samples {args.samples} --seed {args.seed} --layout {args.layout} '
        f'--output "{args.output}" --json-output "{args.json_output}"'
    )
    payload = {
        "ai_kind": ai_kind,
        "ai_kwargs_source": "release/v1.0/default_params.json",
        "default_layout": args.layout,
        **result,
        "command": command,
    }
    write_reports(payload, args.output, args.json_output)
    print(f"wrote {args.output}")
    print(f"wrote {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run helper tests and verify GREEN**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_timing_budget_probe.py
```

Expected: PASS.

## Task 3: Script Smoke and Report Generation

**Files:**
- Verify: `scripts/timing_budget_probe.py`
- Generate: `reports/p6_timing_budget_probe_20260516.md`
- Generate: `reports/p6_timing_budget_probe_20260516.json`

- [ ] **Step 1: Run a small script smoke**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 3 --seed 26016 --output "reports/p6_timing_budget_probe_smoke.md" --json-output "reports/p6_timing_budget_probe_smoke.json"
```

Expected: exit code 0 and both smoke files written.

- [ ] **Step 2: Run the full P6.4 probe**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" --samples 120 --seed 26016 --output "reports/p6_timing_budget_probe_20260516.md" --json-output "reports/p6_timing_budget_probe_20260516.json"
```

Expected: exit code 0 and both P6.4 report files written.

- [ ] **Step 3: Inspect JSON thresholds**

Run:

```powershell
& ".venv/Scripts/python.exe" -c "import json; p=json.load(open('reports/p6_timing_budget_probe_20260516.json', encoding='utf-8')); print(p['illegal_recommendations'], p['exceptions'], p['p99_ms'], p['max_ms'])"
```

Expected:

```text
0 0 <p99_ms> <max_ms>
```

If `p99_ms > 1000.0` or `max_ms > 5000.0`, mark the Markdown report as "赛前关注" before moving to P7.2.

## Task 4: P6.4 Verification

**Files:**
- Verify: `scripts/timing_budget_probe.py`
- Verify: `tests/test_timing_budget_probe.py`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_timing_budget_probe.py
```

Expected: PASS.

- [ ] **Step 2: Run preflight**

Run:

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

Expected: output ends with `READY FOR MATCH`.

## Self-Review

- Spec coverage: Covers P6.4 timing probe, JSON fields, Markdown report, and threshold inspection.
- Placeholder scan: No placeholder tokens or omitted code blocks.
- Boundary check: The script is report-only and does not write release defaults.
