"""mcts_eval_v1 bench 兼容入口：等价于 ``scripts/bench_ai.py --candidate mcts_eval_v1``。

为不破坏既有复现实验命令（如 ``python scripts/bench_mcts.py --stage promotion``），
本入口保留，自动注入 ``--candidate mcts_eval_v1``，并把 MCTS 特定的旧 flags
（``--time-limit-ms`` / ``--max-iterations``）翻译成 ``--candidate-arg KEY=VALUE`` 透传。

新的候选 AI 工作建议直接使用 ``scripts/bench_ai.py``——参数模型更通用。

依据：docs/superpowers/specs/2026-05-14-tactical-patches-design.md §10.2。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bench_ai import main as bench_ai_main


# 旧 CLI flag → build_ai kwargs key。
_MCTS_KWARG_FLAGS = {
    "--time-limit-ms": "time_limit_ms",
    "--max-iterations": "max_iterations",
}


def _has_candidate_flag(argv: list[str]) -> bool:
    return any(a == "--candidate" or a.startswith("--candidate=") for a in argv)


def _translate(argv: list[str]) -> list[str]:
    """把旧 MCTS-specific flags 翻译成 bench_ai 接受的形式。

    - ``--candidate`` 未显式给出时注入 ``--candidate mcts_eval_v1``。
    - ``--time-limit-ms VALUE`` / ``--time-limit-ms=VALUE`` → ``--candidate-arg time_limit_ms=VALUE``。
    - ``--max-iterations VALUE`` / ``--max-iterations=VALUE`` → ``--candidate-arg max_iterations=VALUE``。
    - 其余 argv 透传。
    """
    out: list[str] = []
    if not _has_candidate_flag(argv):
        out.extend(["--candidate", "mcts_eval_v1"])

    i = 0
    while i < len(argv):
        token = argv[i]

        # `--flag VALUE` 两段式
        if token in _MCTS_KWARG_FLAGS:
            key = _MCTS_KWARG_FLAGS[token]
            if i + 1 >= len(argv):
                raise SystemExit(f"{token} 需要一个值")
            out.extend(["--candidate-arg", f"{key}={argv[i + 1]}"])
            i += 2
            continue

        # `--flag=VALUE` 单段式
        matched = False
        for flag, key in _MCTS_KWARG_FLAGS.items():
            if token.startswith(flag + "="):
                value = token.split("=", 1)[1]
                out.extend(["--candidate-arg", f"{key}={value}"])
                matched = True
                break
        if matched:
            i += 1
            continue

        out.append(token)
        i += 1

    return out


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return bench_ai_main(_translate(list(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
