from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARAMS_PATH = ROOT / "release" / "v1.0" / "default_params.json"


def load_release_default_rollout_kwargs(
    path: str | Path = DEFAULT_PARAMS_PATH,
) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("ai") != "rollout":
        raise ValueError("release/v1.0/default_params.json must use ai='rollout'")
    metadata_keys = {"ai", "fallback_ai", "promotion_report"}
    return {key: value for key, value in data.items() if key not in metadata_keys}


RELEASE_DEFAULT_ROLLOUT_KWARGS = load_release_default_rollout_kwargs()
