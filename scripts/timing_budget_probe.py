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
        except Exception as exc:  # noqa: BLE001 - probe records exceptions.
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
        timed_out = bool(getattr(ai, "last_timed_out", False))
        used_fallback = bool(getattr(ai, "last_used_fallback", False))
        if timed_out:
            timed_out_count += 1
        if used_fallback:
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
                "timed_out": timed_out,
                "used_fallback": used_fallback,
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
    ]
    flagged = [
        sample
        for sample in payload.get("samples", [])
        if sample.get("timed_out")
        or sample.get("used_fallback")
        or sample.get("illegal")
        or sample.get("exception")
    ]
    if flagged:
        markdown.extend(["## Flagged Samples", ""])
        for sample in flagged[:20]:
            markdown.append(
                "- "
                f"index={sample.get('index')} "
                f"player={sample.get('player')} "
                f"dice={sample.get('dice')} "
                f"elapsed_ms={float(sample.get('elapsed_ms', 0.0)):.2f} "
                f"timeout={bool(sample.get('timed_out', False))} "
                f"fallback={bool(sample.get('used_fallback', False))} "
                f"illegal={bool(sample.get('illegal', False))} "
                f"exception={sample.get('exception', '')}"
            )
        markdown.append("")
    markdown.extend(
        [
            "## Reproduce",
            "",
            "```powershell",
            payload["command"],
            "```",
        ]
    )
    output.write_text("\n".join(markdown) + "\n", encoding="utf-8")


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
        f"--samples {args.samples} --seed {args.seed} --layout {args.layout} "
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
    hard_failures = []
    if payload["exceptions"] > 0:
        hard_failures.append(f"exceptions={payload['exceptions']}")
    if payload["illegal_recommendations"] > 0:
        hard_failures.append(f"illegal_recommendations={payload['illegal_recommendations']}")
    if hard_failures:
        print(f"[FAIL] timing gate: {', '.join(hard_failures)}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
