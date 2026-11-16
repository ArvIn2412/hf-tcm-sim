"""Count-only analysis checks; no receiver or Monte Carlo experiment calls."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analyze_energy_exp01.py"
_SPEC = importlib.util.spec_from_file_location("energy_exp01_analysis", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
analysis = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analysis)


def row(phase: str = "pilot", sweep: str = "amplitude", errors: int = 0) -> dict:
    return {
        "phase": phase,
        "scenario": "awgn",
        "sweep": sweep,
        "gamma_db": 6,
        "status": "completed",
        "bits": 100,
        "pairs": 50,
        "bit_errors": {"joint": errors, "b0": errors},
        "pair_errors": {"joint": errors, "b0": errors},
        "frame_errors": {"joint": int(errors > 0), "b0": int(errors > 0)},
        "frame_symbols": 50,
        "seeds": {"bits": 1, "fading": 2, "noise": 3},
        "runtime_seconds": {"joint": 0.2, "b0": 0.1},
        "elapsed_seconds": 0.4,
        "eb_d": 4,
        "amplitude": 1,
        "noise_variance": 1,
        "source": {"path": "synthetic", "sha256": "synthetic", "seeds": {}},
    }


def save_record(root: Path, value: dict, name: str = "t00") -> Path:
    path = root / value["phase"] / value["scenario"] / value["sweep"] / name / "record.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    path.with_name("manifest.json").write_text(
        json.dumps({"files": {"record.json": hashlib.sha256(raw).hexdigest()}})
    )
    return path


def test_zero_observations_report_frame_upper_bound_and_missing_memory() -> None:
    point = analysis.summarize_points([row() for _ in range(3)], 40, 9)[0]
    assert point["ber"]["joint"] == 0
    assert point["ci95"]["ber"]["joint"] == [0, 0]
    assert point["zero_error_fer_upper95"]["joint"] == pytest.approx(1 - 0.05 ** (1 / 3))
    assert point["saved_array_bytes"]["max"] is None
    assert point["peak_working_set_process_bytes"]["max"] is None
    assert point["fer_wilson_ci95"]["joint"][1] > 0


def test_wilson_frame_intervals_remain_nondegenerate_at_both_boundaries() -> None:
    zero = analysis.wilson_frame_interval(0, 20)
    all_error = analysis.wilson_frame_interval(20, 20)
    assert zero == pytest.approx([0, 0.16112515805281938])
    assert all_error == pytest.approx([1 - zero[1], 1])
    point = analysis.summarize_points([row(errors=1) for _ in range(20)], 30, 7)[0]
    assert point["all_error_fer_lower95"]["joint"] == pytest.approx(0.05 ** (1 / 20))
    assert point["ci95"]["fer"]["joint"] == [1, 1]
    assert point["fer_wilson_ci95"]["joint"][0] < 1


def test_linear_sensitivity_can_use_zero_without_changing_log_primary() -> None:
    points = [{"gamma_db": 0, "ber": {"joint": 0.1}}, {"gamma_db": 2, "ber": {"joint": 0}}]
    assert analysis.linear_ber_crossing(points, 0.05, "joint")["required_gamma_db"] == 1


def test_manifested_count_analysis_preserves_phases_and_independent_sweeps(tmp_path: Path) -> None:
    save_record(tmp_path, row("pilot"))
    save_record(tmp_path, row("confirmatory", errors=4))
    save_record(tmp_path, row("confirmatory", sweep="noise", errors=2))
    summary = analysis.analyze(tmp_path, [0.05], 20, 1, plots=False)
    assert summary["groups"] == 3
    aggregates = json.loads((tmp_path / "analysis/aggregates.json").read_text(encoding="utf-8"))
    assert all(group["points"][0]["trials"] == 1 for group in aggregates["groups"])
    comparisons = json.loads(
        (tmp_path / "analysis/sweep_comparison.json").read_text(encoding="utf-8")
    )
    assert len(comparisons["comparisons"]) == 2
    assert comparisons["comparisons"][0]["difference_amplitude_minus_noise"][
        "ber"
    ] == pytest.approx(0.02)
    gains = json.loads((tmp_path / "analysis/gains.json").read_text(encoding="utf-8"))
    noise = next(value for value in gains["analyses"] if value["sweep"] == "noise")
    assert "actual transmitted Eb,d remains fixed" in noise["energy_interpretation"]


def test_hash_mismatch_rejected_and_uncommitted_record_excluded(tmp_path: Path) -> None:
    path = save_record(tmp_path, row())
    path.write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        analysis.load_records(tmp_path)
    path.with_name("manifest.json").unlink()
    rows, excluded = analysis.load_records(tmp_path)
    assert not rows
    assert len(excluded) == 1
