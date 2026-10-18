"""可在源码与便携 EXE 中运行的桌面比赛流程验收。

只使用独立数据目录和注入的单调时钟；不会修改默认 AI、规则或用户棋谱。
每个检查均经过真实控制器入口，失败直接抛出异常供发行自检报告捕获。
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from ai.opening_layouts import PRESETS
from core.types import Player
from desktop_qt.match_session import MatchSession
from record.auto_save import load_auto_save, load_auto_save_match
from record.game_record import GameRecord


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        _require(seconds >= 0.0, "验收时钟不能倒退")
        self.value += seconds


def _require(condition: bool, message: str) -> None:
    # 显式抛出，避免 Python 优化模式关闭 assert 后出现伪成功。
    if not condition:
        raise AssertionError(message)


def _expect_value_error(action, message: str) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError(message)


def _layouts():
    red, blue = dict(PRESETS["balanced_v1"].red), dict(PRESETS["balanced_v1"].blue)
    red[1], red[6] = red[6], red[1]
    blue[2], blue[5] = blue[5], blue[2]
    return red, blue


def _confirm(session: MatchSession) -> None:
    session.confirm_opening(*_layouts(), layout_id="acceptance_custom")
    _require(session.phase == "playing" and not session.timer.is_paused, "确认开局后未开始计时")
    _require(session.save_error is None, f"确认开局的自动保存失败：{session.save_error}")


def _make_timeout(session: MatchSession, clock: _Clock, winner: Player) -> None:
    """以合法走子和实际计时归零构造裁判判负，不直接改棋局或结果。"""
    loser = winner.opponent
    if session.state.current_player is winner:
        session.set_dice(6)
        moves = session.legal_moves()
        _require(bool(moves), "验收局面没有合法走法")
        session.apply_move(moves[0])
    _require(session.state.current_player is loser, "目标超时方不是当前行动方")
    clock.advance(session.timer.snapshot().remaining_seconds[loser] + 1.0)
    _require(session.check_timeout() is loser, "归零时未发现超时")
    _require(not session.record.result, "默认模式在裁判确认前擅自判负")
    session.forfeit_timeout(loser)
    _require(session.record.result["winner"] == winner.value, "超时结果胜方错误")
    _require(session.record.result["reason"] == "timeout", "超时结果原因错误")


def _play_match(root: Path, outcomes: tuple[bool, ...], *, side: Player, role: str) -> dict:
    clock = _Clock()
    session = MatchSession(root, now=clock)
    session.start_match(our_side=side, our_role=role, total_seconds=20.0)
    expected_us = expected_them = 0
    for index, us_won in enumerate(outcomes, 1):
        _require(session.match.current_game_index == index, "比赛盘号不连续")
        expected_first = side if ((index in {1, 4, 5}) == (role == "甲")) else side.opponent
        _confirm(session)
        _require(session.state.current_player is expected_first, "比赛实际首手与甲乙序列不一致")
        _make_timeout(session, clock, side if us_won else side.opponent)
        expected_us += int(us_won)
        expected_them += int(not us_won)
        _require((session.match.games_won_us, session.match.games_won_them) == (expected_us, expected_them),
                 "比赛比分错误")
        _require(len(session.match.games) == index and not session.pending_finalize, "终盘未成功保存")
        saved = load_auto_save_match(path=session.auto_save_match_path)
        _require(len(saved.games) == index, "整轮落盘局数错误")
        # 每盘都用新实例恢复；已结算的单盘残留不能再次增加比分。
        restarted = MatchSession(root, now=clock)
        _require(restarted.restore_recovery(), "整轮恢复未执行")
        _require((restarted.match.games_won_us, restarted.match.games_won_them) == (expected_us, expected_them),
                 "整轮恢复重复计分或丢分")
        _require(len(restarted.match.games) == index, "整轮恢复重复追加棋谱")
        session = restarted
        if index < len(outcomes):
            _require(session.can_next_game, "未决出整轮胜者时无法进入下一盘")
            session.next_game()
            _require(session.phase == "setup" and session.timer.is_paused, "盘间设置未暂停计时")
    _require(session.match.is_finished() and session.phase == "finished", "先胜四盘后未结束比赛")
    _require(not session.can_next_game and not session.can_undo and not session.can_play,
             "整轮结束后仍允许操作")
    _expect_value_error(session.next_game, "整轮结束后允许新开第八盘")
    export = root / "completed-match.json"
    session.save_match(export)
    imported = MatchSession(root / "imported", now=clock)
    imported.load(export)
    _require(imported.match.to_dict() == session.match.to_dict(), "整轮导出导入不一致")
    return {"games": len(outcomes), "score": [expected_us, expected_them], "restarts": len(outcomes)}


def _terminal_recovery(root: Path) -> int:
    """把真实合法棋步走至终局，重启后补交最后一次整轮写入。"""
    from desktop_qt import match_session as match_module

    clock = _Clock()
    session = MatchSession(root, now=clock)
    session.start_match()
    _confirm(session)
    original_save = match_module.auto_save_match

    def fail_save(*args, **kwargs):
        raise OSError("acceptance interrupted match write")

    try:
        match_module.auto_save_match = fail_save
        for turn in range(96):
            session.set_dice(turn % 6 + 1)
            moves = session.legal_moves()
            _require(bool(moves), "终局恢复验收没有合法走法")
            # 只使用 core 的合法步，选择向目标角推进最多的那一步。
            direction = 1 if session.state.current_player is Player.RED else -1
            move = max(moves, key=lambda item: direction * (item.to_pos.row + item.to_pos.col))
            clock.advance(0.25)
            session.apply_move(move)
            if session.state.get_winner() is not None:
                break
        _require(session.state.get_winner() is not None, "有界合法走子演练未到终局")
        _require(session.pending_finalize and session.save_error is not None,
                 "末步整轮保存失败没有保留补结算信息")
        _require(session.record.result["reason"] in {"target_corner", "capture_all"},
                 "真实棋盘终局原因错误")
        winner = session.state.get_winner()
        moves_played = len(session.record.steps)
    finally:
        match_module.auto_save_match = original_save
    restored = MatchSession(root, now=clock)
    _require(restored.restore_recovery(), "末步棋盘终局不能恢复")
    _require(len(restored.match.games) == 1 and restored.record.result["winner"] == winner.value,
             "末步棋盘终局补结算错误")
    again = MatchSession(root, now=clock)
    _require(again.restore_recovery() and len(again.match.games) == 1,
             "末步棋盘终局二次重启重复计分")
    return moves_played


def run_flow_acceptance(data_dir: str | Path) -> dict:
    """运行全部有界流程验收；仅成功时返回 checks，任何失败向调用方传播。"""
    root = Path(data_dir) / ("flow-acceptance-" + uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    checks: dict[str, bool] = {}
    clock = _Clock()
    session = MatchSession(root / "single", now=clock)
    session.start_single(total_seconds=60.0)
    _confirm(session)
    initial = session.state.serialize()
    for player, layout in zip((Player.RED, Player.BLUE), _layouts()):
        _require({key: piece.position for key, piece in session.state.pieces[player].items()} == layout,
                 "自定义开局未原样进入核心局面")
    checks["custom_opening"] = True
    clock.advance(3.0)
    session.set_dice(6)
    session.apply_move(session.legal_moves()[0])
    _require(session.record.steps[0].step_seconds == 3.0, "单步用时未写入棋谱")
    clock.advance(2.0)
    session.toggle_pause()
    paused = session.timer.snapshot().remaining_seconds
    clock.advance(100.0)
    _require(session.timer.snapshot().remaining_seconds == paused, "暂停期间仍在扣时")
    session.toggle_pause()
    clock.advance(4.0)
    session.undo()
    _require(session.state.serialize() == initial and session.dice is None, "悔棋未恢复初始局面或未清空骰子")
    _require(session.timer.snapshot().remaining_seconds == {Player.RED: 57.0, Player.BLUE: 54.0},
             "悔棋返还历史用时或丢失对方本轮用时")
    checks["pause_resume_and_undo_clock"] = True
    clock.advance(1.5)
    _require(session.retry_save(), "单盘自动保存失败")
    expected_remaining = session.timer.snapshot().remaining_seconds
    recovered = MatchSession(root / "single", now=clock)
    _require(recovered.restore_recovery(), "单盘未恢复")
    _require(recovered.state.serialize() == session.state.serialize(), "单盘恢复局面错误")
    _require(recovered.timer.snapshot().remaining_seconds == expected_remaining, "单盘恢复计时错误")
    checks["single_game_recovery"] = True
    export = root / "single" / "export.json"
    recovered.save(export)
    _require(GameRecord.load(export).restore_state().serialize() == recovered.state.serialize(),
             "旧 GameRecord 读取器无法读取新界面导出的棋谱")
    checks["existing_record_reader"] = True

    role_color_cases = 0
    for side in (Player.RED, Player.BLUE):
        for role in ("甲", "乙"):
            mapping = MatchSession(root / f"mapping-{side.value}-{role}", now=clock)
            mapping.start_match(our_side=side, our_role=role)
            for index in range(1, 8):
                expected = side if ((index in {1, 4, 5}) == (role == "甲")) else side.opponent
                _require(mapping.match.first_mover_color(index) is expected, "甲乙与红蓝先手映射错误")
            _confirm(mapping)
            _require(mapping.state.current_player is (side if role == "甲" else side.opponent),
                     "首盘确认开局后没有采用比赛首手")
            role_color_cases += 1
    checks["role_color_first_mover_matrix"] = True
    sweep = _play_match(root / "sweep", (True,) * 4, side=Player.RED, role="甲")
    full = _play_match(root / "seven-games", (True, False, True, False, True, False, True),
                       side=Player.BLUE, role="乙")
    checks["four_zero_match"] = checks["four_three_match"] = True
    checks["match_recovery_no_duplicate_score"] = True

    corrupt_dir = root / "corrupt"
    corrupt = MatchSession(corrupt_dir, now=clock)
    corrupt.start_single()
    bad = b'{"broken":'
    corrupt.auto_save_path.write_bytes(bad)
    rejected = MatchSession(corrupt_dir, now=clock)
    previous = (rejected.state.serialize(), rejected.record.to_dict(), rejected.revision)
    _expect_value_error(rejected.restore_recovery, "损坏恢复文件未被拒绝")
    _require((rejected.state.serialize(), rejected.record.to_dict(), rejected.revision) == previous,
             "恢复失败改变了当前局面")
    _require(corrupt.auto_save_path.read_bytes() == bad, "损坏文件未保留供检查")
    checks["corrupt_recovery_preserved"] = True

    # 可控故障注入仅作用于当前验收调用；finally 保证恢复保存函数。
    from desktop_qt import match_session as match_module
    retry_clock = _Clock()
    retry = MatchSession(root / "retry", now=retry_clock)
    retry.start_match()
    _confirm(retry)
    original_save = match_module.auto_save_match
    interrupted_root = root / "interrupted-timeout"
    interrupted_paths = MatchSession(interrupted_root, now=retry_clock)

    def fail_save(*args, **kwargs):
        raise OSError("acceptance simulated full disk")

    try:
        match_module.auto_save_match = fail_save
        _make_timeout(retry, retry_clock, Player.BLUE)
        _require(retry.pending_finalize and retry.save_error is not None, "保存失败后未保留待结算状态")
        _require(not retry.can_next_game and not retry.can_play and not retry.can_undo, "结算保存失败仍允许推进")
        _require(not retry.retry_save(), "模拟磁盘写入失败返回了成功")
        _require(len(retry.match.games) == 1 and retry.match.games_won_them == 1, "重试保存重复加分")
        saved_record, _ = load_auto_save(path=retry.auto_save_path)
        _require(saved_record.result["reason"] == "timeout", "失败后单盘恢复文件丢失超时结果")
        interrupted_paths.auto_save_path.parent.mkdir(parents=True, exist_ok=False)
        interrupted_paths.auto_save_path.write_bytes(retry.auto_save_path.read_bytes())
        interrupted_paths.auto_save_match_path.write_bytes(retry.auto_save_match_path.read_bytes())
    finally:
        match_module.auto_save_match = original_save
    _require(retry.retry_save() and not retry.pending_finalize, "故障解除后重试保存失败")
    _require(len(retry.match.games) == 1 and retry.match.games_won_them == 1, "保存成功时重复加分")
    recovered_retry = MatchSession(root / "retry", now=retry_clock)
    _require(recovered_retry.restore_recovery(), "重试成功后无法恢复")
    _require(recovered_retry.match.games_won_them == 1, "重试后的重启重复计分")
    checks["failed_finalization_retry_once"] = True
    interrupted = MatchSession(interrupted_root, now=retry_clock)
    _require(interrupted.restore_recovery(), "崩溃前的末步结果无法补结算")
    _require(len(interrupted.match.games) == 1 and interrupted.match.games_won_them == 1,
             "崩溃后补结算未准确计分")
    second_restart = MatchSession(interrupted_root, now=retry_clock)
    _require(second_restart.restore_recovery() and len(second_restart.match.games) == 1,
             "补结算后再次重启重复追加结果")
    checks["uncommitted_timeout_recovery_once"] = True
    terminal_moves = _terminal_recovery(root / "interrupted-terminal")
    checks["uncommitted_terminal_recovery_once"] = True

    legacy = GameRecord.from_state(deepcopy(session.state))
    legacy.metadata.pop("rules_version", None)
    legacy.metadata["legacy_note"] = "保留旧棋谱自定义字段"
    legacy_path = root / "legacy.json"
    legacy.save(legacy_path)
    reader = MatchSession(root / "legacy-reader", now=clock)
    reader.load(legacy_path)
    _require(reader.continuation_error is None and reader.record.metadata == legacy.metadata,
             "无版本旧棋谱兼容性或元数据被改变")
    reader.set_dice(6)
    reader.apply_move(reader.legal_moves()[0])
    old_rules = GameRecord.from_state(deepcopy(session.state))
    old_rules.metadata["rules_version"] = "historical-rules-for-acceptance"
    old_rules_path = root / "old-rules.json"
    old_rules.save(old_rules_path)
    reader.load(old_rules_path)
    _require(reader.continuation_error is not None and not reader.can_play, "显式旧规则棋谱没有保持只读")
    _expect_value_error(lambda: reader.set_dice(6), "旧规则棋谱允许续走")
    _require(reader.record.metadata["rules_version"] == "historical-rules-for-acceptance", "旧规则标签被篡改")
    checks["legacy_records_compatible"] = True
    return {
        "checks": checks,
        "statistics": {"role_color_cases": role_color_cases, "first_mover_checks": role_color_cases * 7,
                       "completed_match_games": sweep["games"] + full["games"],
                       "match_restarts": sweep["restarts"] + full["restarts"],
                       "terminal_recovery_moves": terminal_moves,
                       "scores": [sweep["score"], full["score"]]},
        "data_dir": str(root),
    }
