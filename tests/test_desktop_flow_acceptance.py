"""完整桌面控制器流程可在未安装 Qt 的研究环境独立验收。"""

from pathlib import Path

import pytest

from desktop_qt.acceptance import run_flow_acceptance


def test_complete_flow_acceptance_uses_real_session_and_isolated_records(tmp_path):
    result = run_flow_acceptance(tmp_path)
    assert result["checks"]
    assert all(result["checks"].values())
    assert result["statistics"]["role_color_cases"] == 4
    assert result["statistics"]["first_mover_checks"] == 28
    assert result["statistics"]["completed_match_games"] == 11
    assert result["statistics"]["match_restarts"] == 11
    assert result["statistics"]["scores"] == [[4, 0], [4, 3]]
    root = Path(result["data_dir"])
    assert root.parent == tmp_path
    assert (root / "sweep" / "completed-match.json").is_file()
    assert (root / "seven-games" / "completed-match.json").is_file()
    assert (root / "corrupt" / "recovery" / "auto_save.json").read_bytes() == b'{"broken":'


def test_flow_acceptance_propagates_failed_controller_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr("desktop_qt.acceptance.MatchSession.retry_save", lambda self: False)
    with pytest.raises(AssertionError):
        run_flow_acceptance(tmp_path)
