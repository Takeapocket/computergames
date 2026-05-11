from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from core.types import MAX_PIECE_ID, MIN_PIECE_ID, Position


Layout = dict[int, Position]

RED_ZONE = frozenset(
    Position(row, col)
    for row in range(5)
    for col in range(5)
    if row + col <= 2
)
BLUE_ZONE = frozenset(
    Position(row, col)
    for row in range(5)
    for col in range(5)
    if row + col >= 6
)
EXPECTED_PIECE_IDS = frozenset(range(MIN_PIECE_ID, MAX_PIECE_ID + 1))
DEFAULT_LAYOUT_DIR = Path(__file__).resolve().parents[1] / "layouts"


@dataclass(frozen=True)
class OpeningLayout:
    id: str
    name: str
    red: Layout
    blue: Layout
    created: str = ""


def balanced_layout() -> tuple[Layout, Layout]:
    return _copy_layout(PRESETS["balanced_v1"].red), _copy_layout(PRESETS["balanced_v1"].blue)


def validate_layout(red: Mapping[int, Position], blue: Mapping[int, Position]) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_side("红方", red, RED_ZONE))
    errors.extend(_validate_side("蓝方", blue, BLUE_ZONE))
    errors.extend(_validate_unique_positions(red, blue))
    return errors


def save_layout(
    layout_id: str,
    red: Mapping[int, Position],
    blue: Mapping[int, Position],
    name: str,
    *,
    directory: str | Path = DEFAULT_LAYOUT_DIR,
) -> OpeningLayout:
    _validate_layout_id(layout_id)
    errors = validate_layout(red, blue)
    if errors:
        raise ValueError("; ".join(errors))

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    layout = OpeningLayout(
        id=layout_id,
        name=name,
        red=_copy_layout(red),
        blue=_copy_layout(blue),
        created=created,
    )
    target = Path(directory) / f"{layout_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_layout_to_dict(layout), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return layout


def load_layout(
    layout_id: str,
    *,
    directory: str | Path = DEFAULT_LAYOUT_DIR,
) -> OpeningLayout:
    _validate_layout_id(layout_id)
    path = Path(directory) / f"{layout_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _layout_from_dict(payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid layout file") from exc


def list_saved_layouts(*, directory: str | Path = DEFAULT_LAYOUT_DIR) -> list[OpeningLayout]:
    root = Path(directory)
    if not root.is_dir():
        return []

    layouts: list[OpeningLayout] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            layouts.append(_layout_from_dict(payload))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return layouts


def mirror_layout(layout: Mapping[int, Position]) -> Layout:
    return {
        int(piece_id): Position(row=4 - position.row, col=4 - position.col)
        for piece_id, position in layout.items()
    }


def layout_to_metadata(layout: Mapping[int, Position]) -> dict[str, list[int]]:
    return {str(piece_id): [position.row, position.col] for piece_id, position in sorted(layout.items())}


def _validate_side(label: str, layout: Mapping[int, Position], zone: frozenset[Position]) -> list[str]:
    errors: list[str] = []
    ids = {int(piece_id) for piece_id in layout}
    missing = sorted(EXPECTED_PIECE_IDS - ids)
    unexpected = sorted(ids - EXPECTED_PIECE_IDS)
    if missing:
        errors.append(f"{label}缺少棋子：{','.join(str(piece_id) for piece_id in missing)}")
    if unexpected:
        errors.append(f"{label}存在非法编号：{','.join(str(piece_id) for piece_id in unexpected)}")

    for piece_id, position in sorted(layout.items()):
        if position not in zone:
            errors.append(f"{label} {piece_id} 不在出发区")
    return errors


def _validate_unique_positions(red: Mapping[int, Position], blue: Mapping[int, Position]) -> list[str]:
    seen: dict[Position, str] = {}
    errors: list[str] = []
    for label, layout in (("红方", red), ("蓝方", blue)):
        for piece_id, position in sorted(layout.items()):
            previous = seen.get(position)
            current = f"{label} {piece_id}"
            if previous is not None:
                errors.append(f"棋子位置重叠：{previous} 与 {current}")
            else:
                seen[position] = current
    return errors


def _layout_to_dict(layout: OpeningLayout) -> dict[str, Any]:
    return {
        "id": layout.id,
        "name": layout.name,
        "created": layout.created,
        "red": layout_to_metadata(layout.red),
        "blue": layout_to_metadata(layout.blue),
    }


def _layout_from_dict(data: Mapping[str, Any]) -> OpeningLayout:
    try:
        layout = OpeningLayout(
            id=str(data["id"]),
            name=str(data["name"]),
            created=str(data["created"]),
            red=_parse_layout(data["red"]),
            blue=_parse_layout(data["blue"]),
        )
        _validate_layout_id(layout.id)
        errors = validate_layout(layout.red, layout.blue)
        if errors:
            raise ValueError("invalid layout file")
        return layout
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid layout file") from exc


def _parse_layout(data: Mapping[str, Any]) -> Layout:
    layout: Layout = {}
    for piece_id, raw_position in data.items():
        row, col = raw_position
        layout[int(piece_id)] = Position(int(row), int(col))
    return layout


def _copy_layout(layout: Mapping[int, Position]) -> Layout:
    return {int(piece_id): position for piece_id, position in layout.items()}


def _validate_layout_id(layout_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", layout_id):
        raise ValueError("layout id must contain only letters, numbers, '_' or '-'")


PRESETS: dict[str, OpeningLayout] = {
    "balanced_v1": OpeningLayout(
        id="balanced_v1",
        name="均衡型 V1",
        red={
            1: Position(0, 0),
            2: Position(0, 1),
            3: Position(0, 2),
            4: Position(1, 0),
            5: Position(1, 1),
            6: Position(2, 0),
        },
        blue={
            1: Position(4, 4),
            2: Position(4, 3),
            3: Position(4, 2),
            4: Position(3, 4),
            5: Position(3, 3),
            6: Position(2, 4),
        },
    ),
    "aggressive_v1": OpeningLayout(
        id="aggressive_v1",
        name="速攻型 V1",
        red={
            1: Position(1, 1),
            2: Position(0, 2),
            3: Position(2, 0),
            4: Position(0, 1),
            5: Position(1, 0),
            6: Position(0, 0),
        },
        blue={
            1: Position(3, 3),
            2: Position(4, 2),
            3: Position(2, 4),
            4: Position(4, 3),
            5: Position(3, 4),
            6: Position(4, 4),
        },
    ),
    "defensive_v1": OpeningLayout(
        id="defensive_v1",
        name="防守型 V1",
        red={
            1: Position(0, 1),
            2: Position(1, 0),
            3: Position(0, 0),
            4: Position(0, 2),
            5: Position(2, 0),
            6: Position(1, 1),
        },
        blue={
            1: Position(4, 3),
            2: Position(3, 4),
            3: Position(4, 4),
            4: Position(4, 2),
            5: Position(2, 4),
            6: Position(3, 3),
        },
    ),
}
