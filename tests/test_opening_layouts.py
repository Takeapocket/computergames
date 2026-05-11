from __future__ import annotations

import json

import pytest

from core.types import Position


def test_all_opening_presets_are_valid() -> None:
    from ai.opening_layouts import PRESETS, validate_layout

    assert len(PRESETS) >= 3
    for preset in PRESETS.values():
        assert validate_layout(preset.red, preset.blue) == []


def test_validate_layout_rejects_missing_piece_ids() -> None:
    from ai.opening_layouts import balanced_layout, validate_layout

    red, blue = balanced_layout()
    red.pop(3)

    errors = validate_layout(red, blue)

    assert any("红方" in error and "缺少" in error and "3" in error for error in errors)


def test_validate_layout_rejects_unexpected_piece_ids() -> None:
    from ai.opening_layouts import balanced_layout, validate_layout

    red, blue = balanced_layout()
    red[7] = red.pop(6)

    errors = validate_layout(red, blue)

    assert any("红方" in error and "非法编号" in error and "7" in error for error in errors)


def test_validate_layout_rejects_out_of_zone_positions() -> None:
    from ai.opening_layouts import balanced_layout, validate_layout

    red, blue = balanced_layout()
    red[1] = Position(3, 1)

    errors = validate_layout(red, blue)

    assert any("红方" in error and "出发区" in error for error in errors)


def test_validate_layout_rejects_duplicate_coordinates() -> None:
    from ai.opening_layouts import balanced_layout, validate_layout

    red, blue = balanced_layout()
    red[2] = red[1]

    errors = validate_layout(red, blue)

    assert any("重叠" in error for error in errors)


def test_save_and_load_layout_round_trip(tmp_path) -> None:
    from ai.opening_layouts import balanced_layout, load_layout, save_layout

    red, blue = balanced_layout()

    save_layout("custom_v1", red, blue, "Custom V1", directory=tmp_path)
    loaded = load_layout("custom_v1", directory=tmp_path)

    assert loaded.red == red
    assert loaded.blue == blue
    assert loaded.id == "custom_v1"
    assert loaded.name == "Custom V1"


def test_list_saved_layouts_skips_corrupt_files(tmp_path) -> None:
    from ai.opening_layouts import balanced_layout, list_saved_layouts, save_layout

    red, blue = balanced_layout()
    save_layout("valid_v1", red, blue, "Valid V1", directory=tmp_path)
    (tmp_path / "bad.json").write_text("{not-json", encoding="utf-8")

    saved = list_saved_layouts(directory=tmp_path)

    assert [layout.id for layout in saved] == ["valid_v1"]


def test_list_saved_layouts_skips_invalid_schema_files(tmp_path) -> None:
    from ai.opening_layouts import balanced_layout, list_saved_layouts, save_layout

    red, blue = balanced_layout()
    save_layout("valid_v1", red, blue, "Valid V1", directory=tmp_path)
    (tmp_path / "missing_fields.json").write_text(json.dumps({"id": "missing_fields"}), encoding="utf-8")

    saved = list_saved_layouts(directory=tmp_path)

    assert [layout.id for layout in saved] == ["valid_v1"]


def test_load_layout_rejects_invalid_schema(tmp_path) -> None:
    from ai.opening_layouts import load_layout

    (tmp_path / "broken.json").write_text(json.dumps({"id": "broken"}), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid layout file"):
        load_layout("broken", directory=tmp_path)
