"""Build a versioned onedir preview without replacing prior distributions."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from desktop_qt.version import VERSION


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output = (args.output_dir or ROOT / "dist" / f"desktop-preview-{datetime.now():%Y%m%d-%H%M%S}").resolve()
    if output.exists():
        parser.error("output-dir already exists; use a new directory")
    output.mkdir(parents=True)
    work = ROOT / "build" / output.name
    command = [sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "desktop_preview.spec"),
               "--distpath", str(output), "--workpath", str(work), "--noconfirm"]
    build_environment = os.environ.copy()
    build_environment.pop("PYTHONHOME", None)
    build_environment.pop("PYTHONPATH", None)
    if sys.platform == "win32":
        windows = Path(os.environ["SystemRoot"])
        # Do not collect same-named DLLs from unrelated tools on the caller PATH.
        # In particular, Poppler's ICU DLL is not Windows' ICU API expected by Qt.
        build_environment["PATH"] = os.pathsep.join((str(Path(sys.executable).parent),
                                                    sys.base_prefix, str(windows / "System32"), str(windows)))
    subprocess.run(command, cwd=ROOT, env=build_environment, check=True)
    app_dir = output / "EinsteinChess-preview"
    shutil.copy2(ROOT / "docs" / "DESKTOP_PREVIEW.md", app_dir / "使用说明.md")
    shutil.copy2(ROOT / "LICENSE", app_dir / "LICENSE.txt")
    license_dir = app_dir / "third-party-licenses"
    license_dir.mkdir()
    for package in ("PySide6-Essentials", "shiboken6", "PyInstaller"):
        dist = metadata.distribution(package)
        for entry in dist.files or ():
            if any("license" in part.lower() or "copying" in part.lower() for part in entry.parts):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    destination = license_dir / package / str(entry).replace("..", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    manifest = {
        "version": VERSION, "python": sys.version,
        "packages": {name: metadata.version(name) for name in
                     ("PySide6-Essentials", "shiboken6", "PyInstaller", "pyinstaller-hooks-contrib")},
        "default_params_sha256": hashlib.sha256((ROOT / "release/v1.0/default_params.json").read_bytes()).hexdigest(),
        "files": {path.relative_to(app_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(app_dir.rglob("*")) if path.is_file()},
    }
    (app_dir / "build-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = shutil.make_archive(str(output / "EinsteinChess-preview-windows-x64"), "zip", output, app_dir.name)
    print(json.dumps({"exe": str(app_dir / "EinsteinChess.exe"), "zip": archive,
                      "sha256": hashlib.sha256(Path(archive).read_bytes()).hexdigest()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
