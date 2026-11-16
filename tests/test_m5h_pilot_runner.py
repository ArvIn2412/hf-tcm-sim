from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from hf_tcm.evaluation.m5h_pilot_runner import (
    _memory_status_windows,
    _process_rss_windows,
    create_approved_run_config,
    load_run_checkpoints,
    write_run_checkpoint,
)


def test_approved_config_is_separate_and_contains_runtime_provenance(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    source = root / "configs/m5h_pilot_draft.json"
    before = source.read_bytes()
    approved_path = tmp_path / "approved.json"
    approved = create_approved_run_config(
        source,
        approved_path,
        code_paths=(root / "src/hf_tcm/evaluation/m5h_pilot_protocol.py",),
        available_memory_before_bytes=5 * 1024**3,
        runtime_utc="2026-10-29T10:00:00+00:00",
    )
    assert approved["design_status"] == "approved_for_pilot"
    assert approved["execution_authorized"] is True
    assert approved["execution_scope"] == "m5h_pilot_only"
    assert source.read_bytes() == before
    assert approved["authorization_provenance"]["execution_date_time_utc"]
    assert approved["source_draft_sha256"] == hashlib.sha256(before).hexdigest()
    assert approved["code_fingerprint"]
    assert approved["authorization_provenance"]["code_fingerprint"] == approved["code_fingerprint"]


def test_checkpoint_round_trip_and_fingerprint_mismatch_rejection(tmp_path: Path) -> None:
    checkpoints = tmp_path / "checkpoints"
    record = {
        "run_id": "pilot:gamma-5:run-001",
        "status": "completed",
        "b_bit_errors": 3,
        "c_bit_errors": 8,
    }
    write_run_checkpoint(
        checkpoints,
        record,
        config_fingerprint="a" * 64,
        code_fingerprint="b" * 64,
    )
    loaded = load_run_checkpoints(
        checkpoints,
        expected_config_fingerprint="a" * 64,
        expected_code_fingerprint="b" * 64,
    )
    assert loaded == {record["run_id"]: record}
    with pytest.raises(ValueError, match="fingerprint"):
        load_run_checkpoints(
            checkpoints,
            expected_config_fingerprint="c" * 64,
            expected_code_fingerprint="b" * 64,
        )


def test_checkpoint_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    checkpoints = tmp_path / "checkpoints"
    first = {"run_id": "duplicate", "status": "completed"}
    write_run_checkpoint(
        checkpoints,
        first,
        config_fingerprint="a" * 64,
        code_fingerprint="b" * 64,
    )
    second_path = checkpoints / "manual-duplicate.json"
    second_path.write_text(
        json.dumps(
            {
                "run_id": "duplicate",
                "config_fingerprint": "a" * 64,
                "code_fingerprint": "b" * 64,
                "record": first,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate run_id"):
        load_run_checkpoints(
            checkpoints,
            expected_config_fingerprint="a" * 64,
            expected_code_fingerprint="b" * 64,
        )


def test_windows_resource_measurements_are_reported_when_supported() -> None:
    memory = _memory_status_windows()
    if memory is not None:
        available, total = memory
        assert 0 < available <= total
    rss = _process_rss_windows(os.getpid())
    assert rss is None or rss > 0
