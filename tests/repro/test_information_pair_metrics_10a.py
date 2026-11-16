from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.repro.information_pair_metrics import evaluate_information_pair_errors
from hf_tcm.studio.scientific import (
    ScientificRunConfig,
    load_run_summary,
    run_scientific_run,
)


def test_information_pair_errors_are_recounted_from_the_same_decoded_bits() -> None:
    reference = np.asarray([0, 1, 1, 0, 0, 1, 1, 1], dtype=np.int8)
    decoded = np.asarray([0, 0, 0, 0, 0, 1, 0, 1], dtype=np.int8)

    result = evaluate_information_pair_errors(reference, decoded)

    assert result.compared_bits == 8
    assert result.bit_errors == 3
    assert result.bit_error_positions.tolist() == [1, 2, 6]
    assert result.compared_pairs == 4
    assert result.pair_errors == 3
    assert result.pair_error_positions.tolist() == [0, 1, 3]
    assert result.ber == pytest.approx(3 / 8)
    assert result.pair_ser == pytest.approx(3 / 4)
    assert result.pair_errors <= result.bit_errors <= 2 * result.pair_errors


def test_pair_error_count_is_not_phase_symbol_error_count() -> None:
    reference = np.asarray([0, 0, 1, 1, 1, 0], dtype=np.int8)
    decoded = np.asarray([0, 1, 1, 1, 1, 0], dtype=np.int8)
    hard_demodulated_phase_errors = 3

    result = evaluate_information_pair_errors(reference, decoded)

    assert result.bit_errors == 1
    assert result.pair_errors == 1
    assert hard_demodulated_phase_errors > result.pair_errors


def test_legacy_summary_gets_read_only_pair_metrics_from_saved_bits(tmp_path: Path) -> None:
    root = tmp_path
    run_scientific_run(
        ScientificRunConfig(
            run_id="legacy-pair-audit",
            frame_symbols=32,
            source_seed=101,
            channel_seed=303,
            channel_profile="rician_ar1_multipath",
            noise_variance=0.005,
            output_root=str(root),
            delays_samples=(0, 3),
        )
    )
    run_dir = root / "legacy-pair-audit"
    summary_path, manifest_path = run_dir / "summary.json", run_dir / "manifest.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.pop("metric_labels_version", None)
    summary.pop("pair_metrics_recomputed_from_saved_bits", None)
    for arm_name in ("joint", "separate"):
        arm = summary[arm_name]
        for key in (
            "compared_information_pairs",
            "information_pair_errors",
            "information_pair_ser",
            "information_pair_error_positions",
            "phase_symbol_errors",
            "phase_symbol_ser",
            "phase_symbol_error_positions",
            "compared_phase_symbols",
            "symbol_metric_semantics",
        ):
            arm.pop(key, None)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    original_summary, original_trace = (
        summary_path.read_bytes(),
        (run_dir / "traces.npz").read_bytes(),
    )

    loaded = load_run_summary(run_dir)

    assert loaded["pair_metrics_recomputed_from_saved_bits"] is True
    assert "information_pair_errors" in loaded["separate"]
    assert loaded["separate"]["phase_symbol_ser"] == loaded["separate"]["ser"]
    assert summary_path.read_bytes() == original_summary
    assert (run_dir / "traces.npz").read_bytes() == original_trace


def test_scientific_run_reports_pair_and_phase_errors_as_distinct_metrics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "scientific-run"
    summary = run_scientific_run(
        ScientificRunConfig(
            run_id="metrics-audit",
            frame_symbols=32,
            source_seed=101,
            channel_seed=303,
            channel_profile="rician_ar1_multipath",
            noise_variance=0.005,
            output_root=str(root),
            delays_samples=(0, 3),
        )
    )
    with np.load(root / "metrics-audit" / "traces.npz") as traces:
        reference = traces["information_bits"]
        decoded = traces["separate_decoded_bits"][: reference.size]
        phases = traces["phase_indices"]
        hard_phases = traces["hard_phase_indices"][: phases.size]

    bit_error_mask = decoded != reference
    pair_error_mask = bit_error_mask.reshape((-1, 2)).any(axis=1)
    phase_error_mask = hard_phases != phases
    separate = summary["separate"]

    assert separate["bit_errors"] == int(bit_error_mask.sum())
    assert separate["information_pair_errors"] == int(pair_error_mask.sum())
    assert separate["phase_symbol_errors"] == int(phase_error_mask.sum())
    assert separate["symbol_metric_semantics"] == "hard_demodulated_8psk_phase_symbol"
    assert separate["ser"] == separate["phase_symbol_ser"]
    assert separate["information_pair_errors"] <= separate["bit_errors"]
    assert separate["bit_errors"] <= 2 * separate["information_pair_errors"]


@pytest.mark.parametrize(
    ("reference", "decoded"),
    [
        ([0, 1], [0]),
        ([0], [0]),
        ([0, 2], [0, 1]),
        ([0.0, 1.0], [0, 1]),
    ],
)
def test_pair_metrics_reject_malformed_bit_sequences(
    reference: list[int] | list[float], decoded: list[int]
) -> None:
    with pytest.raises((TypeError, ValueError)):
        evaluate_information_pair_errors(reference, decoded)
