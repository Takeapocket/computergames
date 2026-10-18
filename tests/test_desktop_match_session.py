from __future__ import annotations

import json
from copy import deepcopy

import pytest

import desktop_qt.match_session as module
from ai.match import starting_state_for
from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from desktop_qt.match_session import MatchSession
from record.auto_save import auto_save, auto_save_match, load_auto_save, load_auto_save_match
from record.game_record import GameRecord


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def layouts():
    state = starting_state_for("balanced_v1")
    return tuple({i: p.position for i, p in state.pieces[side].items()} for side in Player)


def begin(session, *, match=False, **kwargs):
    if match:
        session.start_match(**kwargs)
    else:
        session.start_single(**kwargs)
    session.confirm_opening(*layouts())


def make_session(tmp_path):
    clock = Clock()
    return MatchSession(tmp_path, now=clock), clock


def lose_current(session, clock):
    clock.advance(session.total_seconds + 1)
    session.forfeit_timeout(session.state.current_player)


def test_constructor_preserves_existing_recovery_and_starts_paused(tmp_path):
    path = tmp_path / "recovery" / "auto_save.json"
    path.parent.mkdir()
    path.write_text("broken user file", encoding="utf-8")
    session, _ = make_session(tmp_path)
    assert session.phase == "setup" and session.timer.is_paused
    assert session.has_recovery and not session.has_started
    assert not session.checkpoint()
    assert path.read_text(encoding="utf-8") == "broken user file"


def test_custom_opening_stores_exact_layout_and_starts_clock(tmp_path):
    session, clock = make_session(tmp_path)
    red, blue = layouts()
    red[1], red[6] = red[6], red[1]
    session.start_single(total_seconds=600, our_side=Player.BLUE)
    clock.advance(50)
    session.confirm_opening(red, blue, current_player=Player.BLUE)
    assert session.state.current_player is Player.BLUE
    assert session.state.pieces[Player.RED][1].position == red[1]
    assert session.timer.snapshot().remaining_seconds[Player.BLUE] == 600
    record, _ = load_auto_save(path=session.auto_save_path)
    assert record.metadata["red_layout"]["1"] == [red[1].row, red[1].col]
    assert record.metadata["time_limit_seconds"] == 600


def test_invalid_opening_and_settings_leave_current_state_unchanged(tmp_path):
    session, _ = make_session(tmp_path)
    old = session.state.serialize()
    red, blue = layouts()
    red[1] = (3, 3)
    with pytest.raises(ValueError):
        session.confirm_opening(red, blue)
    with pytest.raises(ValueError):
        session.start_match(our_role="丙")
    with pytest.raises(ValueError):
        session.start_single(total_seconds=float("nan"))
    assert session.state.serialize() == old
    assert not session.has_recovery


def test_move_records_time_source_and_undo_does_not_refund(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, our_side=Player.RED)
    session.set_dice(6)
    clock.advance(12)
    session.apply_move(session.legal_moves()[0])
    assert session.record.steps[0].step_seconds == 12
    assert session.record.steps[0].source == "self"
    assert session.timer.snapshot().remaining_seconds[Player.RED] == 228
    clock.advance(5)
    session.undo()
    assert session.state.current_player is Player.RED
    assert session.timer.snapshot().remaining_seconds == {Player.RED: 228, Player.BLUE: 235}
    assert session.dice is None
    record, _ = load_auto_save(path=session.auto_save_path)
    assert not record.steps


def test_failed_append_and_illegal_move_do_not_mutate_timer(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session)
    session.set_dice(6)
    clock.advance(5)
    state, timer = session.state.serialize(), session.timer.snapshot()
    with pytest.raises(ValueError):
        session.apply_move(Move(Player.RED, 6, (4, 4), (0, 0)))
    monkeypatch.setattr(GameRecord, "append", lambda *a, **k: (_ for _ in ()).throw(ValueError("append failed")))
    with pytest.raises(ValueError, match="append failed"):
        session.apply_move(session.legal_moves()[0])
    assert session.state.serialize() == state
    assert session.timer.snapshot() == timer


def test_pause_resume_dice_checkpoint_and_recovery_preserve_clock(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session)
    clock.advance(10)
    session.set_dice(4)
    session.toggle_pause()
    clock.advance(100)
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.dice == 4 and restored.timer.is_paused
    assert restored.timer.snapshot().remaining_seconds[Player.RED] == 230
    restored.toggle_pause()
    clock.advance(3)
    assert restored.checkpoint()
    clock.advance(500)
    again = MatchSession(tmp_path, now=clock)
    assert again.restore_recovery()
    assert not again.timer.is_paused
    assert again.timer.snapshot().remaining_seconds[Player.RED] == 227


def test_default_timeout_requires_judge_and_blocks_late_undo(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    clock.advance(241)
    assert session.check_timeout() is Player.RED
    assert session.phase == "playing" and not session.record.result
    session.forfeit_timeout(Player.RED)
    assert session.record.result["reason"] == "timeout"
    assert session.match.games_won_them == 1
    assert session.can_next_game and not session.can_undo
    with pytest.raises(ValueError):
        session.undo()
    with pytest.raises(ValueError):
        session.forfeit_timeout(Player.RED)
    assert session.match.games_won_them == 1


def test_auto_timeout_finalizes_once_and_each_next_game_resets_clock(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True, auto_timeout_enabled=True)
    clock.advance(241)
    session.check_timeout()
    session.check_timeout()
    assert len(session.match.games) == 1
    session.next_game()
    assert session.phase == "setup" and session.timer.is_paused
    assert session.timer.snapshot().remaining_seconds == {Player.RED: 240, Player.BLUE: 240}
    session.confirm_opening(*layouts())
    assert session.state.current_player is Player.BLUE


@pytest.mark.parametrize("our_side", [Player.RED, Player.BLUE])
@pytest.mark.parametrize("our_role", ["甲", "乙"])
def test_all_seven_game_first_movers_and_final_score(tmp_path, our_side, our_role):
    session, clock = make_session(tmp_path)
    session.start_match(our_side=our_side, our_role=our_role)
    expected = []
    # 每盘令先手超时；甲先手三盘、乙先手四盘，恰在第七盘结束。
    for index in range(1, 8):
        session.confirm_opening(*layouts())
        first = our_side if ((index in (1, 4, 5)) == (our_role == "甲")) else our_side.opponent
        expected.append(first)
        assert session.state.current_player is first
        lose_current(session, clock)
        assert len(session.match.games) == index
        if index < 7:
            assert session.can_next_game, session.save_error
            session.next_game()
    assert session.match.is_finished() and not session.can_next_game
    assert sorted([session.match.games_won_us, session.match.games_won_them]) == [3, 4]
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert len(restored.match.games) == 7
    assert restored.match.to_dict() == session.match.to_dict()


def test_match_save_failure_blocks_next_game_and_retry_never_rescores(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    real = module.auto_save_match
    monkeypatch.setattr(module, "auto_save_match", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    lose_current(session, clock)
    assert session.pending_finalize and session.save_error and not session.can_next_game
    assert load_auto_save(path=session.auto_save_path)[0].result["reason"] == "timeout"
    assert not session.retry_save()
    assert len(session.match.games) == 1
    with pytest.raises(ValueError):
        session.next_game()
    monkeypatch.setattr(module, "auto_save_match", real)
    assert session.retry_save() and session.can_next_game
    assert session.retry_save() and len(session.match.games) == 1


def test_restart_completes_uncommitted_timeout_once(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    real = module.auto_save_match
    monkeypatch.setattr(module, "auto_save_match", lambda *a, **k: (_ for _ in ()).throw(OSError("fail")))
    lose_current(session, clock)
    monkeypatch.setattr(module, "auto_save_match", real)
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.match.games_won_them == 1
    assert len(load_auto_save_match(path=session.auto_save_match_path).games) == 1
    restored_again = MatchSession(tmp_path, now=clock)
    assert restored_again.restore_recovery()
    assert restored_again.match.games_won_them == 1


def test_terminal_move_before_score_commit_restores_once(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    # 使用实际可重放的近终局棋谱模拟旧程序“末步已保存、比分尚未落盘”。
    state = GameState.from_layout(red={1: Position(3, 3)}, blue={1: Position(0, 4)})
    record = GameRecord.from_state(state)
    record.metadata.update(session.record.metadata)
    move = next(m for m in state.legal_moves(Player.RED, 1) if m.to_pos == Position(4, 4))
    canonical = state.apply_move(move, dice=1)
    record.append(dice=1, move=canonical, state_after=state)
    session.timer.set_active_player(state.current_player)
    session.timer.pause()
    auto_save(record, session.timer.snapshot(), path=session.auto_save_path)
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.match.games_won_us == 1
    assert restored.record.result["reason"] == "target_corner"


@pytest.mark.parametrize("damage", ["json", "match_id", "timer", "score", "committed", "timeout"])
def test_corrupt_or_mismatched_recovery_never_replaces_state_or_deletes_files(tmp_path, damage):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    if damage == "committed":
        lose_current(session, clock)
    game = json.loads(session.auto_save_path.read_text(encoding="utf-8"))
    if damage == "json":
        session.auto_save_path.write_text("{bad", encoding="utf-8")
    elif damage == "match_id":
        game["metadata"]["match_id"] = "different"
    elif damage == "timer":
        game["metadata"]["auto_save"]["timer_current_player"] = "blue"
    elif damage == "score":
        match = json.loads(session.auto_save_match_path.read_text(encoding="utf-8"))
        match["games_won_us"] = 1
        session.auto_save_match_path.write_text(json.dumps(match), encoding="utf-8")
    elif damage == "committed":
        game["metadata"]["extra"] = "different"
    elif damage == "timeout":
        game["result"] = {"winner": "blue", "reason": "timeout", "game_index": 1}
    if damage != "json":
        session.auto_save_path.write_text(json.dumps(game), encoding="utf-8")
    before = {p: p.read_bytes() for p in (session.auto_save_path, session.auto_save_match_path)}
    target = MatchSession(tmp_path, now=clock)
    state, revision = target.state.serialize(), target.revision
    with pytest.raises(ValueError):
        target.restore_recovery()
    assert target.state.serialize() == state and target.revision == revision
    assert before == {p: p.read_bytes() for p in before}


def test_legacy_game_record_compatibility_and_explicit_rules_read_only(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session)
    session.set_dice(6)
    session.apply_move(session.legal_moves()[0])
    legacy = deepcopy(session.record)
    legacy.metadata.pop("rules_version")
    path = tmp_path / "legacy.json"
    legacy.save(path)
    target = MatchSession(tmp_path / "other", now=clock)
    target.load(path)
    assert target.can_play and len(target.record.steps) == 1
    legacy.metadata["rules_version"] = "old-broken-rules"
    legacy.save(path)
    target.load(path)
    assert not target.can_play and target.continuation_error


def test_legacy_auto_save_timer_options_restore_and_new_single_ignores_old_match(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True, total_seconds=600, auto_timeout_enabled=True)
    payload = json.loads(session.auto_save_match_path.read_text(encoding="utf-8"))
    payload.pop("time_limit_seconds")
    payload.pop("auto_timeout_enabled")
    session.auto_save_match_path.write_text(json.dumps(payload), encoding="utf-8")
    target = MatchSession(tmp_path, now=clock)
    assert target.restore_recovery()
    assert target.match.time_limit_seconds == 600 and target.match.auto_timeout_enabled
    target.start_single()
    assert target.auto_save_match_path.exists()
    single = MatchSession(tmp_path, now=clock)
    assert single.restore_recovery()
    assert single.match is None and single.phase == "setup"


def test_manual_save_exports_current_game_and_match_separately(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    clock.advance(4)
    session.set_dice(3)
    game_path, match_path = tmp_path / "game.json", tmp_path / "match.json"
    session.save(game_path)
    session.save_match(match_path)
    loaded = MatchSession(tmp_path / "loaded", now=clock)
    loaded.load(game_path)
    assert loaded.dice == 3 and loaded.timer.snapshot().remaining_seconds[Player.RED] == 236
    before = loaded.state.serialize()
    with pytest.raises(ValueError, match="正在进行盘"):
        loaded.load(match_path)
    assert loaded.state.serialize() == before


def test_match_only_between_games_load_and_missing_active_game_rejection(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    active = tmp_path / "active.json"
    session.save_match(active)
    target = MatchSession(tmp_path / "target", now=clock)
    with pytest.raises(ValueError):
        target.restore_recovery(game_path=tmp_path / "missing", match_path=active)
    lose_current(session, clock)
    between = tmp_path / "between.json"
    session.save_match(between)
    target.load(between)
    assert target.phase == "setup" and target.match.current_game_index == 2
    assert target.match.games_won_them == 1


def test_periodic_checkpoint_failure_stays_visible_until_explicit_retry(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session)
    real = module.auto_save
    monkeypatch.setattr(module, "auto_save", lambda *a, **k: (_ for _ in ()).throw(OSError("no space")))
    assert not session.checkpoint() and session.save_error
    monkeypatch.setattr(module, "auto_save", real)
    clock.advance(9)
    assert not session.checkpoint() and session.save_error
    assert session.retry_save() and session.save_error is None
    assert load_auto_save(path=session.auto_save_path)[1]["timer_remaining"]["red"] == 231


def test_restored_match_export_keeps_final_timeout_snapshot(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    clock.advance(5)
    session.checkpoint()
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    lose_current(restored, clock)
    game = restored.match.games[-1]
    assert game.metadata["auto_save"]["timer_remaining"]["red"] == 0
    assert game.metadata["auto_save"]["timer_paused"] is True
    path = tmp_path / "round.json"
    restored.save_match(path)
    imported = MatchSession(tmp_path / "imported", now=clock)
    imported.load(path)
    assert imported.match.games_won_them == 1
    assert imported.phase == "setup"


def test_single_game_save_failure_prevents_committing_match(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    prior_match = session.auto_save_match_path.read_bytes()
    real = module.auto_save
    monkeypatch.setattr(module, "auto_save", lambda *a, **k: (_ for _ in ()).throw(OSError("game failed")))
    lose_current(session, clock)
    assert session.pending_finalize and session.save_error
    assert session.auto_save_match_path.read_bytes() == prior_match
    assert len(session.match.games) == 1
    monkeypatch.setattr(module, "auto_save", real)
    assert session.retry_save()
    assert len(load_auto_save_match(path=session.auto_save_match_path).games) == 1


def test_direct_initial_opening_marks_session_started(tmp_path):
    session, _ = make_session(tmp_path)
    session.confirm_opening(*layouts())
    assert session.has_started and session.checkpoint()


def test_explicit_old_rules_running_clock_is_read_only_without_periodic_writes(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session)
    clock.advance(11)
    session.checkpoint()
    payload = json.loads(session.auto_save_path.read_text(encoding="utf-8"))
    payload["metadata"]["rules_version"] = "old-broken-rules"
    session.auto_save_path.write_text(json.dumps(payload), encoding="utf-8")
    original = session.auto_save_path.read_bytes()
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.continuation_error and restored.timer.is_paused
    remaining = restored.timer.snapshot().remaining_seconds
    clock.advance(30)
    assert restored.timer.snapshot().remaining_seconds == remaining
    assert not restored.checkpoint()
    assert session.auto_save_path.read_bytes() == original
    exported = tmp_path / "old-rules-copy.json"
    restored.save(exported)
    assert GameRecord.load(exported).metadata["rules_version"] == "old-broken-rules"


def test_judge_can_adjudicate_previous_player_timeout_and_recover(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    session.set_dice(6)
    clock.advance(241)
    session.apply_move(session.legal_moves()[0])
    assert session.state.current_player is Player.BLUE
    session.forfeit_timeout(Player.RED)
    assert session.state.current_player is Player.BLUE
    assert session.record.result["timed_out_player"] == "red"
    assert session.record.result["winner"] == "blue"
    assert session.match.games_won_them == 1
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.state.current_player is Player.BLUE
    assert restored.record.result == session.record.result
    path = tmp_path / "match-export.json"
    session.save_match(path)
    imported = MatchSession(tmp_path / "import", now=clock)
    imported.load(path)
    assert imported.match.games_won_them == 1


@pytest.mark.parametrize("chosen", [Player.RED, Player.BLUE])
def test_both_players_zero_can_choose_either_judge_timeout(tmp_path, chosen):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    session.set_dice(6)
    clock.advance(241)
    session.apply_move(session.legal_moves()[0])
    clock.advance(241)
    assert session.check_timeout() is Player.BLUE
    assert session.timer.snapshot().timeout_players == (Player.RED, Player.BLUE)
    session.forfeit_timeout(chosen)
    assert session.record.result["winner"] == chosen.opponent.value
    assert session.record.result["timed_out_player"] == chosen.value
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.record.result == session.record.result


def test_legacy_late_timeout_uses_last_step_zero_evidence(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session)
    session.set_dice(6)
    clock.advance(241)
    session.apply_move(session.legal_moves()[0])
    record = deepcopy(session.record)
    record.result = {"winner": "blue", "reason": "timeout"}
    record.metadata.pop("auto_save", None)
    path = tmp_path / "legacy-late-timeout.json"
    record.save(path)
    restored = MatchSession(tmp_path / "other", now=clock)
    restored.load(path)
    assert restored.phase == "finished"
    assert restored.state.current_player is Player.BLUE


def test_timeout_explicit_loser_requires_matching_zero_clock(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session)
    lose_current(session, clock)
    payload = json.loads(session.auto_save_path.read_text(encoding="utf-8"))
    payload["result"]["timed_out_player"] = "blue"
    path = tmp_path / "invalid-loser.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    target = MatchSession(tmp_path / "other", now=clock)
    with pytest.raises(ValueError, match="超时方"):
        target.load(path)


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_transient_windows_replace_failure_retries_io_only(tmp_path, monkeypatch, winerror):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    actual_save, calls, delays = module.auto_save_match, [], []

    def fail_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            error = PermissionError("transient Windows sharing violation")
            error.winerror = winerror
            raise error
        return actual_save(*args, **kwargs)

    monkeypatch.setattr(module, "auto_save_match", fail_once)
    monkeypatch.setattr(module.time, "sleep", delays.append)
    lose_current(session, clock)
    assert len(calls) == 2 and delays == [0.02]
    assert session.save_error is None and not session.pending_finalize
    assert len(session.match.games) == 1
    assert len(load_auto_save_match(path=session.auto_save_match_path).games) == 1


def test_persistent_windows_replace_failure_reports_after_bounded_retries(tmp_path, monkeypatch):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    calls, delays = [], []
    original_match = session.auto_save_match_path.read_bytes()

    def always_fail(*args, **kwargs):
        calls.append(1)
        error = PermissionError("persistent Windows access denied")
        error.winerror = 5
        raise error

    monkeypatch.setattr(module, "auto_save_match", always_fail)
    monkeypatch.setattr(module.time, "sleep", delays.append)
    lose_current(session, clock)
    assert len(calls) == 3 and delays == [0.02, 0.05]
    assert session.pending_finalize and "persistent Windows access denied" in session.save_error
    assert len(session.match.games) == 1 and not session.can_next_game
    assert session.auto_save_match_path.read_bytes() == original_match
    assert load_auto_save(path=session.auto_save_path)[0].result["reason"] == "timeout"


@pytest.mark.parametrize("stale_kind", ["next_game_playing", "older_finished_game"])
def test_committed_recovery_rejects_missing_current_game_or_old_finished_board(tmp_path, stale_kind):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    lose_current(session, clock)
    previous_game = session.auto_save_path.read_bytes()
    session.next_game()
    session.confirm_opening(*layouts())
    if stale_kind == "older_finished_game":
        lose_current(session, clock)
    session.auto_save_path.write_bytes(previous_game)
    before = {p: p.read_bytes() for p in (session.auto_save_path, session.auto_save_match_path)}
    target = MatchSession(tmp_path, now=clock)
    state, revision = target.state.serialize(), target.revision
    pattern = "当前盘进度缺失" if stale_kind == "next_game_playing" else "最后已结算盘"
    with pytest.raises(ValueError, match=pattern):
        target.restore_recovery()
    assert target.state.serialize() == state and target.revision == revision
    assert target.match is None and not target.has_started
    assert before == {p: p.read_bytes() for p in before}


def test_latest_committed_game_between_games_restores_without_reopening_or_rescoring(tmp_path):
    session, clock = make_session(tmp_path)
    begin(session, match=True)
    for index in range(1, 3):
        lose_current(session, clock)
        if index == 1:
            session.next_game()
            session.confirm_opening(*layouts())
    restored = MatchSession(tmp_path, now=clock)
    assert restored.restore_recovery()
    assert restored.match.phase == "setup" and restored.phase == "finished"
    assert restored.can_next_game and restored.match.current_game_index == 3
    assert len(restored.match.games) == 2
    assert restored.record.result["game_index"] == 2
