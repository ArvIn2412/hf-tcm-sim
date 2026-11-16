"""Authorized M9b two-policy evaluation on one paired received sequence per run."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.coding.encoder import INITIAL_STATE
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.error_metrics import (
    ErrorCounts,
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
)
from hf_tcm.evaluation.m5h_pilot_runner import _process_rss_windows
from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design
from hf_tcm.evaluation.m7b_train_runner import (
    _atomic_json,
    _historical_tree_hash,
    _sha256_file,
    historical_integrity_baseline,
)
from hf_tcm.evaluation.m8b_train_runner import _prepare_received
from hf_tcm.evaluation.m9a_fixed_policy_study_design import (
    validate_m9a_fixed_policy_study,
)
from hf_tcm.evaluation.paired_cluster_bootstrap import (
    PairedRunCounts,
    paired_cluster_bootstrap,
)
from hf_tcm.receiver.reconstruction_conditional_decode import (
    decode_reconstruction_conditional_sequence,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import RECTANGULAR_ZOH_RULE
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_SAMPLES_PER_SYMBOL,
    ADR012_WAVEFORM_RULE,
)
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

ROOT = Path(__file__).resolve().parents[3]
DRAFT_PATH = ROOT / "configs/m9a_fixed_policy_study_draft.json"
APPROVED_PATH = ROOT / "configs/m9b_evaluation_approved_run.json"
OUTPUT_PATH = ROOT / "outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1"
EXPECTED_DRAFT_SHA256 = "a6be31a2225aeaee48fffec5ff6f868866773a1087978a561e4cadea78e1d5ac"
SCHEMA = "m9b.fixed-policy-evaluation.v1"
CLASSIFICATION = (
    "prospective fixed-policy comparison motivated by post-hoc M8 runner-up; "
    "not M8 validation, not tuning, not paper-exact, not physical HF evaluation"
)
WALL_CLOCK_BUDGET_SECONDS = 900
RSS_MONITORING_BUDGET_BYTES = 1_610_612_736
_PROTOCOL_WORD = 1_295_337_521
_PARTITION_CODE = 901
_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37, "metadata": 41}
_RUNTIME_FIELDS = {
    "authorization_provenance",
    "runtime_provenance",
    "execution_limits",
    "output",
    "run_manifest",
    "historical_integrity_baseline",
}
_SOURCE_PATHS = (
    "configs/m9a_fixed_policy_study_draft.json",
    "configs/m5i_confirmatory_design_draft.json",
    "src/hf_tcm/evaluation/m9a_fixed_policy_study_design.py",
    "src/hf_tcm/evaluation/m9b_fixed_policy_evaluation_runner.py",
    "src/hf_tcm/evaluation/m7b_train_runner.py",
    "src/hf_tcm/evaluation/m8b_train_runner.py",
    "src/hf_tcm/evaluation/matched_m2_b5_experiment.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/evaluation/paired_cluster_bootstrap.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_sequence.py",
    "src/hf_tcm/receiver/reconstruction_posterior_estimator_step.py",
    "src/hf_tcm/receiver/reconstruction_candidate_metrics.py",
    "src/hf_tcm/receiver/reconstruction_posterior.py",
    "src/hf_tcm/receiver/reconstruction_conditional_decode.py",
    "src/hf_tcm/receiver/reconstruction_forward.py",
    "src/hf_tcm/receiver/reconstruction_observation.py",
    "src/hf_tcm/receiver/reconstruction_labeling.py",
    "src/hf_tcm/receiver/iq_prediction.py",
    "src/hf_tcm/receiver/paper_recursion.py",
    "src/hf_tcm/decoding/reconstruction_viterbi.py",
    "src/hf_tcm/coding/encoder.py",
    "src/hf_tcm/coding/hypotheses.py",
    "src/hf_tcm/modulation/psk8.py",
    "src/hf_tcm/modulation/labeling.py",
    "src/hf_tcm/receiver/iq.py",
    "src/hf_tcm/reconstruction_config.py",
)
_HISTORICAL_PATHS = {
    "M5f": "outputs/m5f_paired_monte_carlo_records.json",
    "M5h": "outputs/m5h_independent_pilot",
    "M5j": "outputs/m5j_confirmatory",
    "M6b": "outputs/m6b_trace_diagnostics",
    "M6g": "outputs/m6g_multistep_feedback_audit/deterministic_trace.json",
    "M6h": "outputs/m6h_posterior_clamp/deterministic_trace.json",
    "M7b": "outputs/m7b_train",
    "M8_original_failed": "outputs/m8b_train/m8_anchored_reconstructed_adaptation_v1",
    "M8_recovery": "outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2",
    "M8_closeout": "outputs/m8c_closeout/paired_runnerup_audit.json",
    "M8a_draft": "configs/m8a_anchored_study_draft.json",
    "M8b_recovery_approval": "configs/m8b_train_recovery_approved_run.json",
    "M9a_draft": "configs/m9a_fixed_policy_study_draft.json",
}


class M9BExecutionBlocked(RuntimeError):
    """The approved M9b evaluation gate or a provenance/integrity check failed."""


@dataclass(frozen=True, slots=True)
class M9BClockOrigins:
    absolute_sample_origin: int
    absolute_symbol_origin: int
    estimator_time_index_origin: int
    provenance: Mapping[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "absolute_sample_origin": self.absolute_sample_origin,
            "absolute_symbol_origin": self.absolute_symbol_origin,
            "estimator_time_index_origin": self.estimator_time_index_origin,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class M9BPolicyOutput:
    record: Mapping[str, Any]
    result: Any
    receiver_kwargs: Mapping[str, Any]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256_value(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


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


def _source_fingerprint() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in _SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise M9BExecutionBlocked(f"runtime source file missing: {relative}")
        result[relative] = _sha256_file(path)
    return result


def _historical_baseline() -> dict[str, Any]:
    baseline = historical_integrity_baseline()
    for key, relative in _HISTORICAL_PATHS.items():
        baseline[key] = _historical_tree_hash(ROOT / relative)
    return baseline


def resolve_m9_clock_origins(receiver_configuration: Mapping[str, Any]) -> M9BClockOrigins:
    """Resolve explicit clocks from M5i config and the B4d fresh-sequence contract.

    M9a does not contain a ``clock_origins`` field. The sample and estimator
    tick origins come from the accepted receiver configuration; B4d requires a
    new independent sequence to start at its symbol origin, which is zero.
    """
    validated = validate_reconstructed_offline_config(receiver_configuration)
    sample_origin = validated["timebase"].get("symbol_origin_sample")
    tick_origin = validated["estimator"].get("initial_time_index")
    if sample_origin != 0 or tick_origin != 0:
        raise M9BExecutionBlocked("M9 fixed evaluation requires accepted zero sample/tick origins")
    return M9BClockOrigins(
        absolute_sample_origin=0,
        absolute_symbol_origin=0,
        estimator_time_index_origin=0,
        provenance={
            "sample_origin": "M5i accepted reconstruction_configuration.timebase.symbol_origin_sample",
            "symbol_origin": "B4d new_independent_sequence: first_symbol_index equals sequence_origin_symbol_index; fresh sequence starts at 0",
            "estimator_tick_origin": "M5i accepted reconstruction_configuration.estimator.initial_time_index",
            "m9a_clock_origins_field": "absent; no default fallback",
        },
    )


def _receiver_configuration() -> dict[str, Any]:
    return load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]


def _derive_seed(master_seed: int, spawn_key: list[int]) -> int:
    sequence = np.random.SeedSequence(master_seed, spawn_key=tuple(spawn_key))
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def build_run_manifest(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the exact planned seed provenance, not data/noise generator draws."""
    validate_m9a_fixed_policy_study(draft)
    roots = draft["partition"]["seed_namespaces"]
    rows = []
    all_child_seeds: list[int] = []
    for run in draft["partition"]["planned_runs"]:
        streams: dict[str, Any] = {}
        for name in ("data", "noise", "metadata"):
            proposal = run["streams"][name]
            key = list(proposal["spawn_key"])
            child = _derive_seed(int(roots[name]), key)
            all_child_seeds.append(child)
            streams[name] = {
                "master_seed": int(roots[name]),
                "spawn_key": key,
                "derived_seed": child,
                "generator": "PCG64",
                "initialized": False,
            }
        rows.append({"run_id": run["run_id"], "run_index": run["run_index"], "streams": streams})
    bootstrap = draft["partition"]["bootstrap_stream"]
    bootstrap_seed = _derive_seed(int(bootstrap["master_seed"]), list(bootstrap["spawn_key"]))
    all_child_seeds.append(bootstrap_seed)
    if len(all_child_seeds) != len(set(all_child_seeds)):
        raise M9BExecutionBlocked("M9 derived seeds collide across data/noise/metadata/bootstrap")
    return {
        "partition": "EVALUATION",
        "partition_code": _PARTITION_CODE,
        "run_index_origin": 0,
        "run_order": "ascending run_index 0..99",
        "stream_codes": dict(_STREAM_CODES),
        "runs": rows,
        "bootstrap": {
            "master_seed": int(bootstrap["master_seed"]),
            "spawn_key": list(bootstrap["spawn_key"]),
            "derived_seed": bootstrap_seed,
            "generator": "PCG64",
            "initialized": False,
        },
    }


def create_approved_m9b_config(
    *,
    draft: Mapping[str, Any],
    output_config_path: str | Path = APPROVED_PATH,
    output_directory: str = "outputs/m9b_fixed_policy_evaluation/m9_fixed_anchored_vs_frozen_v1",
) -> dict[str, Any]:
    """Freeze approved snapshot + sidecar before any M9 data/noise RNG draw."""
    validate_m9a_fixed_policy_study(draft)
    draft_hash = _sha256_file(DRAFT_PATH)
    if draft_hash != EXPECTED_DRAFT_SHA256:
        raise M9BExecutionBlocked("M9a draft fingerprint mismatch; blocked before RNG")
    if output_directory != OUTPUT_PATH.relative_to(ROOT).as_posix():
        raise M9BExecutionBlocked("M9b output namespace must be the isolated approved path")
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    manifest = build_run_manifest(draft)
    approved = copy.deepcopy(dict(draft))
    approved.update(
        design_status="approved_evaluation",
        execution_authorized=True,
        execution_scope="m9b_evaluation_only",
    )
    approved["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization through this M9b Codex instruction",
        "scope": "M9b fixed-policy evaluation only; no other partition or study authorized",
    }
    fingerprint = _source_fingerprint()
    environment = {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "git": _git_provenance(),
    }
    approved["runtime_provenance"] = {
        "m9a_draft_sha256": draft_hash,
        "source_file_manifest": fingerprint,
        "runtime_source_fingerprint_sha256": _sha256_value(fingerprint),
        "environment": environment,
        "receiver_configuration_source": "M5i accepted reconstructed_offline configuration",
        "receiver_configuration_sha256": _sha256_value(receiver_config),
        "clock_origins": clocks.as_dict(),
        "output_schema": SCHEMA,
        "config_sha256_sidecar": True,
        "git_revision_unavailable_is_recorded": True,
    }
    approved["execution_limits"] = {
        "wall_clock_budget_seconds": WALL_CLOCK_BUDGET_SECONDS,
        "rss_monitoring_budget_bytes": RSS_MONITORING_BUDGET_BYTES,
        "rss_semantics": "periodic monitoring only; not a hard OS process limit",
        "process_count": 1,
        "multiprocessing": False,
        "atomic_checkpoint_after_each_run": True,
        "stop_at_next_run_boundary_on_budget": True,
        "bootstrap_time_measured_separately": True,
    }
    approved["output"] = {
        "experiment_id": draft["experiment_id"],
        "namespace": output_directory,
        "schema_version": SCHEMA,
        "atomic_checkpoint_per_run": True,
        "integrity_manifest_excludes_itself": True,
    }
    approved["run_manifest"] = manifest
    approved["historical_integrity_baseline"] = _historical_baseline()
    target = Path(output_config_path)
    if target.exists() or Path(f"{target}.sha256").exists():
        raise M9BExecutionBlocked("M9b approved config or sidecar already exists; no overwrite")
    _atomic_json(target, approved, exclusive=True)
    digest = _sha256_file(target)
    sidecar = Path(f"{target}.sha256")
    with sidecar.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return approved


def _strip_runtime(approved: Mapping[str, Any]) -> dict[str, Any]:
    stripped = {
        key: copy.deepcopy(value) for key, value in approved.items() if key not in _RUNTIME_FIELDS
    }
    stripped.update(design_status="proposed", execution_authorized=False, execution_scope="none")
    return stripped


def validate_approved_m9b(
    approved: object,
    *,
    draft: Mapping[str, Any],
    config_path: str | Path | None = None,
    verify_file: bool = True,
) -> dict[str, Any]:
    """Validate all authorization/provenance fields before any RNG callback."""
    validate_m9a_fixed_policy_study(draft)
    if not isinstance(approved, Mapping) or (
        approved.get("design_status") != "approved_evaluation"
        or approved.get("execution_authorized") is not True
        or approved.get("execution_scope") != "m9b_evaluation_only"
    ):
        raise M9BExecutionBlocked("M9b evaluation authorization scope mismatch")
    if approved.get("authorization_provenance", {}).get("explicit_user_authorization") != (
        "explicit user authorization through this M9b Codex instruction"
    ):
        raise M9BExecutionBlocked("M9b authorization provenance mismatch")
    if _strip_runtime(approved) != dict(draft):
        raise M9BExecutionBlocked("approved M9b scientific design differs from M9a draft")
    if approved.get("runtime_provenance", {}).get("m9a_draft_sha256") != EXPECTED_DRAFT_SHA256:
        raise M9BExecutionBlocked("approved M9a draft hash mismatch")
    fingerprint = _source_fingerprint()
    runtime = approved.get("runtime_provenance", {})
    if runtime.get("source_file_manifest") != fingerprint:
        raise M9BExecutionBlocked("M9b runtime source fingerprint changed")
    if runtime.get("runtime_source_fingerprint_sha256") != _sha256_value(fingerprint):
        raise M9BExecutionBlocked("M9b runtime source fingerprint digest mismatch")
    if runtime.get("environment") != {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "git": _git_provenance(),
    }:
        raise M9BExecutionBlocked("M9b environment differs from approved snapshot")
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    if runtime.get("receiver_configuration_sha256") != _sha256_value(receiver_config):
        raise M9BExecutionBlocked("M9b receiver configuration fingerprint changed")
    if runtime.get("clock_origins") != clocks.as_dict():
        raise M9BExecutionBlocked("M9b clock origins differ from B4d/M5i contracts")
    if approved.get("run_manifest") != build_run_manifest(draft):
        raise M9BExecutionBlocked("M9b run IDs or exact seed derivation changed")
    if approved.get("historical_integrity_baseline") != _historical_baseline():
        raise M9BExecutionBlocked("historical artifact integrity baseline changed")
    if approved.get("execution_limits") != {
        "wall_clock_budget_seconds": WALL_CLOCK_BUDGET_SECONDS,
        "rss_monitoring_budget_bytes": RSS_MONITORING_BUDGET_BYTES,
        "rss_semantics": "periodic monitoring only; not a hard OS process limit",
        "process_count": 1,
        "multiprocessing": False,
        "atomic_checkpoint_after_each_run": True,
        "stop_at_next_run_boundary_on_budget": True,
        "bootstrap_time_measured_separately": True,
    }:
        raise M9BExecutionBlocked("M9b execution limits differ from approved snapshot")
    if approved.get("output", {}).get("namespace") != OUTPUT_PATH.relative_to(ROOT).as_posix():
        raise M9BExecutionBlocked("M9b output namespace mismatch")
    if verify_file:
        if config_path is None:
            raise M9BExecutionBlocked("M9b approved config path is required")
        path = Path(config_path)
        sidecar = Path(f"{path}.sha256")
        if not path.is_file() or not sidecar.is_file():
            raise M9BExecutionBlocked("M9b config snapshot or checksum sidecar is missing")
        digest = _sha256_file(path)
        if sidecar.read_text(encoding="ascii").strip() != digest:
            raise M9BExecutionBlocked("M9b approved config checksum mismatch")
        if json.loads(path.read_text(encoding="utf-8")) != approved:
            raise M9BExecutionBlocked("M9b in-memory config differs from frozen file")
    return dict(approved)


def guard_m9b_execution(
    approved: object,
    *,
    draft: Mapping[str, Any],
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
    config_path: str | Path | None = None,
    verify_file: bool = False,
) -> object:
    """Fail closed before any RNG, sample, or receiver callback."""
    validate_approved_m9b(approved, draft=draft, config_path=config_path, verify_file=verify_file)
    if any(name not in callbacks or not callable(callbacks[name]) for name in ("rng", "receiver")):
        raise M9BExecutionBlocked("M9b RNG and receiver guard spies are required")
    return executor()


def _receiver_kwargs(
    *,
    policy: Mapping[str, Any],
    received: NDArray[np.complex128],
    receiver_configuration: Mapping[str, Any],
    clocks: M9BClockOrigins,
) -> dict[str, Any]:
    receiver = validate_reconstructed_offline_config(receiver_configuration)
    if received.flags.writeable or received.ndim != 1 or not np.all(np.isfinite(received)):
        raise M9BExecutionBlocked("receiver input must be finite, one-dimensional, and immutable")
    count = int(received.size // ADR012_SAMPLES_PER_SYMBOL)
    if count < 1 or received.size != count * ADR012_SAMPLES_PER_SYMBOL:
        raise M9BExecutionBlocked("received sample count must be an exact 8sps sequence")
    sample_start = clocks.absolute_sample_origin + 8 * clocks.absolute_symbol_origin
    state = ReconstructionEstimatorState(
        [policy["initial_fluctuating_iq"]],
        [policy["initial_full_iq"]],
        clocks.estimator_time_index_origin,
    )
    indices = np.arange(sample_start, sample_start + received.size, dtype=np.int64)
    return {
        "received": received,
        "absolute_sample_indices": indices,
        "received_start_sample": sample_start,
        "symbol_origin_sample": clocks.absolute_sample_origin,
        "first_symbol_index": clocks.absolute_symbol_origin,
        "sequence_origin_symbol_index": clocks.absolute_symbol_origin,
        "symbol_count": count,
        "symbol_indices": tuple(
            range(clocks.absolute_symbol_origin, clocks.absolute_symbol_origin + count)
        ),
        "initial_estimator_state": state,
        "initial_estimator_time_index": clocks.estimator_time_index_origin,
        "initial_encoder_state": INITIAL_STATE,
        "sequence_mode": "new_independent_sequence",
        "beta": float(policy["beta"]),
        "alpha_prime": float(policy["alpha_prime"]),
        "k_tilde": np.asarray([policy["k_tilde"]], dtype=np.float64),
        "mu0": np.asarray([policy["mu0"]], dtype=np.float64),
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": ADR012_SAMPLES_PER_SYMBOL,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": str(receiver["labeling"]["name"]),
        "bit_order": tuple(receiver["labeling"]["bit_order"]),
        "timebase_profile": str(receiver["timebase"]["name"]),
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": "zero_padding",
    }


def _decode_policy(
    *,
    policy: Mapping[str, Any],
    received: NDArray[np.complex128],
    reference_bits: NDArray[np.int8],
    reference_symbols: NDArray[np.int64],
    received_hash: str,
    receiver_configuration: Mapping[str, Any],
    clocks: M9BClockOrigins,
    true_gain_for_evaluation: float,
) -> M9BPolicyOutput:
    kwargs = _receiver_kwargs(
        policy=policy,
        received=received,
        receiver_configuration=receiver_configuration,
        clocks=clocks,
    )
    if reference_bits.shape != (2 * reference_symbols.size,) or reference_symbols.shape != (
        received.size // 8,
    ):
        raise M9BExecutionBlocked("evaluation reference shapes do not match sequence dimensions")
    result = decode_reconstruction_conditional_sequence(**kwargs)
    count = int(reference_symbols.size)
    path = tuple(int(value) for value in result.decoder_result.hypothesis_ids)
    validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
    decoded_bits = np.asarray(result.decoder_result.decoded_bits, dtype=np.int8)
    decoded_symbols = decoded_path_symbol_indices(
        path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    if (
        decoded_bits.shape != (2 * count,)
        or decoded_symbols.shape != (count,)
        or len(path) != count
    ):
        raise ValueError("conditional decoder returned invalid bit/symbol/path dimensions")
    if result.candidate_metrics.shape != (count, 16) or not np.all(
        np.isfinite(result.candidate_metrics)
    ):
        raise FloatingPointError("conditional candidate metric matrix is invalid")
    final_state = result.final_estimator_state
    if not np.all(np.isfinite(final_state.fluctuating_iq)) or not np.all(
        np.isfinite(final_state.full_iq)
    ):
        raise FloatingPointError("conditional estimator returned non-finite final coefficients")
    if not np.isclose(float(np.sum(result.final_posterior)), 1.0, rtol=0.0, atol=1e-12):
        raise FloatingPointError("conditional final posterior is not normalized")
    sample_origin = clocks.absolute_sample_origin
    symbol_origin = clocks.absolute_symbol_origin
    tick_origin = clocks.estimator_time_index_origin
    for local, provenance in enumerate(result.metric_provenance):
        symbol = symbol_origin + local
        first = sample_origin + 8 * symbol
        if (
            provenance.absolute_symbol_index != symbol
            or provenance.estimator_time_index != tick_origin + local
            or provenance.sample_indices != tuple(range(first, first + 8))
            or provenance.prediction_cutoff_sample_index != first - 1
            or provenance.observation_cutoff_sample_index != first + 7
            or provenance.hypothesis_ids != tuple(range(16))
        ):
            raise ValueError("B4d metric provenance violates absolute clock/edge contract")
    counts = {
        "bit_errors": count_bit_errors(reference_bits, decoded_bits),
        "total_bits": int(reference_bits.size),
        "symbol_errors": count_symbol_errors(reference_symbols, decoded_symbols),
        "total_symbols": count,
    }
    full = np.asarray(final_state.full_iq, dtype=np.float64)
    fluctuating = np.asarray(final_state.fluctuating_iq, dtype=np.float64)
    anchor = np.asarray(policy["mu0"], dtype=np.float64)[None, :]
    if not np.allclose(fluctuating + anchor, full, rtol=0.0, atol=1e-12):
        raise FloatingPointError("full/fluctuating/anchor state decomposition failed")
    record = {
        "candidate_id": policy["candidate_id"],
        "alpha_prime": policy["alpha_prime"],
        "k_tilde": list(policy["k_tilde"]),
        "mu0": list(policy["mu0"]),
        "initial_fluctuating_iq": list(policy["initial_fluctuating_iq"]),
        "initial_full_iq": list(policy["initial_full_iq"]),
        "beta": float(policy["beta"]),
        "status": "complete_valid_output",
        "decoder_invocations": 1,
        "received_sha256": received_hash,
        "counts": counts,
        "decoded_information_bits": decoded_bits.tolist(),
        "decoded_symbol_indices": decoded_symbols.tolist(),
        "decoded_hypothesis_path": list(path),
        "decoder_path_cost": float(result.decoder_result.best_path_metric),
        "candidate_metrics_shape": list(result.candidate_metrics.shape),
        "final_posterior": result.final_posterior.tolist(),
        "metric_clock_provenance": [
            {
                "absolute_symbol_index": row.absolute_symbol_index,
                "estimator_time_index": row.estimator_time_index,
                "sample_indices": list(row.sample_indices),
                "prediction_cutoff_sample_index": row.prediction_cutoff_sample_index,
                "observation_cutoff_sample_index": row.observation_cutoff_sample_index,
                "hypothesis_ids": list(row.hypothesis_ids),
            }
            for row in result.metric_provenance
        ],
        "diagnostics": {
            "finite_final_state": True,
            "finite_candidate_metrics": True,
            "final_posterior_normalized": True,
            "final_posterior_sum": float(np.sum(result.final_posterior)),
            "initial_full_norm": float(np.linalg.norm(policy["initial_full_iq"])),
            "final_full_norm": float(np.linalg.norm(full)),
            "final_coefficient_error_norm_evaluation_only": float(
                np.linalg.norm(full - np.full_like(full, true_gain_for_evaluation))
            ),
            "per_symbol_coefficient_history": "unavailable from conditional decode result",
        },
    }
    return M9BPolicyOutput(record=record, result=result, receiver_kwargs=kwargs)


def run_real_integration_smoke(
    draft: Mapping[str, Any], receiver_configuration: Mapping[str, Any]
) -> dict[str, Any]:
    """Real B4d/B5b deterministic smoke; it creates no M9 sample or RNG stream."""
    from hf_tcm.receiver.reconstruction_candidate_metrics import (
        generate_reconstruction_candidate_metrics,
    )
    from hf_tcm.receiver.reconstruction_forward import APPROXIMATE_RECTANGULAR_8SPS

    design = validate_m9a_fixed_policy_study(draft)
    clocks = resolve_m9_clock_origins(receiver_configuration)
    bits = np.asarray([0, 1, 1, 0, 0, 0, 1, 1], dtype=np.int8)
    symbols = encode_reference_symbol_indices(
        bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    received = np.asarray(
        [complex((index - 15) / 90.0, ((index % 5) - 2) / 110.0) for index in range(32)],
        dtype=np.complex128,
    )
    received.setflags(write=False)
    received_hash = hashlib.sha256(received.tobytes()).hexdigest()
    outputs = [
        _decode_policy(
            policy={
                "candidate_id": policy.candidate_id,
                "alpha_prime": policy.alpha_prime,
                "k_tilde": list(policy.k_tilde),
                "mu0": list(policy.mu0),
                "initial_fluctuating_iq": list(policy.initial_fluctuating_iq),
                "initial_full_iq": list(policy.initial_full_iq),
                "beta": policy.beta,
            },
            received=received,
            reference_bits=bits,
            reference_symbols=symbols,
            received_hash=received_hash,
            receiver_configuration=receiver_configuration,
            clocks=clocks,
            true_gain_for_evaluation=0.75,
        )
        for policy in design.policies
    ]
    if len(outputs) != 2 or any(row.record["status"] != "complete_valid_output" for row in outputs):
        raise M9BExecutionBlocked("real deterministic M9 receiver smoke failed")
    first_b, first_anchor = outputs
    np.testing.assert_array_equal(
        first_b.result.candidate_metrics[0], first_anchor.result.candidate_metrics[0]
    )
    assert np.array_equal(
        first_b.receiver_kwargs["initial_estimator_state"].full_iq,
        first_anchor.receiver_kwargs["initial_estimator_state"].full_iq,
    )
    first_predictions = []
    first_metric_rows = []
    validated_receiver = validate_reconstructed_offline_config(receiver_configuration)
    for policy in design.policies:
        state = ReconstructionEstimatorState(
            [policy.initial_fluctuating_iq],
            [policy.initial_full_iq],
            clocks.estimator_time_index_origin,
        )
        candidate = generate_reconstruction_candidate_metrics(
            received=received[:8],
            absolute_sample_indices=np.arange(8, dtype=np.int64),
            received_start_sample=0,
            symbol_origin_sample=0,
            target_symbol_index=0,
            state=state,
            time_index=0,
            profile=ADR012_PROFILE,
            adr_profile=ADR012_PROFILE_ID,
            path_count=1,
            path_delays_samples=(0,),
            samples_per_symbol=8,
            iq_rule=ADR012_IQ_RULE,
            waveform_rule=ADR012_WAVEFORM_RULE,
            labeling_profile=str(validated_receiver["labeling"]["name"]),
            bit_order=tuple(validated_receiver["labeling"]["bit_order"]),
            timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
            symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
            edge_policy="zero_padding",
        )
        first_predictions.append(candidate.sample_predictions_iq)
        first_metric_rows.append(candidate.metrics)
    np.testing.assert_array_equal(first_predictions[0], first_predictions[1])
    np.testing.assert_array_equal(first_metric_rows[0], first_metric_rows[1])
    np.testing.assert_array_equal(first_metric_rows[0], first_b.result.candidate_metrics[0])
    assert first_b.record["candidate_metrics_shape"] == [4, 16]
    for output, policy in zip(outputs, design.policies, strict=True):
        assert output.record["counts"]["total_bits"] == 8
        assert output.record["counts"]["total_symbols"] == 4
        assert output.receiver_kwargs["beta"] == 0.7
        assert output.receiver_kwargs["initial_estimator_state"].fluctuating_iq.tolist() == [
            list(policy.initial_fluctuating_iq)
        ]
        assert output.receiver_kwargs["initial_estimator_state"].full_iq.tolist() == [
            list(policy.initial_full_iq)
        ]
        assert np.asarray(output.receiver_kwargs["mu0"]).tolist() == [list(policy.mu0)]
        assert output.result.final_posterior.shape == (16,)
        assert np.isclose(np.sum(output.result.final_posterior), 1.0, rtol=0.0, atol=1e-12)
        assert len(output.result.decoder_result.hypothesis_ids) == 4
        assert output.result.candidate_metrics.shape == (4, 16)
        for i, row in enumerate(output.result.metric_provenance):
            assert row.absolute_symbol_index == i
            assert row.estimator_time_index == i
            assert row.sample_indices == tuple(range(8 * i, 8 * i + 8))
            assert row.prediction_cutoff_sample_index == 8 * i - 1
            assert row.observation_cutoff_sample_index == 8 * i + 7
            assert row.hypothesis_ids == tuple(range(16))
        direct_kwargs = dict(output.receiver_kwargs)
        direct_kwargs["received"] = received
        direct = decode_reconstruction_conditional_sequence(**direct_kwargs)
        np.testing.assert_array_equal(
            direct.decoder_result.decoded_bits, output.result.decoder_result.decoded_bits
        )
        assert direct.decoder_result.hypothesis_ids == output.result.decoder_result.hypothesis_ids
        np.testing.assert_array_equal(direct.candidate_metrics, output.result.candidate_metrics)
        np.testing.assert_array_equal(
            direct.final_estimator_state.full_iq, output.result.final_estimator_state.full_iq
        )
    forbidden_receiver_inputs = {
        "reference_bits",
        "reference_symbols",
        "true_gain",
        "channel_truth",
        "ChannelTruth",
    }
    return {
        "status": "PASS",
        "fixture": "existing deterministic 4-symbol / 32-sample receiver fixture; no RNG",
        "experimental_sample_used": False,
        "orchestrator_decodes": 2,
        "direct_api_comparison_decodes": 2,
        "policy_ids": [row.candidate_id for row in design.policies],
        "received_sha256": received_hash,
        "candidate_metrics_shape": [4, 16],
        "initial_predictions_identical": True,
        "posterior_shape": [16],
        "clocks": clocks.as_dict(),
        "direct_api_equivalence": True,
        "receiver_arguments_exclude_truth": all(
            forbidden_receiver_inputs.isdisjoint(output.receiver_kwargs) for output in outputs
        ),
    }


def _checkpoint_path(directory: Path, run_id: str) -> Path:
    return directory / "checkpoints" / f"{run_id.rsplit(':', 1)[-1]}.json"


def _output_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "integrity_manifest.json"
    }


def _counts_from_policy(record: Mapping[str, Any]) -> ErrorCounts:
    counts = record["counts"]
    return ErrorCounts(
        bit_errors=int(counts["bit_errors"]),
        total_bits=int(counts["total_bits"]),
        symbol_errors=int(counts["symbol_errors"]),
        total_symbols=int(counts["total_symbols"]),
    )


def independent_verify(
    directory: str | Path,
    approved: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> dict[str, Any]:
    """Recount all errors from checkpoint reference and decoded arrays."""
    root = Path(directory)
    paths = sorted((root / "checkpoints").glob("run-*.json"))
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    planned = approved["run_manifest"]["runs"]
    policies = draft["policies"]
    expected_ids = [row["run_id"] for row in planned]
    if [row.get("run_id") for row in rows] != expected_ids[: len(rows)]:
        raise ValueError("M9b run IDs missing, duplicated, or out of order")
    accum = {policy["candidate_id"]: [0, 0, 0, 0, 0] for policy in policies}
    received_hashes: set[str] = set()
    total_calls = 0
    complete_runs = 0
    failure_count = 0
    failure_records: list[dict[str, Any]] = []
    paired_records: list[PairedRunCounts] = []
    for checkpoint, run in zip(rows, planned, strict=False):
        if checkpoint.get("run_index") != run["run_index"]:
            raise ValueError("M9b zero-based run index mismatch")
        if checkpoint.get("seed_provenance") != run["streams"]:
            normalized_provenance = copy.deepcopy(checkpoint.get("seed_provenance"))
            if isinstance(normalized_provenance, dict):
                for name in ("data", "noise"):
                    if name in normalized_provenance:
                        normalized_provenance[name]["initialized"] = False
            if normalized_provenance != run["streams"]:
                raise ValueError("M9b checkpoint seed provenance mismatch")
        if checkpoint.get("status") != "complete" or len(checkpoint.get("policies", [])) != 2:
            failure_count += 1
            failure_records.append(
                {
                    "run_id": checkpoint["run_id"],
                    "status": checkpoint.get("status"),
                    "detail": checkpoint.get("detail"),
                }
            )
            continue
        digest = checkpoint.get("received_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("M9b received hash missing/invalid")
        received_hashes.add(digest)
        reference_bits = np.asarray(
            checkpoint["evaluation_only"]["reference_information_bits"], dtype=np.int8
        )
        reference_symbols = np.asarray(
            checkpoint["evaluation_only"]["reference_symbol_indices"], dtype=np.int64
        )
        if reference_bits.shape != (512,) or reference_symbols.shape != (256,):
            raise ValueError("M9b saved reference vector shapes are invalid")
        if not np.array_equal(
            reference_symbols,
            encode_reference_symbol_indices(
                reference_bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            ),
        ):
            raise ValueError("M9b coded reference symbols do not match the M1 encoder")
        record_map = {record.get("candidate_id"): record for record in checkpoint["policies"]}
        if tuple(record_map) != tuple(policy["candidate_id"] for policy in policies):
            raise ValueError("M9b policy order or IDs mismatch")
        pair_counts: dict[str, ErrorCounts] = {}
        row_calls = 0
        for policy in policies:
            candidate_id = policy["candidate_id"]
            record = record_map[candidate_id]
            for field in (
                "alpha_prime",
                "k_tilde",
                "mu0",
                "initial_fluctuating_iq",
                "initial_full_iq",
                "beta",
            ):
                if record.get(field) != policy[field]:
                    raise ValueError(f"M9b policy {candidate_id} field {field} mismatch")
            if record.get("received_sha256") not in (None, digest):
                raise ValueError("M9b policies did not share one received realization")
            calls = int(record.get("decoder_invocations", 0))
            total_calls += calls
            row_calls += calls
            if record.get("status") != "complete_valid_output" or calls != 1:
                failure_count += 1
                failure_records.append(
                    {
                        "run_id": checkpoint["run_id"],
                        "candidate_id": candidate_id,
                        "status": record.get("status"),
                        "exception_type": record.get("exception_type"),
                        "detail": record.get("detail"),
                    }
                )
                continue
            if record.get("received_sha256") != digest:
                raise ValueError("valid M9b policy record lacks paired received hash")
            decoded_bits = np.asarray(record["decoded_information_bits"], dtype=np.int8)
            decoded_symbols = np.asarray(record["decoded_symbol_indices"], dtype=np.int64)
            path = tuple(int(x) for x in record["decoded_hypothesis_path"])
            if decoded_bits.shape != (512,) or decoded_symbols.shape != (256,) or len(path) != 256:
                raise ValueError("M9b decoded arrays/path have invalid dimensions")
            validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
            path_bits = np.asarray(
                [bit for edge in path for bit in HYPOTHESES[edge].input_bits], dtype=np.int8
            )
            path_symbols = decoded_path_symbol_indices(
                path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            )
            if not np.array_equal(decoded_bits, path_bits) or not np.array_equal(
                decoded_symbols, path_symbols
            ):
                raise ValueError("M9b decoded arrays do not match canonical decoded path")
            counted = ErrorCounts(
                bit_errors=count_bit_errors(reference_bits, decoded_bits),
                total_bits=512,
                symbol_errors=count_symbol_errors(reference_symbols, decoded_symbols),
                total_symbols=256,
            )
            if counted != _counts_from_policy(record):
                raise ValueError("M9b stored integer errors differ from independent array recount")
            diag = record["diagnostics"]
            if not all(
                (
                    diag["finite_final_state"],
                    diag["finite_candidate_metrics"],
                    diag["final_posterior_normalized"],
                )
            ):
                raise ValueError("M9b finite/normalization diagnostics failed")
            accum[candidate_id][0] += counted.bit_errors
            accum[candidate_id][1] += counted.total_bits
            accum[candidate_id][2] += counted.symbol_errors
            accum[candidate_id][3] += counted.total_symbols
            accum[candidate_id][4] += 1
            pair_counts[candidate_id] = counted
        if row_calls > 2:
            raise ValueError("M9b run contains unexpected duplicate decoder calls")
        if row_calls != 2:
            failure_count += 1
            failure_records.append(
                {
                    "run_id": checkpoint["run_id"],
                    "status": "decoder_call_count_mismatch",
                    "calls": row_calls,
                }
            )
            continue
        if len(pair_counts) != 2:
            failure_count += 1
            continue
        paired_records.append(
            PairedRunCounts(
                run_id=checkpoint["run_id"],
                b_counts=pair_counts["historical_frozen_B"],
                c_counts=pair_counts["anch_a085_k025"],
            )
        )
        complete_runs += 1
    all_complete = len(rows) == 100 and complete_runs == 100 and total_calls == 200
    pooled = {}
    for policy in policies:
        key = policy["candidate_id"]
        bit_errors, total_bits, symbol_errors, total_symbols, valid = accum[key]
        pooled[key] = {
            "bit_errors": bit_errors,
            "total_bits": total_bits,
            "ber": bit_errors / total_bits if total_bits else None,
            "symbol_errors": symbol_errors,
            "total_symbols": total_symbols,
            "ser": symbol_errors / total_symbols if total_symbols else None,
            "valid_records": valid,
            "eligible": valid == 100,
        }
    complete_inference = all_complete and len(received_hashes) == 100 and failure_count == 0
    if complete_inference:
        b = pooled["historical_frozen_B"]
        anchored = pooled["anch_a085_k025"]
        delta_ber = (anchored["bit_errors"] - b["bit_errors"]) / 51200
        delta_ser = (anchored["symbol_errors"] - b["symbol_errors"]) / 25600
        primary_counts = {
            "ber_B": b["ber"],
            "ber_anchored": anchored["ber"],
            "delta_ber": delta_ber,
            "ser_B": b["ser"],
            "ser_anchored": anchored["ser"],
            "delta_ser": delta_ser,
        }
    else:
        primary_counts = None
    return {
        "status": "M9_EVALUATION_COMPLETE_VERIFIED"
        if complete_inference
        else "M9_INCOMPLETE_OR_BLOCKED",
        "run_count": len(rows),
        "unique_run_count": len({row.get("run_id") for row in rows}),
        "unique_received_hash_count": len(received_hashes),
        "complete_paired_runs": complete_runs,
        "policy_record_count": sum(len(row.get("policies", [])) for row in rows),
        "decoder_invocations": total_calls,
        "decoder_invocations_expected": 200,
        "failure_count": failure_count,
        "failures": sum(
            1
            for row in rows
            for record in row.get("policies", [])
            if record.get("status") != "complete_valid_output"
        ),
        "failure_records": failure_records,
        "pooled_policy_counts": pooled,
        "paired_estimands": primary_counts,
        "paired_run_counts": paired_records,
    }


def _independent_bootstrap_oracle(
    records: tuple[PairedRunCounts, ...], bootstrap_seed: int, replicates: int = 2000
) -> dict[str, Any]:
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    indices = rng.integers(0, len(records), size=(replicates, len(records)), dtype=np.int64)
    values = np.empty((replicates, 2), dtype=np.float64)
    for b, selected in enumerate(indices):
        b_bits = a_bits = b_symbols = a_symbols = 0
        for raw_index in selected:
            record = records[int(raw_index)]
            b_bits += record.b_counts.bit_errors
            a_bits += record.c_counts.bit_errors
            b_symbols += record.b_counts.symbol_errors
            a_symbols += record.c_counts.symbol_errors
        values[b, 0] = (a_bits - b_bits) / 51200
        values[b, 1] = (a_symbols - b_symbols) / 25600
    bounds = np.quantile(values, [0.025, 0.975], axis=0, method="linear")
    return {
        "indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
        "delta_ber_ci": [float(bounds[0, 0]), float(bounds[1, 0])],
        "delta_ser_ci": [float(bounds[0, 1]), float(bounds[1, 1])],
    }


def execute_m9b(
    *,
    approved_config_path: str | Path = APPROVED_PATH,
    draft_path: str | Path = DRAFT_PATH,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run only the approved 100-sequence M9 evaluation partition."""
    approved_path = Path(approved_config_path)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    validate_approved_m9b(approved, draft=draft, config_path=approved_path, verify_file=True)
    out = Path(output_root) if output_root is not None else OUTPUT_PATH
    if out.resolve() != OUTPUT_PATH.resolve():
        raise M9BExecutionBlocked("M9b output root differs from frozen namespace")
    if out.exists() and any(out.iterdir()):
        raise M9BExecutionBlocked("M9b output namespace is nonempty; resume is not implicit")
    if out.exists():
        raise M9BExecutionBlocked("M9b output namespace already exists; no overwrite")

    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    smoke = run_real_integration_smoke(draft, receiver_config)
    if smoke.get("status") != "PASS":
        raise M9BExecutionBlocked("real receiver integration smoke failed before M9 RNG")
    baseline = _historical_baseline()
    if baseline != approved["historical_integrity_baseline"]:
        raise M9BExecutionBlocked("historical integrity changed after approval")

    out.mkdir(parents=True, exist_ok=False)
    config_hash = _sha256_file(approved_path)
    _atomic_json(out / "approved_config_snapshot.json", approved, exclusive=True)
    _atomic_json(
        out / "approved_config.sha256",
        {
            "sha256": config_hash,
            "sidecar": str(Path(f"{approved_path}.sha256").relative_to(ROOT).as_posix()),
        },
        exclusive=True,
    )
    _atomic_json(
        out / "manifest.json",
        {
            "schema_version": SCHEMA,
            "experiment_id": draft["experiment_id"],
            "approved_config_sha256": config_hash,
            "runtime_source_fingerprint": approved["runtime_provenance"]["source_file_manifest"],
            "run_manifest": approved["run_manifest"],
            "smoke_test": smoke,
            "other_partition_executed": False,
        },
        exclusive=True,
    )

    conditional_module = __import__(
        "hf_tcm.receiver.reconstruction_conditional_decode",
        fromlist=["decode_reconstruction_viterbi"],
    )
    original_decoder = conditional_module.decode_reconstruction_viterbi
    decoder_calls = 0

    def counted_decoder(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoder_calls
        decoder_calls += 1
        return original_decoder(*args, **kwargs)

    conditional_module.decode_reconstruction_viterbi = counted_decoder
    start = time.perf_counter()
    completed = 0
    failures = 0
    rss_peak: int | None = None
    rss_unverified = False
    try:
        for planned in approved["run_manifest"]["runs"]:
            elapsed = time.perf_counter() - start
            if elapsed >= WALL_CLOCK_BUDGET_SECONDS:
                break
            rss = _process_rss_windows(os.getpid())
            if rss is None:
                rss_unverified = True
            else:
                rss_peak = max(rss_peak or 0, int(rss))
                if rss >= RSS_MONITORING_BUDGET_BYTES:
                    break
            checkpoint_path = _checkpoint_path(out, planned["run_id"])
            if checkpoint_path.exists():
                raise M9BExecutionBlocked("M9b checkpoint already exists; no implicit resume")
            seeds = planned["streams"]
            try:
                data_rng = np.random.Generator(np.random.PCG64(seeds["data"]["derived_seed"]))
                bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
                received, reference_symbols, received_hash = _prepare_received(
                    bits,
                    gain=0.75,
                    noise_seed=int(seeds["noise"]["derived_seed"]),
                    variance=0.7115124735378853,
                    stream_id=f"M9b:EVALUATION:{planned['run_id']}:noise",
                )
            except Exception as exc:
                failure = {
                    "schema_version": SCHEMA,
                    "run_id": planned["run_id"],
                    "run_index": planned["run_index"],
                    "status": "received_generation_failure",
                    "decoder_invocations": 0,
                    "seed_provenance": seeds,
                    "exception_type": type(exc).__name__,
                    "detail": str(exc),
                }
                _atomic_json(checkpoint_path, failure, exclusive=True)
                failures += 1
                break
            actual_streams = copy.deepcopy(seeds)
            actual_streams["data"]["initialized"] = True
            actual_streams["noise"]["initialized"] = True
            records: list[dict[str, Any]] = []
            calls_before_run = decoder_calls
            for policy in draft["policies"]:
                calls_before_policy = decoder_calls
                try:
                    output = _decode_policy(
                        policy=policy,
                        received=received,
                        reference_bits=bits,
                        reference_symbols=reference_symbols,
                        received_hash=received_hash,
                        receiver_configuration=receiver_config,
                        clocks=clocks,
                        true_gain_for_evaluation=0.75,
                    )
                    calls = decoder_calls - calls_before_policy
                    if calls != 1:
                        raise RuntimeError(f"expected one decoder invocation, got {calls}")
                    record = dict(output.record)
                    record["decoder_invocations"] = calls
                    records.append(record)
                except Exception as exc:
                    calls = decoder_calls - calls_before_policy
                    policy_failure = {
                        "candidate_id": policy["candidate_id"],
                        "alpha_prime": policy["alpha_prime"],
                        "k_tilde": policy["k_tilde"],
                        "mu0": policy["mu0"],
                        "initial_fluctuating_iq": policy["initial_fluctuating_iq"],
                        "initial_full_iq": policy["initial_full_iq"],
                        "beta": policy["beta"],
                        "status": "numerical_or_decoder_failure",
                        "decoder_invocations": calls,
                        "received_sha256": received_hash,
                        "exception_type": type(exc).__name__,
                        "detail": str(exc),
                    }
                    records.append(policy_failure)
                    failures += 1
            checkpoint = {
                "schema_version": SCHEMA,
                "run_id": planned["run_id"],
                "run_index": planned["run_index"],
                "status": "complete" if len(records) == 2 else "incomplete",
                "received_sha256": received_hash,
                "approved_config_sha256": config_hash,
                "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
                    "runtime_source_fingerprint_sha256"
                ],
                "seed_provenance": actual_streams,
                "clock_origins": clocks.as_dict(),
                "decoder_invocations": decoder_calls - calls_before_run,
                "evaluation_only": {
                    "reference_information_bits": bits.astype(int).tolist(),
                    "reference_symbol_indices": reference_symbols.astype(int).tolist(),
                    "real_channel_gain": 0.75,
                    "sigma_squared": 0.7115124735378853,
                },
                "policies": records,
            }
            _atomic_json(checkpoint_path, checkpoint, exclusive=True)
            completed += 1
    finally:
        conditional_module.decode_reconstruction_viterbi = original_decoder
    eval_elapsed = time.perf_counter() - start

    verification = independent_verify(out, approved, draft)
    if verification["status"] != "M9_EVALUATION_COMPLETE_VERIFIED":
        status = "M9_INCOMPLETE_OR_BLOCKED"
        bootstrap_record = None
    else:
        run_counts = tuple(verification["paired_run_counts"])
        bootstrap_seed = int(approved["run_manifest"]["bootstrap"]["derived_seed"])
        bootstrap_start = time.perf_counter()
        bootstrap = paired_cluster_bootstrap(
            run_counts,
            bootstrap_replicates=2000,
            confidence_level=0.95,
            bootstrap_seed=bootstrap_seed,
        )
        oracle = _independent_bootstrap_oracle(run_counts, bootstrap_seed)
        api_delta_ber = bootstrap.interval("delta_ber")
        api_delta_ser = bootstrap.interval("delta_ser")
        if (
            not np.allclose(
                [api_delta_ber.lower, api_delta_ber.upper],
                oracle["delta_ber_ci"],
                rtol=0.0,
                atol=1e-15,
            )
            or not np.allclose(
                [api_delta_ser.lower, api_delta_ser.upper],
                oracle["delta_ser_ci"],
                rtol=0.0,
                atol=1e-15,
            )
            or hashlib.sha256(bootstrap.resample_indices.tobytes()).hexdigest()
            != oracle["indices_sha256"]
        ):
            verification = {
                **verification,
                "status": "M9_VERIFICATION_FAILED",
                "detail": "bootstrap oracle mismatch",
            }
            status = "M9_VERIFICATION_FAILED"
            bootstrap_record = None
        else:
            status = "M9_EVALUATION_COMPLETE_VERIFIED"
            bootstrap_record = {
                "method": "ADR-014 paired cluster bootstrap",
                "cluster_unit": "one complete independent coded sequence",
                "replicates": 2000,
                "confidence_level": 0.95,
                "interval": "percentile",
                "quantile_method": "numpy.quantile(method='linear')",
                "bit_generator": "PCG64",
                "bootstrap_seed_provenance": approved["run_manifest"]["bootstrap"],
                "delta_ber_ci": [api_delta_ber.lower, api_delta_ber.upper],
                "delta_ser_ci": [api_delta_ser.lower, api_delta_ser.upper],
                "independent_scalar_oracle": oracle,
                "warning_flags": list(bootstrap.warning_flags),
                "bootstrap_wall_clock_seconds": time.perf_counter() - bootstrap_start,
            }
            verification["bootstrap"] = bootstrap_record
    historical_after = _historical_baseline()
    history_ok = historical_after == approved["historical_integrity_baseline"]
    if not history_ok:
        status = "M9_VERIFICATION_FAILED"
        verification = {
            **verification,
            "status": status,
            "detail": "historical artifact hashes changed",
        }
    summary = {
        "schema_version": SCHEMA,
        "classification": CLASSIFICATION,
        "status": status,
        "approved_config_sha256": config_hash,
        "m9a_draft_sha256": EXPECTED_DRAFT_SHA256,
        "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
            "runtime_source_fingerprint_sha256"
        ],
        "planned_runs": 100,
        "completed_runs": completed,
        "policy_records": sum(
            len(json.loads(path.read_text(encoding="utf-8")).get("policies", []))
            for path in sorted((out / "checkpoints").glob("run-*.json"))
        ),
        "decoder_invocations": decoder_calls,
        "received_unique_hashes": verification.get("unique_received_hash_count", 0),
        "failure_count": failures,
        "pooled_policy_counts": verification.get("pooled_policy_counts"),
        "paired_estimands": verification.get("paired_estimands"),
        "bootstrap": bootstrap_record,
        "independent_verification": {
            key: value for key, value in verification.items() if key != "paired_run_counts"
        },
        "resource": {
            "evaluation_wall_clock_seconds": eval_elapsed,
            "completed_runs": completed,
            "decoder_invocations": decoder_calls,
            "rss_peak_bytes_observed": rss_peak,
            "rss_status": "RSS_UNVERIFIED"
            if rss_unverified or rss_peak is None
            else "periodic_monitor_observed",
            "process_count": 1,
            "multiprocessing": False,
            "wall_clock_budget_seconds": WALL_CLOCK_BUDGET_SECONDS,
            "rss_monitoring_budget_bytes": RSS_MONITORING_BUDGET_BYTES,
        },
        "historical_integrity": {
            "before": approved["historical_integrity_baseline"],
            "after": historical_after,
            "unchanged": history_ok,
        },
        "other_partition_executed": False,
    }
    _atomic_json(
        out / "bootstrap_summary.json",
        bootstrap_record or {"status": "not_computed_incomplete"},
        exclusive=True,
    )
    _atomic_json(
        out / "independent_verification.json", summary["independent_verification"], exclusive=True
    )
    _atomic_json(out / "summary.json", summary, exclusive=True)
    _atomic_json(out / "integrity_manifest.json", _output_hashes(out), exclusive=True)
    return summary
