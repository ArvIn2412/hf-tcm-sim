"""Durable, paired and resumable execution helpers for SCIENTIFIC-EXP-03B."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal

import numpy as np

from hf_tcm.repro.atomic_io import atomic_replace_bytes
from hf_tcm.repro.confirmatory_exp03b import (
    build_metric_trial_spec,
    build_system_trial_spec,
    system_trial_seeds,
    validate_frozen_protocol,
)
from hf_tcm.repro.energy_experiment import run_energy_trial
from hf_tcm.repro.metric_experiment import MetricTrialResult, run_metric_trial


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metric_arrays(result: MetricTrialResult) -> bytes:
    schedule = result.schedule
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        reference_payload_pairs=result.reference_payload_pairs,
        decoded_euclidean_pairs=result.decoded_euclidean_pairs,
        decoded_hamming_pairs=result.decoded_hamming_pairs,
        transmitted_samples=result.transmitted_samples,
        received_samples=result.received_samples,
        equalized_symbols=result.equalized_symbols,
        euclidean_branch_metrics=result.euclidean_branch_metrics,
        hamming_branch_metrics=result.hamming_branch_metrics,
        payload_mask=(
            np.ones(result.summary["frame_symbols_total"], dtype=bool)
            if schedule is None
            else schedule.payload_mask
        ),
        pilot_mask=(
            np.zeros(result.summary["frame_symbols_total"], dtype=bool)
            if schedule is None
            else schedule.pilot_mask
        ),
        known_phase_indices=(
            np.full(result.summary["frame_symbols_total"], -1, dtype=np.int8)
            if schedule is None
            else schedule.known_phase_indices
        ),
        selected_sample_indices=result.frontend.selected_sample_indices,
        estimated_composite_gain=result.frontend.estimated_composite_gain,
        output_noise_variance=result.frontend.output_noise_variance,
        gain_update_mask=result.frontend.gain_update_mask,
        gain_age_symbols=result.frontend.gain_age_symbols,
    )
    return buffer.getvalue()


def persist_metric_trial(
    root: str | os.PathLike[str],
    result: MetricTrialResult,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically persist one complete paired metric trial and its provenance."""
    base = Path(root)
    trial_id = str(metadata.get("trial_id", result.summary.get("trial_id", "")))
    if not trial_id or trial_id != result.summary.get("trial_id"):
        raise ValueError("metric record metadata trial_id must match the decoded trial")
    if any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
        for character in trial_id
    ):
        raise ValueError("trial_id contains an unsafe file-name character")
    trial_dir = base / "trials"
    array_name = f"{trial_id}.npz"
    record_name = f"{trial_id}.json"
    array_bytes = _metric_arrays(result)
    array_hash = sha256_bytes(array_bytes)
    row = {
        "schema_version": "scientific-exp03b-metric-trial-v1",
        **result.summary,
        **dict(metadata),
        "array_file": array_name,
        "array_file_sha256": array_hash,
    }
    if row.get("observation_sha256") != row.get("paired_observation_sha256"):
        raise ValueError("A-E/A-H observation provenance differs")
    if row.get("frontend_output_sha256_euclidean") != row.get("frontend_output_sha256_hamming"):
        raise ValueError("A-E/A-H frontend outputs differ")
    atomic_replace_bytes(trial_dir / array_name, array_bytes)
    atomic_replace_bytes(
        trial_dir / record_name,
        json.dumps(row, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n",
    )
    return row


def verify_metric_records(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Verify metric trial payload hashes, paired provenance and integer counts."""
    base = Path(root).resolve()
    paths = sorted((base / "trials").glob("*.json"))
    ids: set[str] = set()
    paired = 0
    bit_errors_seen = 0
    for record_path in paths:
        row = json.loads(record_path.read_text(encoding="utf-8"))
        trial_id = row.get("trial_id")
        if not isinstance(trial_id, str) or trial_id in ids:
            raise ValueError("missing or duplicate confirmatory trial_id")
        ids.add(trial_id)
        array_name = row.get("array_file")
        if not isinstance(array_name, str) or Path(array_name).name != array_name:
            raise ValueError("metric record array path must be a plain filename")
        array_path = base / "trials" / array_name
        if not array_path.is_file() or sha256_file(array_path) != row.get("array_file_sha256"):
            raise ValueError(f"metric trial payload failed SHA-256 verification: {array_name}")
        if row.get("observation_sha256") != row.get("paired_observation_sha256"):
            raise ValueError("A-E/A-H observation hashes differ")
        if row.get("frontend_output_sha256_euclidean") != row.get("frontend_output_sha256_hamming"):
            raise ValueError("A-E/A-H frontend hashes differ")
        with np.load(array_path, allow_pickle=False) as arrays:
            reference = arrays["reference_payload_pairs"].astype(np.int8)
            mask = arrays["payload_mask"].astype(bool)
            for arm, name in (
                ("euclidean", "decoded_euclidean_pairs"),
                ("hamming", "decoded_hamming_pairs"),
            ):
                decoded = arrays[name][mask].astype(np.int8)
                if decoded.shape != reference.shape:
                    raise ValueError("decoded payload length differs from reference")
                differences = decoded != reference
                bits = int(np.count_nonzero(differences))
                pairs = int(np.count_nonzero(np.any(differences, axis=1)))
                if bits != int(row[arm]["bit_errors"]) or pairs != int(row[arm]["pair_errors"]):
                    raise ValueError(f"independent BER/SER recount differs for {arm}")
                if not pairs <= bits <= 2 * pairs:
                    raise ValueError("BER and information-pair SER counts are inconsistent")
                bit_errors_seen += bits
        paired += 1
    return {
        "record_count": len(paths),
        "paired_observations": paired,
        "bit_errors_recounted": bit_errors_seen,
        "independent_count_replay": "PASS",
    }


def load_frozen_protocol(path: str | os.PathLike[str]) -> tuple[dict[str, Any], bytes, str, Path]:
    """Load and verify the v1.1 file plus its immutable parent/source hashes."""
    protocol_path = Path(path).resolve()
    raw = protocol_path.read_bytes()
    protocol = json.loads(raw.decode("utf-8"))
    validate_frozen_protocol(protocol)
    repo_root = protocol_path.parent.parent
    parent_path = repo_root / protocol["parent_protocol"]
    parent_hash = sha256_file(parent_path)
    if parent_hash != protocol.get("parent_protocol_sha256"):
        raise ValueError("parent frozen protocol SHA-256 differs from amendment")
    source_hashes = set()
    for line in (repo_root / "references/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=1)
        if fields:
            source_hashes.add(fields[0].lower())
    if not set(protocol["source_sha256"].values()) <= source_hashes:
        raise ValueError(
            "one or more scientific source hashes are absent from references/SHA256SUMS.txt"
        )
    if not (repo_root / protocol["amendment"]).is_file():
        raise FileNotFoundError("the protocol amendment must be present before execution")
    return protocol, raw, sha256_bytes(raw), repo_root


def _atomic_json(path: Path, value: object) -> None:
    atomic_replace_bytes(
        path,
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode(
            "utf-8"
        )
        + b"\n",
    )


def _acquire_lock(root: Path) -> Path:
    lock = root / ".run.lock"
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(str(os.getpid()))
                stream.flush()
                os.fsync(stream.fileno())
            return lock
        except FileExistsError:
            try:
                owner_pid = int(lock.read_text(encoding="ascii").strip())
                os.kill(owner_pid, 0)
            except ProcessLookupError:
                lock.unlink(missing_ok=True)
                continue
            except (ValueError, OSError):
                raise RuntimeError(f"cannot establish whether another run owns {lock}")
            raise RuntimeError(f"another SCIENTIFIC-EXP-03B process owns {lock}")
    raise RuntimeError(f"failed to acquire run lock {lock}")


def _append_checkpoint(root: Path, entry: Mapping[str, Any]) -> None:
    path = root / "checkpoint.jsonl"
    line = canonical_json(dict(entry)) + b"\n"
    with path.open("ab") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def _rebuild_metric_checkpoint(root: Path, rows: list[dict[str, Any]]) -> None:
    entries = []
    for row in sorted(rows, key=lambda item: item["trial_id"]):
        record_path = root / "trials" / f"{row['trial_id']}.json"
        array_path = root / "trials" / row["array_file"]
        entries.append(
            {
                "trial_id": row["trial_id"],
                "record_path": record_path.relative_to(root).as_posix(),
                "record_sha256": sha256_file(record_path),
                "array_path": array_path.relative_to(root).as_posix(),
                "array_sha256": sha256_file(array_path),
            }
        )
    atomic_replace_bytes(
        root / "checkpoint.jsonl", b"".join(canonical_json(entry) + b"\n" for entry in entries)
    )


def _rebuild_system_checkpoint(root: Path, rows: list[dict[str, Any]]) -> None:
    entries = []
    for row in sorted(rows, key=lambda item: item["trial_id"]):
        sidecar_path = root / "trials" / f"{row['trial_id']}.json"
        entries.append(
            {
                "trial_id": row["trial_id"],
                "record_path": sidecar_path.relative_to(root).as_posix(),
                "record_sha256": sha256_file(sidecar_path),
                "array_path": row["array_path"],
                "array_sha256": row["array_sha256"],
            }
        )
    atomic_replace_bytes(
        root / "checkpoint.jsonl", b"".join(canonical_json(entry) + b"\n" for entry in entries)
    )


def _write_root_manifest(
    root: Path, *, protocol_sha256: str, study_id: str, completed_trials: int, planned_trials: int
) -> None:
    checkpoint = root / "checkpoint.jsonl"
    _atomic_json(
        root / "manifest.json",
        {
            "schema_version": "scientific-exp03b-study-manifest-v1",
            "study_id": study_id,
            "protocol_sha256": protocol_sha256,
            "completed_trials": completed_trials,
            "planned_trials": planned_trials,
            "checkpoint_sha256": sha256_file(checkpoint)
            if checkpoint.is_file()
            else sha256_bytes(b""),
            "status": "completed" if completed_trials == planned_trials else "incomplete",
            "integrity_method": "per-trial JSON/NPZ SHA-256 plus durable checkpoint chain",
        },
    )


def _prepare_study(
    root: Path, raw_protocol: bytes, protocol_hash: str, design: dict[str, Any]
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "protocol.snapshot.json": raw_protocol,
        "design.json": json.dumps(design, sort_keys=True, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        + b"\n",
    }
    if not any((root / name).exists() for name in files) and any(root.iterdir()):
        raise ValueError("cannot resume a study directory without its immutable snapshot")
    for name, payload in files.items():
        target = root / name
        if target.exists():
            if target.read_bytes() != payload:
                raise ValueError(f"immutable study file differs on resume: {name}")
        else:
            atomic_replace_bytes(target, payload)
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != protocol_hash:
            raise ValueError("study manifest protocol hash mismatch")


def _check_resource_guard(root: Path, protocol: Mapping[str, Any]) -> None:
    free = shutil.disk_usage(root).free
    minimum = int(protocol["resource_protection"]["minimum_free_disk_bytes"])
    if free < minimum:
        raise OSError(f"free disk reserve {free} is below frozen minimum {minimum} bytes")


def _metric_existing(root: Path, protocol_hash: str, expected: set[str]) -> list[dict[str, Any]]:
    if not (root / "trials").is_dir():
        return []
    verify_metric_records(root)
    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "trials").glob("*.json"))
    ]
    ids = [row["trial_id"] for row in rows]
    if len(ids) != len(set(ids)) or not set(ids) <= expected:
        raise ValueError("metric checkpoint contains duplicate or out-of-design trials")
    if any(row.get("protocol_sha256") != protocol_hash for row in rows):
        raise ValueError("metric trial refers to a different frozen protocol")
    return rows


def run_metric_series(
    protocol_path: str | os.PathLike[str],
    output_root: str | os.PathLike[str],
    *,
    scenario_key: str,
    sweep: Literal["amplitude_fixed_noise", "noise_fixed_amplitude"],
    stage: Literal["preflight", "confirmatory"],
    stop_event: Any = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run/resume one frozen metric scenario/sweep with no wall-clock timeout."""
    protocol, raw, protocol_hash, _ = load_frozen_protocol(protocol_path)
    scenario = next(
        (row for row in protocol["metric_isolation"]["scenarios"] if row["id"] == scenario_key),
        None,
    )
    if scenario is None or sweep not in protocol["metric_isolation"]["sweeps"]:
        raise ValueError("metric series is outside the frozen protocol")
    if stage not in {"preflight", "confirmatory"}:
        raise ValueError("stage must be preflight or confirmatory")
    full_grid = list(scenario["energy_offsets_db"])
    point_indices = [len(full_grid) // 2] if stage == "preflight" else list(range(len(full_grid)))
    trials_per_point = int(
        protocol["metric_isolation"]["preflight_trials_per_point"]
        if stage == "preflight"
        else protocol["metric_isolation"]["confirmatory_trials_per_point"]
    )
    study_id = f"{stage}-{scenario_key}-{sweep}"
    root = Path(output_root).resolve() / "metric" / stage / study_id
    design = {
        "study_id": study_id,
        "block": "metric_isolation",
        "stage": stage,
        "scenario_key": scenario_key,
        "sweep": sweep,
        "point_indices": point_indices,
        "energy_offsets_db": [full_grid[index] for index in point_indices],
        "trials_per_point": trials_per_point,
        "planned_trials": len(point_indices) * trials_per_point,
        "protocol_sha256": protocol_hash,
    }
    _prepare_study(root, raw, protocol_hash, design)
    lock = _acquire_lock(root)
    started = time.perf_counter()
    planned = int(design["planned_trials"])
    expected = {
        f"exp03b-{stage}-{scenario_key}-{sweep}-p{point:02d}-t{trial:04d}"
        for point in point_indices
        for trial in range(trials_per_point)
    }
    try:
        rows = _metric_existing(root, protocol_hash, expected)
        _rebuild_metric_checkpoint(root, rows)
        existing = {row["trial_id"] for row in rows}
        skipped = len(existing)
        completed = skipped
        cpu_this_invocation = 0.0
        for point_index in point_indices:
            for trial_index in range(trials_per_point):
                spec = build_metric_trial_spec(
                    protocol, scenario_key, sweep, point_index, trial_index, stage
                )
                if spec.trial_id in existing:
                    continue
                if stop_event is not None and stop_event.is_set():
                    break
                _check_resource_guard(root, protocol)
                wall_start = time.perf_counter_ns()
                cpu_start = time.process_time_ns()
                result = run_metric_trial(spec)
                wall_elapsed_ns = time.perf_counter_ns() - wall_start
                cpu_elapsed_ns = time.process_time_ns() - cpu_start
                cpu_this_invocation += cpu_elapsed_ns / 1e9
                metadata = {
                    "experiment_id": protocol["experiment_id"],
                    "protocol_id": protocol["schema"],
                    "protocol_sha256": protocol_hash,
                    "block": "metric_isolation",
                    "stage": stage,
                    "scenario_key": scenario_key,
                    "sweep": sweep,
                    "sweep_offset_db": float(full_grid[point_index]),
                    "point_index": point_index,
                    "trial_index": trial_index,
                    "root_seed": int(
                        scenario["preflight_root_seed"]
                        if stage == "preflight"
                        else scenario["root_seed"]
                    ),
                    "derived_seeds": [
                        spec.source_seed,
                        spec.channel_config.fading_seed,
                        spec.channel_config.noise_seed,
                    ],
                    "raw_wall_elapsed_seconds": wall_elapsed_ns / 1e9,
                    "process_cpu_seconds": cpu_elapsed_ns / 1e9,
                    "timing_note": "No timing outlier is excluded from BER/SER/FER statistics.",
                }
                row = persist_metric_trial(root, result, metadata)
                entry = {
                    "trial_id": spec.trial_id,
                    "record_path": f"trials/{spec.trial_id}.json",
                    "record_sha256": sha256_file(root / "trials" / f"{spec.trial_id}.json"),
                    "array_path": f"trials/{row['array_file']}",
                    "array_sha256": row["array_file_sha256"],
                }
                _append_checkpoint(root, entry)
                existing.add(spec.trial_id)
                rows.append(row)
                completed += 1
                if completed % 100 == 0 or completed == planned:
                    _write_root_manifest(
                        root,
                        protocol_sha256=protocol_hash,
                        study_id=study_id,
                        completed_trials=completed,
                        planned_trials=planned,
                    )
                progress = {
                    "study_id": study_id,
                    "completed_trials": completed,
                    "planned_trials": planned,
                    "last_trial_id": spec.trial_id,
                    "raw_wall_seconds_this_invocation": time.perf_counter() - started,
                    "process_cpu_seconds_this_invocation": cpu_this_invocation,
                    "remaining_trials": planned - completed,
                }
                _atomic_json(root / "progress.json", progress)
                if progress_callback is not None:
                    progress_callback(progress)
                if stop_event is not None and stop_event.is_set():
                    break
        verified = verify_metric_records(root)
        status = "completed" if verified["record_count"] == planned else "incomplete"
        summary = {
            "schema_version": "scientific-exp03b-series-summary-v1",
            **design,
            "status": status,
            "completed_trials": verified["record_count"],
            "duplicate_trials_skipped": skipped,
            "verification": verified,
            "confirmatory_series_executed": stage == "confirmatory",
            "preflight_excluded_from_inference": stage == "preflight",
            "raw_wall_seconds_this_invocation": time.perf_counter() - started,
        }
        _atomic_json(root / "summary.json", summary)
        _write_root_manifest(
            root,
            protocol_sha256=protocol_hash,
            study_id=study_id,
            completed_trials=verified["record_count"],
            planned_trials=planned,
        )
        return summary
    finally:
        lock.unlink(missing_ok=True)


def run_system_series(
    protocol_path: str | os.PathLike[str],
    output_root: str | os.PathLike[str],
    *,
    scenario: Literal["awgn", "static", "rician"],
    stage: Literal["preflight", "confirmatory"],
    stop_event: Any = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run/resume the separate complete-system Joint/B0/B1 series."""
    protocol, raw, protocol_hash, _ = load_frozen_protocol(protocol_path)
    system = protocol["system_comparison"]
    grid = list(system["energy_grid_gamma_db"][scenario])
    if stage == "preflight":
        point_indices = sorted({0, len(grid) // 2, len(grid) - 1})
        trials_per_point = int(system["preflight_trials_per_scenario"])
    elif stage == "confirmatory":
        point_indices = list(range(len(grid)))
        trials_per_point = int(system["confirmatory_trials_per_point"])
    else:
        raise ValueError("stage must be preflight or confirmatory")
    study_id = f"{stage}-{scenario}-full-receivers"
    root = Path(output_root).resolve() / "system" / stage / scenario
    design = {
        "study_id": study_id,
        "block": "full_system_comparison",
        "stage": stage,
        "scenario": scenario,
        "point_indices": point_indices,
        "gamma_db_grid": [grid[index] for index in point_indices],
        "trials_per_point": trials_per_point,
        "planned_trials": len(point_indices) * trials_per_point,
        "protocol_sha256": protocol_hash,
    }
    _prepare_study(root, raw, protocol_hash, design)
    lock = _acquire_lock(root)
    started = time.perf_counter()
    expected_count = int(design["planned_trials"])
    try:
        trial_root = root / "trials"
        trial_root.mkdir(parents=True, exist_ok=True)
        sidecars = sorted(trial_root.glob("*.json"))
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in sidecars]
        if rows:
            verify_system_records(root)
        ids = [row["trial_id"] for row in rows]
        expected_ids = {
            f"{stage}-{scenario}-p{point:02d}-t{trial:04d}"
            for point in point_indices
            for trial in range(trials_per_point)
        }
        if len(ids) != len(set(ids)) or not set(ids) <= expected_ids:
            raise ValueError("system checkpoint contains duplicate or out-of-design trials")
        if any(row.get("protocol_sha256") != protocol_hash for row in rows):
            raise ValueError("system checkpoint protocol hash mismatch")
        existing = set(ids)
        _rebuild_system_checkpoint(root, rows)
        skipped = len(existing)
        completed = skipped
        cpu_this_invocation = 0.0
        for point_index in point_indices:
            for trial_index in range(trials_per_point):
                trial_id = f"{stage}-{scenario}-p{point_index:02d}-t{trial_index:04d}"
                spec = build_system_trial_spec(protocol, scenario, point_index, trial_index, stage)
                if trial_id in existing:
                    continue
                if stop_event is not None and stop_event.is_set():
                    break
                _check_resource_guard(root, protocol)
                wall_start = time.perf_counter_ns()
                cpu_start = time.process_time_ns()
                system_seeds = system_trial_seeds(spec, scenario)
                record = run_energy_trial(spec, root, seed_override=system_seeds)
                raw_wall_ns = time.perf_counter_ns() - wall_start
                process_cpu_ns = time.process_time_ns() - cpu_start
                cpu_this_invocation += process_cpu_ns / 1e9
                record_path = (
                    root
                    / spec.phase
                    / spec.scenario
                    / spec.sweep
                    / f"p{point_index:02d}"
                    / f"t{trial_index:04d}"
                    / "record.json"
                )
                array_path = record_path.with_name("arrays.npz")
                trial_sidecar = {
                    "schema_version": "scientific-exp03b-system-trial-link-v1",
                    "trial_id": trial_id,
                    "stage": stage,
                    "scenario": scenario,
                    "point_index": point_index,
                    "trial_index": trial_index,
                    "gamma_db": float(grid[point_index]),
                    "protocol_sha256": protocol_hash,
                    "record_path": record_path.relative_to(root).as_posix(),
                    "record_sha256": sha256_file(record_path),
                    "array_path": array_path.relative_to(root).as_posix(),
                    "array_sha256": sha256_file(array_path),
                    "observation_sha256": record["observation_sha256"],
                    "receiver_observation_hashes": record["receiver_observation_hashes"],
                    "derived_seeds": record["seeds"],
                    "raw_wall_elapsed_seconds": raw_wall_ns / 1e9,
                    "process_cpu_seconds": process_cpu_ns / 1e9,
                    "record": record,
                }
                sidecar_path = trial_root / f"{trial_id}.json"
                _atomic_json(sidecar_path, trial_sidecar)
                _append_checkpoint(
                    root,
                    {
                        "trial_id": trial_id,
                        "record_path": sidecar_path.relative_to(root).as_posix(),
                        "record_sha256": sha256_file(sidecar_path),
                        "array_path": trial_sidecar["array_path"],
                        "array_sha256": trial_sidecar["array_sha256"],
                    },
                )
                existing.add(trial_id)
                rows.append(trial_sidecar)
                completed += 1
                if completed % 100 == 0 or completed == expected_count:
                    _write_root_manifest(
                        root,
                        protocol_sha256=protocol_hash,
                        study_id=study_id,
                        completed_trials=completed,
                        planned_trials=expected_count,
                    )
                progress = {
                    "study_id": study_id,
                    "completed_trials": completed,
                    "planned_trials": expected_count,
                    "last_trial_id": trial_id,
                    "raw_wall_seconds_this_invocation": time.perf_counter() - started,
                    "process_cpu_seconds_this_invocation": cpu_this_invocation,
                    "remaining_trials": expected_count - completed,
                }
                _atomic_json(root / "progress.json", progress)
                if progress_callback is not None:
                    progress_callback(progress)
                if stop_event is not None and stop_event.is_set():
                    break
        verify_system_records(root)
        summary = {
            "schema_version": "scientific-exp03b-series-summary-v1",
            **design,
            "status": "completed" if completed == expected_count else "incomplete",
            "completed_trials": completed,
            "duplicate_trials_skipped": skipped,
            "verification": verify_system_records(root),
            "preflight_excluded_from_inference": stage == "preflight",
            "confirmatory_series_executed": stage == "confirmatory",
            "raw_wall_seconds_this_invocation": time.perf_counter() - started,
        }
        _atomic_json(root / "summary.json", summary)
        _write_root_manifest(
            root,
            protocol_sha256=protocol_hash,
            study_id=study_id,
            completed_trials=completed,
            planned_trials=expected_count,
        )
        return summary
    finally:
        lock.unlink(missing_ok=True)


def verify_system_records(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Independently verify system sidecars, nested trial manifests, bits and hashes."""
    base = Path(root).resolve()
    sidecars = sorted((base / "trials").glob("*.json"))
    ids: set[str] = set()
    decoded_bits = 0
    for sidecar_path in sidecars:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        trial_id = sidecar.get("trial_id")
        if not isinstance(trial_id, str) or trial_id in ids:
            raise ValueError("system confirmatory trial ID is missing or duplicated")
        ids.add(trial_id)
        record_path = (base / sidecar["record_path"]).resolve()
        array_path = (base / sidecar["array_path"]).resolve()
        if base not in record_path.parents or base not in array_path.parents:
            raise ValueError("system trial path escapes experiment root")
        if sha256_file(record_path) != sidecar.get("record_sha256"):
            raise ValueError("system record failed SHA-256 verification")
        if sha256_file(array_path) != sidecar.get("array_sha256"):
            raise ValueError("system arrays failed SHA-256 verification")
        record_dir = record_path.parent
        nested_manifest = json.loads((record_dir / "manifest.json").read_text(encoding="utf-8"))
        for name, expected_hash in nested_manifest["files"].items():
            if sha256_file(record_dir / name) != expected_hash:
                raise ValueError(f"nested receiver output failed SHA-256 verification: {name}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record["observation_sha256"] != sidecar["observation_sha256"]:
            raise ValueError("system observation hash differs from provenance sidecar")
        if set(record["receiver_observation_hashes"].values()) != {record["observation_sha256"]}:
            raise ValueError("complete-system receivers did not share one observation")
        with np.load(array_path, allow_pickle=False) as arrays:
            truth = arrays["information_bits"].astype(np.int8)
            for arm in record["bit_errors"]:
                decoded = arrays[f"{arm}_decoded_bits"].astype(np.int8)
                if decoded.shape != truth.shape:
                    raise ValueError("system decoder payload alignment differs")
                errors = decoded != truth
                bit_count = int(np.count_nonzero(errors))
                pair_count = int(np.count_nonzero(errors.reshape(-1, 2).any(axis=1)))
                if (
                    bit_count != record["bit_errors"][arm]
                    or pair_count != record["pair_errors"][arm]
                ):
                    raise ValueError(f"independent system BER/SER recount differs for {arm}")
                if not pair_count <= bit_count <= 2 * pair_count:
                    raise ValueError("system BER and pair-SER counts disagree")
                decoded_bits += bit_count
    return {
        "record_count": len(sidecars),
        "unique_trial_ids": len(ids),
        "decoded_bit_errors_recounted": decoded_bits,
        "paired_observation_hashes": "PASS",
        "nested_sha256_manifests": "PASS",
        "independent_count_replay": "PASS",
    }
