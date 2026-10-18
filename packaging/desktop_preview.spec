# Build using the isolated .venv-desktop environment; old Tk stays in source.
from pathlib import Path
import os

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "scripts" / "run_desktop.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "release" / "v1.0" / "default_params.json"), "release/v1.0"),
        (str(root / "desktop_qt" / "assets" / "app.ico"), "desktop_qt/assets"),
    ],
    hiddenimports=[],
    excludes=["tkinter", "_tkinter", "PyQt5", "PyQt6", "PySide2", "numpy", "torch", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="EinsteinChess",
          debug=False, strip=False, upx=False, console=os.environ.get("CG_DESKTOP_CONSOLE") == "1",
          icon=str(root / "desktop_qt" / "assets" / "app.ico"))
coll = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False,
               name="EinsteinChess-preview")
