"""Phase 4.0 + 4.1 验收数据一次性 reproducer。

review #1 + #3 提到：旧 5 份 bench JSON 缺 per-game 明细与可复现命令。本脚本固化所有
重跑命令为单一入口；用同一 master seed=2026 让每次重跑得到字节一致的 bench JSON
（除 generated_at / git_revision 外），覆盖 reports/replays 下的固定名字文件。

固定文件名（不带时间戳，方便 git diff 与重复重跑）：
  reports/bench_phase_4_0_random_vs_random.json
  reports/bench_phase_4_1_baseline_greedy_vs_random.json   (stuck_penalty=0, 复现 0.59)
  reports/bench_phase_4_1_greedy_vs_random.json            (stuck_penalty=100, 当前 0.65)
  reports/bench_phase_4_1_random_vs_greedy.json            (蓝 greedy, 反向 sanity)
  reports/bench_phase_4_1_greedy_vs_greedy.json            (自对弈, 100 局)
  replays/match_phase_4_0_sample_random_vs_random_seed2026.json   (schema v2 replay 范例)

用法：
  python scripts/reproduce_phase_4_1.py                # 全部跑
  python scripts/reproduce_phase_4_1.py --only baseline   # 只重跑 baseline
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# (key, report_name, argv_for_quick_bench)
BENCH_PLAN: list[tuple[str, str, list[str]]] = [
    (
        "phase_4_0",
        "bench_phase_4_0_random_vs_random",
        [
            "--red", "random", "--blue", "random",
            "--games", "100", "--seed", "2026",
            "--starting-layout", "standard_triangle_v1",
        ],
    ),
    (
        "baseline",
        "bench_phase_4_1_baseline_greedy_vs_random",
        [
            "--red", "greedy", "--blue", "random",
            "--games", "200", "--seed", "2026",
            "--red-stuck-penalty", "0",
            "--starting-layout", "standard_triangle_v1",
        ],
    ),
    (
        "production",
        "bench_phase_4_1_greedy_vs_random",
        ["--red", "greedy", "--blue", "random", "--games", "200", "--seed", "2026"],
    ),
    (
        "reverse",
        "bench_phase_4_1_random_vs_greedy",
        ["--red", "random", "--blue", "greedy", "--games", "200", "--seed", "2026"],
    ),
    (
        "self_play",
        "bench_phase_4_1_greedy_vs_greedy",
        ["--red", "greedy", "--blue", "greedy", "--games", "100", "--seed", "2026"],
    ),
]

REPLAY_PLAN: list[tuple[str, str, list[str]]] = [
    (
        "replay",
        "match_phase_4_0_sample_random_vs_random_seed2026",
        ["--red", "random", "--blue", "random", "--seed", "2026"],
    ),
]

CHOICES = ["all", *(k for k, *_ in BENCH_PLAN), *(k for k, *_ in REPLAY_PLAN)]


def _run(script: str, argv: list[str]) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *argv]
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--only",
        choices=CHOICES,
        default="all",
        help="Run only one task (default: all).",
    )
    args = parser.parse_args(argv)

    failures: list[str] = []
    for key, name, base_argv in BENCH_PLAN:
        if args.only != "all" and key != args.only:
            continue
        full_argv = [*base_argv, "--report-name", name]
        print(f"\n=== bench: {key} ({name}) ===", flush=True)
        rc = _run("quick_bench.py", full_argv)
        if rc != 0:
            failures.append(f"bench:{key} (exit {rc})")

    for key, name, base_argv in REPLAY_PLAN:
        if args.only != "all" and key != args.only:
            continue
        full_argv = [*base_argv, "--replay-name", name]
        print(f"\n=== replay: {key} ({name}) ===", flush=True)
        rc = _run("run_match.py", full_argv)
        if rc != 0:
            failures.append(f"replay:{key} (exit {rc})")

    if failures:
        print(f"\n{len(failures)} failures: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nAll reproductions complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
