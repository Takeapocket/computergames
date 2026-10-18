from pathlib import Path

import pytest

from desktop_qt.paths import resolve_data_dir


def test_frozen_data_is_next_to_executable_not_cwd(tmp_path, monkeypatch):
    from desktop_qt import paths
    package = tmp_path / "中文 便携目录"
    package.mkdir()
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(package / "EinsteinChess.exe"))
    monkeypatch.chdir(tmp_path)
    result = resolve_data_dir()
    assert result == package / "user-data"
    assert (result / "records").is_dir()
    assert (result / "logs").is_dir()


def test_explicit_data_directory_is_honored(tmp_path):
    result = resolve_data_dir(tmp_path / "chosen")
    assert result == tmp_path / "chosen"
    assert sorted(path.name for path in result.iterdir()) == ["layouts", "logs", "records", "recovery"]


def test_invalid_data_directory_fails_instead_of_silent_fallback(tmp_path):
    invalid = tmp_path / "file"
    invalid.write_text("keep", encoding="utf-8")
    with pytest.raises(OSError):
        resolve_data_dir(invalid)
    assert invalid.read_text(encoding="utf-8") == "keep"


def test_recommendation_worker_import_does_not_import_tk():
    import subprocess
    import sys
    subprocess.run([sys.executable, "-c", "import gui.recommendation_worker; import sys; assert 'tkinter' not in sys.modules"],
                   cwd=Path(__file__).resolve().parents[1], check=True)
