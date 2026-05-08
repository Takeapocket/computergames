import pytest

from core.types import Player
from gui.timer_panel import MatchTimer


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_match_timer_starts_with_equal_remaining_time():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    snapshot = timer.snapshot()

    assert snapshot.current_player is Player.RED
    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(240)
    assert snapshot.remaining_seconds[Player.BLUE] == pytest.approx(240)
    assert snapshot.current_step_seconds == pytest.approx(0)
    assert snapshot.paused is False
    assert snapshot.timeout_players == ()


def test_match_timer_running_snapshot_deducts_current_player_only():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    clock.advance(5)
    snapshot = timer.snapshot()

    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(235)
    assert snapshot.remaining_seconds[Player.BLUE] == pytest.approx(240)
    assert snapshot.current_step_seconds == pytest.approx(5)


def test_match_timer_pause_resume_does_not_count_paused_time():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    clock.advance(5)
    timer.pause()
    clock.advance(20)
    paused_snapshot = timer.snapshot()
    timer.resume()
    clock.advance(3)
    resumed_snapshot = timer.snapshot()

    assert paused_snapshot.current_step_seconds == pytest.approx(5)
    assert paused_snapshot.remaining_seconds[Player.RED] == pytest.approx(235)
    assert resumed_snapshot.current_step_seconds == pytest.approx(8)
    assert resumed_snapshot.remaining_seconds[Player.RED] == pytest.approx(232)


def test_match_timer_finish_turn_records_step_time_and_switches_player():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    clock.advance(12.5)
    step_seconds, remaining_seconds = timer.finish_turn(Player.BLUE)
    snapshot = timer.snapshot()

    assert step_seconds == pytest.approx(12.5)
    assert remaining_seconds[Player.RED] == pytest.approx(227.5)
    assert remaining_seconds[Player.BLUE] == pytest.approx(240)
    assert snapshot.current_player is Player.BLUE
    assert snapshot.current_step_seconds == pytest.approx(0)


def test_match_timer_timeout_warns_but_still_allows_finish_turn():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=3, now=clock)

    clock.advance(5)
    snapshot = timer.snapshot()
    step_seconds, remaining_seconds = timer.finish_turn(Player.BLUE)

    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(0)
    assert snapshot.timeout_players == (Player.RED,)
    assert step_seconds == pytest.approx(5)
    assert remaining_seconds[Player.RED] == pytest.approx(0)
    assert timer.snapshot().current_player is Player.BLUE
