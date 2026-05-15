from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path
import tkinter as tk

import pytest


_SHARED_ROOT: tk.Tk | None = None


def configure_tk_library_paths() -> None:
    """Ensure Tcl/Tk can find Python's bundled initialization scripts."""
    _set_library_path_if_present("TCL_LIBRARY", "tcl8.6", "init.tcl")
    _set_library_path_if_present("TK_LIBRARY", "tk8.6", "tk.tcl")


def make_hidden_tk_root() -> tk.Tk:
    global _SHARED_ROOT
    if _SHARED_ROOT is not None:
        try:
            if _SHARED_ROOT.winfo_exists():
                return _SHARED_ROOT
        except tk.TclError:
            _SHARED_ROOT = None

    try:
        root = _create_hidden_root()
    except tk.TclError as first_exc:
        configure_tk_library_paths()
        try:
            root = _create_hidden_root()
        except tk.TclError as exc:
            pytest.skip(f"no Tk display available: {first_exc}; after Tcl/Tk path repair: {exc}")
    _SHARED_ROOT = root
    return root


def _create_hidden_root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()
    return root


def _set_library_path_if_present(env_var: str, directory_name: str, marker_file: str) -> None:
    if os.environ.get(env_var):
        return
    candidate = Path(sys.base_prefix) / "tcl" / directory_name
    if (candidate / marker_file).is_file():
        os.environ[env_var] = str(candidate)


def _destroy_shared_root() -> None:
    global _SHARED_ROOT
    if _SHARED_ROOT is None:
        return
    try:
        if _SHARED_ROOT.winfo_exists():
            _SHARED_ROOT.destroy()
    except tk.TclError:
        pass
    _SHARED_ROOT = None


atexit.register(_destroy_shared_root)
