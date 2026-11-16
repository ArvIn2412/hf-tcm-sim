"""Read-only recount of REPRO-10's inconsistent legacy SER labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from hf_tcm.studio.scientific import load_run_summary

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "F256": "run-20261110-121002-fa58a96e",
    "F32": "run-20261110-115623-ccedf172",
}


def recount(run_id: str) -> dict[str, object]:
    run_dir = ROOT / "outputs" / "repro09" / run_id
    summary_path, trace_path = run_dir / "summary.json", run_dir / "traces.npz"
    summary_before = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    trace_before = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    old_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    loaded = load_run_summary(run_dir)
    with np.load(trace_path, allow_pickle=False) as arrays:
        ref = arrays["information_bits"].astype(np.int8)
        decoded = arrays["separate_decoded_bits"][: ref.size].astype(np.int8)
        phase_errors = int(
            np.count_nonzero(
                arrays["hard_phase_indices"][: arrays["phase_indices"].size]
                != arrays["phase_indices"]
            )
        )
        phase_count = int(arrays["phase_indices"].size)
    bit_mask = decoded != ref
    pair_errors = int(bit_mask.reshape((-1, 2)).any(axis=1).sum())
    bit_errors = int(bit_mask.sum())
    if not pair_errors <= bit_errors <= 2 * pair_errors:
        raise AssertionError("Recounted pair/bit errors violate the two-bit grouping invariant")
    result = {
        "run_id": run_id,
        "frame_symbols": old_summary["frame_symbols"],
        "observation_sha256": old_summary["receiver_observation_sha256"],
        "summary_sha256_before": summary_before,
        "trace_sha256_before": trace_before,
        "legacy_ser_semantics": "hard_demodulated_8psk_phase_symbol",
        "legacy_phase_errors": old_summary["separate"]["symbol_errors"],
        "legacy_phase_ser": old_summary["separate"]["ser"],
        "recounted_information_bit_errors": bit_errors,
        "recounted_information_pair_errors": pair_errors,
        "recounted_information_pair_ser": pair_errors / (ref.size // 2),
        "recounted_phase_symbol_errors": phase_errors,
        "recounted_phase_symbol_ser": phase_errors / phase_count,
        "enriched_read_only_summary_pair_errors": loaded["separate"]["information_pair_errors"],
        "bit_error_count_invariant": pair_errors <= bit_errors <= 2 * pair_errors,
        "old_summary_file_unchanged": hashlib.sha256(summary_path.read_bytes()).hexdigest()
        == summary_before,
        "old_trace_file_unchanged": hashlib.sha256(trace_path.read_bytes()).hexdigest()
        == trace_before,
    }
    if result["legacy_phase_errors"] != phase_errors:
        raise AssertionError("Archived legacy SER no longer matches phase-error recount")
    if result["enriched_read_only_summary_pair_errors"] != pair_errors:
        raise AssertionError("Read-only summary enrichment differs from independent recount")
    return result


def main() -> None:
    report = {label: recount(run_id) for label, run_id in CASES.items()}
    output_dir = ROOT / "outputs" / "repro10a" / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "legacy_pair_ser_recount.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
