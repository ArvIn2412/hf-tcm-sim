"""Authorized TRAIN-only runner for the fixed M8 anchored policy study.

This evaluation orchestration reuses the existing B4d/B5b path. It does not
change receiver mathematics and has no validation/final execution path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.error_metrics import (
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.m5h_pilot_runner import _process_rss_windows
from hf_tcm.evaluation.m7b_train_runner import (
    _atomic_json,
    _historical_tree_hash,
    _mode_record,
    _sha256_file,
    historical_integrity_baseline,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import generate_independent_complex_awgn
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import _config_operands, _mode_run
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DRAFT = ROOT / "configs/m8a_anchored_study_draft.json"
DEFAULT_APPROVED = ROOT / "configs/m8b_train_approved_run.json"
SCHEMA = "m8b.train.v1"
CLASSIFICATION = (
    "authorized exploratory anchored-adaptation TRAIN study, NOT independently "
    "validated improvement, NOT confirmatory performance evidence, NOT paper-exact receiver"
)
_RUNTIME_FIELDS = {
    "authorization_provenance",
    "execution_limits",
    "runtime_provenance",
    "output",
    "run_manifest",
    "historical_integrity_baseline",
}
_SOURCE_PATHS = (
    "src/hf_tcm/evaluation/m8a_anchored_study_design.py",
    "src/hf_tcm/evaluation/m8b_train_runner.py",
    "configs/m5i_confirmatory_design_draft.json",
    "src/hf_tcm/evaluation/m7b_train_runner.py",
    "src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/evaluation/matched_m2_b5_experiment.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_step.py",
    "src/hf_tcm/receiver/reconstruction_candidate_metrics.py",
    "src/hf_tcm/receiver/reconstruction_posterior.py",
    "src/hf_tcm/receiver/reconstruction_conditional_decode.py",
    "src/hf_tcm/receiver/reconstruction_forward.py",
    "src/hf_tcm/receiver/reconstruction_observation.py",
    "src/hf_tcm/receiver/iq_prediction.py",
    "src/hf_tcm/receiver/paper_recursion.py",
    "src/hf_tcm/receiver/reconstruction_labeling.py",
    "src/hf_tcm/decoding/reconstruction_viterbi.py",
    "src/hf_tcm/coding/encoder.py",
    "src/hf_tcm/coding/hypotheses.py",
    "src/hf_tcm/modulation/psk8.py",
    "src/hf_tcm/modulation/labeling.py",
    "src/hf_tcm/receiver/iq.py",
    "src/hf_tcm/reconstruction_config.py",
)


class M8BExecutionBlocked(RuntimeError):
    """M8b authorization, provenance, or design validation failed."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha256_value(value: object) -> str:  # type: ignore[no-redef]
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_fingerprint() -> dict[str, str]:
    result = {}
    for relative in _SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise M8BExecutionBlocked(f"runtime source missing: {relative}")
        result[relative] = _sha256_file(path)
    return result


def _git_provenance() -> dict[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return {"revision": None, "status": "unavailable: workspace is not a Git worktree"}
    revision = result.stdout.strip()
    return {"revision": revision or None, "status": "available" if revision else "unavailable"}


def _m8b_manifest(draft: Mapping[str, Any]) -> dict[str, Any]:
    roots = draft["partitions"]["training"]["seed_namespaces"]
    seed_rule = draft["seed_derivation"]
    partition_code = int(seed_rule["partition_codes"]["training"])
    codes = seed_rule["stream_codes"]
    runs = []
    for run_index in range(40):
        displayed = run_index + 1
        run_id = draft["study_id"] + f":train:run-{displayed:03d}"
        streams: dict[str, Any] = {}
        for stream_name in ("data", "noise", "bootstrap", "experiment_metadata"):
            master = int(roots[stream_name])
            stream_code = int(codes[stream_name])
            spawn_key = (1295337521, partition_code, run_index, stream_code)
            child = np.random.SeedSequence(master, spawn_key=spawn_key).generate_state(
                1, dtype=np.uint64
            )[0]
            streams[stream_name] = {
                "master_seed": master,
                "spawn_key": list(spawn_key),
                "derived_seed": int(child),
                "generator": "PCG64",
                "instantiated": stream_name in ("data", "noise"),
            }
        runs.append({"run_id": run_id, "run_index": displayed, "streams": streams})
    used = [
        run["streams"][name]["derived_seed"]
        for run in runs
        for name in ("data", "noise", "bootstrap", "experiment_metadata")
    ]
    if len(used) != len(set(used)):
        raise M8BExecutionBlocked("M8 TRAIN child seeds collide across runs or streams")
    return {
        "partition": "TRAIN",
        "partition_code": partition_code,
        "run_index_origin": {"displayed": 1, "spawned": 0},
        "generator": "PCG64",
        "runs": runs,
        "reserved_streams_not_instantiated": ["bootstrap"],
        "validation_and_final_seeds_derived": False,
    }


def _historical_baseline() -> dict[str, Any]:
    baseline = historical_integrity_baseline()
    baseline["M7b"] = _historical_tree_hash(ROOT / "outputs/m7b_train")
    baseline["M8a_draft"] = {"file_count": 1, "sha256": _sha256_file(DEFAULT_DRAFT)}
    baseline["M8a_sidecar"] = {
        "file_count": 1,
        "sha256": _sha256_file(Path(f"{DEFAULT_DRAFT}.sha256")),
    }
    return baseline


def create_approved_m8b_config(
    *, draft: Mapping[str, Any], output_path: str | Path = DEFAULT_APPROVED
) -> dict[str, Any]:
    """Create a run-specific TRAIN authorization snapshot without drawing RNG."""
    from hf_tcm.evaluation.m8a_anchored_study_design import validate_m8a_anchored_study

    validate_m8a_anchored_study(draft)
    draft_hash = _sha256_file(DEFAULT_DRAFT)
    sidecar_path = Path(f"{DEFAULT_DRAFT}.sha256")
    if not sidecar_path.is_file() or sidecar_path.read_text(encoding="ascii").strip() != draft_hash:
        raise M8BExecutionBlocked("M8a draft sidecar checksum mismatch")
    approved = copy.deepcopy(dict(draft))
    approved["design_status"] = "approved_training"
    approved["execution_authorized"] = True
    approved["execution_scope"] = "m8b_train_only"
    approved["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization through this M8b TRAIN Codex instruction",
        "authorized_partition": "TRAIN only; VALIDATION and FINAL not authorized",
    }
    approved["execution_limits"] = {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "rss_limit_semantics": "periodic process RSS monitoring, not a hard OS process limit",
        "worker_processes": 1,
        "multiprocessing": False,
        "stop_at_sequence_boundary_on_budget": True,
        "atomic_checkpoint_per_sequence": True,
    }
    fingerprints = _source_fingerprint()
    from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design

    reconstruction_configuration = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]
    receiver_configuration = validate_reconstructed_offline_config(reconstruction_configuration)
    clock_origins = {
        "absolute_sample_origin": int(receiver_configuration["timebase"]["symbol_origin_sample"]),
        "absolute_symbol_origin": 0,
        "estimator_time_index_origin": int(
            receiver_configuration["estimator"]["initial_time_index"]
        ),
        "provenance": "sample/tick origins from the accepted M5i receiver config; each new independent sequence starts at symbol index 0",
        "m8a_explicit_clock_fields": False,
    }
    approved["runtime_provenance"] = {
        "m8a_draft_file_sha256": draft_hash,
        "m8a_draft_sidecar_sha256": sidecar_path.read_text(encoding="ascii").strip(),
        "code_fingerprint": fingerprints,
        "code_fingerprint_sha256": _sha256_value(fingerprints),
        "git": _git_provenance(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "prng": "numpy.random.PCG64",
        "receiver_configuration_source": "configs/m5i_confirmatory_design_draft.json accepted reconstructed receiver configuration",
        "clock_origins": clock_origins,
    }
    approved["output"] = {
        "experiment_id": str(draft["study_id"]),
        "namespace": f"outputs/m8b_train/{draft['study_id']}",
        "schema_version": SCHEMA,
        "checkpoint_policy": "atomic JSON checkpoint after each complete sequence",
    }
    approved["run_manifest"] = _m8b_manifest(draft)
    approved["historical_integrity_baseline"] = _historical_baseline()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(approved, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    digest = _sha256_file(target)
    with Path(f"{target}.sha256").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return approved


def _strip_runtime(value: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: copy.deepcopy(item) for key, item in value.items() if key not in _RUNTIME_FIELDS}
    result["design_status"] = "proposed"
    result["execution_authorized"] = False
    result["execution_scope"] = "none"
    return result


def validate_approved_m8b(
    value: object,
    *,
    draft: Mapping[str, Any],
    approved_path: str | Path | None = None,
    verify_fingerprint: bool = True,
    callbacks: Mapping[str, Callable[[], object]] | None = None,
) -> dict[str, Any]:
    """Validate every precondition before any RNG, waveform, noise, or decoder call."""
    from hf_tcm.evaluation.m8a_anchored_study_design import validate_m8a_anchored_study

    if not isinstance(value, Mapping) or (
        value.get("design_status") != "approved_training"
        or value.get("execution_authorized") is not True
        or value.get("execution_scope") != "m8b_train_only"
    ):
        raise M8BExecutionBlocked("M8b requires approved_training/m8b_train_only authorization")
    if value.get("authorization_provenance", {}).get("explicit_user_authorization") != (
        "explicit user authorization through this M8b TRAIN Codex instruction"
    ):
        raise M8BExecutionBlocked("M8b authorization provenance mismatch")
    validate_m8a_anchored_study(draft)
    if _strip_runtime(value) != dict(draft):
        raise M8BExecutionBlocked("approved scientific design differs from M8a draft")
    runtime = value.get("runtime_provenance")
    if not isinstance(runtime, Mapping):
        raise M8BExecutionBlocked("runtime provenance missing")
    draft_hash = _sha256_file(DEFAULT_DRAFT)
    if runtime.get("m8a_draft_file_sha256") != draft_hash:
        raise M8BExecutionBlocked("M8a draft file changed since approval")
    sidecar = Path(f"{DEFAULT_DRAFT}.sha256")
    if not sidecar.is_file() or sidecar.read_text(encoding="ascii").strip() != draft_hash:
        raise M8BExecutionBlocked("M8a draft sidecar checksum mismatch")
    fingerprint = runtime.get("code_fingerprint")
    if fingerprint != _source_fingerprint() or runtime.get(
        "code_fingerprint_sha256"
    ) != _sha256_value(fingerprint):
        raise M8BExecutionBlocked("runtime source fingerprint changed since approval")
    if (
        runtime.get("python_version") != platform.python_version()
        or runtime.get("numpy_version") != np.__version__
    ):
        raise M8BExecutionBlocked("Python/NumPy runtime differs from approved snapshot")
    if runtime.get("prng") != "numpy.random.PCG64":
        raise M8BExecutionBlocked("M8b requires PCG64")
    clock_origins = runtime.get("clock_origins")
    if not isinstance(clock_origins, Mapping) or (
        clock_origins.get("absolute_sample_origin") != 0
        or clock_origins.get("absolute_symbol_origin") != 0
        or clock_origins.get("estimator_time_index_origin") != 0
        or clock_origins.get("m8a_explicit_clock_fields") is not False
    ):
        raise M8BExecutionBlocked("M8b clock origins are missing or differ from the frozen profile")
    if verify_fingerprint:
        if approved_path is None:
            raise M8BExecutionBlocked("approved config path is required")
        path = Path(approved_path)
        sidecar_config = Path(f"{path}.sha256")
        if not path.is_file() or not sidecar_config.is_file():
            raise M8BExecutionBlocked("approved config or checksum sidecar missing")
        if sidecar_config.read_text(encoding="ascii").strip() != _sha256_file(path):
            raise M8BExecutionBlocked("approved config checksum mismatch")
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise M8BExecutionBlocked("approved config snapshot differs from loaded value")
    if value.get("run_manifest") != _m8b_manifest(draft):
        raise M8BExecutionBlocked("TRAIN run IDs or seed derivation differ from M8a")
    if value.get("execution_limits") != {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "rss_limit_semantics": "periodic process RSS monitoring, not a hard OS process limit",
        "worker_processes": 1,
        "multiprocessing": False,
        "stop_at_sequence_boundary_on_budget": True,
        "atomic_checkpoint_per_sequence": True,
    }:
        raise M8BExecutionBlocked("approved resource/stopping policy mismatch")
    baseline = value.get("historical_integrity_baseline")
    if baseline != _historical_baseline():
        raise M8BExecutionBlocked("historical M5/M6/M7/M8a artifact baseline mismatch")
    if callbacks is not None and any(
        name not in callbacks or not callable(callbacks[name])
        for name in ("rng", "data", "noise", "receiver")
    ):
        raise M8BExecutionBlocked("all guarded callback spies are required")
    return dict(value)


def guard_m8b_execution(
    authorization: object,
    *,
    draft: Mapping[str, Any],
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> object:
    validate_approved_m8b(authorization, draft=draft, callbacks=callbacks)
    return executor()


def _initial_state(policy: Mapping[str, Any], time_index: int) -> ReconstructionEstimatorState:
    return ReconstructionEstimatorState(
        [policy["initial_fluctuating_iq"]], [policy["initial_full_iq"]], time_index
    )


def _prepare_received(
    bits: NDArray[np.int8], *, gain: float, noise_seed: int, variance: float, stream_id: str
) -> tuple[NDArray[np.complex128], NDArray[np.int64], str]:
    reference_symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [index_to_label(int(item), profile=BASELINE_ASSUMPTION) for item in reference_symbols]
    baseband = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    i_wave, q_wave = symbols_to_iq_waveform(baseband, samples_per_symbol=8)
    clean = gain * (i_wave + 1j * q_wave)
    noise = generate_independent_complex_awgn(
        sample_count=8 * len(reference_symbols),
        sigma_squared=variance,
        seed=noise_seed,
        stream_id=stream_id,
    ).noise
    received = np.asarray(clean + noise, dtype=np.complex128, order="C")
    if received.shape != (2048,) or not np.all(np.isfinite(received)):
        raise ValueError("generated received buffer must be finite with shape (2048,)")
    received.setflags(write=False)
    return (
        received,
        np.asarray(reference_symbols, dtype=np.int64),
        hashlib.sha256(received.tobytes()).hexdigest(),
    )


def _mode_for_policy(
    *,
    policy: Mapping[str, Any],
    bits: NDArray[np.int8],
    reference_symbols: NDArray[np.int64],
    received: NDArray[np.complex128],
    received_hash: str,
    configuration: Mapping[str, Any],
    gain: float,
    beta: float,
    sample_origin: int,
    symbol_origin: int,
    time_origin: int,
) -> Any:
    validated, labeling, timebase = _config_operands(
        configuration, origin=sample_origin, initial_time=time_origin
    )
    if validated["likelihood"]["beta"] != beta:
        raise M8BExecutionBlocked("policy beta differs from accepted reconstruction config")
    state = _initial_state(policy, time_origin)
    count = len(reference_symbols)
    labels = np.arange(
        sample_origin + 8 * symbol_origin, sample_origin + 8 * symbol_origin + 2048, dtype=np.int64
    )
    return _mode_run(
        mode=str(policy["candidate_id"]),
        initial_state=state,
        alpha=(float(policy["alpha_prime"]),) * count,
        gains=tuple(np.asarray([policy["k_tilde"]], dtype=np.float64) for _ in range(count)),
        regular=tuple(np.asarray([policy["mu0"]], dtype=np.float64) for _ in range(count)),
        received=received,
        labels=labels,
        received_start=sample_origin + 8 * symbol_origin,
        origin=sample_origin,
        first_symbol=symbol_origin,
        first_time=time_origin,
        beta=beta,
        labeling=labeling,
        timebase=timebase,
        receiver_mode="monolithic",
        partition=(count,),
        reference_bits=np.asarray(bits, dtype=np.int8),
        reference_symbols=np.asarray(reference_symbols, dtype=np.int64),
        received_sha256=received_hash,
        true_gain_for_evaluation=gain,
    )


def _policy_record(policy: Mapping[str, Any], mode: Any, decoder_calls: int) -> dict[str, Any]:
    base = _mode_record(
        type(
            "Policy",
            (),
            {
                "candidate_id": policy["candidate_id"],
                "alpha_prime": policy["alpha_prime"],
                "k_scale": policy["k_scale"],
                "k_tilde": tuple(policy["k_tilde"]),
            },
        )(),
        mode,
    )
    base["mu0"] = list(policy["mu0"])
    base["initial_full_iq"] = list(policy["initial_full_iq"])
    base["initial_fluctuating_iq"] = list(policy["initial_fluctuating_iq"])
    base["decoder_invocations"] = decoder_calls
    return base


def _checkpoint_path(output: Path, run_id: str) -> Path:
    return output / "checkpoints" / f"{run_id.rsplit(':', 1)[-1]}.json"


def independent_verify(output: str | Path, draft: Mapping[str, Any]) -> dict[str, Any]:
    """Independently replay saved integer counts, policy validity, and ranking."""
    directory = Path(output)
    files = sorted((directory / "checkpoints").glob("run-*.json"))
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    expected_runs = [f"{draft['study_id']}:train:run-{index:03d}" for index in range(1, 41)]
    planned_runs = _m8b_manifest(draft)["runs"]
    expected_candidates = [
        row["candidate_id"] for row in draft["policy_grid"]["candidate_policies"]
    ]
    if [row.get("run_id") for row in rows] != expected_runs[: len(rows)]:
        raise ValueError("run IDs are missing, duplicated, or out of deterministic order")
    if len({row.get("received_sha256") for row in rows if row.get("received_sha256")}) != len(rows):
        raise ValueError("received hashes must be unique across TRAIN sequences")
    policy_by_id = {row["candidate_id"]: row for row in draft["policy_grid"]["candidate_policies"]}
    totals = {
        candidate_id: {
            "bit_errors": 0,
            "total_bits": 0,
            "symbol_errors": 0,
            "total_symbols": 0,
            "valid_records": 0,
            "failures": 0,
        }
        for candidate_id in expected_candidates
    }
    decoder_total = 0
    complete_runs = 0
    b_complete = True
    for row, planned in zip(rows, planned_runs, strict=False):
        if (
            row.get("status") != "complete"
            or [item.get("candidate_id") for item in row.get("policies", [])] != expected_candidates
        ):
            raise ValueError("run checkpoint is incomplete or has a malformed candidate grid")
        if (
            row.get("run_index") != planned["run_index"]
            or row.get("seed_provenance") != planned["streams"]
        ):
            raise ValueError("run index or seed provenance differs from the frozen TRAIN manifest")
        complete_runs += 1
        if len(row.get("received_sha256", "")) != 64:
            raise ValueError("received SHA-256 missing or malformed")
        ref_bits = np.asarray(row["evaluation_only"]["reference_information_bits"], dtype=np.int8)
        ref_symbols = np.asarray(row["evaluation_only"]["reference_symbol_indices"], dtype=np.int64)
        if ref_bits.shape != (512,) or ref_symbols.shape != (256,):
            raise ValueError("reference evaluation arrays have invalid shape")
        if not np.array_equal(
            ref_symbols,
            encode_reference_symbol_indices(
                ref_bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            ),
        ):
            raise ValueError("reference symbol indices do not match saved M1 encoded bits")
        for record in row["policies"]:
            candidate_id = record["candidate_id"]
            expected = policy_by_id[candidate_id]
            decoder_total += int(record.get("decoder_invocations", 0))
            for key in (
                "alpha_prime",
                "k_tilde",
                "mu0",
                "initial_full_iq",
                "initial_fluctuating_iq",
            ):
                if record.get(key) != expected[key]:
                    raise ValueError(f"{candidate_id} {key} differs from frozen M8a design")
            if record.get("status") != "complete_valid_output":
                totals[candidate_id]["failures"] += 1
                if candidate_id == "historical_frozen_B":
                    b_complete = False
                continue
            if record.get("decoder_invocations") != 1:
                raise ValueError("each valid policy record must contain exactly one decoder pass")
            if record.get("received_sha256") != row["received_sha256"]:
                raise ValueError("policy used a different received buffer")
            decoded_bits = np.asarray(record["decoded_information_bits"], dtype=np.int8)
            decoded_symbols = np.asarray(record["decoded_symbol_indices"], dtype=np.int64)
            decoded_path = tuple(int(item) for item in record["decoded_hypothesis_path"])
            if (
                decoded_bits.shape != (512,)
                or decoded_symbols.shape != (256,)
                or len(decoded_path) != 256
            ):
                raise ValueError("decoded result shapes are invalid")
            validate_hypothesis_edge_path(decoded_path, initial_state=INITIAL_STATE)
            path_bits = np.asarray(
                [bit for edge in decoded_path for bit in HYPOTHESES[edge].input_bits], dtype=np.int8
            )
            path_symbols = decoded_path_symbol_indices(
                decoded_path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            )
            if not np.array_equal(decoded_bits, path_bits) or not np.array_equal(
                decoded_symbols, path_symbols
            ):
                raise ValueError("decoded arrays differ from validated canonical edge path")
            counts = {
                "bit_errors": count_bit_errors(ref_bits, decoded_bits),
                "total_bits": 512,
                "symbol_errors": count_symbol_errors(ref_symbols, decoded_symbols),
                "total_symbols": 256,
            }
            if record.get("counts") != counts:
                raise ValueError("raw integer error count mismatch")
            total = totals[candidate_id]
            for key, value in counts.items():
                total[key] += value
            total["valid_records"] += 1
        if row.get("decoder_invocations") != sum(
            item.get("decoder_invocations", 0) for item in row["policies"]
        ):
            raise ValueError("run decoder invocation counter mismatch")
    ranking = []
    for candidate_id in expected_candidates:
        total = totals[candidate_id]
        eligible = (
            b_complete
            and len(rows) == 40
            and total["valid_records"] == 40
            and total["failures"] == 0
        )
        if (
            total["total_bits"] != total["valid_records"] * 512
            or total["total_symbols"] != total["valid_records"] * 256
        ):
            raise ValueError("pooled denominators differ from complete valid records")
        policy = policy_by_id[candidate_id]
        ranking.append(
            {
                "candidate_id": candidate_id,
                **total,
                "eligible": eligible,
                "pooled_ber": total["bit_errors"] / total["total_bits"]
                if total["total_bits"]
                else None,
                "pooled_ser": total["symbol_errors"] / total["total_symbols"]
                if total["total_symbols"]
                else None,
                "role": policy["role"],
                "k_scale": policy["k_scale"],
                "alpha_prime": policy["alpha_prime"],
            }
        )
    eligible_rows = [item for item in ranking if item["eligible"]]
    eligible_rows.sort(
        key=lambda item: (
            item["pooled_ber"],
            item["pooled_ser"],
            abs(item["k_scale"]),
            -item["alpha_prime"],
            item["candidate_id"],
        )
    )
    selected = (
        eligible_rows[0]["candidate_id"]
        if eligible_rows and complete_runs == 40 and b_complete
        else None
    )
    return {
        "status": "TRAIN_SELECTED_NOT_VALIDATED" if selected else "TRAIN_INCOMPLETE_OR_BLOCKED",
        "run_count": len(rows),
        "unique_run_count": len({item["run_id"] for item in rows}),
        "unique_received_hash_count": len(
            {item["received_sha256"] for item in rows if item.get("received_sha256")}
        ),
        "policy_record_count": sum(len(item.get("policies", [])) for item in rows),
        "decoder_invocations": decoder_total,
        "decoder_invocations_expected": 320 if len(rows) == 40 else 8 * len(rows),
        "b_control_complete": b_complete,
        "ranking": eligible_rows,
        "all_policy_totals": ranking,
        "selected_candidate_id": selected,
    }


def _output_file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "integrity_manifest.json"
    }


def execute_m8b_train(
    approved_config_path: str | Path = DEFAULT_APPROVED,
    *,
    draft_path: str | Path = DEFAULT_DRAFT,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Execute the sole authorized M8b TRAIN partition (40 sequences)."""
    approved_path = Path(approved_config_path)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    value = json.loads(approved_path.read_text(encoding="utf-8"))
    validate_approved_m8b(value, draft=draft, approved_path=approved_path)
    from hf_tcm.evaluation import reconstruction_adaptive_diagnostics as diagnostics
    from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design

    receiver_config = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]
    out = Path(output_root) if output_root is not None else ROOT / value["output"]["namespace"]
    if out.exists() and any(out.iterdir()):
        raise M8BExecutionBlocked("M8b output namespace is not empty; resume is not implicit")
    out.mkdir(parents=True, exist_ok=True)
    config_hash = _sha256_file(approved_path)
    _atomic_json(out / "approved_config_snapshot.json", value, exclusive=True)
    _atomic_json(
        out / "manifest.json",
        {
            "schema_version": SCHEMA,
            "experiment_id": value["output"]["experiment_id"],
            "approved_config_sha256": config_hash,
            "m8a_draft_sha256": value["runtime_provenance"]["m8a_draft_file_sha256"],
            "runtime_source_fingerprint": value["runtime_provenance"]["code_fingerprint"],
            "run_manifest": value["run_manifest"],
            "candidate_ids": [
                p["candidate_id"] for p in draft["policy_grid"]["candidate_policies"]
            ],
            "validation_or_final_executed": False,
        },
        exclusive=True,
    )
    beta = float(draft["anchored_profile"]["shared_beta"])
    gain = float(draft["profile"]["real_channel_gain"])
    variance = float(draft["profile"]["sigma_squared"])
    if variance != 0.7115124735378853:
        raise M8BExecutionBlocked("M8 ADR-015 variance mismatch")
    validated = validate_reconstructed_offline_config(receiver_config)
    if (
        validated["profile"] != "reconstructed_offline"
        or validated["receiver_enabled"] is not False
    ):
        raise M8BExecutionBlocked("receiver configuration differs from accepted offline profile")
    started = time.perf_counter()
    decoder_calls = 0
    completed = 0
    rss_peak: int | None = None
    rss_unverified = False
    limits = value["execution_limits"]
    original_decoder = diagnostics.decode_reconstruction_viterbi

    def counted_decoder(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoder_calls
        decoder_calls += 1
        return original_decoder(*args, **kwargs)

    diagnostics.decode_reconstruction_viterbi = counted_decoder
    try:
        for run in value["run_manifest"]["runs"]:
            if time.perf_counter() - started >= limits["wall_clock_limit_seconds"]:
                break
            rss = _process_rss_windows(os.getpid())
            if rss is None:
                rss_unverified = True
            else:
                rss_peak = max(rss_peak or 0, int(rss))
                if rss >= limits["rss_monitoring_budget_bytes"]:
                    break
            seeds = run["streams"]
            policies = draft["policy_grid"]["candidate_policies"]
            try:
                data_rng = np.random.Generator(np.random.PCG64(seeds["data"]["derived_seed"]))
                bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
                received, reference_symbols, received_hash = _prepare_received(
                    bits,
                    gain=gain,
                    noise_seed=int(seeds["noise"]["derived_seed"]),
                    variance=variance,
                    stream_id=f"M8b:TRAIN:{run['run_id']}:noise",
                )
            except Exception as exc:
                record = {
                    "schema_version": SCHEMA,
                    "run_id": run["run_id"],
                    "run_index": run["run_index"],
                    "status": "received_generation_failure",
                    "seed_provenance": seeds,
                    "policies": [
                        {
                            "candidate_id": p["candidate_id"],
                            "status": "not_run_received_generation_failure",
                            "decoder_invocations": 0,
                            "exception_type": type(exc).__name__,
                            "detail": str(exc),
                        }
                        for p in policies
                    ],
                    "decoder_invocations": 0,
                }
                _atomic_json(_checkpoint_path(out, run["run_id"]), record, exclusive=True)
                break
            reference_bits = np.asarray(bits, dtype=np.int8)
            reference_bits.setflags(write=False)
            records = []
            run_calls = 0
            for policy in policies:
                calls_before = decoder_calls
                try:
                    mode = _mode_for_policy(
                        policy=policy,
                        bits=reference_bits,
                        reference_symbols=reference_symbols,
                        received=received,
                        received_hash=received_hash,
                        configuration=receiver_config,
                        gain=gain,
                        beta=beta,
                        sample_origin=int(
                            value["runtime_provenance"]["clock_origins"]["absolute_sample_origin"]
                        ),
                        symbol_origin=int(
                            value["runtime_provenance"]["clock_origins"]["absolute_symbol_origin"]
                        ),
                        time_origin=int(
                            value["runtime_provenance"]["clock_origins"][
                                "estimator_time_index_origin"
                            ]
                        ),
                    )
                    policy_calls = decoder_calls - calls_before
                    if policy_calls != 1:
                        raise RuntimeError(
                            f"policy decoder calls must equal one, got {policy_calls}"
                        )
                    records.append(_policy_record(policy, mode, policy_calls))
                except Exception as exc:
                    policy_calls = decoder_calls - calls_before
                    records.append(
                        {
                            "candidate_id": policy["candidate_id"],
                            "alpha_prime": policy["alpha_prime"],
                            "k_scale": policy["k_scale"],
                            "k_tilde": policy["k_tilde"],
                            "mu0": policy["mu0"],
                            "initial_full_iq": policy["initial_full_iq"],
                            "initial_fluctuating_iq": policy["initial_fluctuating_iq"],
                            "status": "numerical_or_decoder_failure",
                            "exception_type": type(exc).__name__,
                            "detail": str(exc),
                            "decoder_invocations": policy_calls,
                        }
                    )
                run_calls += decoder_calls - calls_before
            checkpoint = {
                "schema_version": SCHEMA,
                "run_id": run["run_id"],
                "run_index": run["run_index"],
                "status": "complete" if len(records) == 8 else "incomplete",
                "received_sha256": received_hash,
                "approved_config_sha256": config_hash,
                "runtime_source_fingerprint_sha256": value["runtime_provenance"][
                    "code_fingerprint_sha256"
                ],
                "seed_provenance": seeds,
                "decoder_invocations": run_calls,
                "evaluation_only": {
                    "reference_information_bits": [int(x) for x in bits],
                    "reference_symbol_indices": [int(x) for x in reference_symbols],
                    "real_channel_gain": gain,
                    "sigma_squared": variance,
                },
                "policies": records,
            }
            for policy_record in records:
                policy_record["approved_config_sha256"] = config_hash
                policy_record["runtime_source_fingerprint_sha256"] = value["runtime_provenance"][
                    "code_fingerprint_sha256"
                ]
            _atomic_json(_checkpoint_path(out, run["run_id"]), checkpoint, exclusive=True)
            completed += 1
    finally:
        diagnostics.decode_reconstruction_viterbi = original_decoder
    elapsed = time.perf_counter() - started
    try:
        verification = independent_verify(out, draft)
    except (ValueError, KeyError, TypeError) as exc:
        verification = {"status": "VERIFICATION_FAILED", "detail": str(exc)}
    complete = (
        verification.get("status") == "TRAIN_SELECTED_NOT_VALIDATED"
        and verification.get("run_count") == 40
        and verification.get("decoder_invocations") == 320
    )
    historical_after = _historical_baseline()
    historical_ok = historical_after == value["historical_integrity_baseline"]
    selected = verification.get("selected_candidate_id") if complete and historical_ok else None
    status = "TRAIN_SELECTED_NOT_VALIDATED" if selected else "TRAIN_INCOMPLETE_OR_BLOCKED"
    if not historical_ok:
        verification = {
            **verification,
            "status": "VERIFICATION_FAILED",
            "detail": "historical artifact hash changed",
        }
    summary = {
        "schema_version": SCHEMA,
        "classification": CLASSIFICATION,
        "status": status,
        "approved_config_sha256": config_hash,
        "runtime_source_fingerprint": value["runtime_provenance"]["code_fingerprint"],
        "planned_sequences": 40,
        "completed_sequences": completed,
        "policy_records": sum(
            len(json.loads(p.read_text(encoding="utf-8")).get("policies", []))
            for p in sorted((out / "checkpoints").glob("run-*.json"))
        ),
        "decoder_invocations": decoder_calls,
        "unique_received_samples": completed * 2048,
        "policy_symbol_passes": decoder_calls * 256,
        "ranking": verification.get("ranking", []),
        "all_policy_totals": verification.get("all_policy_totals", []),
        "selected_candidate_id": selected,
        "independent_verification": verification,
        "resource": {
            "wall_clock_seconds": elapsed,
            "completed_sequences": completed,
            "decoder_invocations": decoder_calls,
            "rss_peak_bytes_observed": rss_peak,
            "rss_status": "RSS_UNVERIFIED"
            if rss_unverified or rss_peak is None
            else "periodic_monitor_observed",
            "process_count": 1,
            "multiprocessing": False,
            "wall_clock_budget_seconds": limits["wall_clock_limit_seconds"],
            "rss_monitoring_budget_bytes": limits["rss_monitoring_budget_bytes"],
        },
        "historical_integrity": {
            "before": value["historical_integrity_baseline"],
            "after": historical_after,
            "unchanged": historical_ok,
        },
        "validation_or_final_executed": False,
    }
    _atomic_json(out / "independent_verification.json", verification, exclusive=True)
    _atomic_json(out / "summary.json", summary, exclusive=True)
    if selected:
        policy = next(
            row
            for row in draft["policy_grid"]["candidate_policies"]
            if row["candidate_id"] == selected
        )
        selected_doc = {
            "status": "TRAIN_SELECTED_NOT_VALIDATED",
            "candidate_id": selected,
            "role": policy["role"],
            "alpha_prime": policy["alpha_prime"],
            "k_tilde": policy["k_tilde"],
            "mu0": policy["mu0"],
            "initial_full_iq": policy["initial_full_iq"],
            "initial_fluctuating_iq": policy["initial_fluctuating_iq"],
            "beta": beta,
            "pooled_training_statistics": next(
                item
                for item in verification["all_policy_totals"]
                if item["candidate_id"] == selected
            ),
            "approved_config_sha256": config_hash,
            "training_run_ids": [row["run_id"] for row in value["run_manifest"]["runs"]],
            "validation_or_final_authorized": False,
        }
        _atomic_json(out / "selected_policy.json", selected_doc, exclusive=True)
    _atomic_json(out / "integrity_manifest.json", _output_file_hashes(out), exclusive=True)
    return summary
