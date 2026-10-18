"""Writable portable data stays outside bundled, read-only resources."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def resolve_data_dir(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
    elif getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "user-data"
    else:
        root = Path(__file__).resolve().parents[1] / "user-data" / "desktop-preview"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("records", "logs", "recovery", "layouts"):
        directory = root / name
        directory.mkdir(exist_ok=True)
        # Fail visibly at startup instead of silently losing a game later.
        with tempfile.TemporaryFile(dir=directory):
            pass
    return root
