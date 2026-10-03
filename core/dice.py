from __future__ import annotations

import secrets
from collections.abc import Callable

from core.validation import require_int

DICE_SIDES = 6


def roll_die(randbelow: Callable[[int], int] | None = None) -> int:
    """Return one fair EWN dice value in [1, 6]."""
    generator = randbelow if randbelow is not None else secrets.randbelow
    value = require_int(generator(DICE_SIDES), "randbelow result")
    if not 0 <= value < DICE_SIDES:
        raise ValueError("randbelow must return a value in [0, 6)")
    return value + 1
