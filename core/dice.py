from __future__ import annotations

import secrets
from collections.abc import Callable

DICE_SIDES = 6


def roll_die(randbelow: Callable[[int], int] | None = None) -> int:
    """Return one fair EWN dice value in [1, 6]."""
    generator = randbelow if randbelow is not None else secrets.randbelow
    value = int(generator(DICE_SIDES))
    if not 0 <= value < DICE_SIDES:
        raise ValueError("randbelow must return a value in [0, 6)")
    return value + 1
