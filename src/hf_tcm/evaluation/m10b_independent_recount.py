"""Independent, read-only M10b checkpoint recount after runner completion.

This module does not run a receiver or create experimental observations. It
reconstructs stored paired inputs from the approved seeds, recounts decoded
arrays, and computes the predeclared run-cluster statistics.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.evaluation.controlled_piecewise_real_gain import (
    PROFILE_IDS,
    apply_symbol_gain_schedule,
    build_gain_schedule,
)
from hf_tcm.evaluation.error_metrics import encode_reference_symbol_indices
from hf_tcm.evaluation.m10a_variable_gain_study_design import (
    EXPECTED_SEED_ROOTS,
    PARTITION_CODE,
    PROTOCOL_WORD,
    STUDY_ID,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import generate_independent_complex_awgn
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label, label_to_index
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICIES = ("historical_frozen_B", "anch_a085_k025")
SIGMA_SQUARED = 0.7115124735378853
BOOTSTRAP_REPLICATES = 2000


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complex_hash(values: np.ndarray) -> str:
    raw = np.asarray(values, dtype="<c16", order="C").tobytes(order="C")
    return hashlib.sha256(raw).hexdigest()


def _decode_complex(encoded: str) -> np.ndarray:
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) != 2048 * 16:
        raise ValueError("checkpoint complex vector must have 2048 complex128 samples")
    return np.frombuffer(raw, dtype="<c16").astype(np.complex128, copy=True)


def _expected_seed(master: int, run_index: int, stream_code: int) -> dict[str, Any]:
    spawn_key = [PROTOCOL_WORD, PARTITION_CODE, run_index, stream_code]
    child = np.random.SeedSequence(master, spawn_key=tuple(spawn_key)).generate_state(
        1, dtype=np.uint64
    )[0]
    return {
        "master_seed": master,
        "spawn_key": spawn_key,
        "derived_seed": int(child),
        "generator": "PCG64",
        "initialized": False,
    }


def _checkpoint_seed_provenance(checkpoint: dict[str, Any], index: int) -> bool:
    expected = {
        "data": _expected_seed(EXPECTED_SEED_ROOTS["data"], index, 11),
        "noise": _expected_seed(EXPECTED_SEED_ROOTS["noise"], index, 23),
        "metadata": _expected_seed(EXPECTED_SEED_ROOTS["metadata"], index, 41),
    }
    actual = checkpoint.get("seed_provenance", {})
    if set(actual) != set(expected):
        return False
    for name, row in expected.items():
        actual_row = actual[name]
        for field in ("master_seed", "spawn_key", "derived_seed", "generator"):
            if actual_row.get(field) != row[field]:
                return False
        expected_initialized = name in ("data", "noise")
        if actual_row.get("initialized") is not expected_initialized:
            return False
    return True


def _rebuild_waveform(bits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    symbol_indices = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(symbol), profile=BASELINE_ASSUMPTION) for symbol in symbol_indices]
    samples = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    in_phase, quadrature = symbols_to_iq_waveform(samples, samples_per_symbol=8)
    waveform = np.asarray(in_phase + 1j * quadrature, dtype=np.complex128)
    return np.asarray(symbol_indices, dtype=np.int64), waveform


def _summary_from_runs(runs: list[dict[str, Any]], bootstrap_seed: int) -> dict[str, Any]:
    bootstrap_started = time.perf_counter()
    profile_points: dict[str, dict[str, Any]] = {}
    for profile_id in PROFILE_IDS:
        aggregate = {
            policy: {"bit_errors": 0, "total_bits": 0, "symbol_errors": 0, "total_symbols": 0}
            for policy in POLICIES
        }
        for run in runs:
            for policy in POLICIES:
                counts = run["profiles"][profile_id][policy]
                for field in aggregate[policy]:
                    aggregate[policy][field] += counts[field]
        for policy in POLICIES:
            counts = aggregate[policy]
            if counts["total_bits"] != 51200 or counts["total_symbols"] != 25600:
                raise ValueError("independent pooled denominators differ from the frozen design")
            counts["ber"] = counts["bit_errors"] / counts["total_bits"]
            counts["ser"] = counts["symbol_errors"] / counts["total_symbols"]
        profile_points[profile_id] = {
            **aggregate,
            "delta_bit_errors": aggregate[POLICIES[1]]["bit_errors"]
            - aggregate[POLICIES[0]]["bit_errors"],
            "delta_ber": aggregate[POLICIES[1]]["ber"] - aggregate[POLICIES[0]]["ber"],
            "delta_symbol_errors": aggregate[POLICIES[1]]["symbol_errors"]
            - aggregate[POLICIES[0]]["symbol_errors"],
            "delta_ser": aggregate[POLICIES[1]]["ser"] - aggregate[POLICIES[0]]["ser"],
        }

    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    indices = rng.integers(0, len(runs), size=(BOOTSTRAP_REPLICATES, len(runs)), dtype=np.int64)
    outcomes = np.empty((BOOTSTRAP_REPLICATES, 8), dtype=np.float64)
    columns = (
        "DeltaBER_P0",
        "DeltaBER_P1",
        "DeltaBER_P2",
        "DeltaSER_P0",
        "DeltaSER_P1",
        "DeltaSER_P2",
        "DeltaBER_P1_minus_P0",
        "DeltaBER_P2_minus_P1",
    )
    for replicate, selected in enumerate(indices):
        bit_delta = [0, 0, 0]
        symbol_delta = [0, 0, 0]
        for run_index in selected:
            run = runs[int(run_index)]
            for profile_index, profile_id in enumerate(PROFILE_IDS):
                pair = run["profiles"][profile_id]
                bit_delta[profile_index] += (
                    pair[POLICIES[1]]["bit_errors"] - pair[POLICIES[0]]["bit_errors"]
                )
                symbol_delta[profile_index] += (
                    pair[POLICIES[1]]["symbol_errors"] - pair[POLICIES[0]]["symbol_errors"]
                )
        ber = [value / (len(runs) * 512) for value in bit_delta]
        ser = [value / (len(runs) * 256) for value in symbol_delta]
        outcomes[replicate] = (
            *ber,
            *ser,
            ber[1] - ber[0],
            ber[2] - ber[1],
        )
    alpha = 0.025
    bounds = np.quantile(outcomes, [alpha, 1 - alpha], axis=0, method="linear")
    intervals = {
        name: [float(bounds[0, index]), float(bounds[1, index])]
        for index, name in enumerate(columns)
    }
    return {
        "cluster_count": len(runs),
        "primary_profile": "P1_HIGH_TO_LOW",
        "primary_delta_ber": profile_points["P1_HIGH_TO_LOW"]["delta_ber"],
        "primary_95_percent_ci": intervals["DeltaBER_P1"],
        "profiles": profile_points,
        "difference_in_differences": {
            "P1_minus_P0_delta_ber": intervals["DeltaBER_P1_minus_P0"],
            "P2_minus_P1_delta_ber": intervals["DeltaBER_P2_minus_P1"],
        },
        "bootstrap": {
            "method": "ADR-014 paired full-run cluster bootstrap",
            "cluster_unit": "one run containing all profiles and both policies",
            "replicates": BOOTSTRAP_REPLICATES,
            "confidence_level": 0.95,
            "interval": "percentile",
            "quantile_method": "numpy.quantile(method='linear')",
            "generator": "PCG64",
            "shared_run_indices_across_all_six_outputs": True,
            "index_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
            "intervals": intervals,
        },
        "bootstrap_wall_clock_seconds": time.perf_counter() - bootstrap_started,
    }


def independent_recount(output_dir: str | Path) -> dict[str, Any]:
    """Verify the frozen M10b outputs without invoking a receiver."""
    root = Path(output_dir)
    approved_path = root / "approved_run_config_snapshot.json"
    approved_hash = root / "approved_run_config.sha256"
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    approved_digest = _file_hash(approved_path)
    if json.loads(approved_hash.read_text(encoding="utf-8"))["sha256"] != approved_digest:
        raise ValueError("approved snapshot copy hash mismatch")
    if approved["design_status"] != "approved_evaluation" or not approved["execution_authorized"]:
        raise ValueError("M10b snapshot is not explicitly approved")
    source_manifest = approved["runtime_provenance"]["source_file_manifest"]
    for relative, expected in source_manifest.items():
        if _file_hash(REPO_ROOT / relative) != expected:
            raise ValueError(f"executed runtime source mismatch: {relative}")

    draft_path = REPO_ROOT / "configs/m10a_variable_gain_study_draft.json"
    if _file_hash(draft_path) != approved["runtime_provenance"]["m10a_draft_sha256"]:
        raise ValueError("M10a draft changed after approval")
    decision_json = REPO_ROOT / "configs/adr_016_controlled_piecewise_real_gain.json"
    decision_doc = REPO_ROOT / "docs/M10_PROPOSED_SCIENTIFIC_DECISION.md"
    if (
        _file_hash(decision_json)
        != approved["accepted_decision_provenance"]["decision_json_sha256"]
    ):
        raise ValueError("accepted ADR-016 JSON fingerprint mismatch")
    if (
        _file_hash(decision_doc)
        != approved["accepted_decision_provenance"]["decision_document_sha256"]
    ):
        raise ValueError("accepted ADR-016 document fingerprint mismatch")

    expected_run_ids = [f"{STUDY_ID}:evaluation:run-{index + 1:03d}" for index in range(100)]
    paths = sorted((root / "checkpoints").glob("run-*.json"))
    if len(paths) != 100:
        raise ValueError(f"expected 100 saved run checkpoints, found {len(paths)}")
    runs: list[dict[str, Any]] = []
    all_received_hashes: set[str] = set()
    decoder_calls = 0
    policy_record_count = 0
    failure_count = 0
    segment_totals: dict[str, dict[str, dict[str, list[int]]]] = {
        profile: {policy: {"pre_switch": [0, 0], "post_switch": [0, 0]} for policy in POLICIES}
        for profile in PROFILE_IDS
    }
    coefficient_norms: dict[str, dict[str, list[float]]] = {
        profile: {policy: [] for policy in POLICIES} for profile in PROFILE_IDS
    }
    for index, path in enumerate(paths):
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("run_id") != expected_run_ids[index]
            or checkpoint.get("run_index") != index
        ):
            raise ValueError("M10 run IDs/indexes are not exact and ordered")
        if checkpoint.get("status") != "complete":
            raise ValueError(f"M10 run is incomplete: {expected_run_ids[index]}")
        if checkpoint.get("approved_config_sha256") != approved_digest:
            raise ValueError("checkpoint approved-config fingerprint mismatch")
        if (
            checkpoint.get("runtime_source_fingerprint_sha256")
            != approved["runtime_provenance"]["runtime_source_fingerprint_sha256"]
        ):
            raise ValueError("checkpoint runtime fingerprint mismatch")
        if not _checkpoint_seed_provenance(checkpoint, index):
            raise ValueError("M10 run seed provenance differs from the frozen spawn derivation")
        data_seed = int(approved["run_manifest"]["runs"][index]["streams"]["data"]["derived_seed"])
        noise_seed = int(
            approved["run_manifest"]["runs"][index]["streams"]["noise"]["derived_seed"]
        )
        data_rng = np.random.Generator(np.random.PCG64(data_seed))
        expected_bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
        common = checkpoint["evaluation_only"]
        bits = np.asarray(common["reference_information_bits"], dtype=np.int8)
        if bits.shape != (512,) or not np.array_equal(bits, expected_bits):
            raise ValueError("M10 information bits do not reproduce from the approved data stream")
        expected_symbols = encode_reference_symbol_indices(
            bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
        )
        symbols = np.asarray(common["reference_symbol_indices"], dtype=np.int64)
        if symbols.shape != (256,) or not np.array_equal(symbols, expected_symbols):
            raise ValueError("M10 M1 encoded symbol sequence mismatch")
        labels = [index_to_label(int(value), profile=BASELINE_ASSUMPTION) for value in symbols]
        samples = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
        i_samples, q_samples = symbols_to_iq_waveform(samples, samples_per_symbol=8)
        waveform = np.asarray(i_samples + 1j * q_samples, dtype=np.complex128)
        saved_waveform = _decode_complex(common["waveform_iq_base64"])
        if (
            not np.array_equal(waveform, saved_waveform)
            or _complex_hash(waveform) != common["waveform_sha256"]
        ):
            raise ValueError("M10 common normalized waveform mismatch")
        expected_noise = np.asarray(
            generate_independent_complex_awgn(
                sample_count=2048,
                sigma_squared=SIGMA_SQUARED,
                seed=noise_seed,
                stream_id=f"M10b:EVALUATION:{expected_run_ids[index]}:shared-noise",
            ).noise,
            dtype=np.complex128,
            order="C",
        )
        saved_noise = _decode_complex(common["noise_iq_base64"])
        if (
            not np.array_equal(expected_noise, saved_noise)
            or _complex_hash(saved_noise) != common["noise_sha256"]
        ):
            raise ValueError(
                "M10 common AWGN vector does not reproduce from the approved noise stream"
            )

        profile_rows = json.loads(json.dumps(checkpoint["profiles"]))
        if [row["profile_id"] for row in profile_rows] != list(PROFILE_IDS):
            raise ValueError("M10 profile order mismatch")
        run = {"run_id": expected_run_ids[index], "profiles": {}}
        for profile_row in profile_rows:
            profile_id = profile_row["profile_id"]
            schedule = build_gain_schedule(profile_id)
            received = apply_symbol_gain_schedule(waveform, saved_noise, schedule)
            received_hash = _complex_hash(received)
            if profile_row.get("received_sha256") != received_hash:
                raise ValueError(f"M10 {profile_id} received hash mismatch")
            all_received_hashes.add(received_hash)
            policy_rows = profile_row.get("policies", [])
            if [row.get("candidate_id") for row in policy_rows] != list(POLICIES):
                raise ValueError("M10 policy ordering/IDs mismatch")
            run["profiles"][profile_id] = {}
            for row in policy_rows:
                policy_record_count += 1
                decoder_calls += int(row.get("decoder_invocations", 0))
                if (
                    row.get("status") != "complete_valid_output"
                    or row.get("decoder_invocations") != 1
                ):
                    failure_count += 1
                    raise ValueError("M10 policy output failure blocks the complete design")
                if row.get("received_sha256") != received_hash:
                    raise ValueError(
                        "B and anchored do not use the same profile-specific received vector"
                    )
                decoded_bits = np.asarray(row["decoded_information_bits"], dtype=np.int8)
                decoded_symbols = np.asarray(row["decoded_symbol_indices"], dtype=np.int64)
                path_ids = [int(value) for value in row["decoded_hypothesis_path"]]
                if (
                    decoded_bits.shape != (512,)
                    or decoded_symbols.shape != (256,)
                    or len(path_ids) != 256
                ):
                    raise ValueError("M10 decoded information/symbol/path dimensions mismatch")
                path_rows = [HYPOTHESES[edge] for edge in path_ids]
                if path_rows[0].current_state != (0, 0) or any(
                    previous.next_state != following.current_state
                    for previous, following in zip(path_rows, path_rows[1:])
                ):
                    raise ValueError("M10 conditional Viterbi path violates M1 trellis continuity")
                path_bits = np.asarray(
                    [bit for edge in path_rows for bit in edge.input_bits], dtype=np.int8
                )
                path_symbols = np.asarray(
                    [
                        label_to_index(tuple(edge.output_bits), profile=BASELINE_ASSUMPTION)
                        for edge in path_rows
                    ],
                    dtype=np.int64,
                )
                if not np.array_equal(path_bits, decoded_bits) or not np.array_equal(
                    path_symbols, decoded_symbols
                ):
                    raise ValueError("M10 decoded arrays disagree with canonical M1 path")
                bit_errors = sum(
                    int(left != right) for left, right in zip(bits, decoded_bits, strict=True)
                )
                symbol_errors = sum(
                    int(left != right) for left, right in zip(symbols, decoded_symbols, strict=True)
                )
                counts = {
                    "bit_errors": bit_errors,
                    "total_bits": 512,
                    "symbol_errors": symbol_errors,
                    "total_symbols": 256,
                }
                if row.get("counts") != counts:
                    raise ValueError(
                        "M10 stored raw errors disagree with independently recounted arrays"
                    )
                if (
                    not row.get("posterior_normalized")
                    or not row["coefficient_diagnostics"].get("finite_final_full_iq")
                    or not row["coefficient_diagnostics"].get("finite_final_fluctuating_iq")
                ):
                    raise ValueError("M10 finite-state/posterior integrity flags failed")
                if row.get("initial_full_iq") != [0.42, 0.91] or row.get("beta") != 0.7:
                    raise ValueError("M10 common receiver initial full state or beta changed")
                for segment_index, segment_name in enumerate(("pre_switch", "post_switch")):
                    segment = row["segment_diagnostics"][segment_index]
                    if segment["symbol_interval_half_open"] != (
                        [0, 128] if segment_index == 0 else [128, 256]
                    ):
                        raise ValueError("M10 segment diagnostics do not align to the gain switch")
                    segment_totals[profile_id][row["candidate_id"]][segment_name][0] += int(
                        segment["bit_errors"]
                    )
                    segment_totals[profile_id][row["candidate_id"]][segment_name][1] += int(
                        segment["symbol_errors"]
                    )
                coefficient_norms[profile_id][row["candidate_id"]].append(
                    float(row["coefficient_diagnostics"]["final_full_norm"])
                )
                if row["candidate_id"] == "historical_frozen_B":
                    expected_arm = (1.0, [0.0, 0.0], [0.0, 0.0], [0.42, 0.91])
                else:
                    expected_arm = (0.85, [0.0875, -0.05], [0.42, 0.91], [0.0, 0.0])
                if (
                    row.get("alpha_prime") != expected_arm[0]
                    or row.get("k_tilde") != expected_arm[1]
                    or row.get("mu0") != expected_arm[2]
                    or row.get("initial_fluctuating_iq") != expected_arm[3]
                ):
                    raise ValueError("M10 fixed receiver policy parameters changed")
                run["profiles"][profile_id][row["candidate_id"]] = counts
        runs.append(run)

    if len(all_received_hashes) != 300 or decoder_calls != 600 or policy_record_count != 600:
        raise ValueError("M10 complete-design counts do not equal 300 buffers/600 decodes/records")
    bootstrap_seed = int(approved["run_manifest"]["bootstrap"]["derived_seed"])
    summary = _summary_from_runs(runs, bootstrap_seed)
    return {
        "status": "M10_EVALUATION_COMPLETE_VERIFIED",
        "verification_method": "independent read-only recount; runner audit seed-provenance comparison corrected by treating initialized flags as execution state",
        "runner_initial_verification": "M10_VERIFICATION_FAILED: the runner compared planned initialized=false seed records against checkpoint execution flags true for data/noise",
        "approved_config_sha256": approved_digest,
        "run_count": len(runs),
        "unique_run_count": len({run["run_id"] for run in runs}),
        "unique_received_hash_count": len(all_received_hashes),
        "policy_record_count": policy_record_count,
        "decoder_invocations": decoder_calls,
        "failure_count": failure_count,
        "seed_provenance_verified": True,
        "data_and_noise_reproduced_from_approved_seeds": True,
        "raw_error_counts_recounted_from_saved_arrays": True,
        "segment_diagnostics": {
            profile: {
                policy: {
                    "pre_switch": {
                        "bit_errors": values["pre_switch"][0],
                        "symbol_errors": values["pre_switch"][1],
                        "bits": 25600,
                        "symbols": 12800,
                        "interpretation": "descriptive segment of full-frame Viterbi traceback",
                    },
                    "post_switch": {
                        "bit_errors": values["post_switch"][0],
                        "symbol_errors": values["post_switch"][1],
                        "bits": 25600,
                        "symbols": 12800,
                        "interpretation": "descriptive segment of full-frame Viterbi traceback",
                    },
                    "final_full_norm_mean": float(np.mean(coefficient_norms[profile][policy])),
                    "final_full_norm_max": float(np.max(coefficient_norms[profile][policy])),
                }
                for policy, values in rows.items()
            }
            for profile, rows in segment_totals.items()
        },
        "summary": summary,
        "independent_verifier_sha256": _file_hash(Path(__file__)),
    }


def _atomic_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive and path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def finalize_recount_artifacts(output_dir: str | Path, audit: dict[str, Any]) -> dict[str, str]:
    """Add the independent recount while retaining the runner's first audit."""
    root = Path(output_dir)
    original_verification_path = root / "independent_verification.json"
    initial_verification_path = root / "runner_initial_verification.json"
    initial_summary_path = root / "runner_initial_summary.json"
    summary_path = root / "summary.json"
    if not original_verification_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("original M10 runner verification artifacts are required")
    if not initial_verification_path.exists():
        initial_verification_path.write_bytes(original_verification_path.read_bytes())
    if not initial_summary_path.exists():
        initial_summary_path.write_bytes(summary_path.read_bytes())

    _atomic_json(root / "independent_recount.json", audit)
    _atomic_json(original_verification_path, audit)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["status"] = audit["status"]
    summary["independent_verification"] = {
        key: value for key, value in audit.items() if key != "summary"
    }
    summary["received_profile_buffers"] = audit["unique_received_hash_count"]
    summary["policy_records"] = audit["policy_record_count"]
    summary["generation_failures"] = 0
    summary["numerical_or_decoder_failure_count"] = audit["failure_count"]
    summary["statistics"] = audit["summary"]
    summary["resource"]["bootstrap_wall_clock_seconds"] = audit["summary"][
        "bootstrap_wall_clock_seconds"
    ]
    summary["runner_initial_verification"] = {
        "status": "M10_VERIFICATION_FAILED",
        "reason": "planned seed records used initialized=false while checkpoints correctly marked data/noise streams initialized=true after use",
        "preserved_as": "runner_initial_verification.json",
    }
    _atomic_json(summary_path, summary)

    hashes = {
        path.relative_to(root).as_posix(): _file_hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "integrity_manifest.json"
    }
    _atomic_json(root / "integrity_manifest.json", hashes)
    verified = {
        path.relative_to(root).as_posix(): _file_hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "integrity_manifest.json"
    }
    if hashes != verified:
        raise ValueError("M10 output integrity manifest did not match after independent recount")
    return {
        "status": summary["status"],
        "integrity_manifest_sha256": _file_hash(root / "integrity_manifest.json"),
    }
