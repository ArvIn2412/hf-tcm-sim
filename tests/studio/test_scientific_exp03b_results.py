from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from hf_tcm.studio import scientific_exp03b_results as archive
from hf_tcm.studio.scientific_exp03b_results import _verify_study, load_exp03b_analysis


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_verified_hash_cache_rechecks_edits_and_missing_files(tmp_path, monkeypatch):
    path = tmp_path / "payload"
    path.write_bytes(b"original")
    calls = []
    original = archive.sha256_file

    def counted(file):
        calls.append(file)
        return original(file)

    monkeypatch.setattr(archive, "sha256_file", counted)
    first = archive._checked_sha(path)
    assert archive._checked_sha(path) == first
    assert len(calls) == 1
    stat = path.stat()
    path.write_bytes(b"modified")  # Same size and restored mtime must not reuse SHA.
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert archive._checked_sha(path) != first
    assert len(calls) == 2
    path.unlink()
    with pytest.raises(FileNotFoundError):
        archive._checked_sha(path)


def test_hash_cache_does_not_accept_a_file_changed_while_hashing(tmp_path, monkeypatch):
    path = tmp_path / "payload"
    path.write_bytes(b"before")

    def changed(file):
        digest = _sha(file.read_bytes())
        file.write_bytes(b"after modification")
        return digest

    monkeypatch.setattr(archive, "sha256_file", changed)
    with pytest.raises(ValueError, match="changed during integrity verification"):
        archive._checked_sha(path)


def test_gui_result_loader_rejects_analysis_without_valid_digest(tmp_path: Path) -> None:
    analysis_path = tmp_path / "independent_analysis.json"
    analysis_path.write_text("{}\n", encoding="utf-8")
    (tmp_path / "analysis_manifest.json").write_text(
        json.dumps({"analysis_sha256": "0" * 64, "protocol_sha256": "0" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="analysis SHA-256"):
        load_exp03b_analysis(
            analysis_path,
            Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"),
            tmp_path,
        )


def test_gui_result_loader_rejects_incomplete_series_provenance(tmp_path: Path) -> None:
    protocol_raw = Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json").read_bytes()
    protocol_hash = _sha(protocol_raw)
    analysis_path = tmp_path / "independent_analysis.json"
    protocol = json.loads(protocol_raw)
    scenario_keys = [row["id"] for row in protocol["metric_isolation"]["scenarios"]]
    sweep_names = protocol["metric_isolation"]["sweeps"]
    analysis = {
        "protocol_sha256": protocol_hash,
        "preflight_included": False,
        "metric_isolation": {
            scenario: {sweep: {"provenance": {"manifest_sha256": "x"}} for sweep in sweep_names}
            for scenario in scenario_keys
        },
        "full_system_comparison": {
            scenario: {"provenance": {"manifest_sha256": "x"}}
            for scenario in protocol["system_comparison"]["energy_grid_gamma_db"]
        },
    }
    analysis_bytes = (json.dumps(analysis) + "\n").encode("utf-8")
    analysis_path.write_bytes(analysis_bytes)
    (tmp_path / "analysis_manifest.json").write_text(
        json.dumps(
            {
                "analysis_sha256": _sha(analysis_bytes),
                "protocol_sha256": protocol_hash,
                "confirmatory_only": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="confirmatory study manifest"):
        load_exp03b_analysis(
            analysis_path, Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"), tmp_path
        )


def test_saved_gui_series_rejects_changed_record_payload(tmp_path: Path) -> None:
    protocol_hash = "c" * 64
    study_root = tmp_path / "study"
    study_root.mkdir()
    record_path = study_root / "trial.json"
    array_path = study_root / "trial.npz"
    record_path.write_bytes(b"immutable record")
    array_path.write_bytes(b"immutable array")
    checkpoint_path = study_root / "checkpoint.jsonl"
    checkpoint_path.write_text(
        json.dumps(
            {
                "trial_id": "trial-0001",
                "record_path": "trial.json",
                "record_sha256": _sha(record_path.read_bytes()),
                "array_path": "trial.npz",
                "array_sha256": _sha(array_path.read_bytes()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = study_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "protocol_sha256": protocol_hash,
                "completed_trials": 1,
                "planned_trials": 1,
                "checkpoint_sha256": _sha(checkpoint_path.read_bytes()),
            }
        ),
        encoding="utf-8",
    )
    manifest_hash = _sha(manifest_path.read_bytes())

    _verify_study(study_root, protocol_hash, 1, manifest_hash)
    record_path.write_bytes(b"changed after analysis")

    with pytest.raises(ValueError, match="record SHA-256 mismatch"):
        _verify_study(study_root, protocol_hash, 1, manifest_hash)
