"""Authorized execution driver for exactly the frozen M6b trace diagnostic."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.evaluation.error_metrics import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
    evaluate_run,
)
from hf_tcm.evaluation.m6b_trace_protocol import (
    M6B_OUTPUT_ROOT,
    deserialize_m6b_trace_payload,
    guarded_m6b_execution,
    serialize_m6b_trace_payload,
    validate_m6b_trace_diagnostic_config,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import generate_independent_complex_awgn
from hf_tcm.evaluation.reconstruction_causal_trace import (
    TRACE_STATUS,
    compare_reconstruction_causal_traces,
    run_reconstruction_causal_trace_pair,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

_RTOL = 1e-12
_ATOL = 1e-14


class M6BConfigurationMismatch(RuntimeError):
    """Approved run snapshot differs from the frozen preparation draft."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _atomic_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _canonical_json(value)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _sha256(content)


def _array(value: np.ndarray) -> dict[str, object]:
    contiguous = np.ascontiguousarray(value)
    return {
        "dtype": contiguous.dtype.name,
        "shape": list(contiguous.shape),
        "values": contiguous.tolist(),
    }


def _state(state: ReconstructionEstimatorState) -> dict[str, object]:
    return {
        "fluctuating_iq": _array(state.fluctuating_iq),
        "full_iq": _array(state.full_iq),
    }


def _mode_payload(mode: Any) -> dict[str, object]:
    history: list[dict[str, object]] = []
    for local_position, row in enumerate(mode.history):
        sample_predictions = np.asarray(row.predicted_iq, dtype=np.float64)
        posterior = np.asarray(row.posterior, dtype=np.float64)
        observed = np.asarray(row.observed_iq, dtype=np.float64)
        # Independent scalar-loop replay of the read-only derived innovation.
        derived_innovation = np.zeros(2, dtype=np.float64)
        for hypothesis_index in range(16):
            derived_innovation += posterior[hypothesis_index] * (
                observed - sample_predictions[hypothesis_index]
            )
        if not np.allclose(derived_innovation, row.innovation_operand, rtol=_RTOL, atol=_ATOL):
            raise ValueError("derived innovation does not match the independent operand replay")
        history.append(
            {
                "absolute_symbol_index": row.absolute_symbol_index,
                "estimator_time_index": row.estimator_time_index,
                "sequence_local_position": local_position,
                "processing_segment_index": row.segment_index,
                "processing_segment_local_position": row.segment_local_position,
                "sample_window": list(row.sample_window),
                "prediction_cutoff_sample_index": row.prediction_cutoff_sample_index,
                "observation_cutoff_sample_index": row.observation_cutoff_sample_index,
                "pre_fluctuating_iq": _array(row.pre_state.fluctuating_iq),
                "pre_full_iq": _array(row.pre_state.full_iq),
                "mu0": _array(row.mu0),
                "observed_iq_mean": _array(observed),
                "candidate_metrics": _array(row.candidate_metrics),
                "hypothesis_ids": list(row.hypothesis_ids),
                "phase_indices": list(row.phase_indices),
                "edge_mode": row.edge_mode,
                "posterior_input": _array(row.posterior_input),
                "posterior_input_kind": row.posterior_input_kind,
                "posterior_transition_provenance": row.posterior_transition_provenance,
                "posterior": _array(posterior),
                "transition_predicted_posterior_q": {"status": "unavailable", "value": None},
                "predicted_iq": _array(sample_predictions),
                "alpha_prime": row.alpha_prime,
                "k_tilde": _array(row.k_tilde),
                "innovation_operand": _array(derived_innovation),
                "innovation_provenance": "derived_from_actual_B4c_posterior_observation_prediction",
                "post_fluctuating_iq": _array(row.post_state.fluctuating_iq),
                "post_full_iq": _array(row.post_state.full_iq),
                "fluctuating_increment": _array(row.fluctuating_increment),
                "full_increment": _array(row.full_increment),
                "posterior_sum": row.posterior_sum,
                "posterior_normalized": row.posterior_normalized,
                "decoded_hypothesis_id": row.decoded_hypothesis_id,
            }
        )
    return {
        "receiver_mode": mode.mode,
        "received_sha256": mode.received_sha256,
        "initial_state": _state(mode.initial_state),
        "symbol_trace": history,
        "frozen_metric_history": _array(mode.frozen_metric_history),
        "final_state": _state(mode.final_state),
        "decoded_hypothesis_path": list(mode.decoded_hypothesis_path),
        "decoded_information_bits": [int(value) for value in mode.decoded_information_bits],
        "best_conditional_path_cost": mode.best_conditional_path_cost,
        "decoded_path_valid": mode.decoded_path_valid,
        "decode_call_count": mode.decode_call_count,
    }


def _validate_causal_pair(pair: Any, *, expected_run_id: str) -> dict[str, object]:
    if pair.status != TRACE_STATUS or pair.sequence_id != expected_run_id:
        raise ValueError("B4d trace status or sequence ID mismatch")
    if (
        pair.received_sha256 != pair.frozen.received_sha256
        or pair.received_sha256 != pair.adaptive.received_sha256
    ):
        raise ValueError("B/C received hashes do not match")
    if len(pair.frozen.history) != 32 or len(pair.adaptive.history) != 32:
        raise ValueError("B4d history must contain exactly 32 rows per mode")
    cmp = compare_reconstruction_causal_traces(pair, rtol=_RTOL, atol=_ATOL)
    if not cmp.received_sha256_equal or not cmp.initial_state_equal:
        raise ValueError("B/C pairing invariants failed")
    for mode in (pair.frozen, pair.adaptive):
        if mode.decode_call_count != 1 or not mode.decoded_path_valid:
            raise ValueError("B5b must produce one structurally valid final path per mode")
        metrics_from_rows = np.stack([row.candidate_metrics for row in mode.history])
        if not np.array_equal(metrics_from_rows, mode.frozen_metric_history):
            raise ValueError("frozen B5b metric matrix differs from exact B4d rows")
        for local_position, row in enumerate(mode.history):
            absolute_symbol = local_position
            first_sample = 8 * absolute_symbol
            if (
                row.absolute_symbol_index != absolute_symbol
                or row.estimator_time_index != absolute_symbol
                or row.segment_index != 0
                or row.segment_local_position != local_position
                or row.sample_window != tuple(range(first_sample, first_sample + 8))
                or row.prediction_cutoff_sample_index != first_sample - 1
                or row.observation_cutoff_sample_index != first_sample + 7
                or row.hypothesis_ids != tuple(range(16))
                or row.posterior_normalized is not True
                or not np.all(np.isfinite(row.candidate_metrics))
            ):
                raise ValueError(
                    "B4d trace clock, ordering, posterior, or finite-value invariant failed"
                )
            if local_position == 0:
                if (
                    row.edge_mode != "first_edge"
                    or row.posterior_transition_provenance != "none_first_edge"
                ):
                    raise ValueError("first symbol must use ADR-004 prior without transition")
            else:
                previous = mode.history[local_position - 1]
                if row.edge_mode != "later_edge" or not np.array_equal(
                    row.posterior_input, previous.posterior
                ):
                    raise ValueError(
                        "continuation posterior must be the preceding actual posterior"
                    )
                if not np.array_equal(row.pre_state.full_iq, previous.post_state.full_iq):
                    raise ValueError("post-state f must be exactly the next pre-state")
        if mode.mode == "mismatched_frozen":
            for row in mode.history:
                if not np.array_equal(row.pre_state.full_iq, row.post_state.full_iq):
                    raise ValueError("frozen B estimator state changed")
    post_div = cmp.post_state_differing_symbols
    pre_div = cmp.pre_state_differing_symbols
    metric_div = cmp.candidate_metric_differing_symbols
    posterior_div = cmp.posterior_differing_symbols
    path_div = cmp.decoded_edge_differing_symbols

    def local(values: tuple[int, ...]) -> list[int]:
        return [int(value) for value in values]

    return {
        "rtol": _RTOL,
        "atol": _ATOL,
        "first_post_state_divergence_symbol": cmp.first_estimator_state_divergence_symbol,
        "first_pre_state_divergence_symbol": pre_div[0] if pre_div else None,
        "first_candidate_metric_divergence_symbol": cmp.first_candidate_metric_divergence_symbol,
        "first_posterior_divergence_symbol": posterior_div[0] if posterior_div else None,
        "first_final_decoded_path_divergence_symbol": path_div[0] if path_div else None,
        "total_differing_decoded_edges": len(path_div),
        "post_state_divergence_positions": local(post_div),
        "pre_state_divergence_positions": local(pre_div),
        "candidate_metric_divergence_positions": local(metric_div),
        "posterior_divergence_positions": local(posterior_div),
        "decoded_path_divergence_positions": local(path_div),
        "paired_received_hash_equal": cmp.received_sha256_equal,
        "initial_state_equal": cmp.initial_state_equal,
        "causal_integrity": "passed_trace_and_B4d_history_invariants",
    }


def _derive_seed(
    master_seed: int, *, run_index: int, stream_code: int
) -> tuple[int, tuple[int, ...]]:
    spawn_key = (1295337521, 306, run_index, stream_code)
    sequence = np.random.SeedSequence(master_seed, spawn_key=spawn_key)
    seed = int(sequence.generate_state(1, dtype=np.uint64)[0])
    return seed, spawn_key


def _source_fingerprints() -> tuple[dict[str, str], str]:
    source_root = Path("src/hf_tcm")
    files = sorted(path for path in source_root.rglob("*.py") if "__pycache__" not in path.parts)
    hashes = {path.as_posix(): _sha256(path.read_bytes()) for path in files}
    return hashes, _sha256(_canonical_json(hashes))


def _approved_matches_draft(draft: dict[str, Any], approved: dict[str, Any]) -> None:
    normalized = json.loads(json.dumps(approved))
    normalized["design_status"] = "proposed"
    normalized["execution_authorized"] = False
    normalized["execution_scope"] = "none"
    normalized["authorization"] = None
    normalized["resource_policy"]["resource_limits"] = None
    if normalized != draft:
        raise M6BConfigurationMismatch("approved snapshot differs from frozen M6b-prep draft")


class _WorkingSetMonitor:
    """Periodic Windows working-set sampling; observation only, not an OS limit."""

    def __init__(self, interval_seconds: float = 0.2) -> None:
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self.peak_bytes: int | None = None
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    @staticmethod
    def _current_working_set() -> int:
        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize)

    def _sample(self) -> None:
        try:
            while not self._stop.is_set():
                value = self._current_working_set()
                self.peak_bytes = value if self.peak_bytes is None else max(self.peak_bytes, value)
                self._stop.wait(self.interval_seconds)
        except Exception as exc:  # monitoring failure must not hide experiment status
            self.error = f"{type(exc).__name__}: {exc}"

    def start(self) -> bool:
        try:
            self.peak_bytes = self._current_working_set()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            return False
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def _write_run_payload(
    *,
    run_dir: Path,
    run_id: str,
    config_sha256: str,
    source_hashes: dict[str, str],
    pair: Any,
    comparison: dict[str, object],
    evaluation: dict[str, object],
    run_provenance: dict[str, object],
) -> dict[str, str]:
    mode_b = _mode_payload(pair.frozen)
    mode_c = _mode_payload(pair.adaptive)
    payload = {
        "schema_version": 1,
        "experiment_id": "m6b_causal_trace_20261030_v1",
        "run_id": run_id,
        "config_sha256": config_sha256,
        "software_provenance": {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "file_sha256": source_hashes,
        },
        "received_sha256": pair.received_sha256,
        "mode_B": mode_b,
        "mode_C": mode_c,
        "paired_comparison": {
            "rtol": _RTOL,
            "atol": _ATOL,
            "first_post_state_divergence_symbol": comparison["first_post_state_divergence_symbol"],
            "first_candidate_metric_divergence_symbol": comparison[
                "first_candidate_metric_divergence_symbol"
            ],
            "first_posterior_divergence_symbol": comparison["first_posterior_divergence_symbol"],
            "decoded_path_divergence_positions": comparison["decoded_path_divergence_positions"],
        },
        "trace_integrity_status": "complete_valid_trace",
    }
    encoded = serialize_m6b_trace_payload(payload)
    parsed = deserialize_m6b_trace_payload(encoded)
    if parsed["run_id"] != run_id:
        raise ValueError("serialized trace run ID changed during round-trip")
    file_hashes: dict[str, str] = {}
    file_hashes["trace_pair.json"] = _atomic_json(run_dir / "trace_pair.json", json.loads(encoded))
    file_hashes["B_trace.json"] = _atomic_json(run_dir / "B_trace.json", mode_b)
    file_hashes["C_trace.json"] = _atomic_json(run_dir / "C_trace.json", mode_c)
    file_hashes["paired_comparison.json"] = _atomic_json(
        run_dir / "paired_comparison.json", comparison
    )
    file_hashes["evaluation_only.json"] = _atomic_json(run_dir / "evaluation_only.json", evaluation)
    file_hashes["run_manifest.json"] = _atomic_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "config_sha256": config_sha256,
            "received_sha256": pair.received_sha256,
            "rng_provenance": run_provenance,
            "trace_row_count": 64,
            "trace_schema_version": 1,
            "trace_integrity_status": "complete_valid_trace",
        },
    )
    file_hashes["status.json"] = _atomic_json(
        run_dir / "status.json", {"status": "complete", "failure": None}
    )
    return file_hashes


def run_authorized_m6b_trace_experiment(
    *, approved_config_path: str | Path, draft_config_path: str | Path
) -> dict[str, object]:
    """Run exactly three authorized fresh-seed B/C trace pairs and checkpoint them."""
    approved_path = Path(approved_config_path)
    draft_path = Path(draft_config_path)
    approved_bytes = approved_path.read_bytes()
    draft_bytes = draft_path.read_bytes()
    approved_raw = json.loads(approved_bytes)
    draft_raw = json.loads(draft_bytes)
    config = validate_m6b_trace_diagnostic_config(approved_raw)
    if _sha256(draft_bytes) != approved_raw["authorization"]["source_draft_sha256"]:
        raise M6BConfigurationMismatch(
            "approved source draft fingerprint does not match current draft"
        )
    _approved_matches_draft(draft_raw, approved_raw)
    source_hashes, code_fingerprint = _source_fingerprints()
    config_sha256 = _sha256(approved_bytes)
    output_root = Path(M6B_OUTPUT_ROOT)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite M6b output namespace: {output_root}")
    run_ids = tuple(approved_raw["run_design"]["planned_run_ids"])
    roots = approved_raw["seed_derivation"]["master_seed_roots"]
    stream_codes = approved_raw["seed_derivation"]["stream_codes"]
    seeds: list[dict[str, object]] = []
    for run_index, run_id in enumerate(run_ids):
        streams: dict[str, object] = {}
        for name, code in stream_codes.items():
            child, spawn_key = _derive_seed(roots[name], run_index=run_index, stream_code=code)
            streams[name] = {
                "master_seed": roots[name],
                "spawn_key": list(spawn_key),
                "derived_seed_uint64": child,
                "bit_generator": "PCG64",
            }
        seeds.append({"run_id": run_id, "run_index": run_index, "streams": streams})

    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "config_snapshot.json").write_bytes(approved_bytes)
    _atomic_json(
        output_root / "config_fingerprint.json",
        {
            "approved_config_sha256": config_sha256,
            "draft_config_sha256": _sha256(draft_bytes),
            "runtime_code_fingerprint_sha256": code_fingerprint,
            "runtime_source_file_sha256": source_hashes,
            "schema_version": 1,
            "design_version": "m6b-prep-1",
        },
    )
    git_revision = "unavailable: workspace has no .git metadata"
    manifest: dict[str, object] = {
        "experiment_id": config.experiment_id,
        "status": "running",
        "authorization": approved_raw["authorization"],
        "approved_config_sha256": config_sha256,
        "draft_config_sha256": _sha256(draft_bytes),
        "runtime_code_fingerprint_sha256": code_fingerprint,
        "runtime_source_file_sha256": source_hashes,
        "git_revision": git_revision,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "rng_derivation": approved_raw["seed_derivation"],
        "run_seed_provenance": seeds,
        "planned_run_ids": list(run_ids),
        "run_results": [],
        "resource_policy": approved_raw["resource_policy"],
        "evidence_status": "authorized fresh-seed causal trace diagnostics, NOT new performance evidence, NOT established scientific root cause, NOT paper-exact receiver",
    }
    _atomic_json(output_root / "manifest.json", manifest)
    run_started = time.monotonic()
    monitor = _WorkingSetMonitor()
    rss_available = monitor.start()
    results: list[dict[str, object]] = []
    stopped_reason: str | None = None
    try:
        for run_index, run_id in enumerate(run_ids):
            elapsed = time.monotonic() - run_started
            if elapsed >= 300:
                stopped_reason = "wall_clock_budget_exhausted_before_next_run"
                break
            run_name = run_id.rsplit(":", maxsplit=1)[-1]
            final_dir = output_root / run_name
            staging_dir = output_root / f".{run_name}.staging"
            if final_dir.exists() or staging_dir.exists():
                raise FileExistsError(f"run checkpoint path already exists: {run_name}")
            staging_dir.mkdir()
            run_seed = seeds[run_index]
            data_seed = int(run_seed["streams"]["data"]["derived_seed_uint64"])
            noise_seed = int(run_seed["streams"]["noise"]["derived_seed_uint64"])
            stage = "reference_data_generation"
            try:
                data_rng = np.random.Generator(np.random.PCG64(data_seed))
                reference_bits = data_rng.integers(0, 2, size=64, dtype=np.int8)
                reference_symbols = encode_reference_symbol_indices(
                    reference_bits,
                    profile=ASSUMED_NATURAL_BINARY,
                    bit_order=OUTPUT_BIT_ORDER,
                )
                labels = [
                    index_to_label(int(symbol), profile=BASELINE_ASSUMPTION)
                    for symbol in reference_symbols
                ]
                modulated = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
                in_phase, quadrature = symbols_to_iq_waveform(modulated, samples_per_symbol=8)
                clean = 0.75 * (in_phase + 1j * quadrature)
                stage = "single_awgn_generation"
                awgn = generate_independent_complex_awgn(
                    sample_count=256,
                    sigma_squared=0.7115124735378853,
                    seed=noise_seed,
                    stream_id=f"m6b:{run_id}:noise:pcg64",
                )
                received = np.asarray(clean + awgn.noise, dtype=np.complex128)
                if received.shape != (256,) or not np.all(np.isfinite(received)):
                    raise ValueError("received buffer must be finite complex128 shape (256,)")
                received_hash = _sha256(np.ascontiguousarray(received).tobytes())
                state = ReconstructionEstimatorState(
                    fluctuating_iq=np.asarray([[0.42, 0.91]], dtype=np.float64),
                    full_iq=np.asarray([[0.42, 0.91]], dtype=np.float64),
                    time_index=0,
                )
                stage = "paired_B_C_causal_trace_and_decode"
                pair = run_reconstruction_causal_trace_pair(
                    received=received,
                    absolute_sample_indices=np.arange(256, dtype=np.int64),
                    received_start_sample=0,
                    symbol_origin_sample=0,
                    first_symbol_index=0,
                    initial_estimator_time_index=0,
                    initial_state=state,
                    beta=0.7,
                    sequence_id=run_id,
                    adaptive_alpha_prime=0.85,
                    adaptive_k_tilde=np.asarray([[0.35, -0.2]], dtype=np.float64),
                    adaptive_mu0=np.zeros((1, 2), dtype=np.float64),
                )
                if pair.received_sha256 != received_hash:
                    raise ValueError("M6a received hash differs from generated paired buffer")
                stage = "causal_trace_validation"
                comparison = _validate_causal_pair(pair, expected_run_id=run_id)
                ref_symbols = np.asarray(reference_symbols, dtype=np.int64)
                bit_eval_b = evaluate_run(
                    reference_bits,
                    pair.frozen.decoded_information_bits,
                    ref_symbols,
                    decoded_path_symbol_indices(
                        pair.frozen.decoded_hypothesis_path,
                        profile=ASSUMED_NATURAL_BINARY,
                        bit_order=OUTPUT_BIT_ORDER,
                    ),
                )
                bit_eval_c = evaluate_run(
                    reference_bits,
                    pair.adaptive.decoded_information_bits,
                    ref_symbols,
                    decoded_path_symbol_indices(
                        pair.adaptive.decoded_hypothesis_path,
                        profile=ASSUMED_NATURAL_BINARY,
                        bit_order=OUTPUT_BIT_ORDER,
                    ),
                )
                # True gain is used only after both decodes for evaluation-side coefficient error.
                target = np.full((1, 2), 0.75, dtype=np.float64)
                coefficient_rows: dict[str, object] = {}
                for mode_name, mode in (("B", pair.frozen), ("C", pair.adaptive)):
                    full_states = [row.post_state.full_iq for row in mode.history]
                    errors = [float(np.linalg.norm(value - target)) for value in full_states]
                    increments = [
                        float(np.linalg.norm(row.fluctuating_increment)) for row in mode.history
                    ]
                    posterior_deviations = [abs(row.posterior_sum - 1.0) for row in mode.history]
                    all_coefficients = np.concatenate([value.ravel() for value in full_states])
                    coefficient_rows[mode_name] = {
                        "initial_coefficient_error_norm_relative_to_a": float(
                            np.linalg.norm(mode.initial_state.full_iq - target)
                        ),
                        "final_coefficient_error_norm_relative_to_a": errors[-1],
                        "per_symbol_coefficient_error_norms": errors,
                        "per_symbol_increment_norms": increments,
                        "largest_absolute_coefficient_magnitude": float(
                            np.max(np.abs(all_coefficients))
                        ),
                        "first_large_increment_position": None,
                        "large_increment_criterion": "not_defined_no_predeclared_threshold",
                        "finite_trajectory": bool(
                            np.all(np.isfinite(all_coefficients)) and all(np.isfinite(increments))
                        ),
                        "posterior_normalization_max_abs_error": max(posterior_deviations),
                    }
                evaluation = {
                    "evaluation_only": True,
                    "reference_bits_persisted": False,
                    "B": {
                        "bit_errors": bit_eval_b.counts.bit_errors,
                        "total_bits": bit_eval_b.counts.total_bits,
                        "ber": bit_eval_b.ber,
                        "symbol_errors": bit_eval_b.counts.symbol_errors,
                        "total_symbols": bit_eval_b.counts.total_symbols,
                        "ser": bit_eval_b.ser,
                    },
                    "C": {
                        "bit_errors": bit_eval_c.counts.bit_errors,
                        "total_bits": bit_eval_c.counts.total_bits,
                        "ber": bit_eval_c.ber,
                        "symbol_errors": bit_eval_c.counts.symbol_errors,
                        "total_symbols": bit_eval_c.counts.total_symbols,
                        "ser": bit_eval_c.ser,
                    },
                    "coefficient_diagnostics": coefficient_rows,
                }
                stage = "trace_serialization_and_atomic_checkpoint"
                file_hashes = _write_run_payload(
                    run_dir=staging_dir,
                    run_id=run_id,
                    config_sha256=config_sha256,
                    source_hashes=source_hashes,
                    pair=pair,
                    comparison=comparison,
                    evaluation=evaluation,
                    run_provenance=run_seed,
                )
                del reference_bits, reference_symbols, received, awgn, pair
                os.replace(staging_dir, final_dir)
                run_result = {
                    "run_id": run_id,
                    "status": "complete",
                    "received_sha256": received_hash,
                    "rng_provenance": run_seed,
                    "comparison": comparison,
                    "evaluation_only": evaluation,
                    "files_sha256": file_hashes,
                    "elapsed_seconds": time.monotonic() - run_started,
                }
                results.append(run_result)
                manifest["run_results"] = results
                _atomic_json(output_root / "manifest.json", manifest)
            except Exception as exc:
                failure = {
                    "run_id": run_id,
                    "status": "failed",
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "rng_provenance": run_seed,
                }
                _atomic_json(staging_dir / "status.json", failure)
                os.replace(staging_dir, final_dir)
                results.append(failure)
                manifest["run_results"] = results
                _atomic_json(output_root / "manifest.json", manifest)
            if time.monotonic() - run_started >= 300:
                stopped_reason = "wall_clock_budget_exhausted_after_completed_run"
                break
            if monitor.peak_bytes is not None and monitor.peak_bytes > 536870912:
                stopped_reason = "sampled_rss_budget_exceeded_after_run"
                break
    finally:
        monitor.stop()

    completed_ids = {item["run_id"] for item in results if item["status"] == "complete"}
    attempted_ids = {item["run_id"] for item in results}
    for run_id in run_ids:
        if run_id not in attempted_ids:
            run_name = run_id.rsplit(":", maxsplit=1)[-1]
            run_dir = output_root / run_name
            run_dir.mkdir(exist_ok=False)
            record = {
                "run_id": run_id,
                "status": "not_started_resource_budget",
                "reason": stopped_reason,
            }
            _atomic_json(run_dir / "status.json", record)
            results.append(record)
    all_complete = len(completed_ids) == 3 and len(results) == 3
    manifest["run_results"] = results
    manifest["status"] = "complete" if all_complete else "incomplete"
    manifest["stopped_reason"] = stopped_reason
    manifest["wall_clock_seconds"] = time.monotonic() - run_started
    manifest["process_rss_monitoring"] = {
        "available": rss_available,
        "sample_interval_seconds": monitor.interval_seconds,
        "sampled_peak_working_set_bytes": monitor.peak_bytes,
        "hard_os_limit": False,
        "error": monitor.error,
    }
    _atomic_json(output_root / "summary.json", manifest)
    return manifest


def run_m6b_after_guard(
    *, approved_config_path: str | Path, draft_config_path: str | Path
) -> dict[str, object]:
    approved = json.loads(Path(approved_config_path).read_text(encoding="utf-8"))
    return guarded_m6b_execution(
        approved,
        on_authorized=lambda _: run_authorized_m6b_trace_experiment(
            approved_config_path=approved_config_path, draft_config_path=draft_config_path
        ),
    )
