import pytest
import tkinter as tk

from core.types import Player
from gui.timer_panel import MatchTimer, TimerPanel, TimerSnapshot
from tests.tk_support import make_hidden_tk_root


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.fixture(scope="module")
def _tk_root():
    root = make_hidden_tk_root()
    yield root


@pytest.fixture
def tk_root(_tk_root):
    top = tk.Toplevel(_tk_root)
    top.withdraw()
    yield top
    if top.winfo_exists():
        top.destroy()


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


def test_set_active_player_charges_current_elapsed_then_switches():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    clock.advance(8)
    timer.set_active_player(Player.BLUE)
    snapshot = timer.snapshot()

    assert snapshot.current_player is Player.BLUE
    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(232)
    assert snapshot.remaining_seconds[Player.BLUE] == pytest.approx(240)
    assert snapshot.current_step_seconds == pytest.approx(0)


def test_set_active_player_preserves_paused_state():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)
    clock.advance(4)
    timer.pause()

    timer.set_active_player(Player.BLUE)

    assert timer.is_paused is True
    snapshot = timer.snapshot()
    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(236)


def test_reset_clears_remaining_to_total():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)
    clock.advance(50)
    timer.finish_turn(Player.BLUE)

    timer.reset()

    snapshot = timer.snapshot()
    assert snapshot.current_player is Player.RED
    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(240)
    assert snapshot.remaining_seconds[Player.BLUE] == pytest.approx(240)


def test_reset_with_remaining_seconds_overrides_default():
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    timer.reset(current_player=Player.BLUE, remaining_seconds={Player.RED: 100, Player.BLUE: 80})

    snapshot = timer.snapshot()
    assert snapshot.current_player is Player.BLUE
    assert snapshot.remaining_seconds[Player.RED] == pytest.approx(100)
    assert snapshot.remaining_seconds[Player.BLUE] == pytest.approx(80)


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), -1.0])
def test_reset_rejects_invalid_remaining_seconds(seconds):
    clock = FakeClock()
    timer = MatchTimer(total_seconds=240, now=clock)

    with pytest.raises(ValueError, match="计时秒数"):
        timer.reset(remaining_seconds={Player.RED: seconds, Player.BLUE: 80})


def test_timer_panel_default_timeout_mode_waits_for_judge_and_enables_timed_out_player(
    tk_root,
):
    confirmed: list[Player] = []
    panel = TimerPanel(
        tk_root,
        on_toggle_pause=lambda: None,
        on_confirm_timeout_forfeit=confirmed.append,
    )
    snapshot = TimerSnapshot(
        current_player=Player.RED,
        remaining_seconds={Player.RED: 0.0, Player.BLUE: 10.0},
        current_step_seconds=12.0,
        paused=False,
        timeout_players=(Player.RED,),
    )

    panel.set_snapshot(
        snapshot,
        auto_timeout_enabled=False,
        timeout_adjudication_enabled=True,
    )

    assert panel.timer_status_var.get() == "超时提示：红方（等裁判）"
    assert panel.red_timeout_button["state"] == tk.NORMAL
    assert panel.blue_timeout_button["state"] == tk.DISABLED

    panel.red_timeout_button.invoke()

    assert confirmed == [Player.RED]
