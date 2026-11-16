"""Authorized TRAIN-only runner for the proposed M7 estimator-policy grid.

This module orchestrates the existing reconstructed B4d/B5b APIs. It does not
change receiver mathematics and has no VALIDATION or FINAL execution path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.error_metrics import (
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.matched_m2_b5_experiment import generate_independent_complex_awgn
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import (
    _config_operands,
    _mode_run,
)
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, index_to_label
from hf_tcm.modulation.psk8 import modulate
from hf_tcm.receiver.iq import symbols_to_iq_waveform
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
BitArray = NDArray[np.int8]
SymbolArray = NDArray[np.int64]

_ROOT = Path(__file__).resolve().parents[3]
_DRAFT_PATH = _ROOT / "configs/m7a_policy_study_draft.json"
_RECONSTRUCTION_SOURCE_PATH = _ROOT / "configs/m5i_confirmatory_design_draft.json"
_CODE_PATHS = (
    "src/hf_tcm/evaluation/m7a_policy_study_design.py",
    "src/hf_tcm/evaluation/m7b_train_runner.py",
    "src/hf_tcm/evaluation/m5i_confirmatory_design.py",
    "src/hf_tcm/evaluation/m5h_pilot_runner.py",
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
_RUNTIME_FIELDS = {
    "authorization_provenance",
    "execution_limits",
    "runtime_provenance",
    "output",
    "run_manifest",
    "historical_integrity_baseline",
}


class M7BExecutionBlocked(RuntimeError):
    """M7b authorization/configuration gate failed before stochastic work."""


@dataclass(frozen=True, slots=True)
class M7BPolicy:
    candidate_id: str
    alpha_prime: float
    k_scale: float
    k_tilde: tuple[float, float]


@dataclass(frozen=True, slots=True)
class M7BTrainSummary:
    status: str
    completed_runs: int
    decoder_invocations: int
    selected_candidate_id: str | None
    candidate_ranking: tuple[Mapping[str, Any], ...]
    verification: Mapping[str, Any]
    resource: Mapping[str, Any]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_value(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _code_fingerprint() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in _CODE_PATHS:
        path = _ROOT / relative
        if not path.is_file():
            raise M7BExecutionBlocked(f"required runtime source is missing: {relative}")
        result[relative] = _sha256_file(path)
    return result


def _git_revision() -> dict[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "revision": None,
            "status": "unavailable: workspace is not a Git worktree",
        }
    revision = result.stdout.strip()
    return {"revision": revision or None, "status": "available" if revision else "unavailable"}


def _historical_tree_hash(path: Path) -> dict[str, Any]:
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
    else:
        raise M7BExecutionBlocked(f"historical artifact is missing: {path.relative_to(_ROOT)}")
    digest = hashlib.sha256()
    for item in files:
        relative = item.relative_to(_ROOT).as_posix().encode("utf-8")
        file_digest = hashlib.sha256(item.read_bytes()).hexdigest().encode("ascii")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(file_digest)
    return {"file_count": len(files), "sha256": digest.hexdigest()}


def historical_integrity_baseline() -> dict[str, Any]:
    paths = {
        "M5f": "outputs/m5f_paired_monte_carlo_records.json",
        "M5h": "outputs/m5h_independent_pilot",
        "M5j": "outputs/m5j_confirmatory",
        "M6b": "outputs/m6b_trace_diagnostics",
        "M6g": "outputs/m6g_multistep_feedback_audit/deterministic_trace.json",
        "M6h": "outputs/m6h_posterior_clamp/deterministic_trace.json",
    }
    return {name: _historical_tree_hash(_ROOT / relative) for name, relative in paths.items()}


def _derive_seed(master: int, partition_code: int, run_index: int, stream_code: int) -> int:
    sequence = np.random.SeedSequence(
        master, spawn_key=(1295337521, partition_code, run_index, stream_code)
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def _train_manifest(draft: Mapping[str, Any]) -> dict[str, Any]:
    partition = draft["partitions"]["training"]
    roots = partition["seed_namespaces"]
    stream_codes = draft["seed_derivation"]["stream_codes"]
    runs = []
    for zero_index in range(40):
        display_index = zero_index + 1
        run_id = f"{draft['study_id']}:train:run-{display_index:03d}"
        streams = {}
        for name in ("data", "noise", "experiment_metadata"):
            code = int(stream_codes[name])
            spawn_key = [1295337521, 701, zero_index, code]
            streams[name] = {
                "master_seed": int(roots[name]),
                "spawn_key": spawn_key,
                "derived_seed": _derive_seed(int(roots[name]), 701, zero_index, code),
                "generator": "PCG64",
            }
        runs.append({"run_id": run_id, "run_index": display_index, "streams": streams})
    all_seeds = [
        item["streams"][stream]["derived_seed"]
        for item in runs
        for stream in ("data", "noise", "experiment_metadata")
    ]
    if len(all_seeds) != len(set(all_seeds)):
        raise M7BExecutionBlocked("derived TRAIN seeds collide across namespaces")
    return {
        "partition": "TRAIN",
        "partition_code": 701,
        "run_index_origin": {"displayed": 1, "spawned": 0},
        "stream_codes": {
            key: int(stream_codes[key]) for key in ("data", "noise", "experiment_metadata")
        },
        "runs": runs,
    }


def create_approved_m7b_config(
    *,
    draft: Mapping[str, Any],
    reconstruction_configuration: Mapping[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """Freeze a run-specific TRAIN authorization before any RNG is created."""
    from hf_tcm.evaluation.m7a_policy_study_design import validate_m7a_policy_study

    validate_m7a_policy_study(draft)
    receiver = validate_reconstructed_offline_config(reconstruction_configuration)
    if (
        receiver["profile"] != "reconstructed_offline"
        or receiver["paper_exact"] is not False
        or receiver["receiver_enabled"] is not False
        or receiver["likelihood"]["beta"] != 0.7
        or receiver["timebase"]["samples_per_symbol"] != 8
        or receiver["timebase"]["symbol_origin_sample"] != 0
        or receiver["estimator"]["initial_time_index"] != 0
    ):
        raise ValueError("receiver configuration does not match M7a TRAIN profile/clocks")
    shared = draft["shared_estimator"]
    initial = receiver["estimator"]["initial_estimates"]
    if (
        initial["full_iq"] != [shared["initial_full_iq"]]
        or initial["fluctuating_iq"] != [shared["initial_fluctuating_iq"]]
        or receiver["estimator"]["mu0"] != [shared["mu0"]]
    ):
        raise ValueError("receiver initial-state or mu0 differs from frozen M7a profile")
    baseline = historical_integrity_baseline()
    approved = copy.deepcopy(dict(draft))
    approved["design_status"] = "approved_training"
    approved["execution_authorized"] = True
    approved["execution_scope"] = "m7b_train_only"
    approved["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization supplied through this Codex M7b instruction",
        "partition_scope": "TRAIN only; VALIDATION and FINAL not authorized",
    }
    approved["execution_limits"] = {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "rss_limit_semantics": "periodic process RSS monitoring, not a hard OS process limit",
        "worker_processes": 1,
        "multiprocessing": False,
        "stop_before_next_sequence_on_budget": True,
        "atomic_checkpoint_per_sequence": True,
    }
    approved["runtime_provenance"] = {
        "draft_sha256": hashlib.sha256(_canonical_json(draft)).hexdigest(),
        "draft_file_sha256": _sha256_file(_DRAFT_PATH),
        "code_fingerprint": _code_fingerprint(),
        "code_fingerprint_sha256": _sha256_value(_code_fingerprint()),
        "git": _git_revision(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "prng": "numpy.random.PCG64",
        "receiver_configuration_source": "configs/m5i_confirmatory_design_draft.json reconstruction_configuration; same accepted reconstructed profile",
        "receiver_configuration_sha256": _sha256_value(reconstruction_configuration),
        "receiver_configuration": copy.deepcopy(dict(reconstruction_configuration)),
    }
    approved["output"] = {
        "experiment_id": str(draft["study_id"]),
        "namespace": f"outputs/m7b_train/{draft['study_id']}",
        "schema_version": "m7b.train.v1",
        "checkpoint_policy": "atomic JSON checkpoint after each complete sequence",
    }
    approved["run_manifest"] = _train_manifest(draft)
    approved["historical_integrity_baseline"] = baseline
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(approved, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    digest = _sha256_file(target)
    sidecar = Path(f"{target}.sha256")
    with sidecar.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return approved


def _strip_run_metadata(approved: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        key: copy.deepcopy(value) for key, value in approved.items() if key not in _RUNTIME_FIELDS
    }
    base["design_status"] = "proposed"
    base["execution_authorized"] = False
    base["execution_scope"] = "none"
    return base


def validate_m7b_approved_config(
    value: object,
    *,
    draft: Mapping[str, Any],
    callbacks: Mapping[str, Callable[[], object]] | None = None,
    approved_config_path: str | Path | None = None,
    verify_fingerprint: bool = True,
) -> dict[str, Any]:
    """Validate authorization and frozen design before any injected callback."""
    if not isinstance(value, Mapping):
        raise M7BExecutionBlocked("approved M7b config must be a mapping")
    if (
        value.get("design_status") != "approved_training"
        or value.get("execution_authorized") is not True
        or value.get("execution_scope") != "m7b_train_only"
    ):
        raise M7BExecutionBlocked("M7b requires approved_training/m7b_train_only authorization")
    if value.get("authorization_provenance", {}).get("explicit_user_authorization") != (
        "explicit user authorization supplied through this Codex M7b instruction"
    ):
        raise M7BExecutionBlocked("M7b authorization provenance mismatch")
    from hf_tcm.evaluation.m7a_policy_study_design import validate_m7a_policy_study

    validate_m7a_policy_study(draft)
    if _strip_run_metadata(value) != dict(draft):
        raise M7BExecutionBlocked("approved scientific design differs from immutable M7a draft")
    runtime = value.get("runtime_provenance")
    if not isinstance(runtime, Mapping):
        raise M7BExecutionBlocked("runtime provenance missing")
    if runtime.get("draft_file_sha256") != hashlib.sha256(_DRAFT_PATH.read_bytes()).hexdigest():
        raise M7BExecutionBlocked("M7a draft file fingerprint changed")
    if runtime.get("code_fingerprint") != _code_fingerprint():
        raise M7BExecutionBlocked("runtime source fingerprint changed since approval")
    if runtime.get("code_fingerprint_sha256") != _sha256_value(runtime["code_fingerprint"]):
        raise M7BExecutionBlocked("runtime source fingerprint digest mismatch")
    if (
        runtime.get("python_version") != platform.python_version()
        or runtime.get("numpy_version") != np.__version__
    ):
        raise M7BExecutionBlocked("Python/NumPy runtime differs from approved fingerprint")
    if runtime.get("prng") != "numpy.random.PCG64":
        raise M7BExecutionBlocked("approved PRNG is not PCG64")
    if verify_fingerprint:
        if approved_config_path is None:
            raise M7BExecutionBlocked("approved config path is required for hash verification")
        config_path = Path(approved_config_path)
        sidecar = Path(f"{config_path}.sha256")
        if not config_path.is_file() or not sidecar.is_file():
            raise M7BExecutionBlocked("approved config or SHA-256 sidecar is missing")
        if sidecar.read_text(encoding="ascii").strip() != _sha256_file(config_path):
            raise M7BExecutionBlocked("approved config SHA-256 sidecar mismatch")
        if json.loads(config_path.read_text(encoding="utf-8")) != value:
            raise M7BExecutionBlocked("loaded approved config differs from frozen file")
    expected_manifest = _train_manifest(draft)
    if value.get("run_manifest") != expected_manifest:
        raise M7BExecutionBlocked("TRAIN IDs/seeds differ from M7a derivation")
    if value.get("execution_limits") != {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "rss_limit_semantics": "periodic process RSS monitoring, not a hard OS process limit",
        "worker_processes": 1,
        "multiprocessing": False,
        "stop_before_next_sequence_on_budget": True,
        "atomic_checkpoint_per_sequence": True,
    }:
        raise M7BExecutionBlocked("approved TRAIN resource limits mismatch")
    receiver_config = runtime.get("receiver_configuration")
    if not isinstance(receiver_config, Mapping):
        raise M7BExecutionBlocked("frozen receiver configuration is missing")
    receiver = validate_reconstructed_offline_config(receiver_config)
    if (
        receiver["profile"] != "reconstructed_offline"
        or receiver["paper_exact"] is not False
        or receiver["receiver_enabled"] is not False
        or receiver["likelihood"]["beta"] != 0.7
        or receiver["timebase"]["samples_per_symbol"] != 8
        or receiver["timebase"]["symbol_origin_sample"] != 0
        or receiver["estimator"]["initial_time_index"] != 0
    ):
        raise M7BExecutionBlocked("approved reconstructed receiver profile mismatch")
    if runtime.get("receiver_configuration_sha256") != _sha256_value(receiver_config):
        raise M7BExecutionBlocked("receiver configuration fingerprint mismatch")
    baseline = value.get("historical_integrity_baseline")
    if not isinstance(baseline, Mapping) or baseline != historical_integrity_baseline():
        raise M7BExecutionBlocked("historical output integrity baseline mismatch")
    if callbacks:
        for name in ("rng", "data", "noise", "receiver"):
            if name not in callbacks or not callable(callbacks[name]):
                raise M7BExecutionBlocked(f"missing guarded callback: {name}")
    return dict(value)


def guard_m7b_execution(
    authorization: object,
    *,
    draft: Mapping[str, Any],
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> object:
    """Run an executor only after the TRAIN authorization and frozen design validate."""
    validate_m7b_approved_config(authorization, draft=draft, callbacks=callbacks)
    return executor()


def _candidate_policies(draft: Mapping[str, Any]) -> tuple[M7BPolicy, ...]:
    rows = draft["policy_grid"]["candidate_policies"]
    return tuple(
        M7BPolicy(
            candidate_id=str(row["candidate_id"]),
            alpha_prime=float(row["alpha_prime"]),
            k_scale=float(row["k_scale"]),
            k_tilde=tuple(float(item) for item in row["k_tilde"]),
        )
        for row in rows
    )


def run_policy_grid_on_received(
    *,
    run_id: str,
    received: ArrayLike,
    reference_information_bits: ArrayLike,
    real_channel_gain: float,
    configuration: Mapping[str, Any],
    initial_state: ReconstructionEstimatorState,
    beta: float,
    symbol_origin_sample: int,
    first_symbol_index: int,
    initial_estimator_time_index: int,
    candidate_ids: Sequence[str] | None = None,
    decoder_invocation_counter: list[int] | None = None,
) -> dict[str, Any]:
    """Run one and only one existing B4d/B5b pass per fixed candidate."""
    from hf_tcm.evaluation import reconstruction_adaptive_diagnostics as diagnostics

    bits_raw = np.asarray(reference_information_bits)
    if bits_raw.ndim != 1 or bits_raw.dtype.kind not in "iub" or bits_raw.size % 2:
        raise ValueError("reference bits must be an even-length integer vector")
    bits = np.asarray(bits_raw, dtype=np.int8)
    if bits.size == 0 or np.any((bits != 0) & (bits != 1)):
        raise ValueError("reference bits must be nonempty binary values")
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    received_values = np.asarray(received, dtype=np.complex128)
    sample_count = 8 * len(symbols)
    if received_values.shape != (sample_count,) or not np.all(np.isfinite(received_values)):
        raise ValueError("received must be a finite complex array with exactly 8F samples")
    validated, labeling, timebase = _config_operands(
        configuration, origin=symbol_origin_sample, initial_time=initial_estimator_time_index
    )
    if validated["likelihood"]["beta"] != beta:
        raise ValueError("policy beta differs from validated reconstruction configuration")
    received_owned = np.array(received_values, dtype=np.complex128, order="C", copy=True)
    received_owned.setflags(write=False)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be nonempty")
    sample_start = symbol_origin_sample + 8 * first_symbol_index
    sample_labels = np.arange(sample_start, sample_start + sample_count, dtype=np.int64)
    received_hash = hashlib.sha256(received_owned.tobytes()).hexdigest()
    reference_symbols = np.asarray(symbols, dtype=np.int64)
    reference_symbols.setflags(write=False)
    all_policy_rows = _candidate_policies(json.loads(_DRAFT_PATH.read_text(encoding="utf-8")))
    selected_ids = (
        tuple(policy.candidate_id for policy in all_policy_rows)
        if candidate_ids is None
        else tuple(candidate_ids)
    )
    policy_by_id = {policy.candidate_id: policy for policy in all_policy_rows}
    if len(selected_ids) != len(set(selected_ids)) or any(
        candidate_id not in policy_by_id for candidate_id in selected_ids
    ):
        raise ValueError("candidate_ids must be a unique subset of the fixed M7a grid")
    policy_rows = tuple(policy_by_id[candidate_id] for candidate_id in selected_ids)
    if decoder_invocation_counter is not None and len(decoder_invocation_counter) != 1:
        raise ValueError("decoder_invocation_counter must be a one-item mutable list")
    results: dict[str, Any] = {}
    decoder_calls = 0
    original_decoder = diagnostics.decode_reconstruction_viterbi

    def counted_decoder(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoder_calls
        decoder_calls += 1
        if decoder_invocation_counter is not None:
            decoder_invocation_counter[0] += 1
        return original_decoder(*args, **kwargs)

    diagnostics.decode_reconstruction_viterbi = counted_decoder
    try:
        for policy in policy_rows:
            length = len(symbols)
            alpha = (policy.alpha_prime,) * length
            gains = tuple(np.asarray([policy.k_tilde], dtype=np.float64) for _ in range(length))
            regular = tuple(np.zeros((1, 2), dtype=np.float64) for _ in range(length))
            results[policy.candidate_id] = _mode_run(
                mode=policy.candidate_id,
                initial_state=initial_state,
                alpha=alpha,
                gains=gains,
                regular=regular,
                received=received_owned,
                labels=sample_labels,
                received_start=sample_start,
                origin=symbol_origin_sample,
                first_symbol=first_symbol_index,
                first_time=initial_estimator_time_index,
                beta=beta,
                labeling=labeling,
                timebase=timebase,
                receiver_mode="monolithic",
                partition=(length,),
                reference_bits=np.asarray(bits, dtype=np.int8),
                reference_symbols=reference_symbols,
                received_sha256=received_hash,
                true_gain_for_evaluation=real_channel_gain,
            )
    finally:
        diagnostics.decode_reconstruction_viterbi = original_decoder
    if decoder_calls != len(policy_rows):
        raise RuntimeError("one unique decoder pass per policy invariant failed")
    if any(item.received_sha256 != received_hash for item in results.values()):
        raise RuntimeError("policy received hash differs from shared sequence buffer")
    return results


def _prepare_received(
    bits: BitArray, *, gain: float, noise_seed: int, sigma_squared: float, stream_id: str
) -> tuple[ComplexArray, SymbolArray, str]:
    reference_symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    labels = [
        index_to_label(int(index), profile=BASELINE_ASSUMPTION) for index in reference_symbols
    ]
    baseband = modulate(labels, phase_offset=0.0, profile=BASELINE_ASSUMPTION)
    in_phase, quadrature = symbols_to_iq_waveform(baseband, samples_per_symbol=8)
    clean = gain * (in_phase + 1j * quadrature)
    noise = generate_independent_complex_awgn(
        sample_count=8 * len(reference_symbols),
        sigma_squared=sigma_squared,
        seed=noise_seed,
        stream_id=stream_id,
    ).noise
    received = np.asarray(clean + noise, dtype=np.complex128)
    digest = hashlib.sha256(received.tobytes()).hexdigest()
    return received, np.asarray(reference_symbols, dtype=np.int64), digest


def _mode_record(policy: M7BPolicy, mode: Any) -> dict[str, Any]:
    counts = mode.evaluation.counts
    history = mode.history
    finite = bool(
        np.all(np.isfinite(mode.candidate_metrics))
        and np.all(np.isfinite(mode.posterior_history))
        and np.all(np.isfinite(mode.final_state.full_iq))
        and np.all(np.isfinite(mode.final_state.fluctuating_iq))
        and all(
            np.isfinite(row.full_estimate_error_norm)
            and np.all(np.isfinite(row.pre_state.full_iq))
            and np.all(np.isfinite(row.post_state.full_iq))
            and np.isclose(row.posterior.sum(), 1.0, rtol=0.0, atol=1e-12)
            for row in history
        )
    )
    if len(mode.decoded_information_bits) != 512 or len(mode.decoded_symbol_indices) != 256:
        raise ValueError("decoder output length invalid")
    if not finite:
        raise FloatingPointError("non-finite candidate state, metric, posterior, or diagnostic")
    return {
        "candidate_id": policy.candidate_id,
        "alpha_prime": policy.alpha_prime,
        "k_scale": policy.k_scale,
        "k_tilde": list(policy.k_tilde),
        "status": "complete_valid_output",
        "counts": {
            "bit_errors": int(counts.bit_errors),
            "total_bits": int(counts.total_bits),
            "symbol_errors": int(counts.symbol_errors),
            "total_symbols": int(counts.total_symbols),
        },
        "decoded_information_bits": [int(item) for item in mode.decoded_information_bits],
        "decoded_symbol_indices": [int(item) for item in mode.decoded_symbol_indices],
        "decoded_hypothesis_path": [int(item) for item in mode.decoded_hypothesis_path],
        "received_sha256": mode.received_sha256,
        "decoder_invocations": 1,
        "diagnostics": {
            "finite_coefficient_trajectory": True,
            "posterior_normalized": all(
                bool(np.isclose(row.posterior.sum(), 1.0, rtol=0.0, atol=1e-12)) for row in history
            ),
            "initial_full_iq": mode.initial_state.full_iq.tolist(),
            "initial_fluctuating_iq": mode.initial_state.fluctuating_iq.tolist(),
            "final_full_iq": mode.final_state.full_iq.tolist(),
            "final_fluctuating_iq": mode.final_state.fluctuating_iq.tolist(),
            "per_symbol_full_coefficient_error_norm": [
                float(row.full_estimate_error_norm) for row in history
            ],
            "full_iq_increment_norms": [
                float(np.linalg.norm(row.full_increment)) for row in history
            ],
            "decoded_path_cost": float(mode.decoder_result.best_path_metric),
        },
    }


def _atomic_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if exclusive else path.with_suffix(path.suffix + ".tmp")
    mode = "x" if exclusive else "w"
    with target.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(target, path)


def _checkpoint_path(directory: Path, run_id: str) -> Path:
    safe = run_id.rsplit(":", 1)[-1]
    return directory / "checkpoints" / f"{safe}.json"


def independent_verify(directory: str | Path, draft: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(directory)
    run_files = sorted((root / "checkpoints").glob("run-*.json"))
    checkpoints = [json.loads(path.read_text(encoding="utf-8")) for path in run_files]
    ids = [item.get("run_id") for item in checkpoints]
    expected_ids = [f"{draft['study_id']}:train:run-{index:03d}" for index in range(1, 41)]
    seen_hashes: set[str] = set()
    policy_totals = {
        candidate["candidate_id"]: {
            "bit_errors": 0,
            "total_bits": 0,
            "symbol_errors": 0,
            "total_symbols": 0,
            "valid_records": 0,
            "failures": 0,
        }
        for candidate in draft["policy_grid"]["candidate_policies"]
    }
    expected_candidates = [
        row["candidate_id"] for row in draft["policy_grid"]["candidate_policies"]
    ]
    policy_map = {row["candidate_id"]: row for row in draft["policy_grid"]["candidate_policies"]}
    planned_runs = _train_manifest(draft)["runs"]
    total_decoder_calls = 0
    complete_checkpoint_count = 0
    for checkpoint, planned in zip(checkpoints, planned_runs, strict=False):
        if (
            checkpoint.get("run_id") != planned["run_id"]
            or checkpoint.get("run_index") != planned["run_index"]
        ):
            raise ValueError("checkpoint run ID/index differs from approved manifest")
        if checkpoint.get("status") == "complete" and len(checkpoint.get("policies", [])) == 9:
            complete_checkpoint_count += 1
        elif checkpoint.get("status") == "received_generation_failure":
            records = checkpoint.get("policies", [])
            if [record.get("candidate_id") for record in records] != expected_candidates:
                raise ValueError(
                    "generation failure checkpoint must retain all candidate failure records"
                )
            for record in records:
                policy_totals[record["candidate_id"]]["failures"] += 1
            if checkpoint.get("seed_provenance") != planned["streams"]:
                raise ValueError("generation failure checkpoint seed provenance mismatch")
            continue
        else:
            raise ValueError("independent verification found malformed sequence checkpoint")
        if checkpoint.get("seed_provenance") != planned["streams"]:
            raise ValueError("checkpoint seed provenance differs from approved manifest")
        received_hash = checkpoint.get("received_sha256")
        if not isinstance(received_hash, str) or len(received_hash) != 64:
            raise ValueError("checkpoint received hash is invalid")
        seen_hashes.add(received_hash)
        reference_bits = np.asarray(
            checkpoint["evaluation_only"]["reference_information_bits"], dtype=np.int8
        )
        reference_symbols = np.asarray(
            checkpoint["evaluation_only"]["reference_symbol_indices"], dtype=np.int64
        )
        if reference_bits.shape != (512,) or reference_symbols.shape != (256,):
            raise ValueError("checkpoint reference evaluation arrays have invalid shapes")
        expected_reference_symbols = encode_reference_symbol_indices(
            reference_bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
        )
        if not np.array_equal(reference_symbols, expected_reference_symbols):
            raise ValueError(
                "reference coded-symbol provenance does not match saved information bits"
            )
        records = checkpoint["policies"]
        if [record.get("candidate_id") for record in records] != expected_candidates:
            raise ValueError("checkpoint policy IDs are missing, duplicated, or reordered")
        checkpoint_decoder_calls = 0
        for record in records:
            candidate_id = record["candidate_id"]
            total = policy_totals[candidate_id]
            total_decoder_calls += int(record.get("decoder_invocations", 0))
            checkpoint_decoder_calls += int(record.get("decoder_invocations", 0))
            if record["status"] != "complete_valid_output":
                total["failures"] += 1
                continue
            if record.get("received_sha256") != received_hash:
                raise ValueError("candidate received hash differs from paired sequence hash")
            expected_policy = policy_map[candidate_id]
            if (
                record.get("alpha_prime") != expected_policy["alpha_prime"]
                or record.get("k_scale") != expected_policy["k_scale"]
                or record.get("k_tilde") != expected_policy["k_tilde"]
            ):
                raise ValueError("checkpoint candidate parameters differ from fixed M7a grid")
            decoded_bits = np.asarray(record["decoded_information_bits"], dtype=np.int8)
            decoded_symbols = np.asarray(record["decoded_symbol_indices"], dtype=np.int64)
            if decoded_bits.shape != (512,) or decoded_symbols.shape != (256,):
                raise ValueError("checkpoint decoded evaluation arrays have invalid shapes")
            bit_errors = count_bit_errors(reference_bits, decoded_bits)
            symbol_errors = count_symbol_errors(reference_symbols, decoded_symbols)
            expected_counts = {
                "bit_errors": bit_errors,
                "total_bits": 512,
                "symbol_errors": symbol_errors,
                "total_symbols": 256,
            }
            if record.get("counts") != expected_counts:
                raise ValueError("independent decoded-output count replay mismatch")
            validate_hypothesis_edge_path(
                record["decoded_hypothesis_path"], initial_state=INITIAL_STATE
            )
            decoded_path = tuple(int(item) for item in record["decoded_hypothesis_path"])
            expected_decoded_bits = np.asarray(
                [bit for edge in decoded_path for bit in HYPOTHESES[edge].input_bits],
                dtype=np.int8,
            )
            expected_decoded_symbols = decoded_path_symbol_indices(
                decoded_path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            )
            if not np.array_equal(decoded_bits, expected_decoded_bits) or not np.array_equal(
                decoded_symbols, expected_decoded_symbols
            ):
                raise ValueError("saved decoder outputs do not match the frozen hypothesis path")
            total["bit_errors"] += bit_errors
            total["total_bits"] += 512
            total["symbol_errors"] += symbol_errors
            total["total_symbols"] += 256
            total["valid_records"] += 1
        if checkpoint.get("decoder_invocations") != checkpoint_decoder_calls:
            raise ValueError("checkpoint decoder invocation count differs from policy records")
    if ids != expected_ids[: len(ids)] or len(ids) != len(set(ids)):
        raise ValueError("checkpoint run IDs are duplicated, unexpected, or out of order")
    if len(seen_hashes) != complete_checkpoint_count:
        raise ValueError("received hashes are not unique across independent sequences")
    frozen_id = "a100_k000"
    frozen_complete = (
        policy_totals[frozen_id]["valid_records"] == 40
        and policy_totals[frozen_id]["failures"] == 0
    )
    rankings: list[dict[str, Any]] = []
    policies = {row["candidate_id"]: row for row in draft["policy_grid"]["candidate_policies"]}
    for candidate_id, total in policy_totals.items():
        eligible = frozen_complete and total["valid_records"] == 40 and total["failures"] == 0
        if (
            total["total_bits"] != total["valid_records"] * 512
            or total["total_symbols"] != total["valid_records"] * 256
        ):
            raise ValueError("denominator does not match complete valid records")
        rankings.append(
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
            }
        )
    eligible_rows = [row for row in rankings if row["eligible"]]
    ordered = sorted(
        eligible_rows,
        key=lambda row: (
            Fraction(row["bit_errors"], row["total_bits"]),
            Fraction(row["symbol_errors"], row["total_symbols"]),
            policies[row["candidate_id"]]["k_scale"],
            abs(1.0 - policies[row["candidate_id"]]["alpha_prime"]),
            row["candidate_id"],
        ),
    )
    training_complete = (
        len(checkpoints) == 40 and complete_checkpoint_count == 40 and total_decoder_calls == 360
    )
    return {
        "status": "TRAIN_SELECTED_NOT_VALIDATED"
        if training_complete and ordered
        else "TRAIN_INCOMPLETE",
        "run_count": len(checkpoints),
        "complete_sequence_checkpoints": complete_checkpoint_count,
        "unique_run_ids": len(set(ids)),
        "unique_received_hashes": len(seen_hashes),
        "expected_policy_records": len(checkpoints) * 9,
        "policy_totals": rankings,
        "ranking": ordered,
        "selected_candidate_id": ordered[0]["candidate_id"] if ordered else None,
        "frozen_B_complete": frozen_complete,
        "decoder_invocations": total_decoder_calls,
        "decoder_invocations_expected": len(checkpoints) * 9,
    }


def _manifest_file_hashes(directory: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(
        item
        for item in directory.rglob("*")
        if item.is_file() and item.name != "integrity_manifest.json"
    ):
        hashes[path.relative_to(directory).as_posix()] = _sha256_file(path)
    return hashes


def execute_m7b_train(
    approved_config_path: str | Path,
    *,
    draft_path: str | Path = _DRAFT_PATH,
    output_root: str | Path | None = None,
) -> M7BTrainSummary:
    """Execute only the 40 authorized TRAIN sequences, with strict preflight."""
    approved_path = Path(approved_config_path)
    value = json.loads(approved_path.read_text(encoding="utf-8"))
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    validate_m7b_approved_config(
        value, draft=draft, approved_config_path=approved_path, verify_fingerprint=True
    )
    directory = (
        Path(output_root) if output_root is not None else _ROOT / value["output"]["namespace"]
    )
    if directory.exists() and any(directory.iterdir()):
        raise M7BExecutionBlocked("output namespace already contains files; resume is not implicit")
    directory.mkdir(parents=True, exist_ok=True)
    config_hash = _sha256_file(approved_path)
    _atomic_json(directory / "approved_config_snapshot.json", value, exclusive=True)
    _atomic_json(
        directory / "manifest.json",
        {
            "schema_version": "m7b.train.v1",
            "experiment_id": value["study_id"],
            "approved_config_sha256": config_hash,
            "draft_sha256": value["runtime_provenance"]["draft_file_sha256"],
            "code_fingerprint": value["runtime_provenance"]["code_fingerprint"],
            "git": value["runtime_provenance"]["git"],
            "run_manifest": value["run_manifest"],
            "candidate_ids": [
                row["candidate_id"] for row in draft["policy_grid"]["candidate_policies"]
            ],
            "status": "authorized TRAIN only",
        },
        exclusive=True,
    )
    # Authorization and all immutable scientific/config checks precede this point.
    receiver_config = value["runtime_provenance"]["receiver_configuration"]
    beta = float(draft["shared_estimator"]["beta"])
    gain = float(draft["profile"]["real_channel_gain"])
    sigma_squared = float(draft["profile"]["sigma_squared"])
    initial = ReconstructionEstimatorState(
        [draft["shared_estimator"]["initial_fluctuating_iq"]],
        [draft["shared_estimator"]["initial_full_iq"]],
        int(draft["clock_origins"]["estimator_time_index_origin"]),
    )
    started = time.perf_counter()
    decoder_total = 0
    completed = 0
    rss_peak: int | None = None
    rss_unverified = False
    limit = value["execution_limits"]
    from hf_tcm.evaluation.m5h_pilot_runner import _process_rss_windows

    for run in value["run_manifest"]["runs"]:
        if time.perf_counter() - started >= int(limit["wall_clock_limit_seconds"]):
            break
        rss = _process_rss_windows(os.getpid())
        if rss is None:
            rss_unverified = True
        else:
            rss_peak = max(rss_peak or 0, rss)
            if rss >= int(limit["rss_monitoring_budget_bytes"]):
                break
        checkpoint_path = _checkpoint_path(directory, run["run_id"])
        if checkpoint_path.exists():
            raise M7BExecutionBlocked("checkpoint exists in non-resume TRAIN execution")
        seeds = run["streams"]
        try:
            data_rng = np.random.Generator(np.random.PCG64(seeds["data"]["derived_seed"]))
            bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
            received, reference_symbols, received_hash = _prepare_received(
                bits,
                gain=gain,
                noise_seed=int(seeds["noise"]["derived_seed"]),
                sigma_squared=sigma_squared,
                stream_id=f"M7b:TRAIN:{run['run_id']}:noise",
            )
        except Exception as exc:
            failure = {
                "schema_version": "m7b.train.v1",
                "run_id": run["run_id"],
                "run_index": run["run_index"],
                "status": "received_generation_failure",
                "exception_type": type(exc).__name__,
                "detail": str(exc),
                "seed_provenance": seeds,
                "policies": [
                    {
                        "candidate_id": policy.candidate_id,
                        "alpha_prime": policy.alpha_prime,
                        "k_scale": policy.k_scale,
                        "k_tilde": list(policy.k_tilde),
                        "status": "not_run_received_generation_failure",
                        "exception_type": type(exc).__name__,
                        "detail": str(exc),
                        "decoder_invocations": 0,
                    }
                    for policy in _candidate_policies(draft)
                ],
                "decoder_invocations": 0,
            }
            _atomic_json(checkpoint_path, failure)
            break
        policy_records: list[dict[str, Any]] = []
        run_decoder_calls = 0
        policies = {row.candidate_id: row for row in _candidate_policies(draft)}
        for candidate_id in (
            row["candidate_id"] for row in draft["policy_grid"]["candidate_policies"]
        ):
            candidate_call_count = [0]
            try:
                mode = run_policy_grid_on_received(
                    run_id=run["run_id"],
                    received=received,
                    reference_information_bits=bits,
                    real_channel_gain=gain,
                    configuration=receiver_config,
                    initial_state=initial,
                    beta=beta,
                    symbol_origin_sample=int(draft["clock_origins"]["absolute_sample_origin"]),
                    first_symbol_index=int(draft["clock_origins"]["absolute_symbol_origin"]),
                    initial_estimator_time_index=int(
                        draft["clock_origins"]["estimator_time_index_origin"]
                    ),
                    candidate_ids=(candidate_id,),
                    decoder_invocation_counter=candidate_call_count,
                )[candidate_id]
                policy_records.append(_mode_record(policies[candidate_id], mode))
            except Exception as exc:
                policy_records.append(
                    {
                        "candidate_id": candidate_id,
                        "alpha_prime": policies[candidate_id].alpha_prime,
                        "k_scale": policies[candidate_id].k_scale,
                        "k_tilde": list(policies[candidate_id].k_tilde),
                        "status": "numerical_or_decoder_failure",
                        "exception_type": type(exc).__name__,
                        "detail": str(exc),
                        "decoder_invocations": candidate_call_count[0],
                    }
                )
            run_decoder_calls += candidate_call_count[0]
        decoder_total += run_decoder_calls
        checkpoint = {
            "schema_version": "m7b.train.v1",
            "run_id": run["run_id"],
            "run_index": run["run_index"],
            "status": "complete" if len(policy_records) == 9 else "incomplete",
            "received_sha256": received_hash,
            "seed_provenance": seeds,
            "decoder_invocations": run_decoder_calls,
            "evaluation_only": {
                "reference_information_bits": [int(item) for item in bits],
                "reference_symbol_indices": [int(item) for item in reference_symbols],
                "real_channel_gain": gain,
                "sigma_squared": sigma_squared,
            },
            "policies": policy_records,
        }
        _atomic_json(checkpoint_path, checkpoint)
        completed += 1
        if len(policy_records) != 9 or any(
            item["status"] != "complete_valid_output" for item in policy_records
        ):
            # Continue the predeclared grid/run order; failures remain explicit.
            continue
    elapsed = time.perf_counter() - started
    try:
        verification = independent_verify(directory, draft)
    except (ValueError, KeyError, TypeError) as exc:
        verification = {"status": "VERIFICATION_FAILED", "detail": str(exc)}
    complete_run_count = int(verification.get("run_count", 0))
    complete = (
        verification.get("status") == "TRAIN_SELECTED_NOT_VALIDATED"
        and complete_run_count == 40
        and verification.get("decoder_invocations") == 360
        and verification.get("decoder_invocations_expected") == 360
    )
    status = "TRAIN_SELECTED_NOT_VALIDATED" if complete else "TRAIN_INCOMPLETE"
    verification["status"] = status if complete else verification.get("status", "TRAIN_INCOMPLETE")
    ranking = verification.get("ranking", [])
    summary = {
        "schema_version": "m7b.train.v1",
        "classification": "authorized exploratory TRAIN policy selection, NOT independent validation, NOT confirmatory performance evidence, NOT source-faithful receiver",
        "status": status,
        "approved_config_sha256": config_hash,
        "runtime_code_fingerprint": value["runtime_provenance"]["code_fingerprint"],
        "planned_run_count": 40,
        "completed_run_count": completed,
        "checkpoint_run_count": complete_run_count,
        "policy_record_count": sum(
            len(json.loads(path.read_text(encoding="utf-8")).get("policies", []))
            for path in sorted((directory / "checkpoints").glob("run-*.json"))
        ),
        "decoder_invocations": decoder_total,
        "received_samples_generated": completed * 256 * 8,
        "information_bits_generated": completed * 512,
        "policy_symbol_passes": decoder_total * 256,
        "unique_policy_decoder_passes": decoder_total,
        "selection_rule": draft["selection"]["tie_break_order"],
        "ranking": ranking,
        "selected_candidate_id": verification.get("selected_candidate_id") if complete else None,
        "independent_verification": verification,
        "resource": {
            "wall_clock_seconds": elapsed,
            "completed_runs": completed,
            "rss_peak_bytes_observed": rss_peak,
            "rss_status": "RSS_UNVERIFIED"
            if rss_unverified or rss_peak is None
            else "periodic_monitor_observed",
            "process_count": 1,
            "multiprocessing": False,
            "budget_wall_clock_seconds": limit["wall_clock_limit_seconds"],
            "budget_rss_bytes": limit["rss_monitoring_budget_bytes"],
        },
        "limitations": draft["scientific_limitations"],
    }
    historical_after = historical_integrity_baseline()
    if historical_after != value["historical_integrity_baseline"]:
        status = "TRAIN_INCOMPLETE"
        verification = {
            **verification,
            "status": "VERIFICATION_FAILED",
            "detail": "historical M5f/M5h/M5j/M6b/M6g/M6h artifact integrity changed",
        }
        selected = None
    else:
        selected = verification.get("selected_candidate_id") if complete else None
    summary["status"] = status
    summary["selected_candidate_id"] = selected
    summary["independent_verification"] = verification
    _atomic_json(directory / "independent_verification.json", verification)
    _atomic_json(directory / "summary.json", summary)
    if selected is not None:
        candidate = next(
            row
            for row in draft["policy_grid"]["candidate_policies"]
            if row["candidate_id"] == selected
        )
        selected_record = {
            "status": "TRAIN_SELECTED_NOT_VALIDATED",
            "candidate_id": selected,
            "alpha_prime": candidate["alpha_prime"],
            "k_tilde": candidate["k_tilde"],
            "k_scale": candidate["k_scale"],
            "beta": beta,
            "initial_full_iq": draft["shared_estimator"]["initial_full_iq"],
            "mu0": draft["shared_estimator"]["mu0"],
            "scientific_profile": draft["profile"],
            "selection_rule": draft["selection"],
            "pooled_training_statistics": next(
                row for row in verification["policy_totals"] if row["candidate_id"] == selected
            ),
            "approved_config_sha256": config_hash,
            "software_fingerprint": value["runtime_provenance"]["code_fingerprint"],
            "training_run_ids": [run["run_id"] for run in value["run_manifest"]["runs"]],
            "validation_or_final_authorized": False,
        }
        _atomic_json(directory / "selected_policy.json", selected_record, exclusive=True)
    _atomic_json(
        directory / "integrity_manifest.json", _manifest_file_hashes(directory), exclusive=True
    )
    return M7BTrainSummary(
        status=status,
        completed_runs=completed,
        decoder_invocations=decoder_total,
        selected_candidate_id=selected,
        candidate_ranking=tuple(ranking),
        verification=verification,
        resource=summary["resource"],
    )
