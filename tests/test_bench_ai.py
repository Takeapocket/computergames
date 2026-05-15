"""scripts/bench_ai.py 泛化框架 + scripts/bench_mcts.py 兼容入口的单测。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.types import Player
from scripts import bench_ai, bench_mcts


# -------- _resolve_profile / _resolve_gates --------

def test_resolve_profile_returns_defaults_for_known_candidate_stage():
    profile = bench_ai._resolve_profile("rollout_tactical", "candidate")

    assert profile["opponent"] == "rollout"
    assert profile["games_per_side"] == 400


def test_resolve_profile_returns_empty_dict_for_unknown_candidate():
    assert bench_ai._resolve_profile("unknown_candidate", "smoke") == {}


def test_resolve_profile_returns_empty_dict_for_unknown_stage_of_known_candidate():
    """rollout_tactical 不定义 promotion stage（设计 §10.3 跳过）→ 空 profile。"""
    assert bench_ai._resolve_profile("rollout_tactical", "promotion") == {}


def test_resolve_gates_for_mcts_promotion_matches_stage_gates():
    gates = bench_ai._resolve_gates("mcts_eval_v1", "promotion")

    assert gates == bench_ai.STAGE_GATES["promotion"]
    assert gates["candidate_win_ci_lower"] == ("ge", 0.52)


def test_resolve_gates_for_rollout_tactical_candidate_merges_extra_gate():
    """rollout_tactical candidate 把 Wilson 下界门禁合并进基础 candidate 门禁。"""
    gates = bench_ai._resolve_gates("rollout_tactical", "candidate")

    assert gates["candidate_win_rate"] == ("ge", 0.55)
    assert gates["candidate_win_ci_lower"] == ("ge", 0.52)
    assert gates["max_step_time_ms"] == ("le", 5000.0)


def test_resolve_gates_smoke_unchanged_for_rollout_tactical():
    """smoke 阶段不引入额外 Wilson 门禁。"""
    gates = bench_ai._resolve_gates("rollout_tactical", "smoke")

    assert gates == bench_ai.STAGE_GATES["smoke"]
    assert "candidate_win_ci_lower" not in gates


def test_resolve_gates_does_not_mutate_stage_gates():
    """合并 extra_gates 时不能污染 STAGE_GATES 模块级常量。"""
    before = {k: dict(v) for k, v in bench_ai.STAGE_GATES.items()}

    bench_ai._resolve_gates("rollout_tactical", "candidate")
    bench_ai._resolve_gates("mcts_eval_v1", "promotion")

    assert {k: dict(v) for k, v in bench_ai.STAGE_GATES.items()} == before


# -------- _aggregate / _combine 的遥测选用 --------

class _R:
    """轻量替身：模拟 play_one_game 返回的 MatchResult 字段子集。"""

    def __init__(self, winner, *, turns=10, step_times=None):
        self.winner = winner
        self.turns = turns
        self.illegal_moves = 0
        self.crashes = 0
        self.step_times_ms = list(step_times or [3.0, 4.0])


def test_aggregate_omits_telemetry_when_ai_does_not_expose_it():
    results = [
        (_R(Player.RED), {}),
        (_R(Player.BLUE), {}),
    ]

    summary = bench_ai._aggregate(results, candidate_side=Player.RED)

    assert summary["candidate_wins"] == 1
    assert summary["candidate_win_rate"] == 0.5
    assert "avg_iterations" not in summary
    assert "max_depth" not in summary


def test_aggregate_includes_telemetry_when_present():
    results = [
        (_R(Player.RED), {"iterations": 100, "max_depth": 5}),
        (_R(Player.RED), {"iterations": 200, "max_depth": 7}),
    ]

    summary = bench_ai._aggregate(results, candidate_side=Player.RED)

    assert summary["avg_iterations"] == 150.0
    assert summary["max_depth"] == 7


def test_combine_skips_telemetry_when_neither_side_has_it():
    red = bench_ai._aggregate([(_R(Player.RED), {})], candidate_side=Player.RED)
    blue = bench_ai._aggregate([(_R(Player.RED), {})], candidate_side=Player.BLUE)

    combined = bench_ai._combine(red, blue)

    assert "avg_iterations" not in combined
    assert "max_depth" not in combined
    assert combined["games"] == 2


# -------- _candidate_telemetry --------

class _FakeMcts:
    last_iterations = 123
    last_max_depth = 9


class _FakePlain:
    pass


def test_candidate_telemetry_pulls_attrs_when_available():
    out = bench_ai._candidate_telemetry(_FakeMcts())

    assert out == {"iterations": 123, "max_depth": 9}


class _FakeTactical:
    """模拟 TacticalAI 的最小接口：暴露 fire_counts(Counter[str])。"""

    def __init__(self, counts):
        from collections import Counter
        self.fire_counts = Counter(counts)


def test_candidate_telemetry_pulls_fire_counts_from_tactical_ai():
    """_candidate_telemetry 必须把 TacticalAI.fire_counts 映射成 fire_<label> 条目。"""
    ai = _FakeTactical({"direct_win": 2, "no_threat_passthrough": 5})

    out = bench_ai._candidate_telemetry(ai)

    assert out == {"fire_direct_win": 2, "fire_no_threat_passthrough": 5}


def test_candidate_telemetry_skips_fire_counts_when_attr_missing():
    """没有 fire_counts 的 AI（如 MCTS / 纯 rollout）不应出现 fire_* 条目。"""
    out = bench_ai._candidate_telemetry(_FakeMcts())

    assert all(not k.startswith("fire_") for k in out)


def test_aggregate_sums_fire_counts_across_games():
    """每局给一份 fire_<label> 计数，_aggregate 把它们累加到 summary。

    没有出现过的 label 不应被新增；这是诊断失败候选时区分各分支贡献的核心信号。
    """
    results = [
        (_R(Player.RED), {"fire_direct_win": 1, "fire_no_threat_passthrough": 3}),
        (_R(Player.RED), {"fire_direct_win": 2, "fire_partial_neutralize_passthrough": 1}),
    ]

    summary = bench_ai._aggregate(results, candidate_side=Player.RED)

    assert summary["fire_direct_win"] == 3
    assert summary["fire_no_threat_passthrough"] == 3
    assert summary["fire_partial_neutralize_passthrough"] == 1
    assert "fire_neutralize_filter_respected" not in summary


def test_combine_sums_fire_counts_across_red_and_blue():
    """两方向各自的 fire_<label> 总和必须在 _combine 后汇总。"""
    red = {
        "games": 2,
        "candidate_wins": 1,
        "illegal_moves": 0,
        "crashes": 0,
        "average_step_time_ms": 1.0,
        "max_step_time_ms": 2.0,
        "fire_direct_win": 3,
        "fire_no_threat_passthrough": 5,
    }
    blue = {
        "games": 2,
        "candidate_wins": 1,
        "illegal_moves": 0,
        "crashes": 0,
        "average_step_time_ms": 1.0,
        "max_step_time_ms": 2.0,
        "fire_direct_win": 2,
        "fire_partial_neutralize_passthrough": 1,
    }

    combined = bench_ai._combine(red, blue)

    assert combined["fire_direct_win"] == 5
    assert combined["fire_no_threat_passthrough"] == 5
    assert combined["fire_partial_neutralize_passthrough"] == 1


def test_candidate_telemetry_returns_empty_for_plain_ai():
    assert bench_ai._candidate_telemetry(_FakePlain()) == {}


# -------- bench_mcts._translate 兼容入口 --------

def test_translate_injects_mcts_candidate_when_absent():
    out = bench_mcts._translate(["--stage", "smoke"])

    assert out[:2] == ["--candidate", "mcts_eval_v1"]
    assert "--stage" in out and out[out.index("--stage") + 1] == "smoke"


def test_translate_keeps_explicit_candidate():
    """显式传 --candidate 时不重复注入 mcts_eval_v1。"""
    out = bench_mcts._translate(["--candidate", "rollout_tactical", "--stage", "smoke"])

    assert out.count("--candidate") == 1
    assert "mcts_eval_v1" not in out


def test_translate_two_token_form_for_time_limit():
    out = bench_mcts._translate(["--stage", "smoke", "--time-limit-ms", "200"])

    assert "--time-limit-ms" not in out
    assert "--candidate-arg" in out
    idx = out.index("--candidate-arg")
    assert out[idx + 1] == "time_limit_ms=200"


def test_translate_eq_form_for_max_iterations():
    out = bench_mcts._translate(["--max-iterations=64"])

    assert "--max-iterations=64" not in out
    idx = out.index("--candidate-arg")
    assert out[idx + 1] == "max_iterations=64"


def test_translate_passes_through_unknown_flags():
    out = bench_mcts._translate([
        "--candidate", "mcts_eval_v1",
        "--seed", "7",
        "--stage", "candidate",
        "--opponent", "rollout",
    ])

    # `--seed 7` 不该被吃掉
    seed_idx = out.index("--seed")
    assert out[seed_idx + 1] == "7"
    # 顺序保留
    assert out.index("--seed") < out.index("--stage") < out.index("--opponent")


# -------- end-to-end mini smoke：rollout_tactical 1 game/方向 --------

def test_bench_ai_main_smokes_rollout_tactical_end_to_end(tmp_path: Path):
    """1 局/方向、max_turns=24 的最小 smoke：验证 bench_ai.main 调用 build_ai、
    play_one_game、聚合、写报告链路完整无异常。

    用 ``rollouts_per_move=1`` 和小 ``max_step_time_ms`` 压成毫秒级，
    避免测试套件被实战 rollout 拖慢。
    """
    report_dir = tmp_path / "reports"
    exit_code = bench_ai.main([
        "--candidate", "rollout_tactical",
        "--stage", "smoke",
        "--games-per-side", "1",
        "--max-turns", "24",
        "--seed", "11",
        "--candidate-arg", "rollouts_per_move=1",
        "--candidate-arg", "max_step_time_ms=20",
        "--report-dir", str(report_dir),
        "--report-name", "smoke_rollout_tactical_test",
    ])

    assert exit_code in (0, 1), "main 应当返回 0/1 而非崩溃"
    json_path = report_dir / "smoke_rollout_tactical_test.json"
    assert json_path.exists(), "smoke 必须落 JSON 报告"
    md_path = report_dir / "smoke_rollout_tactical_test.md"
    assert md_path.exists(), "smoke 必须落 Markdown 报告"

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["candidate"] == "rollout_tactical"
    assert payload["opponent"] == "greedy"
    assert payload["stage"] == "smoke"
    combined = payload["combined"]
    assert combined["games"] == 2  # 1 局/方向
    # 字段命名是 candidate_*，不再有 mcts_* 残留
    assert "candidate_wins" in combined
    assert "candidate_win_rate" in combined
    assert "candidate_win_ci95" in combined
    assert "mcts_wins" not in combined and "mcts_win_rate" not in combined
    # rollout_tactical 不暴露 MCTS 专用遥测 (avg_iterations/max_depth)
    assert "avg_iterations" not in combined
    assert "max_depth" not in combined
    # AI 签名递归包了 base
    candidate_sig = payload["ai_versions"]["candidate"]
    assert candidate_sig["name"] == "rollout_tactical"
    assert candidate_sig["base"]["name"] == "rollout"
    assert candidate_sig["patches"] == ["direct_win", "block_one_step_win"]


def test_bench_ai_main_rejects_unknown_candidate_without_explicit_opponent():
    """未知 candidate 没有 profile → 没默认 opponent → parser.error 抛 SystemExit。"""
    with pytest.raises(SystemExit):
        bench_ai.main([
            "--candidate", "definitely_not_a_real_ai",
            "--stage", "smoke",
            "--games-per-side", "1",
            "--max-turns", "10",
            "--no-save-report",
        ])
