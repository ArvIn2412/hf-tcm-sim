"""Synthetic bundle tests; no historical data or checksum baseline is rewritten."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.ci import verify_historical_bundle as verifier


def _bundle(root: Path) -> Path:
    archive = root / "HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip"
    archive.write_bytes(b"synthetic fixture, not an original archive")
    record = root / "outputs/scientific_exp_01/archive_verification.json"
    record.parent.mkdir(parents=True)
    record.write_text(
        json.dumps(
            {
                "archive_path": archive.name,
                "archive_size": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        )
    )
    manifest = root / "outputs/ci/historical-artifacts.sha256"
    manifest.parent.mkdir()
    manifest.write_text(
        hashlib.sha256(record.read_bytes()).hexdigest()
        + "  "
        + record.relative_to(root).as_posix()
        + "\n"
    )
    return archive


def test_missing_bundle_is_explicitly_blocked(tmp_path):
    with pytest.raises(verifier.MissingHistoricalArtifact, match="BLOCKED_MISSING_ARTIFACT"):
        verifier.verify_bundle(tmp_path)


def test_missing_exp01_archive_is_blocked_without_faking_test_results(tmp_path):
    archive = _bundle(tmp_path)
    archive.unlink()
    with pytest.raises(verifier.MissingHistoricalArtifact, match=archive.name):
        verifier.verify_bundle(tmp_path)


def test_bundle_hashes_are_verified_and_mismatch_is_failure(tmp_path):
    archive = _bundle(tmp_path)
    verified = verifier.verify_bundle(tmp_path)
    assert archive in verified
    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="mismatch"):
        verifier.verify_bundle(tmp_path)


def test_bundle_rejects_escape_before_reading_outside_files(tmp_path):
    _bundle(tmp_path)
    (tmp_path / "outputs/ci/historical-artifacts.sha256").write_text(
        "0" * 64 + "  outputs/../../outside\n"
    )
    with pytest.raises(ValueError, match="safe outputs"):
        verifier.verify_bundle(tmp_path)


def test_install_refuses_to_replace_existing_different_historical_bytes(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _bundle(bundle)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(verifier, "ROOT", checkout)
    protected = checkout / verifier.EXP01_METADATA
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"existing bytes must stay unchanged")
    with pytest.raises(ValueError, match="refusing to replace"):
        verifier.install_verified(bundle, verifier.verify_bundle(bundle))
    assert protected.read_bytes() == b"existing bytes must stay unchanged"
