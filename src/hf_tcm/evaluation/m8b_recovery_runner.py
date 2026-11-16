"""Controlled recovery of the same M8b TRAIN partition after orchestration failure."""

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
from hf_tcm.evaluation.m5i_confirmatory_design import load_m5i_confirmatory_design
from hf_tcm.evaluation.m7b_train_runner import (
    _atomic_json,
    _historical_tree_hash,
    _sha256_file,
    historical_integrity_baseline,
)
from hf_tcm.evaluation.m8b_train_runner import (
    DEFAULT_DRAFT,
    ROOT,
    _m8b_manifest,
    _output_file_hashes,
    _prepare_received,
    _sha256_value,
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

ORIGINAL_APPROVED = ROOT / "configs/m8b_train_approved_run.json"
ORIGINAL_OUTPUT = ROOT / "outputs/m8b_train/m8_anchored_reconstructed_adaptation_v1"
RECOVERY_APPROVED = ROOT / "configs/m8b_train_recovery_approved_run.json"
RECOVERY_OUTPUT = (
    ROOT / "outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2"
)
RECOVERY_ATTEMPT_ID = "m8_anchored_reconstructed_adaptation_v1_attempt2"
RECOVERY_SCHEMA = "m8b.train-recovery.v1"
RECOVERY_CLASSIFICATION = (
    "controlled M8b TRAIN recovery attempt, exploratory policy selection only, "
    "NOT independent validation, NOT confirmatory performance evidence"
)
_RECOVERY_RUNTIME_FIELDS = {
    "authorization_provenance",
    "recovery_provenance",
    "execution_limits",
    "runtime_provenance",
    "output",
    "run_manifest",
    "historical_integrity_baseline",
}
_EXPECTED_ORIGINAL_CONFIG_SHA256 = (
    "a081e98bcbdf6aab94175fe410f5161e06e72d24ad99070147172088c7945e95"
)
_EXPECTED_ORIGINAL_RUNTIME_SHA256 = (
    "a88db99ca90814ec610f135446a1bd03c6f5473f327c010337675a14979a9475"
)
_EXPECTED_ORIGINAL_RUNNER_SHA256 = (
    "e93786aa7fb36cdbc60c9e1cfc787bfd12efb5f97518ec5b2aa276c61c706f5f"
)
_RECOVERY_SOURCE_PATHS = (
    "src/hf_tcm/evaluation/m8a_anchored_study_design.py",
    "src/hf_tcm/evaluation/m8b_train_runner.py",
    "src/hf_tcm/evaluation/m8b_recovery_runner.py",
    "src/hf_tcm/evaluation/m7b_train_runner.py",
    "src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/evaluation/matched_m2_b5_experiment.py",
    "configs/m8a_anchored_study_draft.json",
    "configs/m8b_train_approved_run.json",
    "configs/m5i_confirmatory_design_draft.json",
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


class M8BRecoveryBlocked(RuntimeError):
    """The recovery authorization or a replay/preflight integrity gate failed."""


def _source_fingerprint() -> dict[str, str]:
    fingerprint = {}
    for relative in _RECOVERY_SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise M8BRecoveryBlocked(f"recovery source is missing: {relative}")
        fingerprint[relative] = _sha256_file(path)
    return fingerprint


def _git_info() -> dict[str, str | None]:
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


def resolve_clock_origins(
    draft: Mapping[str, Any], receiver_configuration: Mapping[str, Any]
) -> dict[str, Any]:
    """Resolve clocks from M8a's accepted receiver config and fresh-sequence API contract.

    M8a did not define a ``clock_origins`` key. Sample origin and estimator
    tick are read from the frozen M5i reconstruction configuration. B4d's
    independent-sequence contract requires first_symbol_index to equal the
    sequence symbol origin; each M8 run is a new sequence, so that origin is 0.
    """
    if draft.get("study_id") != "m8_anchored_reconstructed_adaptation_v1":
        raise M8BRecoveryBlocked("clock resolver requires the exact M8a study")
    validated = validate_reconstructed_offline_config(receiver_configuration)
    timebase = validated["timebase"]
    estimator = validated["estimator"]
    sample_origin = timebase.get("symbol_origin_sample")
    estimator_origin = estimator.get("initial_time_index")
    if sample_origin != 0 or estimator_origin != 0:
        raise M8BRecoveryBlocked("M8a TRAIN clocks require accepted zero sample/tick origins")
    return {
        "absolute_sample_origin": int(sample_origin),
        "absolute_symbol_origin": 0,
        "estimator_time_index_origin": int(estimator_origin),
        "provenance": {
            "sample_origin": "M5i accepted reconstruction_configuration.timebase.symbol_origin_sample",
            "symbol_origin": "B4d new_independent_sequence; first_symbol_index equals sequence_origin_symbol_index; fresh sequence begins at 0",
            "estimator_tick_origin": "M5i accepted reconstruction_configuration.estimator.initial_time_index",
            "m8a_explicit_clock_origins_field": False,
        },
    }


def _load_design() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    draft = json.loads(DEFAULT_DRAFT.read_text(encoding="utf-8"))
    original_approved = json.loads(ORIGINAL_APPROVED.read_text(encoding="utf-8"))
    receiver_configuration = load_m5i_confirmatory_design(
        ROOT / "configs/m5i_confirmatory_design_draft.json"
    ).as_dict()["reconstruction_configuration"]
    return draft, original_approved, receiver_configuration


def _original_attempt_integrity(
    draft: Mapping[str, Any], original_approved: Mapping[str, Any]
) -> dict[str, Any]:
    if original_approved.get("execution_scope") != "m8b_train_only":
        raise M8BRecoveryBlocked("original failed attempt has unexpected authorization scope")
    if original_approved.get("runtime_provenance", {}).get("m8a_draft_file_sha256") != _sha256_file(
        DEFAULT_DRAFT
    ):
        raise M8BRecoveryBlocked(
            "original approved config does not reference the current M8a draft"
        )
    original_digest = _sha256_file(ORIGINAL_APPROVED)
    if original_digest != _EXPECTED_ORIGINAL_CONFIG_SHA256:
        raise M8BRecoveryBlocked(
            "original M8b approved config hash differs from recovery authorization"
        )
    if original_approved.get("runtime_provenance", {}).get("code_fingerprint_sha256") != (
        _EXPECTED_ORIGINAL_RUNTIME_SHA256
    ):
        raise M8BRecoveryBlocked(
            "original M8b runtime fingerprint differs from recovery authorization"
        )
    if (
        original_approved.get("runtime_provenance", {})
        .get("code_fingerprint", {})
        .get("src/hf_tcm/evaluation/m8b_train_runner.py")
        != _EXPECTED_ORIGINAL_RUNNER_SHA256
    ):
        raise M8BRecoveryBlocked(
            "original M8b runner fingerprint differs from recovery authorization"
        )
    checkpoints_dir = ORIGINAL_OUTPUT / "checkpoints"
    old_rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(checkpoints_dir.glob("run-*.json"))
    ]
    expected_runs = original_approved["run_manifest"]["runs"]
    expected_ids = [row["run_id"] for row in expected_runs]
    if len(old_rows) != 40 or [row.get("run_id") for row in old_rows] != expected_ids:
        raise M8BRecoveryBlocked("original attempt does not contain the fixed 40 TRAIN run IDs")
    for row, expected in zip(old_rows, expected_runs, strict=True):
        if (
            row.get("run_index") != expected["run_index"]
            or row.get("seed_provenance") != expected["streams"]
        ):
            raise M8BRecoveryBlocked(
                "original failed checkpoints do not preserve the approved seed derivation"
            )
    if len({row.get("received_sha256") for row in old_rows}) != 40:
        raise M8BRecoveryBlocked("original attempt received hashes are not unique")
    if any(
        row.get("decoder_invocations") != 0
        or row.get("status") != "complete"
        or len(row.get("policies", [])) != 8
        or any(
            policy.get("status") != "numerical_or_decoder_failure"
            or policy.get("exception_type") != "KeyError"
            or policy.get("detail") != "'clock_origins'"
            or policy.get("decoder_invocations") != 0
            for policy in row["policies"]
        )
        for row in old_rows
    ):
        raise M8BRecoveryBlocked("original output is not the documented zero-decode clock failure")
    old_summary = json.loads((ORIGINAL_OUTPUT / "summary.json").read_text(encoding="utf-8"))
    if (
        old_summary.get("status") != "TRAIN_INCOMPLETE_OR_BLOCKED"
        or old_summary.get("decoder_invocations") != 0
        or old_summary.get("policy_records") != 320
    ):
        raise M8BRecoveryBlocked(
            "original attempt summary does not match the authorized recovery basis"
        )
    integrity = json.loads(
        (ORIGINAL_OUTPUT / "integrity_manifest.json").read_text(encoding="utf-8")
    )
    if integrity != _output_file_hashes(ORIGINAL_OUTPUT):
        raise M8BRecoveryBlocked("original failed output integrity manifest does not verify")
    return {
        "original_attempt_id": str(draft["study_id"]),
        "original_approved_config_sha256": original_digest,
        "original_runtime_fingerprint_sha256": original_approved["runtime_provenance"][
            "code_fingerprint_sha256"
        ],
        "original_runner_sha256": original_approved["runtime_provenance"]["code_fingerprint"][
            "src/hf_tcm/evaluation/m8b_train_runner.py"
        ],
        "original_output_tree": _historical_tree_hash(ORIGINAL_OUTPUT),
        "original_received_hashes": {row["run_id"]: row["received_sha256"] for row in old_rows},
        "original_failure_status": "TRAIN_INCOMPLETE_OR_BLOCKED",
        "original_policy_failures": 320,
        "original_decoder_calls": 0,
    }


def _recovery_historical_baseline() -> dict[str, Any]:
    baseline = historical_integrity_baseline()
    baseline.update(
        {
            "M7b": _historical_tree_hash(ROOT / "outputs/m7b_train"),
            "M8a_draft": _historical_tree_hash(DEFAULT_DRAFT),
            "M8a_sidecar": _historical_tree_hash(Path(f"{DEFAULT_DRAFT}.sha256")),
            "M8b_original_approved": _historical_tree_hash(ORIGINAL_APPROVED),
            "M8b_original_approved_sidecar": _historical_tree_hash(
                Path(f"{ORIGINAL_APPROVED}.sha256")
            ),
            "M8b_original_failed_output": _historical_tree_hash(ORIGINAL_OUTPUT),
        }
    )
    return baseline


def _recovery_manifest(original_approved: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(original_approved["run_manifest"])


def create_approved_recovery_config(
    *,
    output_config_path: str | Path = RECOVERY_APPROVED,
    output_directory: str = "outputs/m8b_train_recovery/m8_anchored_reconstructed_adaptation_v1_attempt2",
) -> dict[str, Any]:
    """Freeze a new recovery-only authorization; no RNG is initialized here."""
    draft, original, receiver_config = _load_design()
    from hf_tcm.evaluation.m8a_anchored_study_design import validate_m8a_anchored_study

    validate_m8a_anchored_study(draft)
    original_info = _original_attempt_integrity(draft, original)
    manifest = _recovery_manifest(original)
    if manifest != _m8b_manifest(draft):
        raise M8BRecoveryBlocked("original TRAIN IDs/seeds differ from M8a derivation")
    clocks = resolve_clock_origins(draft, receiver_config)
    approved = copy.deepcopy(draft)
    approved.update(
        {
            "design_status": "approved_training_recovery",
            "execution_authorized": True,
            "execution_scope": "m8b_train_recovery_only",
        }
    )
    approved["authorization_provenance"] = {
        "explicit_user_authorization": "explicit user authorization through this M8b-recovery instruction",
        "scope": "same M8b TRAIN partition recovery only; validation/final prohibited",
    }
    approved["recovery_provenance"] = {
        "recovery_attempt_id": RECOVERY_ATTEMPT_ID,
        **original_info,
        "m8a_draft_sha256": _sha256_file(DEFAULT_DRAFT),
        "clock_origins": clocks,
        "technical_reexecution_rationale": "original attempt produced no decoder result; exact same seeds/IDs are permitted by explicit recovery authorization",
        "scientific_design_mutated": False,
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
    fingerprint = _source_fingerprint()
    approved["runtime_provenance"] = {
        "current_source_fingerprint": fingerprint,
        "current_source_fingerprint_sha256": _sha256_value(fingerprint),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "prng": "numpy.random.PCG64",
        "git": _git_info(),
        "receiver_configuration_source": "accepted M5i reconstructed_offline receiver configuration",
        "receiver_configuration_sha256": _sha256_value(receiver_config),
        "receiver_configuration": receiver_config,
        "output_schema": RECOVERY_SCHEMA,
    }
    approved["output"] = {
        "experiment_id": RECOVERY_ATTEMPT_ID,
        "namespace": output_directory,
        "schema_version": RECOVERY_SCHEMA,
        "atomic_checkpoint_per_sequence": True,
    }
    approved["run_manifest"] = manifest
    approved["historical_integrity_baseline"] = _recovery_historical_baseline()
    target = Path(output_config_path)
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


def _strip_recovery_runtime(approved: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(value)
        for key, value in approved.items()
        if key not in _RECOVERY_RUNTIME_FIELDS
    }
    result.update(design_status="proposed", execution_authorized=False, execution_scope="none")
    return result


def validate_recovery_config(
    approved: object,
    *,
    config_path: str | Path | None = None,
    verify_file: bool = True,
) -> dict[str, Any]:
    """Block before any RNG/receiver callback unless recovery snapshot is exact."""
    draft, original, receiver_config = _load_design()
    from hf_tcm.evaluation.m8a_anchored_study_design import validate_m8a_anchored_study

    validate_m8a_anchored_study(draft)
    if not isinstance(approved, Mapping) or (
        approved.get("design_status") != "approved_training_recovery"
        or approved.get("execution_authorized") is not True
        or approved.get("execution_scope") != "m8b_train_recovery_only"
    ):
        raise M8BRecoveryBlocked("M8b recovery authorization scope mismatch")
    if approved.get("authorization_provenance", {}).get("explicit_user_authorization") != (
        "explicit user authorization through this M8b-recovery instruction"
    ):
        raise M8BRecoveryBlocked("recovery authorization provenance mismatch")
    if _strip_recovery_runtime(approved) != draft:
        raise M8BRecoveryBlocked("recovery config scientific fields differ from exact M8a draft")
    recovery = approved.get("recovery_provenance")
    original_info = _original_attempt_integrity(draft, original)
    if not isinstance(recovery, Mapping):
        raise M8BRecoveryBlocked("recovery provenance missing")
    for key, expected in original_info.items():
        if recovery.get(key) != expected:
            raise M8BRecoveryBlocked(f"original attempt provenance mismatch: {key}")
    if recovery.get("m8a_draft_sha256") != _sha256_file(DEFAULT_DRAFT):
        raise M8BRecoveryBlocked("M8a draft hash differs from approved recovery")
    clocks = resolve_clock_origins(draft, receiver_config)
    if recovery.get("clock_origins") != clocks:
        raise M8BRecoveryBlocked("resolved clock provenance differs from B4d contracts")
    fingerprint = approved["runtime_provenance"].get("current_source_fingerprint")
    if fingerprint != _source_fingerprint() or approved["runtime_provenance"].get(
        "current_source_fingerprint_sha256"
    ) != _sha256_value(fingerprint):
        raise M8BRecoveryBlocked("recovery runtime fingerprint changed")
    if (
        approved["runtime_provenance"].get("python_version") != platform.python_version()
        or approved["runtime_provenance"].get("numpy_version") != np.__version__
    ):
        raise M8BRecoveryBlocked("recovery runtime version differs from approved snapshot")
    if approved.get("run_manifest") != original["run_manifest"] or approved.get(
        "run_manifest"
    ) != _m8b_manifest(draft):
        raise M8BRecoveryBlocked("recovery IDs/seeds are not byte-identical to original TRAIN")
    if approved.get("output", {}).get("namespace") != RECOVERY_OUTPUT.relative_to(ROOT).as_posix():
        raise M8BRecoveryBlocked("recovery output namespace differs from isolated attempt-2 path")
    if approved.get("execution_limits") != {
        "wall_clock_limit_seconds": 900,
        "rss_monitoring_budget_bytes": 1610612736,
        "rss_limit_semantics": "periodic process RSS monitoring, not a hard OS process limit",
        "worker_processes": 1,
        "multiprocessing": False,
        "stop_at_sequence_boundary_on_budget": True,
        "atomic_checkpoint_per_sequence": True,
    }:
        raise M8BRecoveryBlocked("recovery resource budget differs from authorization")
    if approved.get("historical_integrity_baseline") != _recovery_historical_baseline():
        raise M8BRecoveryBlocked("historical M5/M6/M7/M8 artifacts changed")
    if verify_file:
        if config_path is None:
            raise M8BRecoveryBlocked("recovery config path required for file verification")
        path = Path(config_path)
        sidecar = Path(f"{path}.sha256")
        if not path.is_file() or not sidecar.is_file():
            raise M8BRecoveryBlocked("recovery config or sidecar missing")
        if sidecar.read_text(encoding="ascii").strip() != _sha256_file(path):
            raise M8BRecoveryBlocked("recovery config checksum mismatch")
        if json.loads(path.read_text(encoding="utf-8")) != approved:
            raise M8BRecoveryBlocked("loaded recovery config differs from frozen file")
    return dict(approved)


def guard_recovery_execution(
    approved: object,
    *,
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> object:
    validate_recovery_config(approved, verify_file=False)
    if any(name not in callbacks or not callable(callbacks[name]) for name in ("rng", "receiver")):
        raise M8BRecoveryBlocked("RNG and receiver guard spies are required")
    return executor()


def _policy_call(
    *,
    policy: Mapping[str, Any],
    received: NDArray[np.complex128],
    reference_bits: NDArray[np.int8],
    reference_symbols: NDArray[np.int64],
    received_hash: str,
    receiver_configuration: Mapping[str, Any],
    clock_origins: Mapping[str, Any],
    true_gain_for_evaluation: float,
) -> dict[str, Any]:
    """Perform exactly one existing conditional B4d/B5b decode for an arm."""
    receiver = validate_reconstructed_offline_config(receiver_configuration)
    timebase = receiver["timebase"]
    labeling = receiver["labeling"]
    count = int(reference_symbols.size)
    sample_origin = int(clock_origins["absolute_sample_origin"])
    symbol_origin = int(clock_origins["absolute_symbol_origin"])
    tick_origin = int(clock_origins["estimator_time_index_origin"])
    if (
        count < 1
        or reference_bits.shape != (2 * count,)
        or received.shape != (8 * count,)
        or not np.all(np.isfinite(received))
        or received.flags.writeable
    ):
        raise M8BRecoveryBlocked(
            "policy call requires a finite immutable 8-sample-per-symbol buffer"
        )
    state = ReconstructionEstimatorState(
        [policy["initial_fluctuating_iq"]],
        [policy["initial_full_iq"]],
        tick_origin,
    )
    sample_start = sample_origin + 8 * symbol_origin
    sample_indices = np.arange(sample_start, sample_start + received.size, dtype=np.int64)
    result = decode_reconstruction_conditional_sequence(
        received=received,
        absolute_sample_indices=sample_indices,
        received_start_sample=sample_start,
        symbol_origin_sample=sample_origin,
        first_symbol_index=symbol_origin,
        sequence_origin_symbol_index=symbol_origin,
        symbol_count=count,
        symbol_indices=tuple(range(symbol_origin, symbol_origin + count)),
        initial_estimator_state=state,
        initial_estimator_time_index=tick_origin,
        initial_encoder_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        beta=float(receiver["likelihood"]["beta"]),
        alpha_prime=float(policy["alpha_prime"]),
        k_tilde=np.asarray([policy["k_tilde"]], dtype=np.float64),
        mu0=np.asarray([policy["mu0"]], dtype=np.float64),
        profile=ADR012_PROFILE,
        adr_profile=ADR012_PROFILE_ID,
        path_count=1,
        path_delays_samples=(0,),
        samples_per_symbol=ADR012_SAMPLES_PER_SYMBOL,
        iq_rule=ADR012_IQ_RULE,
        waveform_rule=ADR012_WAVEFORM_RULE,
        labeling_profile=str(labeling["name"]),
        bit_order=tuple(labeling["bit_order"]),
        timebase_profile=str(timebase["name"]),
        symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
        edge_policy="zero_padding",
    )
    path = tuple(int(value) for value in result.decoder_result.hypothesis_ids)
    validate_hypothesis_edge_path(path, initial_state=INITIAL_STATE)
    decoded_bits = np.asarray(result.decoder_result.decoded_bits, dtype=np.int8)
    decoded_symbols = decoded_path_symbol_indices(
        path, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
    )
    if decoded_bits.shape != (2 * count,) or decoded_symbols.shape != (count,):
        raise ValueError("conditional decoder returned an invalid information/symbol shape")
    if result.candidate_metrics.shape != (count, 16) or not np.all(
        np.isfinite(result.candidate_metrics)
    ):
        raise FloatingPointError("conditional decoder metrics are invalid")
    if not np.all(np.isfinite(result.final_estimator_state.full_iq)) or not np.all(
        np.isfinite(result.final_estimator_state.fluctuating_iq)
    ):
        raise FloatingPointError("conditional estimator final state is non-finite")
    if not np.isclose(np.sum(result.final_posterior), 1.0, rtol=0.0, atol=1e-12):
        raise FloatingPointError("conditional estimator final posterior is not normalized")
    for local_position, row in enumerate(result.metric_provenance):
        symbol = symbol_origin + local_position
        first = sample_origin + 8 * symbol
        expected_samples = tuple(range(first, first + 8))
        if (
            row.absolute_symbol_index != symbol
            or row.estimator_time_index != tick_origin + local_position
            or row.sample_indices != expected_samples
            or row.prediction_cutoff_sample_index != first - 1
            or row.observation_cutoff_sample_index != first + 7
            or row.hypothesis_ids != tuple(range(16))
        ):
            raise ValueError(
                "conditional metric provenance violates clock/canonical order contract"
            )
    bit_errors = count_bit_errors(reference_bits, decoded_bits)
    symbol_errors = count_symbol_errors(reference_symbols, decoded_symbols)
    counts = {
        "bit_errors": bit_errors,
        "total_bits": int(reference_bits.size),
        "symbol_errors": symbol_errors,
        "total_symbols": count,
    }
    final_full = np.asarray(result.final_estimator_state.full_iq, dtype=np.float64)
    initial_full = np.asarray(policy["initial_full_iq"], dtype=np.float64)[None, :]
    true_gain = float(true_gain_for_evaluation)
    return {
        "candidate_id": policy["candidate_id"],
        "role": policy["role"],
        "alpha_prime": policy["alpha_prime"],
        "k_scale": policy["k_scale"],
        "k_tilde": list(policy["k_tilde"]),
        "mu0": list(policy["mu0"]),
        "initial_full_iq": list(policy["initial_full_iq"]),
        "initial_fluctuating_iq": list(policy["initial_fluctuating_iq"]),
        "status": "complete_valid_output",
        "decoder_invocations": 1,
        "received_sha256": received_hash,
        "counts": counts,
        "decoded_information_bits": decoded_bits.tolist(),
        "decoded_symbol_indices": decoded_symbols.tolist(),
        "decoded_hypothesis_path": list(path),
        "decoder_path_cost": float(result.decoder_result.best_path_metric),
        "candidate_metrics_shape": list(result.candidate_metrics.shape),
        "posterior_final": result.final_posterior.tolist(),
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
            "initial_full_norm": float(np.linalg.norm(initial_full)),
            "final_full_norm": float(np.linalg.norm(final_full)),
            "total_full_iq_change_norm": float(np.linalg.norm(final_full - initial_full)),
            "final_coefficient_error_norm_evaluation_only": float(
                np.linalg.norm(final_full - np.full((1, 2), true_gain))
            ),
            "per_symbol_coefficient_history": "unavailable_from conditional decode result",
        },
    }


def require_original_received_hash(run_id: str, actual_hash: str, original_hash: str) -> None:
    """Raise before decode unless replayed received bytes match the failed attempt."""
    if actual_hash != original_hash:
        raise M8BRecoveryBlocked(f"RECEIVED_REPLAY_MISMATCH for {run_id}")


def _original_received_hashes(original_info: Mapping[str, Any]) -> dict[str, str]:
    return dict(original_info["original_received_hashes"])


def _checkpoint_path(output: Path, run_id: str) -> Path:
    return output / "checkpoints" / f"{run_id.rsplit(':', 1)[-1]}.json"


def independent_verify_recovery(
    output: str | Path, draft: Mapping[str, Any], original_hashes: Mapping[str, str]
) -> dict[str, Any]:
    directory = Path(output)
    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((directory / "checkpoints").glob("run-*.json"))
    ]
    expected_runs = _m8b_manifest(draft)["runs"]
    expected_run_ids = [run["run_id"] for run in expected_runs]
    candidate_rows = draft["policy_grid"]["candidate_policies"]
    expected_candidates = [row["candidate_id"] for row in candidate_rows]
    candidates = {row["candidate_id"]: row for row in candidate_rows}
    if [row.get("run_id") for row in rows] != expected_run_ids[: len(rows)]:
        raise ValueError("recovery checkpoint run IDs are missing, duplicated, or out of order")
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
    seen_received_hashes: set[str] = set()
    decoder_calls = 0
    for row, expected_run in zip(rows, expected_runs, strict=False):
        run_id = row["run_id"]
        expected_hash = original_hashes.get(run_id)
        if row.get("received_sha256") != expected_hash:
            raise ValueError("recovery received hash differs from original failed attempt")
        seen_received_hashes.add(row["received_sha256"])
        if (
            row.get("run_index") != expected_run["run_index"]
            or row.get("seed_provenance") != expected_run["streams"]
        ):
            raise ValueError(
                "recovery run seed provenance differs from original M8a TRAIN derivation"
            )
        if (
            row.get("status") != "complete"
            or [item.get("candidate_id") for item in row.get("policies", [])] != expected_candidates
        ):
            raise ValueError("recovery run does not contain the exact eight policy records")
        bits = np.asarray(row["evaluation_only"]["reference_information_bits"], dtype=np.int8)
        symbols = np.asarray(row["evaluation_only"]["reference_symbol_indices"], dtype=np.int64)
        if bits.shape != (512,) or symbols.shape != (256,):
            raise ValueError("recovery reference vectors have invalid dimensions")
        if not np.array_equal(
            symbols,
            encode_reference_symbol_indices(
                bits, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
            ),
        ):
            raise ValueError("saved reference coded symbols do not match M1 encoder replay")
        row_calls = 0
        for record in row["policies"]:
            candidate_id = record["candidate_id"]
            policy = candidates[candidate_id]
            for key in (
                "alpha_prime",
                "k_scale",
                "k_tilde",
                "mu0",
                "initial_full_iq",
                "initial_fluctuating_iq",
            ):
                if record.get(key) != policy[key]:
                    raise ValueError(f"candidate {candidate_id} differs in frozen field {key}")
            calls = int(record.get("decoder_invocations", 0))
            decoder_calls += calls
            row_calls += calls
            if record.get("status") != "complete_valid_output":
                totals[candidate_id]["failures"] += 1
                continue
            if calls != 1 or record.get("received_sha256") != expected_hash:
                raise ValueError("valid policy record lacks exactly one paired decoder call")
            decoded_bits = np.asarray(record["decoded_information_bits"], dtype=np.int8)
            decoded_symbols = np.asarray(record["decoded_symbol_indices"], dtype=np.int64)
            path = tuple(int(value) for value in record["decoded_hypothesis_path"])
            if decoded_bits.shape != (512,) or decoded_symbols.shape != (256,) or len(path) != 256:
                raise ValueError("decoded result has invalid dimensions")
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
                raise ValueError("decoded bits/symbols do not match canonical decoded path")
            counts = {
                "bit_errors": count_bit_errors(bits, decoded_bits),
                "total_bits": 512,
                "symbol_errors": count_symbol_errors(symbols, decoded_symbols),
                "total_symbols": 256,
            }
            if record.get("counts") != counts:
                raise ValueError("independent raw-count replay mismatch")
            total = totals[candidate_id]
            for key, value in counts.items():
                total[key] += value
            total["valid_records"] += 1
        if row.get("decoder_invocations") != row_calls:
            raise ValueError("recovery checkpoint decoder count mismatch")
    b_complete = (
        totals["historical_frozen_B"]["valid_records"] == 40
        and totals["historical_frozen_B"]["failures"] == 0
    )
    ranking = []
    for candidate in candidate_rows:
        candidate_id = candidate["candidate_id"]
        total = totals[candidate_id]
        if (
            total["total_bits"] != total["valid_records"] * 512
            or total["total_symbols"] != total["valid_records"] * 256
        ):
            raise ValueError("candidate denominator differs from complete records")
        eligible = (
            len(rows) == 40
            and b_complete
            and total["valid_records"] == 40
            and total["failures"] == 0
        )
        ranking.append(
            {
                "candidate_id": candidate_id,
                "role": candidate["role"],
                **total,
                "eligible": eligible,
                "pooled_ber": total["bit_errors"] / total["total_bits"]
                if total["total_bits"]
                else None,
                "pooled_ser": total["symbol_errors"] / total["total_symbols"]
                if total["total_symbols"]
                else None,
                "k_scale": candidate["k_scale"],
                "alpha_prime": candidate["alpha_prime"],
            }
        )
    eligible_rows = [row for row in ranking if row["eligible"]]
    eligible_rows.sort(
        key=lambda row: (
            row["pooled_ber"],
            row["pooled_ser"],
            abs(row["k_scale"]),
            -row["alpha_prime"],
            row["candidate_id"],
        )
    )
    selected = (
        eligible_rows[0]["candidate_id"]
        if len(rows) == 40
        and len({row.get("run_id") for row in rows}) == 40
        and len(seen_received_hashes) == 40
        and b_complete
        and eligible_rows
        else None
    )
    return {
        "status": "TRAIN_SELECTED_NOT_VALIDATED" if selected else "TRAIN_INCOMPLETE_OR_BLOCKED",
        "run_count": len(rows),
        "unique_run_count": len({row["run_id"] for row in rows}),
        "unique_received_hash_count": len(seen_received_hashes),
        "policy_record_count": sum(len(row.get("policies", [])) for row in rows),
        "decoder_invocations": decoder_calls,
        "decoder_invocations_expected": 320,
        "b_control_complete": b_complete,
        "ranking": eligible_rows,
        "all_policy_totals": ranking,
        "selected_candidate_id": selected,
    }


def _recovery_output_hashes(directory: Path) -> dict[str, str]:
    return _output_file_hashes(directory)


def execute_recovery(
    *,
    approved_config_path: str | Path = RECOVERY_APPROVED,
    draft_path: str | Path = DEFAULT_DRAFT,
    output_root: str | Path = RECOVERY_OUTPUT,
) -> dict[str, Any]:
    """Replay the exact failed M8b TRAIN inputs and decode only after hash match."""
    approved_path = Path(approved_config_path)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    validate_recovery_config(approved, config_path=approved_path)
    original = json.loads(ORIGINAL_APPROVED.read_text(encoding="utf-8"))
    original_info = _original_attempt_integrity(draft, original)
    original_hashes = _original_received_hashes(original_info)
    receiver_configuration = approved["runtime_provenance"]["receiver_configuration"]
    clocks = approved["recovery_provenance"]["clock_origins"]
    out = Path(output_root)
    if out.exists() and any(out.iterdir()):
        raise M8BRecoveryBlocked("recovery namespace is not empty; resume is not implicit")
    out.mkdir(parents=True, exist_ok=True)
    config_hash = _sha256_file(approved_path)
    _atomic_json(out / "approved_recovery_config_snapshot.json", approved, exclusive=True)
    _atomic_json(
        out / "manifest.json",
        {
            "schema_version": RECOVERY_SCHEMA,
            "recovery_attempt_id": RECOVERY_ATTEMPT_ID,
            "original_attempt_id": original_info["original_attempt_id"],
            "approved_config_sha256": config_hash,
            "original_approved_config_sha256": original_info["original_approved_config_sha256"],
            "runtime_source_fingerprint": approved["runtime_provenance"][
                "current_source_fingerprint"
            ],
            "run_manifest": approved["run_manifest"],
            "original_received_hashes": original_hashes,
            "validation_or_final_executed": False,
        },
        exclusive=True,
    )
    policies = draft["policy_grid"]["candidate_policies"]
    beta = float(draft["anchored_profile"]["shared_beta"])
    gain = float(draft["profile"]["real_channel_gain"])
    variance = float(draft["profile"]["sigma_squared"])
    if beta != 0.7 or gain != 0.75 or variance != 0.7115124735378853:
        raise M8BRecoveryBlocked("frozen M8 scientific values changed")
    original_decoder = decode_reconstruction_conditional_sequence.__globals__[
        "decode_reconstruction_viterbi"
    ]
    decoder_calls = 0

    def counted_decoder(*args: Any, **kwargs: Any) -> Any:
        nonlocal decoder_calls
        decoder_calls += 1
        return original_decoder(*args, **kwargs)

    decode_reconstruction_conditional_sequence.__globals__["decode_reconstruction_viterbi"] = (
        counted_decoder
    )
    started = time.perf_counter()
    completed = 0
    rss_peak: int | None = None
    rss_unverified = False
    recovery_failures = 0
    try:
        for run in approved["run_manifest"]["runs"]:
            if time.perf_counter() - started >= 900:
                break
            rss = _process_rss_windows(os.getpid())
            if rss is None:
                rss_unverified = True
            else:
                rss_peak = max(rss_peak or 0, int(rss))
                if rss >= 1610612736:
                    break
            run_id = run["run_id"]
            checkpoint_path = _checkpoint_path(out, run_id)
            if checkpoint_path.exists():
                raise M8BRecoveryBlocked("recovery checkpoint already exists; no implicit resume")
            seeds = run["streams"]
            try:
                data_rng = np.random.Generator(np.random.PCG64(seeds["data"]["derived_seed"]))
                bits = data_rng.integers(0, 2, size=512, dtype=np.int8)
                original_checkpoint = json.loads(
                    _checkpoint_path(ORIGINAL_OUTPUT, run_id).read_text(encoding="utf-8")
                )
            except Exception as exc:
                _atomic_json(
                    checkpoint_path,
                    {
                        "schema_version": RECOVERY_SCHEMA,
                        "run_id": run_id,
                        "run_index": run["run_index"],
                        "status": "received_generation_failure",
                        "decoder_invocations": 0,
                        "seed_provenance": seeds,
                        "exception_type": type(exc).__name__,
                        "detail": str(exc),
                    },
                    exclusive=True,
                )
                recovery_failures += 1
                break
            if not np.array_equal(
                bits,
                np.asarray(
                    original_checkpoint["evaluation_only"]["reference_information_bits"],
                    dtype=np.int8,
                ),
            ):
                mismatch = {
                    "schema_version": RECOVERY_SCHEMA,
                    "run_id": run_id,
                    "status": "REFERENCE_BITS_REPLAY_MISMATCH",
                    "decoder_invocations": 0,
                    "seed_provenance": seeds,
                }
                _atomic_json(checkpoint_path, mismatch, exclusive=True)
                recovery_failures += 1
                break
            try:
                received, reference_symbols, received_hash = _prepare_received(
                    bits,
                    gain=gain,
                    noise_seed=int(seeds["noise"]["derived_seed"]),
                    variance=variance,
                    stream_id=f"M8b:TRAIN:{run_id}:noise",
                )
            except Exception as exc:
                _atomic_json(
                    checkpoint_path,
                    {
                        "schema_version": RECOVERY_SCHEMA,
                        "run_id": run_id,
                        "run_index": run["run_index"],
                        "status": "received_generation_failure",
                        "decoder_invocations": 0,
                        "seed_provenance": seeds,
                        "reference_bits_sha256": hashlib.sha256(bits.tobytes()).hexdigest(),
                        "exception_type": type(exc).__name__,
                        "detail": str(exc),
                    },
                    exclusive=True,
                )
                recovery_failures += 1
                break
            expected_hash = original_hashes.get(run_id)
            try:
                require_original_received_hash(run_id, received_hash, str(expected_hash))
            except M8BRecoveryBlocked:
                mismatch = {
                    "schema_version": RECOVERY_SCHEMA,
                    "run_id": run_id,
                    "status": "RECEIVED_REPLAY_MISMATCH",
                    "expected_received_sha256": expected_hash,
                    "actual_received_sha256": received_hash,
                    "decoder_invocations": 0,
                    "seed_provenance": seeds,
                    "reference_bits_sha256": hashlib.sha256(bits.tobytes()).hexdigest(),
                }
                _atomic_json(checkpoint_path, mismatch, exclusive=True)
                recovery_failures += 1
                break
            records = []
            calls_before_run = decoder_calls
            for policy in policies:
                before = decoder_calls
                try:
                    record = _policy_call(
                        policy=policy,
                        received=received,
                        reference_bits=bits,
                        reference_symbols=reference_symbols,
                        received_hash=received_hash,
                        receiver_configuration=receiver_configuration,
                        clock_origins=clocks,
                        true_gain_for_evaluation=gain,
                    )
                    actual_calls = decoder_calls - before
                    if actual_calls != 1:
                        raise RuntimeError(
                            f"expected one conditional decoder call, observed {actual_calls}"
                        )
                    record["decoder_invocations"] = actual_calls
                    records.append(record)
                except Exception as exc:
                    records.append(
                        {
                            "candidate_id": policy["candidate_id"],
                            "role": policy["role"],
                            "alpha_prime": policy["alpha_prime"],
                            "k_scale": policy["k_scale"],
                            "k_tilde": policy["k_tilde"],
                            "mu0": policy["mu0"],
                            "initial_full_iq": policy["initial_full_iq"],
                            "initial_fluctuating_iq": policy["initial_fluctuating_iq"],
                            "status": "numerical_or_decoder_failure",
                            "exception_type": type(exc).__name__,
                            "detail": str(exc),
                            "decoder_invocations": decoder_calls - before,
                        }
                    )
                    recovery_failures += 1
            run_calls = decoder_calls - calls_before_run
            checkpoint = {
                "schema_version": RECOVERY_SCHEMA,
                "run_id": run_id,
                "run_index": run["run_index"],
                "status": "complete",
                "original_received_sha256": expected_hash,
                "received_sha256": received_hash,
                "approved_config_sha256": config_hash,
                "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
                    "current_source_fingerprint_sha256"
                ],
                "seed_provenance": seeds,
                "clock_origins": clocks,
                "decoder_invocations": run_calls,
                "evaluation_only": {
                    "reference_information_bits": [int(value) for value in bits],
                    "reference_symbol_indices": [int(value) for value in reference_symbols],
                    "real_channel_gain": gain,
                    "sigma_squared": variance,
                },
                "policies": records,
            }
            _atomic_json(checkpoint_path, checkpoint, exclusive=True)
            completed += 1
    finally:
        decode_reconstruction_conditional_sequence.__globals__["decode_reconstruction_viterbi"] = (
            original_decoder
        )
    elapsed = time.perf_counter() - started
    try:
        verification = independent_verify_recovery(out, draft, original_hashes)
    except (ValueError, KeyError, TypeError) as exc:
        verification = {"status": "VERIFICATION_FAILED", "detail": str(exc)}
    complete = (
        verification.get("status") == "TRAIN_SELECTED_NOT_VALIDATED"
        and verification.get("run_count") == 40
        and verification.get("unique_received_hash_count") == 40
        and verification.get("decoder_invocations") == 320
    )
    historical_after = _recovery_historical_baseline()
    history_ok = historical_after == approved["historical_integrity_baseline"]
    selected = verification.get("selected_candidate_id") if complete and history_ok else None
    status = "TRAIN_SELECTED_NOT_VALIDATED" if selected else "TRAIN_INCOMPLETE_OR_BLOCKED"
    if not history_ok:
        verification = {
            **verification,
            "status": "VERIFICATION_FAILED",
            "detail": "historical artifacts changed",
        }
    summary = {
        "schema_version": RECOVERY_SCHEMA,
        "classification": RECOVERY_CLASSIFICATION,
        "recovery_attempt_id": RECOVERY_ATTEMPT_ID,
        "status": status,
        "approved_config_sha256": config_hash,
        "runtime_source_fingerprint_sha256": approved["runtime_provenance"][
            "current_source_fingerprint_sha256"
        ],
        "planned_run_count": 40,
        "completed_run_count": completed,
        "policy_record_count": sum(
            len(json.loads(path.read_text(encoding="utf-8")).get("policies", []))
            for path in sorted((out / "checkpoints").glob("run-*.json"))
        ),
        "decoder_invocations": decoder_calls,
        "received_hash_matches": verification.get("unique_received_hash_count", 0),
        "failure_record_count": recovery_failures,
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
            "wall_clock_budget_seconds": 900,
            "rss_monitoring_budget_bytes": 1610612736,
        },
        "historical_integrity": {
            "before": approved["historical_integrity_baseline"],
            "after": historical_after,
            "unchanged": history_ok,
        },
        "validation_or_final_executed": False,
    }
    _atomic_json(out / "independent_verification.json", verification, exclusive=True)
    _atomic_json(out / "summary.json", summary, exclusive=True)
    if selected is not None:
        policy = next(row for row in policies if row["candidate_id"] == selected)
        _atomic_json(
            out / "selected_policy.json",
            {
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
                    row
                    for row in verification["all_policy_totals"]
                    if row["candidate_id"] == selected
                ),
                "approved_config_sha256": config_hash,
                "recovery_attempt_id": RECOVERY_ATTEMPT_ID,
                "validation_or_final_authorized": False,
            },
            exclusive=True,
        )
    _atomic_json(out / "integrity_manifest.json", _recovery_output_hashes(out), exclusive=True)
    return summary
