"""Single-worker M5h pilot execution, checkpointing, and resource supervision."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.evaluation.error_metrics import ErrorCounts
from hf_tcm.evaluation.m5h_pilot_protocol import (
    M5HRunProvenance,
    derive_m5h_run_provenance,
    run_m5h_pilot,
    validate_m5h_pilot_config,
)
from hf_tcm.evaluation.paired_cluster_bootstrap import PairedRunCounts, paired_cluster_bootstrap
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import (
    run_adaptive_estimator_diagnostic,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRAFT_PATH = _REPO_ROOT / "configs/m5h_pilot_draft.json"
_CODE_PATHS = (
    Path("src/hf_tcm/evaluation/m5h_pilot_protocol.py"),
    Path("src/hf_tcm/evaluation/m5h_pilot_runner.py"),
    Path("src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py"),
    Path("src/hf_tcm/evaluation/paired_cluster_bootstrap.py"),
    Path("src/hf_tcm/evaluation/error_metrics.py"),
    Path("src/hf_tcm/evaluation/matched_m2_b5_experiment.py"),
    Path("src/hf_tcm/evaluation/matched_m2_observation.py"),
    Path("src/hf_tcm/receiver/reconstruction_estimator_state.py"),
    Path("src/hf_tcm/receiver/reconstruction_forward.py"),
    Path("src/hf_tcm/receiver/reconstruction_labeling.py"),
    Path("src/hf_tcm/receiver/reconstruction_observation.py"),
    Path("src/hf_tcm/receiver/reconstruction_posterior.py"),
    Path("src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py"),
    Path("src/hf_tcm/receiver/reconstruction_posterior_estimator_step.py"),
    Path("src/hf_tcm/receiver/reconstruction_candidate_metrics.py"),
    Path("src/hf_tcm/receiver/reconstruction_causal_step.py"),
    Path("src/hf_tcm/receiver/iq.py"),
    Path("src/hf_tcm/reconstruction_config.py"),
    Path("src/hf_tcm/coding/hypothesis_path.py"),
    Path("src/hf_tcm/coding/encoder.py"),
    Path("src/hf_tcm/coding/hypotheses.py"),
    Path("src/hf_tcm/decoding/reconstruction_viterbi.py"),
    Path("src/hf_tcm/modulation/labeling.py"),
    Path("src/hf_tcm/modulation/psk8.py"),
)
_RSS_LIMIT = 1_610_612_736
_WALL_LIMIT_SECONDS = 1800.0
_MONITOR_INTERVAL_SECONDS = 0.25
_OUTPUT_LIMIT_BYTES = 100 * 1024 * 1024


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compute_code_fingerprint(
    code_paths: Sequence[str | Path] = _CODE_PATHS,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in code_paths:
        path = Path(item)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        try:
            label = path.resolve().relative_to(_REPO_ROOT).as_posix()
        except ValueError as exc:
            raise ValueError(f"code fingerprint path is outside the workspace: {path}") from exc
        if label in result:
            raise ValueError(f"duplicate code fingerprint path: {label}")
        result[label] = file_sha256(path)
    if not result:
        raise ValueError("at least one code path is required for the code fingerprint")
    return dict(sorted(result.items()))


def config_fingerprint(data: Mapping[str, Any]) -> str:
    return _sha256_bytes(_json_bytes(data))


def create_approved_run_config(
    source_draft_path: str | Path,
    output_path: str | Path,
    *,
    code_paths: Sequence[str | Path] = _CODE_PATHS,
    available_memory_before_bytes: int,
    runtime_utc: str | None = None,
) -> dict[str, Any]:
    """Write a new approved run config; never modifies the proposed draft."""
    source_path = Path(source_draft_path)
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"immutable approved run config already exists: {output}")
    try:
        draft = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read proposed M5h draft: {exc}") from exc
    if draft.get("design_status") != "proposed" or draft.get("execution_authorized") is not False:
        raise ValueError("source draft must remain proposed and unauthorized")
    if available_memory_before_bytes < 2 * 1024**3:
        raise RuntimeError("available physical memory is below the recommended 2 GiB preflight")
    approved = dict(draft)
    approved["design_status"] = "approved_for_pilot"
    approved["execution_authorized"] = True
    approved["execution_scope"] = "m5h_pilot_only"
    approved["purpose"] = (
        "authorized independent planning pilot, NOT confirmatory performance evidence, "
        "NOT paper-exact receiver, NOT physical HF Eb/N0 comparison"
    )
    approved["source_draft_sha256"] = file_sha256(source_path)
    approved["code_fingerprint"] = compute_code_fingerprint(code_paths)
    approved["execution_limits"] = {
        "wall_clock_budget_seconds": 1800,
        "rss_ceiling_bytes": _RSS_LIMIT,
        "resource_poll_interval_seconds": 0.25,
        "available_memory_before_bytes": int(available_memory_before_bytes),
        "available_memory_measurement": "Windows GlobalMemoryStatusEx",
        "rss_measurement": "Windows GetProcessMemoryInfo WorkingSetSize, sampled by parent",
        "limit_semantics": "observed by 0.25-second parent monitor; not an OS hard cap",
        "output_size_target_bytes": _OUTPUT_LIMIT_BYTES,
        "decoding_workers": 1,
    }
    approved["authorization_provenance"] = {
        "explicit_user_approval": "explicit user approval through the current Codex execution instruction",
        "design_version": draft["design_version"],
        "source_draft_identifier": draft["study_id"],
        "source_draft_sha256": approved["source_draft_sha256"],
        "execution_date_time_utc": runtime_utc or datetime.now(UTC).isoformat(timespec="seconds"),
        "code_revision_identifier": None,
        "code_revision_status": "unavailable: workspace is not a Git worktree",
        "code_fingerprint": approved["code_fingerprint"],
    }
    from hf_tcm.evaluation.m5h_pilot_protocol import approved_parameter_snapshot

    approved["approved_parameter_snapshot"] = approved_parameter_snapshot(approved)
    validate_m5h_pilot_config(approved)
    atomic_write_json(output, approved, exclusive=True)
    return approved


def atomic_write_json(path: str | Path, value: object, *, exclusive: bool = False) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp")
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    with temporary.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if exclusive and destination.exists():
        temporary.unlink(missing_ok=True)
        raise FileExistsError(destination)
    os.replace(temporary, destination)


def _checkpoint_path(directory: Path, run_id: str) -> Path:
    return directory / f"{_sha256_bytes(run_id.encode('utf-8'))}.json"


def write_run_checkpoint(
    directory: str | Path,
    record: Mapping[str, Any],
    *,
    config_fingerprint: str,
    code_fingerprint: str,
) -> Path:
    if not isinstance(record.get("run_id"), str) or not record["run_id"]:
        raise ValueError("checkpoint record must contain a nonempty run_id")
    if record.get("status") not in ("completed", "numerical_failure"):
        raise ValueError("checkpoint status must be completed or numerical_failure")
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(target_dir, record["run_id"])
    if path.exists():
        raise ValueError(f"checkpoint already exists for run_id {record['run_id']}")
    atomic_write_json(
        path,
        {
            "run_id": record["run_id"],
            "config_fingerprint": config_fingerprint,
            "code_fingerprint": code_fingerprint,
            "record": dict(record),
        },
        exclusive=True,
    )
    return path


def load_run_checkpoints(
    directory: str | Path,
    *,
    expected_config_fingerprint: str,
    expected_code_fingerprint: str,
) -> dict[str, dict[str, Any]]:
    root = Path(directory)
    if not root.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid checkpoint file {path.name}: {exc}") from exc
        if (
            envelope.get("config_fingerprint") != expected_config_fingerprint
            or envelope.get("code_fingerprint") != expected_code_fingerprint
        ):
            raise ValueError(f"checkpoint fingerprint mismatch in {path.name}")
        record = envelope.get("record")
        if not isinstance(record, dict) or record.get("run_id") != envelope.get("run_id"):
            raise ValueError(f"malformed checkpoint record in {path.name}")
        run_id = record["run_id"]
        if run_id in records:
            raise ValueError(f"duplicate run_id found in checkpoints: {run_id}")
        if path.name != _checkpoint_path(root, run_id).name:
            raise ValueError(f"checkpoint filename does not match run_id in {path.name}")
        records[run_id] = record
    return records


def _memory_status_windows() -> tuple[int, int] | None:
    if os.name != "nt":
        return None
    from ctypes import wintypes

    status_type = type(
        "MEMORYSTATUSEX",
        (ctypes.Structure,),
        {
            "_fields_": [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        },
    )
    status = status_type()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys), int(status.ullTotalPhys)


def _process_rss_windows(pid: int) -> int | None:
    if os.name != "nt":
        return None
    from ctypes import wintypes

    size_t = ctypes.c_size_t
    counters_type = type(
        "PROCESS_MEMORY_COUNTERS",
        (ctypes.Structure,),
        {
            "_fields_": [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", size_t),
                ("WorkingSetSize", size_t),
                ("QuotaPeakPagedPoolUsage", size_t),
                ("QuotaPagedPoolUsage", size_t),
                ("QuotaPeakNonPagedPoolUsage", size_t),
                ("QuotaNonPagedPoolUsage", size_t),
                ("PagefileUsage", size_t),
                ("PeakPagefileUsage", size_t),
            ]
        },
    )
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        return None
    counters = counters_type()
    counters.cb = ctypes.sizeof(counters)
    try:
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        return int(counters.WorkingSetSize) if ok else None
    finally:
        kernel32.CloseHandle(handle)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _state_pair(state: ReconstructionEstimatorState) -> tuple[float, float]:
    return tuple(float(item) for item in state.full_iq[0])


def _pilot_run(request: Any) -> dict[str, Any]:
    provenance: M5HRunProvenance = request.provenance
    data_rng = np.random.Generator(np.random.PCG64(provenance.data_seed))
    bits = data_rng.integers(0, 2, size=2 * request.symbols_per_run, dtype=np.int8)
    config = request.reconstruction_configuration
    shared = (0.42, 0.91)
    initial_state = ReconstructionEstimatorState(
        [shared], [shared], provenance.estimator_time_origin
    )
    started = time.perf_counter()
    result = run_adaptive_estimator_diagnostic(
        run_id=provenance.run_id,
        reference_information_bits=bits,
        real_channel_gain=0.75,
        sigma_squared=provenance.sigma_squared,
        noise=None,
        noise_seed=provenance.noise_seed,
        noise_stream_id=f"M5h-pilot:{provenance.stratum_id}:{provenance.run_index}:noise",
        noise_provenance=(
            "ADR-015 SeedSequence/PCG64; "
            f"master={provenance.noise_master_seed}; "
            f"spawn_key={provenance.noise_spawn_key}; derived_seed={provenance.noise_seed}"
        ),
        symbol_origin_sample=provenance.sample_origin,
        first_symbol_index=provenance.symbol_origin,
        initial_estimator_time_index=provenance.estimator_time_origin,
        configuration=config,
        mismatched_initial_state=initial_state,
        adaptive_alpha_prime=0.85,
        adaptive_k_tilde=np.asarray([[0.35, -0.2]], dtype=np.float64),
        adaptive_mu0=np.zeros((1, 2), dtype=np.float64),
        receiver_mode="monolithic",
        segment_partition=None,
    )
    b_mode, c_mode = result.mismatched_frozen, result.mismatched_adaptive
    if not (result.received_sha256 == b_mode.received_sha256 == c_mode.received_sha256):
        raise RuntimeError("B/C received-buffer pairing invariant failed")
    for row in b_mode.history:
        if not np.array_equal(row.pre_state.full_iq, row.post_state.full_iq) or not np.array_equal(
            row.pre_state.fluctuating_iq, row.post_state.fluctuating_iq
        ):
            raise RuntimeError("frozen B changed the estimator state")
    if (
        len(b_mode.decoded_information_bits) != 2 * request.symbols_per_run
        or len(c_mode.decoded_information_bits) != 2 * request.symbols_per_run
    ):
        raise RuntimeError("B/C output length differs from 2F bits")

    b_counts = b_mode.evaluation.counts
    c_counts = c_mode.evaluation.counts
    if (
        b_counts.total_bits != c_counts.total_bits
        or b_counts.total_symbols != c_counts.total_symbols
    ):
        raise RuntimeError("B/C denominators differ")
    c_errors = np.asarray([row.full_estimate_error_norm for row in c_mode.history])
    increments = np.asarray([np.linalg.norm(row.full_increment) for row in c_mode.history])
    entropy = np.asarray(
        [
            -np.sum(row.posterior[row.posterior > 0] * np.log(row.posterior[row.posterior > 0]))
            for row in c_mode.history
        ],
        dtype=np.float64,
    )
    initial_error = float(np.linalg.norm(np.asarray(shared) - np.asarray([0.75, 0.75])))
    finite_trajectory = bool(
        np.all(np.isfinite(c_errors))
        and np.all(np.isfinite(increments))
        and np.all(np.isfinite(entropy))
        and np.all(np.isfinite(c_mode.final_state.full_iq))
        and np.all(np.isfinite(b_mode.candidate_metrics))
        and np.all(np.isfinite(c_mode.candidate_metrics))
        and np.all(np.isfinite(b_mode.posterior_history))
        and np.all(np.isfinite(c_mode.posterior_history))
        and all(
            np.all(np.isfinite(row.pre_state.full_iq))
            and np.all(np.isfinite(row.pre_state.fluctuating_iq))
            and np.all(np.isfinite(row.post_state.full_iq))
            and np.all(np.isfinite(row.post_state.fluctuating_iq))
            for row in c_mode.history
        )
    )
    if not finite_trajectory:
        raise FloatingPointError("adaptive trajectory contains a non-finite diagnostic")
    return {
        "run_id": provenance.run_id,
        "stratum_id": provenance.stratum_id,
        "partition": provenance.study_partition,
        "gamma_b_eff_db": provenance.gamma_db,
        "sigma_squared": provenance.sigma_squared,
        "F": request.symbols_per_run,
        "total_bits": b_counts.total_bits,
        "total_symbols": b_counts.total_symbols,
        "b_bit_errors": b_counts.bit_errors,
        "c_bit_errors": c_counts.bit_errors,
        "b_symbol_errors": b_counts.symbol_errors,
        "c_symbol_errors": c_counts.symbol_errors,
        "delta_ber_run": (c_counts.bit_errors - b_counts.bit_errors) / b_counts.total_bits,
        "delta_ser_run": (c_counts.symbol_errors - b_counts.symbol_errors) / b_counts.total_symbols,
        "received_sha256": result.received_sha256,
        "data_master_seed": provenance.data_master_seed,
        "data_spawn_key": list(provenance.data_spawn_key),
        "data_seed": provenance.data_seed,
        "noise_master_seed": provenance.noise_master_seed,
        "noise_spawn_key": list(provenance.noise_spawn_key),
        "noise_seed": provenance.noise_seed,
        "bootstrap_seed": provenance.bootstrap_seed,
        "sample_origin": provenance.sample_origin,
        "symbol_origin": provenance.symbol_origin,
        "estimator_time_origin": provenance.estimator_time_origin,
        "b_initial_full_iq": list(_state_pair(b_mode.initial_state)),
        "b_final_full_iq": list(_state_pair(b_mode.final_state)),
        "c_initial_full_iq": list(_state_pair(c_mode.initial_state)),
        "c_final_full_iq": list(_state_pair(c_mode.final_state)),
        "c_initial_coefficient_error_norm": initial_error,
        "c_final_coefficient_error_norm": float(c_errors[-1]),
        "c_max_coefficient_error_norm": float(np.max(c_errors)),
        "c_max_update_increment_norm": float(np.max(increments)),
        "c_mean_posterior_entropy": float(np.mean(entropy)),
        "c_max_posterior_entropy": float(np.max(entropy)),
        "c_finite_trajectory": finite_trajectory,
        "c_finite_error_growth_flag": bool(np.max(c_errors) > initial_error),
        "paired_buffer_identity_ok": True,
        "b_state_frozen_ok": True,
        "receiver_status": result.status,
        "receiver_decodes": 3,
        "run_elapsed_seconds": time.perf_counter() - started,
        "completed_at_utc": _utc_now(),
        "status": "completed",
    }


def _failure_json(failure: object) -> dict[str, Any]:
    return {
        "run_id": failure.run_id,
        "stratum_id": failure.stratum_id,
        "exception_type": failure.exception_type,
        "detail": failure.detail,
        "last_valid_state": failure.last_valid_state,
        "last_valid_time_index": failure.last_valid_time_index,
        "diagnostics": failure.diagnostics,
        "status": "numerical_failure",
        "completed_at_utc": _utc_now(),
    }


def _checkpoint_callback(
    directory: Path,
    config_hash: str,
    code_hash: str,
    output_size_limit: int,
):
    def save(provenance: M5HRunProvenance, status: str, result: object) -> None:
        if status == "numerical_failure":
            record = _failure_json(result)
        else:
            record = dict(result)
        record["provenance"] = {
            "run_id": provenance.run_id,
            "partition": provenance.study_partition,
            "stratum_id": provenance.stratum_id,
            "run_index": provenance.run_index,
            "gamma_b_eff_db": provenance.gamma_db,
            "sigma_squared": provenance.sigma_squared,
            "data_master_seed": provenance.data_master_seed,
            "data_spawn_key": list(provenance.data_spawn_key),
            "data_seed": provenance.data_seed,
            "noise_master_seed": provenance.noise_master_seed,
            "noise_spawn_key": list(provenance.noise_spawn_key),
            "noise_seed": provenance.noise_seed,
            "bootstrap_seed": provenance.bootstrap_seed,
            "sample_origin": provenance.sample_origin,
            "symbol_origin": provenance.symbol_origin,
            "estimator_time_origin": provenance.estimator_time_origin,
        }
        record["status"] = status
        record["config_fingerprint"] = config_hash
        record["code_fingerprint"] = code_hash
        write_run_checkpoint(
            directory / "checkpoints",
            record,
            config_fingerprint=config_hash,
            code_fingerprint=code_hash,
        )
        (directory / ".current_run.json").unlink(missing_ok=True)
        size = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
        if size > output_size_limit:
            raise OSError("pilot output exceeded the configured 100 MiB target")

    return save


def _summarize(
    config_data: Mapping[str, Any],
    checkpoint_records: Mapping[str, Mapping[str, Any]],
    *,
    execution_status: str,
    supervisor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = validate_m5h_pilot_config(config_data)
    by_stratum: dict[str, list[Mapping[str, Any]]] = {
        f"gamma-{value:g}dB": [] for value in config.gamma_grid_db
    }
    for record in checkpoint_records.values():
        by_stratum[record["stratum_id"]].append(record)
    stratum_results: list[dict[str, Any]] = []
    total_completed = 0
    total_failed = 0
    for stratum in config.strata:
        stratum_id = f"gamma-{stratum.gamma_db:g}dB"
        records = sorted(by_stratum[stratum_id], key=lambda item: item["run_id"])
        valid = [item for item in records if item["status"] == "completed"]
        failures = [item for item in records if item["status"] == "numerical_failure"]
        expected = config.run_count_per_stratum
        missing = expected - len(records)
        total_completed += len(valid)
        total_failed += len(failures)
        entry: dict[str, Any] = {
            "stratum_id": stratum_id,
            "gamma_b_eff_db": stratum.gamma_db,
            "sigma_squared": stratum.sigma_squared,
            "planned_runs": expected,
            "completed_valid_runs": len(valid),
            "numerical_failures": len(failures),
            "unfinished_runs": missing,
            "full_design_valid": len(valid) == expected and not failures,
            "pooled_metrics_status": "not computed: incomplete or failed stratum",
            "failed_run_ids": [item["run_id"] for item in failures],
        }
        if entry["full_design_valid"]:
            counts = tuple(
                PairedRunCounts(
                    run_id=item["run_id"],
                    b_counts=ErrorCounts(
                        bit_errors=int(item["b_bit_errors"]),
                        total_bits=int(item["total_bits"]),
                        symbol_errors=int(item["b_symbol_errors"]),
                        total_symbols=int(item["total_symbols"]),
                    ),
                    c_counts=ErrorCounts(
                        bit_errors=int(item["c_bit_errors"]),
                        total_bits=int(item["total_bits"]),
                        symbol_errors=int(item["c_symbol_errors"]),
                        total_symbols=int(item["total_symbols"]),
                    ),
                )
                for item in records
            )
            bootstrap_seed = int(valid[0]["bootstrap_seed"])
            summary = paired_cluster_bootstrap(
                counts,
                bootstrap_replicates=2000,
                confidence_level=0.95,
                bootstrap_seed=bootstrap_seed,
            )
            estimates = summary.point_estimates
            entry.update(
                {
                    "pooled_metrics_status": "complete pilot stratum; descriptive only",
                    "pooled": {
                        "b_bit_errors": estimates.b_counts.bit_errors,
                        "b_total_bits": estimates.b_counts.total_bits,
                        "ber_b": estimates.ber_b,
                        "c_bit_errors": estimates.c_counts.bit_errors,
                        "c_total_bits": estimates.c_counts.total_bits,
                        "ber_c": estimates.ber_c,
                        "delta_ber": estimates.delta_ber,
                        "b_symbol_errors": estimates.b_counts.symbol_errors,
                        "b_total_symbols": estimates.b_counts.total_symbols,
                        "ser_b": estimates.ser_b,
                        "c_symbol_errors": estimates.c_counts.symbol_errors,
                        "c_total_symbols": estimates.c_counts.total_symbols,
                        "ser_c": estimates.ser_c,
                        "delta_ser": estimates.delta_ser,
                    },
                    "bootstrap": {
                        "replicates": summary.bootstrap_replicates,
                        "confidence_level": summary.confidence_level,
                        "interval": "two-sided percentile",
                        "quantile_method": summary.quantile_method,
                        "bit_generator": summary.bit_generator,
                        "bootstrap_seed": summary.bootstrap_seed,
                        "ordered_run_ids": list(summary.ordered_run_ids),
                        "intervals": [
                            {"metric": item.metric, "lower": item.lower, "upper": item.upper}
                            for item in summary.intervals
                        ],
                        "warning_flags": list(summary.warning_flags),
                        "replicate_estimates": summary.replicate_estimates.tolist(),
                        "resample_indices": summary.resample_indices.tolist(),
                    },
                    "coefficient_diagnostics": {
                        "finite_trajectory_runs": sum(
                            bool(item["c_finite_trajectory"]) for item in valid
                        ),
                        "finite_error_growth_runs": sum(
                            bool(item["c_finite_error_growth_flag"]) for item in valid
                        ),
                        "mean_c_max_coefficient_error_norm": float(
                            np.mean([item["c_max_coefficient_error_norm"] for item in valid])
                        ),
                        "mean_c_max_update_increment_norm": float(
                            np.mean([item["c_max_update_increment_norm"] for item in valid])
                        ),
                        "mean_c_posterior_entropy": float(
                            np.mean([item["c_mean_posterior_entropy"] for item in valid])
                        ),
                    },
                }
            )
        stratum_results.append(entry)

    primary_records = by_stratum["gamma-5dB"]
    primary_valid = [item for item in primary_records if item["status"] == "completed"]
    differences = np.asarray(
        [
            (int(item["c_bit_errors"]) - int(item["b_bit_errors"])) / (2 * config.symbols_per_run)
            for item in primary_valid
        ],
        dtype=np.float64,
    )
    sd = float(np.std(differences, ddof=1)) if differences.size >= 2 else None
    r_approx = int(math.ceil((1.96 * sd / 0.02) ** 2)) if sd is not None and sd > 0 else None
    sample_size_status = (
        "candidate planning estimate only"
        if r_approx is not None and differences.size == config.run_count_per_stratum
        else "BLOCKED: incomplete, zero-variance, or degenerate primary pilot"
    )
    planned_total = len(config.strata) * config.run_count_per_stratum
    return {
        "study_id": config.study_id,
        "design_version": config.design_version,
        "config_fingerprint": config_fingerprint(config_data),
        "source_draft_sha256": config.source_draft_sha256,
        "code_fingerprint": json.loads(config.code_fingerprint_json or "{}"),
        "status": execution_status,
        "evidence_boundary": "authorized independent planning pilot, NOT confirmatory performance evidence, NOT paper-exact receiver, NOT physical HF Eb/N0 comparison",
        "planned_runs": planned_total,
        "completed_valid_runs": total_completed,
        "numerical_failures": total_failed,
        "unfinished_runs": planned_total - total_completed - total_failed,
        "all_120_valid_runs_complete": total_completed == planned_total and total_failed == 0,
        "confirmatory_inference": "BLOCKED; pilot is not confirmatory",
        "strata": stratum_results,
        "primary_5db_run_level_variability": {
            "valid_run_count": int(differences.size),
            "d_r_definition": "(C_bit_errors-B_bit_errors)/(2F)",
            "d_r_values": differences.tolist(),
            "sample_standard_deviation_s_d": sd,
            "epsilon_candidate": 0.02,
            "R_approx": r_approx,
            "status": sample_size_status,
            "limitations": [
                "normal approximation only; does not guarantee percentile cluster-bootstrap half-width",
                "pilot s_d is uncertain with 30 independent sequences",
                "zero-error or degenerate differences make naive precision claims unreliable",
                "R_approx is not approved and no confirmatory run is launched",
            ],
        },
        "supervisor": dict(supervisor or {}),
        "record_count": len(checkpoint_records),
        "receiver_decodes_total": sum(
            int(record.get("receiver_decodes", 0))
            for record in checkpoint_records.values()
            if record.get("status") == "completed"
        ),
        "output_size_target_bytes": _OUTPUT_LIMIT_BYTES,
        "new_data_generated_for_bootstrap": False,
    }


def _worker(approved_path: Path, output_dir: Path) -> int:
    raw = json.loads(approved_path.read_text(encoding="utf-8"))
    config = validate_m5h_pilot_config(raw)
    if config.design_status != "approved_for_pilot" or config.execution_scope != "m5h_pilot_only":
        raise ValueError("worker received a config outside the authorized pilot scope")
    if file_sha256(_DRAFT_PATH) != config.source_draft_sha256:
        raise ValueError("source M5h draft hash differs from approved run config")
    current_code = compute_code_fingerprint()
    if current_code != json.loads(config.code_fingerprint_json or "{}"):
        raise ValueError("code fingerprint differs from approved run config")
    config_hash = config_fingerprint(raw)
    code_hash = _sha256_bytes(_json_bytes(current_code))
    checkpoint_dir = output_dir / "checkpoints"
    existing = load_run_checkpoints(
        checkpoint_dir,
        expected_config_fingerprint=config_hash,
        expected_code_fingerprint=code_hash,
    )
    expected_provenance = {
        item.run_id: item for item in derive_m5h_run_provenance(config, partition="pilot")
    }
    expected = set(expected_provenance)
    if set(existing).difference(expected):
        raise ValueError("checkpoint contains run IDs outside the approved design")
    for run_id, record in existing.items():
        if record.get("status") not in ("completed", "numerical_failure"):
            raise ValueError(f"checkpoint has a nonterminal status for {run_id}")
        expected_item = expected_provenance[run_id]
        expected_seeds = {
            "data_seed": expected_item.data_seed,
            "data_spawn_key": list(expected_item.data_spawn_key),
            "noise_seed": expected_item.noise_seed,
            "noise_spawn_key": list(expected_item.noise_spawn_key),
            "bootstrap_seed": expected_item.bootstrap_seed,
        }
        stored = record.get("provenance")
        if not isinstance(stored, dict) or any(
            stored.get(key) != value for key, value in expected_seeds.items()
        ):
            raise ValueError(f"checkpoint seed provenance mismatch for {run_id}")

    current_path = output_dir / ".current_run.json"

    def mark_start(item: M5HRunProvenance) -> None:
        atomic_write_json(
            current_path,
            {
                "run_id": item.run_id,
                "stratum_id": item.stratum_id,
                "data_seed": item.data_seed,
                "noise_seed": item.noise_seed,
                "started_at_utc": _utc_now(),
                "status": "in_progress",
            },
        )

    result = run_m5h_pilot(
        config,
        execute_run=_pilot_run,
        completed_run_ids=tuple(existing),
        on_run_start=mark_start,
        on_checkpoint=_checkpoint_callback(output_dir, config_hash, code_hash, _OUTPUT_LIMIT_BYTES),
    )
    checkpoints = load_run_checkpoints(
        checkpoint_dir,
        expected_config_fingerprint=config_hash,
        expected_code_fingerprint=code_hash,
    )
    summary = _summarize(raw, checkpoints, execution_status="completed")
    summary["skipped_on_resume"] = result.skipped_run_count
    summary["approved_config_file_sha256"] = file_sha256(approved_path)
    atomic_write_json(output_dir / "summary.json", summary)
    (output_dir / "progress.json").unlink(missing_ok=True)
    return 0


def supervise_pilot(approved_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Launch one worker and monitor wall time and process RSS from the parent."""
    approved_file = Path(approved_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    raw = json.loads(approved_file.read_text(encoding="utf-8"))
    config = validate_m5h_pilot_config(raw)
    if config.design_status != "approved_for_pilot" or not config.execution_authorized:
        raise ValueError("supervisor requires an approved and explicitly authorized pilot config")
    lock_path = output / "pilot.lock"
    try:
        with lock_path.open("x", encoding="utf-8") as lock:
            lock.write(f"pid={os.getpid()}\nstarted={_utc_now()}\n")
    except FileExistsError as exc:
        raise RuntimeError("another supervisor owns this pilot output directory") from exc
    config_hash = config_fingerprint(raw)
    code_fp = json.loads(config.code_fingerprint_json or "{}")
    code_hash = _sha256_bytes(_json_bytes(code_fp))
    started = time.monotonic()
    wall_limit = _WALL_LIMIT_SECONDS
    rss_available = False
    rss_sample_count = 0
    rss_sample_failures = 0
    peak_rss: int | None = None
    termination_reason: str | None = None
    log_path = output / "worker.log"
    command = [
        sys.executable,
        "-m",
        "hf_tcm.evaluation.m5h_pilot_runner",
        "--worker",
        str(approved_file.resolve()),
        str(output.resolve()),
    ]
    try:
        with log_path.open("ab") as log_stream:
            process = subprocess.Popen(
                command,
                cwd=_REPO_ROOT,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed >= wall_limit:
                        termination_reason = "wall_clock_budget_observed"
                        process.kill()
                        process.wait(timeout=5.0)
                        break
                    rss = _process_rss_windows(process.pid)
                    if rss is None:
                        rss_sample_failures += 1
                    else:
                        rss_available = True
                        rss_sample_count += 1
                        peak_rss = max(peak_rss or 0, rss)
                        if rss > _RSS_LIMIT:
                            termination_reason = "rss_ceiling_observed_by_parent_monitor"
                            process.kill()
                            process.wait(timeout=5.0)
                            break
                    time.sleep(_MONITOR_INTERVAL_SECONDS)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5.0)
    finally:
        lock_path.unlink(missing_ok=True)
    elapsed_total = time.monotonic() - started
    exit_code = process.returncode
    output_size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    checkpoints = load_run_checkpoints(
        output / "checkpoints",
        expected_config_fingerprint=config_hash,
        expected_code_fingerprint=code_hash,
    )
    complete = (
        exit_code == 0
        and termination_reason is None
        and len(checkpoints) == 120
        and all(record["status"] == "completed" for record in checkpoints.values())
    )
    status = (
        "completed"
        if complete
        else "incomplete_resource_or_runtime_interruption"
        if termination_reason is not None
        else "completed_with_numerical_failures"
        if exit_code == 0
        and len(checkpoints) == 120
        and any(record["status"] == "numerical_failure" for record in checkpoints.values())
        else "incomplete_worker_failure"
    )
    progress = {
        "status": status,
        "termination_reason": termination_reason,
        "worker_exit_code": exit_code,
        "wall_clock_seconds": elapsed_total,
        "worker_process_count": 1,
        "rss_measurement_available": rss_available,
        "rss_sample_count": rss_sample_count,
        "rss_sample_failures": rss_sample_failures,
        "observed_peak_rss_bytes": peak_rss if rss_available else None,
        "rss_monitor_interval_seconds": _MONITOR_INTERVAL_SECONDS,
        "resource_limit_semantics": "sampled parent monitor; no OS hard RSS cap; termination may be delayed by polling/scheduling",
        "planned_runs": 120,
        "checkpointed_attempts": len(checkpoints),
        "output_size_bytes": output_size,
        "output_size_target_bytes": _OUTPUT_LIMIT_BYTES,
        "current_run_at_interruption": None,
    }
    current_path = output / ".current_run.json"
    if termination_reason and current_path.exists():
        progress["current_run_at_interruption"] = json.loads(
            current_path.read_text(encoding="utf-8")
        )
        progress["current_run_status"] = "incomplete; may resume with original seeds"
    atomic_write_json(output / "progress.json", progress)
    attempts_path = output / "execution_attempts.json"
    attempts = (
        json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else []
    )
    attempts.append(progress)
    atomic_write_json(attempts_path, attempts)
    summary = _summarize(raw, checkpoints, execution_status=status, supervisor=progress)
    summary["approved_config_file_sha256"] = file_sha256(approved_file)
    atomic_write_json(output / "summary.json", summary)
    return {**progress, "summary_path": str(output / "summary.json")}


def launch_authorized_pilot(
    *,
    output_root: str | Path = _REPO_ROOT / "outputs/m5h_independent_pilot",
) -> dict[str, Any]:
    memory = _memory_status_windows()
    if memory is None:
        raise RuntimeError("system memory preflight is unavailable; no pilot started")
    available, _total = memory
    if available < 2 * 1024**3:
        raise RuntimeError("available physical memory is below the recommended 2 GiB minimum")
    output = create_run_directory(output_root)
    approved_path = output / "approved_run_config.json"
    create_approved_run_config(
        _DRAFT_PATH,
        approved_path,
        available_memory_before_bytes=available,
    )
    code_fingerprint = compute_code_fingerprint()
    config_hash = file_sha256(approved_path)
    atomic_write_json(
        output / "execution_manifest.json",
        {
            "approved_config_path": approved_path.name,
            "approved_config_sha256": config_hash,
            "code_fingerprint": code_fingerprint,
            "code_revision_identifier": None,
            "code_revision_status": "unavailable: workspace is not a Git worktree",
            "available_physical_memory_before_bytes": available,
            "worker_processes": 1,
            "started_at_utc": _utc_now(),
            "python_version": sys.version,
            "numpy_version": np.__version__,
            "platform": platform.platform(),
        },
        exclusive=True,
    )
    return supervise_pilot(approved_path, output)


def create_run_directory(root: str | Path, *, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(root) / timestamp
    output.mkdir(parents=True, exist_ok=False)
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("approved_config", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker(args.approved_config, args.output_dir)
    if args.supervise:
        result = supervise_pilot(args.approved_config, args.output_dir)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["worker_exit_code"] == 0 else 1
    raise SystemExit("Use --supervise with the immutable approved config and its run directory.")


if __name__ == "__main__":
    raise SystemExit(main())
