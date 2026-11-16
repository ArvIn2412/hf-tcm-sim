"""CLI smoke tests for both module invocation and exit codes."""

from pathlib import Path

from hf_tcm.cli import main


def test_doctor(capsys) -> None:
    assert main(["doctor"]) == 0
    captured = capsys.readouterr()
    assert "M3 channel model core ready" in captured.out
    assert "experiment CLI runner not implemented" in captured.out
    assert "blocked on open SCI-02 through SCI-04" in captured.out


def test_check_config(capsys) -> None:
    config = Path(__file__).resolve().parents[1] / "configs" / "m0_smoke.json"
    assert main(["check-config", str(config)]) == 0
    assert "no simulation" in capsys.readouterr().out


def test_check_config_failure(capsys, tmp_path: Path) -> None:
    assert main(["check-config", str(tmp_path / "bad.json")]) == 2
    assert "Invalid config" in capsys.readouterr().err
