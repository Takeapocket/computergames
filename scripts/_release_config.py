"""读取 release AI 配置；预检的独立预期值仍由预检脚本维护。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


DEFAULT_PARAMS_PATH = Path(__file__).resolve().parents[1] / "release" / "v1.0" / "default_params.json"
METADATA_KEYS = frozenset({"ai", "fallback_ai", "promotion_report"})


def reject_nonfinite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def validate_finite_json_numbers(value: Any, *, field: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must contain only finite numbers")
    if isinstance(value, dict):
        for key, item in value.items():
            validate_finite_json_numbers(item, field=f"{field}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_finite_json_numbers(item, field=f"{field}[{index}]")


def load_release_default_ai_config(
    path: str | Path = DEFAULT_PARAMS_PATH,
) -> tuple[str, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_nonfinite_constant)
    if not isinstance(data, dict):
        raise ValueError("release AI config must be a JSON object")
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")
    validate_finite_json_numbers(data, field="release AI config")
    return "rollout", {key: value for key, value in data.items() if key not in METADATA_KEYS}
