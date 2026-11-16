"""Approved single-process M5j confirmatory runner and resource supervisor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.evaluation.error_metrics import ErrorCounts
from hf_tcm.evaluation.m5h_pilot_runner import (
    _process_rss_windows,
    file_sha256,
)
from hf_tcm.evaluation.m5i_confirmatory_design import (
    load_m5i_confirmatory_design,
    validate_m5i_seed_manifest,
)
from hf_tcm.evaluation.paired_cluster_bootstrap import PairedRunCounts, paired_cluster_bootstrap
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import run_adaptive_estimator_diagnostic
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState

_REPO_ROOT = Path(__file__).resolve().parents[3]
_M5I_CONFIG = _REPO_ROOT / "configs/m5i_confirmatory_design_draft.json"
_M5I_MANIFEST = _REPO_ROOT / "configs/m5i_confirmatory_run_manifest_draft.json"
_APPROVAL_PHRASE = "explicit user authorization through the current M5j Codex execution instruction"
_SCOPE = "m5j_confirmatory_only"
_STATUS = "approved_confirmatory"
_WALL_LIMIT = 900.0
_RSS_LIMIT = 1_610_612_736
_POLL = 0.25
_BOOTSTRAP_REPLICATES = 2000
_CONFIDENCE = 0.95
_CODE_PATHS = (
    "src/hf_tcm/evaluation/m5i_confirmatory_design.py",
    "src/hf_tcm/evaluation/m5h_pilot_protocol.py",
    "src/hf_tcm/evaluation/m5h_pilot_runner.py",
    "src/hf_tcm/evaluation/m5j_confirmatory_runner.py",
    "src/hf_tcm/evaluation/reconstruction_paired_monte_carlo.py",
    "src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py",
    "src/hf_tcm/evaluation/paired_cluster_bootstrap.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/reconstruction_config.py",
    "src/hf_tcm/receiver/reconstruction_forward.py",
    "src/hf_tcm/receiver/reconstruction_estimator_state.py",
    "src/hf_tcm/receiver/reconstruction_causal_step.py",
    "src/hf_tcm/receiver/reconstruction_candidate_metrics.py",
    "src/hf_tcm/receiver/reconstruction_labeling.py",
    "src/hf_tcm/receiver/reconstruction_observation.py",
    "src/hf_tcm/receiver/reconstruction_posterior.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_step.py",
    "src/hf_tcm/receiver/iq.py",
    "src/hf_tcm/coding/encoder.py",
    "src/hf_tcm/coding/hypotheses.py",
    "src/hf_tcm/coding/hypothesis_path.py",
    "src/hf_tcm/decoding/reconstruction_viterbi.py",
    "src/hf_tcm/modulation/labeling.py",
    "src/hf_tcm/modulation/psk8.py",
)


class M5JExecutionBlocked(RuntimeError):
    """M5j run-specific authorization is invalid or absent."""


@dataclass(frozen=True, slots=True)
class M5JApprovedRunConfig:
    config_json: str
    config_sha256: str
    path: Path

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.config_json)


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _code_fingerprint() -> dict[str, str]:
    result = {}
    for relative in _CODE_PATHS:
        path = _REPO_ROOT / relative
        if not path.is_file():
            raise ValueError(f"required code file missing: {relative}")
        result[relative] = file_sha256(path)
    return result


def _revision() -> dict[str, str | None]:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "code_revision_identifier": None,
            "code_revision_status": "unavailable: workspace is not a Git worktree",
        }
    rev = done.stdout.strip()
    return {
        "code_revision_identifier": rev or None,
        "code_revision_status": "available" if rev else "unavailable",
    }


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_object(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def create_approved_m5j_run_config(
    design_path: str | Path,
    manifest_path: str | Path,
    output_path: str | Path,
    *,
    available_memory_before_bytes: int | None,
    rss_monitoring_available: bool = False,
    approved_at_utc: str | None = None,
) -> M5JApprovedRunConfig:
    """Freeze and hash an M5j run-specific approval before stochastic work."""
    out = Path(output_path)
    sidecar = Path(str(out) + ".sha256")
    if out.exists() or sidecar.exists():
        raise FileExistsError(f"immutable M5j approval already exists: {out}")
    design = load_m5i_confirmatory_design(design_path)
    manifest = _read_object(manifest_path, "M5i manifest")
    validate_m5i_seed_manifest(manifest, design)
    if available_memory_before_bytes is not None and available_memory_before_bytes < 0:
        raise ValueError("available memory cannot be negative")
    if available_memory_before_bytes is not None and available_memory_before_bytes < 2 * 1024**3:
        raise ValueError("M5j requires at least 2 GiB available memory before execution")
    stamp = approved_at_utc or _utc_now()
    try:
        parsed = datetime.fromisoformat(stamp)
    except (TypeError, ValueError) as exc:
        raise ValueError("approval time must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("approval time must include timezone")
    approval = {
        "schema_version": 1,
        "study_id": design.study_id,
        "design_id": "M5j-independent-confirmatory-evaluation",
        "design_version": "M5j-1",
        "design_status": _STATUS,
        "execution_authorized": True,
        "execution_scope": _SCOPE,
        "authorization_provenance": {
            "explicit_user_authorization": _APPROVAL_PHRASE,
            "approved_at_utc": stamp,
            "source_design_version": design.design_version,
            "source_design_fingerprint": design.fingerprint,
            "approved_parameter_snapshot": design.as_dict(),
        },
        "m5i_design_path": str(Path(design_path).resolve()),
        "m5i_design_file_sha256": file_sha256(design_path),
        "design_snapshot_fingerprint": design.fingerprint,
        "approved_design_fingerprint": design.fingerprint,
        "design_snapshot": design.as_dict(),
        "planned_manifest_path": str(Path(manifest_path).resolve()),
        "planned_manifest_sha256": file_sha256(manifest_path),
        "planned_manifest_fingerprint": _canonical_sha(manifest),
        "planned_manifest_snapshot": manifest,
        "planned_run_count": 100,
        "execution_limits": {
            "wall_clock_limit_seconds": _WALL_LIMIT,
            "rss_limit_bytes": _RSS_LIMIT,
            "rss_monitoring_available_at_approval": rss_monitoring_available,
            "rss_semantics": "periodic parent-process sampling; not a hard OS RSS cap",
            "monitor_interval_seconds": _POLL,
            "worker_processes": 1,
            "multiprocessing": False,
            "available_memory_before_bytes": available_memory_before_bytes,
            "checkpoint_after_each_full_run": True,
            "atomic_checkpoints": True,
        },
        "code_fingerprint": _code_fingerprint(),
        **_revision(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "prng": "numpy.random.PCG64",
        "approval_boundary": "m5j_confirmatory_only; never reuse m5h_pilot_only authorization",
    }
    _write_exclusive(out, approval)
    digest = file_sha256(out)
    with sidecar.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return M5JApprovedRunConfig(
        json.dumps(approval, sort_keys=True, separators=(",", ":"), ensure_ascii=False), digest, out
    )


def validate_approved_m5j_run_config(
    path: str | Path, design_path: str | Path, manifest_path: str | Path
) -> M5JApprovedRunConfig:
    value = _read_object(path, "approved M5j config")
    digest = file_sha256(path)
    sidecar = Path(str(path) + ".sha256")
    if not sidecar.is_file() or sidecar.read_text(encoding="ascii").strip() != digest:
        raise ValueError("approved config hash sidecar mismatch")
    design = load_m5i_confirmatory_design(design_path)
    manifest = _read_object(manifest_path, "M5i manifest")
    validate_m5i_seed_manifest(manifest, design)
    if (
        value.get("design_status") != _STATUS
        or value.get("execution_authorized") is not True
        or value.get("execution_scope") != _SCOPE
    ):
        raise ValueError("M5j approval status/scope invalid")
    if (
        value.get("design_snapshot_fingerprint") != design.fingerprint
        or value.get("approved_design_fingerprint") != design.fingerprint
        or value.get("design_snapshot") != design.as_dict()
    ):
        raise ValueError("M5i frozen design snapshot mismatch")
    if (
        value.get("m5i_design_file_sha256") != file_sha256(design_path)
        or value.get("planned_manifest_sha256") != file_sha256(manifest_path)
        or value.get("planned_manifest_snapshot") != manifest
        or value.get("planned_manifest_fingerprint") != _canonical_sha(manifest)
    ):
        raise ValueError("M5i manifest/config provenance mismatch")
    if value.get("code_fingerprint") != _code_fingerprint():
        raise ValueError("M5j code fingerprint changed since approval")
    if (
        value.get("python_version") != platform.python_version()
        or value.get("numpy_version") != np.__version__
        or value.get("prng") != "numpy.random.PCG64"
    ):
        raise ValueError("runtime/PRNG provenance changed since approval")
    provenance = value.get("authorization_provenance", {})
    if (
        provenance.get("explicit_user_authorization") != _APPROVAL_PHRASE
        or provenance.get("source_design_fingerprint") != design.fingerprint
    ):
        raise ValueError("approval provenance invalid")
    if (
        value.get("planned_run_count") != 100
        or value.get("execution_limits", {}).get("wall_clock_limit_seconds") != 900
    ):
        raise ValueError("fixed M5j run/resource budget mismatch")
    return M5JApprovedRunConfig(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        digest,
        Path(path),
    )


def guard_m5j_execution(authorization: Mapping[str, Any], *, executor: Callable[[], Any]) -> Any:
    """Reject before invoking any callback capable of stochastic work."""
    if (
        authorization.get("design_status") != _STATUS
        or authorization.get("execution_authorized") is not True
        or authorization.get("execution_scope") != _SCOPE
    ):
        raise M5JExecutionBlocked(
            "M5j requires a valid approved_confirmatory/m5j_confirmatory_only authorization"
        )
    return executor()


def _run_one(run: Mapping[str, Any], design: Mapping[str, Any]) -> dict[str, Any]:
    from hf_tcm.evaluation.error_metrics import evaluate_run

    seed_data = int(run["data"]["derived_seed"])
    seed_noise = int(run["noise"]["derived_seed"])
    data_rng = np.random.Generator(np.random.PCG64(seed_data))
    bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
    policies = design["receiver_policies"]
    shared = policies["shared"]
    c = policies["C"]
    cond = design["primary_condition"]
    state = ReconstructionEstimatorState(
        np.asarray([shared["initial_fluctuating_iq"]], dtype=float),
        np.asarray([shared["initial_full_iq"]], dtype=float),
        0,
    )
    result = run_adaptive_estimator_diagnostic(
        run_id=run["run_id"],
        reference_information_bits=bits,
        real_channel_gain=0.75,
        sigma_squared=float(cond["sigma_squared"]),
        noise=None,
        noise_seed=seed_noise,
        noise_stream_id=f"M5j:evaluation:gamma-5dB:{run['run_id']}:noise",
        noise_provenance="M5j evaluation namespace; ADR-015 independent circular complex AWGN; deterministic SeedSequence derivation",
        symbol_origin_sample=0,
        first_symbol_index=0,
        initial_estimator_time_index=0,
        configuration=design["reconstruction_configuration"],
        mismatched_initial_state=state,
        adaptive_alpha_prime=float(c["alpha_prime"]),
        adaptive_k_tilde=np.asarray([c["K_tilde"]], dtype=float),
        adaptive_mu0=np.asarray([c["mu0"]], dtype=float),
        receiver_mode="monolithic",
        segment_partition=None,
    )
    b = result.mismatched_frozen
    adaptive = result.mismatched_adaptive
    if b.received_sha256 != adaptive.received_sha256 or b.received_sha256 != result.received_sha256:
        raise RuntimeError("paired received hash mismatch")
    b_eval = evaluate_run(
        result.reference_information_bits,
        b.decoded_information_bits,
        result.reference_symbol_indices,
        b.decoded_symbol_indices,
    )
    c_eval = evaluate_run(
        result.reference_information_bits,
        adaptive.decoded_information_bits,
        result.reference_symbol_indices,
        adaptive.decoded_symbol_indices,
    )

    def counts(v: Any) -> dict[str, int]:
        return {
            "bit_errors": int(v.counts.bit_errors),
            "total_bits": int(v.counts.total_bits),
            "symbol_errors": int(v.counts.symbol_errors),
            "total_symbols": int(v.counts.total_symbols),
        }

    traj = adaptive.history
    final_state = adaptive.final_state
    finite = bool(
        np.all(np.isfinite(final_state.full_iq)) and np.all(np.isfinite(final_state.fluctuating_iq))
    )
    increment_norms = []
    previous = state.full_iq
    for item in traj:
        current = item.post_state.full_iq
        increment_norms.append(float(np.linalg.norm(current - previous)))
        previous = current
    return {
        "run_id": run["run_id"],
        "stratum_id": run["stratum_id"],
        "run_index": run["run_index"],
        "partition": run["partition"],
        "seed_provenance": {"data": run["data"], "noise": run["noise"]},
        "received_sha256": result.received_sha256,
        "b_counts": counts(b_eval),
        "c_counts": counts(c_eval),
        "status": "complete_valid_output",
        "diagnostics": {
            "finite_coefficient_trajectory": finite,
            "initial_full_iq": shared["initial_full_iq"],
            "final_full_iq": np.asarray(final_state.full_iq).tolist(),
            "final_fluctuating_iq": np.asarray(final_state.fluctuating_iq).tolist(),
            "full_iq_increment_norms": increment_norms,
            "coefficient_error_norm": float(adaptive.history[-1].full_estimate_error_norm)
            if adaptive.history and np.isfinite(adaptive.history[-1].full_estimate_error_norm)
            else None,
            "decoder_output_B_symbols": len(b.decoder_result.symbol_indices),
            "decoder_output_C_symbols": len(adaptive.decoder_result.symbol_indices),
        },
    }


def _atomic_checkpoint(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def execute_m5j(
    approved_path: str | Path,
    design_path: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    approved = validate_approved_m5j_run_config(approved_path, design_path, manifest_path)
    auth = approved.data
    design = auth["design_snapshot"]
    manifest = auth["planned_manifest_snapshot"]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return guard_m5j_execution(
        auth, executor=lambda: _execute_runs(design, manifest, approved, out)
    )


def _execute_runs(
    design: Mapping[str, Any],
    manifest: Mapping[str, Any],
    approved: M5JApprovedRunConfig,
    out: Path,
) -> dict[str, Any]:
    runs = manifest["planned_runs"]
    checkpoints = out / "checkpoints"
    checkpoints.mkdir()
    records = []
    started = time.monotonic()
    reason = None
    existing = list(checkpoints.glob("*.json"))
    loaded_ids = set()
    for saved in existing:
        record = _read_object(saved, "checkpoint")
        if (
            record.get("config_sha256") != approved.config_sha256
            or record.get("code_fingerprint") != approved.data["code_fingerprint"]
        ):
            raise ValueError("checkpoint config/code fingerprint mismatch")
        if record.get("run_id") in loaded_ids:
            raise ValueError("duplicate checkpoint run ID")
        if record.get("run_id") not in {item["run_id"] for item in runs}:
            raise ValueError("checkpoint run ID not in frozen manifest")
        loaded_ids.add(record["run_id"])
    for run in runs:
        cp = checkpoints / f"{run['run_id'].split(':')[-1]}.json"
        if cp.exists():
            record = _read_object(cp, "checkpoint")
            if (
                record.get("config_sha256") != approved.config_sha256
                or record.get("run_id") != run["run_id"]
            ):
                raise ValueError("checkpoint fingerprint/ID mismatch")
            records.append(record)
            if record.get("status") != "complete_valid_output":
                reason = "prior_run_failure_checkpoint"
                break
            continue
        if time.monotonic() - started >= 900:
            reason = "wall_clock_budget_exhausted"
            break
        try:
            record = _run_one(run, design)
            record["config_sha256"] = approved.config_sha256
            record["code_fingerprint"] = approved.data["code_fingerprint"]
        except Exception as exc:
            record = {
                "run_id": run["run_id"],
                "stratum_id": run["stratum_id"],
                "run_index": run["run_index"],
                "status": "numerical_or_runtime_failure",
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
                "config_sha256": approved.config_sha256,
                "code_fingerprint": approved.data["code_fingerprint"],
            }
            _atomic_checkpoint(cp, record)
            records.append(record)
            reason = "planned_run_failure"
            break
        _atomic_checkpoint(cp, record)
        records.append(record)
    complete = [r for r in records if r.get("status") == "complete_valid_output"]
    failures = [r for r in records if r.get("status") != "complete_valid_output"]
    summary = {
        "study_id": "M5j-confirmatory-paired-ber",
        "status": "complete" if len(complete) == 100 and not failures else "incomplete",
        "stop_reason": reason,
        "planned_run_count": 100,
        "completed_valid_run_count": len(complete),
        "failure_record_count": len(failures),
        "not_completed_count": 100 - len(records),
        "elapsed_seconds": time.monotonic() - started,
        "config_sha256": approved.config_sha256,
        "records": records,
    }
    if len(complete) == 100 and not failures:
        paired = []
        for r in complete:

            def ec(x: Mapping[str, Any]) -> ErrorCounts:
                return ErrorCounts(
                    int(x["bit_errors"]),
                    int(x["total_bits"]),
                    int(x["symbol_errors"]),
                    int(x["total_symbols"]),
                )

            paired.append(PairedRunCounts(r["run_id"], ec(r["b_counts"]), ec(r["c_counts"])))
        boot = int(manifest["bootstrap"]["derived_seed"])
        bs = paired_cluster_bootstrap(
            paired, bootstrap_replicates=2000, confidence_level=0.95, bootstrap_seed=boot
        )
        summary["point_estimates"] = {
            "b_counts": bs.point_estimates.b_counts.__dict__
            if hasattr(bs.point_estimates.b_counts, "__dict__")
            else {
                "bit_errors": bs.point_estimates.b_counts.bit_errors,
                "total_bits": bs.point_estimates.b_counts.total_bits,
                "symbol_errors": bs.point_estimates.b_counts.symbol_errors,
                "total_symbols": bs.point_estimates.b_counts.total_symbols,
            },
            "c_counts": {
                "bit_errors": bs.point_estimates.c_counts.bit_errors,
                "total_bits": bs.point_estimates.c_counts.total_bits,
                "symbol_errors": bs.point_estimates.c_counts.symbol_errors,
                "total_symbols": bs.point_estimates.c_counts.total_symbols,
            },
            "ber_b": bs.point_estimates.ber_b,
            "ber_c": bs.point_estimates.ber_c,
            "delta_ber": bs.point_estimates.delta_ber,
            "ser_b": bs.point_estimates.ser_b,
            "ser_c": bs.point_estimates.ser_c,
            "delta_ser": bs.point_estimates.delta_ser,
        }
        summary["bootstrap"] = {
            "replicates": 2000,
            "confidence_level": 0.95,
            "seed": boot,
            "bit_generator": bs.bit_generator,
            "quantile_method": bs.quantile_method,
            "intervals": [
                {"metric": x.metric, "lower": x.lower, "upper": x.upper} for x in bs.intervals
            ],
            "warning_flags": list(bs.warning_flags),
            "delta_ber_half_width": (
                bs.interval("delta_ber").upper - bs.interval("delta_ber").lower
            )
            / 2,
        }
        summary["precision_target_met"] = summary["bootstrap"]["delta_ber_half_width"] <= 0.02
    _atomic_checkpoint(out / "summary.json", summary)
    return summary


def supervise_m5j(
    approved_path: str | Path,
    design_path: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run one worker and sample its RSS/time from a parent process."""
    validate_approved_m5j_run_config(approved_path, design_path, manifest_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "hf_tcm.evaluation.m5j_confirmatory_runner",
        "--worker",
        "--approved",
        str(Path(approved_path).resolve()),
        "--design",
        str(Path(design_path).resolve()),
        "--manifest",
        str(Path(manifest_path).resolve()),
        "--output",
        str(out.resolve()),
    ]
    started = time.monotonic()
    samples = []
    proc = subprocess.Popen(
        command, cwd=_REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    memory_monitoring = _process_rss_windows(proc.pid) is not None
    timed_out = False
    rss_exceeded = False
    try:
        while proc.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= _WALL_LIMIT:
                timed_out = True
                proc.terminate()
                break
            rss = _process_rss_windows(proc.pid)
            if rss is not None:
                value = int(rss)
                samples.append(value)
                if value > _RSS_LIMIT:
                    rss_exceeded = True
                    proc.terminate()
                    break
            time.sleep(_POLL)
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        stdout, stderr = proc.communicate()
    summary_path = out / "summary.json"
    if summary_path.exists():
        summary = _read_object(summary_path, "worker summary")
    else:
        checkpoints = out / "checkpoints"
        saved = (
            [_read_object(p, "checkpoint") for p in checkpoints.glob("*.json")]
            if checkpoints.exists()
            else []
        )
        summary = {
            "status": "incomplete",
            "planned_run_count": 100,
            "completed_valid_run_count": sum(
                r.get("status") == "complete_valid_output" for r in saved
            ),
            "failure_record_count": sum(r.get("status") != "complete_valid_output" for r in saved),
            "not_completed_count": 100 - len(saved),
            "records": saved,
            "stop_reason": "worker_terminated_before_summary",
        }
    summary["supervisor"] = {
        "wall_clock_seconds": time.monotonic() - started,
        "rss_monitoring_available": memory_monitoring,
        "rss_sample_count": len(samples),
        "observed_peak_rss_bytes": max(samples) if samples else None,
        "rss_semantics": "periodic Windows process RSS sampling; not a hard OS cap",
        "wall_clock_budget_exhausted": timed_out,
        "rss_budget_exceeded": rss_exceeded,
        "worker_exit_code": proc.returncode,
        "stdout": stdout[-2000:],
        "stderr": stderr[-4000:],
    }
    if timed_out or rss_exceeded:
        summary["status"] = "incomplete"
        summary["stop_reason"] = (
            "wall_clock_budget_exhausted" if timed_out else "rss_budget_exceeded"
        )
    _atomic_checkpoint(summary_path, summary)
    return summary


def _worker_summary_exit_code(result: Mapping[str, Any]) -> int:
    """Return success only when summary counts agree with all saved run records."""
    records = result.get("records")
    if not isinstance(records, list):
        raise ValueError("worker summary records must be a list")
    planned = int(result["planned_run_count"])
    completed = sum(record.get("status") == "complete_valid_output" for record in records)
    failures = sum(record.get("status") != "complete_valid_output" for record in records)
    not_completed = planned - len(records)
    if not_completed < 0 or (
        completed != result["completed_valid_run_count"]
        or failures != result["failure_record_count"]
        or not_completed != result["not_completed_count"]
    ):
        raise ValueError("worker summary counts do not match its run records")
    is_complete = (
        result["status"] == "complete"
        and completed == planned
        and failures == 0
        and not_completed == 0
    )
    return 0 if is_complete else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--approved")
    parser.add_argument("--design")
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.worker:
        parser.error("worker mode is internal; launch via the guarded supervisor API")
    result = execute_m5j(args.approved, args.design, args.manifest, args.output)
    exit_code = _worker_summary_exit_code(result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_valid_run_count": result["completed_valid_run_count"],
                "failure_record_count": result["failure_record_count"],
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
