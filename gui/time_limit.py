from __future__ import annotations

import argparse
import math


TIME_LIMIT_ERROR = "单方时限必须是正数秒。"
NONNEGATIVE_SECONDS_ERROR = "计时秒数必须是非负有限数。"


def validate_total_seconds(value: float | str) -> float:
    try:
        total_seconds = float(value)
    except (TypeError, ValueError):
        raise ValueError(TIME_LIMIT_ERROR) from None
    if not math.isfinite(total_seconds) or total_seconds <= 0.0:
        raise ValueError(TIME_LIMIT_ERROR)
    return total_seconds


def parse_total_seconds_arg(value: str) -> float:
    try:
        return validate_total_seconds(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def validate_nonnegative_seconds(value: float | str) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise ValueError(NONNEGATIVE_SECONDS_ERROR) from None
    if not math.isfinite(seconds) or seconds < 0.0:
        raise ValueError(NONNEGATIVE_SECONDS_ERROR)
    return seconds
