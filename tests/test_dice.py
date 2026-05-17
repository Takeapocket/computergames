import pytest

from core.dice import roll_die


def test_roll_die_maps_zero_to_one() -> None:
    assert roll_die(lambda n: 0) == 1


def test_roll_die_maps_five_to_six() -> None:
    assert roll_die(lambda n: 5) == 6


def test_roll_die_uses_current_secrets_randbelow_by_default(monkeypatch) -> None:
    calls: list[int] = []

    def fake_randbelow(limit: int) -> int:
        calls.append(limit)
        return 3

    monkeypatch.setattr("core.dice.secrets.randbelow", fake_randbelow)

    assert roll_die() == 4
    assert calls == [6]


def test_roll_die_rejects_out_of_range_randbelow_result() -> None:
    with pytest.raises(ValueError, match=r"\[0, 6\)"):
        roll_die(lambda n: 6)
