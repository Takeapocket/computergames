from pathlib import Path

from scripts import s2_rehearsal


def test_s2_rehearsal_scenario_cleans_temp_dirs(monkeypatch) -> None:
    created: list[Path] = []
    original_mkdtemp = s2_rehearsal.tempfile.mkdtemp

    def tracking_mkdtemp(*args, **kwargs) -> str:
        path = Path(original_mkdtemp(*args, **kwargs))
        created.append(path)
        return str(path)

    monkeypatch.setattr(s2_rehearsal.tempfile, "mkdtemp", tracking_mkdtemp)

    name, passed, detail = s2_rehearsal.scenario_4_0()

    assert name == "4:0 整轮"
    assert passed, detail
    assert created
    assert all(not path.exists() for path in created)
