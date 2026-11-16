"""Validation and non-execution guard for the proposed M7a policy study."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn


class M7AExecutionBlocked(RuntimeError):
    """Raised when an M7a draft is presented for execution."""


@dataclass(frozen=True, slots=True)
class M7APolicyStudy:
    """Validated immutable summary of the M7a draft, not an executable plan."""

    study_id: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    candidate_ids: tuple[str, ...]
    training_sequence_count: int
    validation_sequence_count: int
    final_sequence_count: int
    workload: Mapping[str, int]


_ALPHA = (1.0, 0.95, 0.85)
_K_SCALES = (0.0, 0.5, 1.0)
_BASE_K = (0.35, -0.2)
_HISTORICAL_ROOTS = frozenset(
    {
        2026102801,
        2026102802,
        2026102803,
        2026102901,
        2026102902,
        2026102903,
        2026103001,
        2026103002,
        2026103003,
        2026110101,
        2026110102,
        2026110103,
    }
)
_PARTITION_SIZES = {"training": 40, "validation": 40, "final": 100}
_EXPECTED_CANDIDATE_ROLES = {"a100_k000": "historical_frozen_B", "a085_k100": "historical_C"}


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _require(actual: object, expected: object, *, name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def _require_close(actual: object, expected: float, *, name: str, atol: float = 1e-15) -> None:
    value = _number(actual, name=name)
    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=atol):
        raise ValueError(f"{name} violates the fixed study profile")


def _candidate_grid(root: Mapping[str, Any]) -> tuple[str, ...]:
    grid = _mapping(root.get("policy_grid"), name="policy_grid")
    _require(grid.get("alpha_prime_values"), list(_ALPHA), name="alpha grid")
    _require(grid.get("k_scale_values"), list(_K_SCALES), name="K scale grid")
    _require(grid.get("base_k_tilde"), list(_BASE_K), name="base K_tilde")
    expected: list[dict[str, object]] = []
    for alpha in _ALPHA:
        for scale in _K_SCALES:
            alpha_code = f"{round(alpha * 100):03d}"
            scale_code = f"{round(scale * 100):03d}"
            candidate_id = f"a{alpha_code}_k{scale_code}"
            role = _EXPECTED_CANDIDATE_ROLES.get(candidate_id, "proposed_policy")
            expected.append(
                {
                    "candidate_id": candidate_id,
                    "alpha_prime": alpha,
                    "k_scale": scale,
                    "k_tilde": [scale * _BASE_K[0], scale * _BASE_K[1]],
                    "role": role,
                }
            )
    candidates = grid.get("candidate_policies")
    if not isinstance(candidates, list) or candidates != expected:
        raise ValueError("candidate policies must be the exact nine-arm Cartesian grid")
    if len({item["candidate_id"] for item in candidates}) != 9:
        raise ValueError("candidate IDs must be unique")
    _require(grid.get("policies_are_source_author_receiver_modes"), False, name="source mode claim")
    return tuple(str(item["candidate_id"]) for item in expected)


def _validate_profile(root: Mapping[str, Any]) -> None:
    profile = _mapping(root.get("profile"), name="profile")
    exact = {
        "model": "reconstructed_offline",
        "channel_memory_L": 1,
        "delay_samples": 0,
        "modulation": "normalized_8PSK",
        "pulse_shape": "rectangular_ZOH",
        "samples_per_symbol": 8,
        "observed_iq_convention": "ADR-012",
        "likelihood": "ADR-005 reconstructed pseudo-likelihood",
        "decoder": "ADR-013 conditional full Viterbi",
        "noise_profile": "ADR-015 independent circular complex AWGN",
        "physical_hf_ebn0": False,
    }
    for key, expected in exact.items():
        _require(profile.get(key), expected, name=f"profile.{key}")
    _require_close(profile.get("real_channel_gain"), 0.75, name="real channel gain")
    _require_close(profile.get("gamma_b_eff_db"), 5.0, name="effective gamma_b")
    _require_close(profile.get("gamma_b_eff_linear"), 10.0 ** (5.0 / 10.0), name="linear gamma_b")
    sigma = 4.0 * 0.75 * 0.75 / (10.0 ** (5.0 / 10.0))
    _require_close(profile.get("sigma_squared"), sigma, name="sigma_squared")
    _require(
        profile.get("sigma_squared_formula"),
        "4*a*a / 10^(gamma_b_eff_db/10)",
        name="sigma formula",
    )


def _validate_partitions(root: Mapping[str, Any]) -> None:
    partitions = _mapping(root.get("partitions"), name="partitions")
    all_roots: list[int] = []
    expected_records = {
        "training": {
            "sequence_count": 40,
            "symbols_per_sequence": 256,
            "run_id_template": "{study_id}:train:run-{run_index:03d}",
            "uses_new_seed_roots": True,
        },
        "validation": {
            "sequence_count": 40,
            "symbols_per_sequence": 256,
            "run_id_template": "{study_id}:validation:run-{run_index:03d}",
            "uses_new_seed_roots": True,
            "policies": ["historical_frozen_B", "training_selected_policy"],
            "historical_C": "optional descriptive only; cannot affect selection",
            "selection_repeated": False,
        },
        "final": {
            "sequence_count": 100,
            "symbols_per_sequence": 256,
            "run_id_template": "{study_id}:final:run-{run_index:03d}",
            "uses_new_seed_roots": True,
            "policies": ["historical_frozen_B", "separately_frozen_selected_policy"],
            "historical_C": "optional descriptive only; cannot affect selection",
            "requires_separate_design_and_execution_approval": True,
            "automatic_after_validation": False,
        },
    }
    expected_root_keys = {"data", "noise", "bootstrap", "experiment_metadata"}
    for name, expected in expected_records.items():
        part = _mapping(partitions.get(name), name=f"partitions.{name}")
        for key, value in expected.items():
            _require(part.get(key), value, name=f"partitions.{name}.{key}")
        roots = _mapping(part.get("seed_namespaces"), name=f"{name} seed namespaces")
        if set(roots) != expected_root_keys:
            raise ValueError(f"{name} must have separate data/noise/bootstrap/metadata namespaces")
        for stream, raw_seed in roots.items():
            if isinstance(raw_seed, bool) or not isinstance(raw_seed, int) or raw_seed <= 0:
                raise ValueError(f"{name}.{stream} seed namespace root must be a positive integer")
            all_roots.append(raw_seed)
    if len(all_roots) != len(set(all_roots)):
        raise ValueError("seed namespace roots must be distinct across all partitions and streams")
    if _HISTORICAL_ROOTS.intersection(all_roots):
        raise ValueError("seed namespace conflicts with historical M5/M6 streams")

    derivation = _mapping(root.get("seed_derivation"), name="seed_derivation")
    _require(derivation.get("protocol_version_word"), 1295337521, name="seed protocol word")
    _require(
        derivation.get("partition_codes"),
        {"training": 701, "validation": 702, "final": 703},
        name="partition codes",
    )
    _require(
        derivation.get("stream_codes"),
        {"data": 11, "noise": 23, "bootstrap": 37, "experiment_metadata": 41},
        name="stream codes",
    )
    _require(derivation.get("displayed_run_index_origin"), 1, name="displayed run index")
    _require(derivation.get("spawned_run_index_origin"), 0, name="spawned run index")
    _require(derivation.get("streams_generated_in_M7a"), False, name="M7a RNG generation")
    _require(
        derivation.get("historical_namespaces_reused"), False, name="historical namespace reuse"
    )


def validate_m7a_policy_study(value: object) -> M7APolicyStudy:
    """Validate the exact proposed M7a design without deriving seeds or running anything."""
    root = _mapping(value, name="M7a design")
    _require(root.get("schema_version"), "m7a.policy-study.v1", name="schema_version")
    study_id = root.get("study_id")
    if not isinstance(study_id, str) or not study_id:
        raise ValueError("study_id must be a non-empty string")
    _require(root.get("design_status"), "proposed", name="design_status")
    _require(root.get("execution_authorized"), False, name="draft must remain unauthorized")
    _require(root.get("execution_scope"), "none", name="execution_scope")
    scientific = _mapping(root.get("scientific_status"), name="scientific_status")
    for key, expected in {
        "paper_exact": False,
        "receiver_enabled": False,
        "accepted_adrs": [
            "001",
            "002",
            "003",
            "004",
            "005",
            "006",
            "007",
            "008",
            "010",
            "012",
            "013",
            "014",
            "015",
        ],
        "proposed_adrs": ["009", "011"],
        "open_science_questions": ["SCI-02", "SCI-03", "SCI-METRIC-02"],
        "author_mapping_status": "SOURCE_UNRESOLVED",
    }.items():
        _require(scientific.get(key), expected, name=f"scientific_status.{key}")
    _validate_profile(root)

    sequence = _mapping(root.get("sequence_design"), name="sequence_design")
    for key, expected in {
        "symbols_per_run_F": 256,
        "information_bits_per_run": 512,
        "same_reference_sequence_for_all_policies_within_run": True,
        "one_noise_realization_per_run_shared_by_all_policies": True,
        "channel_truth_passed_to_receiver": False,
        "decoder_calls_per_policy_sequence_target": 1,
    }.items():
        _require(sequence.get(key), expected, name=f"sequence_design.{key}")
    shared = _mapping(root.get("shared_estimator"), name="shared_estimator")
    for key, expected in {
        "initial_fluctuating_iq": [0.42, 0.91],
        "initial_full_iq": [0.42, 0.91],
        "mu0": [0.0, 0.0],
        "beta": 0.7,
    }.items():
        _require(shared.get(key), expected, name=f"shared_estimator.{key}")
    clocks = _mapping(root.get("clock_origins"), name="clock_origins")
    for key, expected in {
        "absolute_sample_origin": 0,
        "absolute_symbol_origin": 0,
        "estimator_time_index_origin": 0,
        "no_resets_within_sequence": True,
    }.items():
        _require(clocks.get(key), expected, name=f"clock_origins.{key}")
    candidate_ids = _candidate_grid(root)

    pairing = _mapping(root.get("pairing"), name="pairing")
    for key in (
        "common_received_buffer_within_sequence",
        "common_reference_bits_within_sequence",
        "common_initial_state_beta_mu0_and_clocks",
        "only_policy_update_coefficients_vary",
        "received_hash_recorded_per_sequence",
    ):
        _require(pairing.get(key), True, name=f"pairing.{key}")
    _validate_partitions(root)
    _require(
        _mapping(root.get("partitions"), name="partitions").get("historical_data_excluded"),
        ["M5f", "M5h", "M5j", "M6b", "M6g", "M6h"],
        name="historical partition exclusions",
    )

    selection = _mapping(root.get("selection"), name="selection")
    _require(selection.get("training_only"), True, name="selection.training_only")
    _require(
        selection.get("estimand"),
        "minimum pooled raw-count BER over all nine fixed candidates",
        name="selection estimand",
    )
    _require(
        selection.get("candidate_eligible_only_if"),
        "all 40 candidate outputs and the paired historical B outputs are valid and complete; no completed-only pooling",
        name="selection eligibility",
    )
    _require(
        selection.get("if_any_candidate_run_fails"),
        "mark that candidate ineligible and retain every failure record; do not replace a seed; continue the predeclared remaining jobs if later authorized",
        name="candidate failure eligibility",
    )
    _require(
        selection.get("if_historical_B_has_any_missing_or_invalid_output"),
        "block selection requiring a complete paired B baseline; do not impute or drop the affected run",
        name="B baseline failure handling",
    )
    _require(
        selection.get("finite_high_error_trajectory"),
        "retain and include if decoder output is valid",
        name="finite high-error handling",
    )
    _require(
        selection.get("nonfinite_or_invalid_decoder_output"),
        "failure record; candidate ineligible unless a separately approved missingness policy changes this contract",
        name="invalid output handling",
    )
    _require(
        selection.get("tie_break_order"),
        [
            "lower pooled raw-count BER",
            "lower pooled raw-count SER",
            "lower K_scale",
            "alpha_prime closer to 1.0",
            "lexicographically lower candidate_id",
        ],
        name="selection tie-break order",
    )
    _require(selection.get("frozen_B_may_win"), True, name="frozen B eligibility")
    _require(
        selection.get("coefficient_error_used_for_selection"),
        False,
        name="coefficient-error selection",
    )
    _require(
        selection.get("training_inference"),
        "selection-oriented descriptive statistics only; no confirmatory claim",
        name="training inference status",
    )
    failure = _mapping(root.get("failure_policy"), name="failure_policy")
    required_failure = {
        "retain_success_and_failure_records": True,
        "record_raw_counts_when_valid": True,
        "record_coefficient_diagnostics": True,
        "retry_with_new_seed": False,
        "zero_error_imputation": False,
        "maximum_error_imputation": False,
        "silent_exclusion": False,
        "training_candidate_with_incomplete_40_run_pairing": "ineligible",
        "validation_or_final_missing_valid_output": "block full paired inference",
        "resume": "same planned IDs, original seeds, identical approved config/code fingerprint only",
    }
    for key, expected in required_failure.items():
        _require(failure.get(key), expected, name=f"failure_policy.{key}")
    _require(
        failure.get("finite_high_BER_trajectory"),
        "retain all observed errors",
        name="finite high-BER policy",
    )

    validation = _mapping(root.get("validation_rule"), name="validation_rule")
    _require(
        validation.get("evaluate_only"),
        ["historical_frozen_B", "one_training_selected_policy"],
        name="validation policies",
    )
    _require(validation.get("same_received_pairing"), True, name="validation pairing")
    _require(validation.get("new_data_and_noise_roots"), True, name="validation seed partition")
    _require(
        validation.get("primary_contrast"),
        "selected_policy BER minus frozen_B BER",
        name="validation primary contrast",
    )
    _require(
        validation.get("validation_does_not_select_a_second_policy"),
        True,
        name="validation selection lock",
    )
    _validate_bootstrap(validation.get("bootstrap"), name="validation bootstrap")
    final_eval = _mapping(root.get("final_evaluation"), name="final_evaluation")
    _require(final_eval.get("status"), "future; not authorized by M7a", name="final status")
    _require(final_eval.get("sample_count_candidate"), 100, name="final candidate count")
    if final_eval.get("confirmatory_label_allowed_before_approval") is not False:
        raise ValueError("final confirmatory label requires separate approval")

    gates = _mapping(root.get("workflow_gates"), name="workflow_gates")
    for key in ("train_to_validation_automatic", "validation_to_final_automatic"):
        _require(gates.get(key), False, name=f"workflow_gates.{key}")
    _require(
        gates.get("validation_requires_frozen_training_selection"), True, name="validation freeze"
    )
    _require(gates.get("final_requires_separate_approval"), True, name="final approval gate")

    workload = _mapping(root.get("workload"), name="workload")
    calculated = {
        "training_sequences": 40,
        "training_sequence_checkpoint_count": 40,
        "training_policy_run_records": 40 * 9,
        "training_unique_policy_decoder_passes_target": 40 * 9,
        "training_policy_symbol_passes_target": 40 * 9 * 256,
        "training_received_samples_generated": 40 * 256 * 8,
        "training_information_bits_generated": 40 * 512,
        "validation_sequences": 40,
        "validation_sequence_checkpoint_count": 40,
        "validation_policy_run_records": 40 * 2,
        "validation_decoder_passes": 40 * 2,
        "validation_optional_historical_C_decoder_passes": 40,
        "validation_policy_symbol_passes": 40 * 2 * 256,
        "validation_received_samples_generated": 40 * 256 * 8,
        "validation_information_bits_generated": 40 * 512,
        "final_sequences": 100,
        "final_sequence_checkpoint_count": 100,
        "final_policy_run_records": 100 * 2,
        "final_decoder_passes": 100 * 2,
        "final_optional_historical_C_decoder_passes": 100,
        "final_policy_symbol_passes": 100 * 2 * 256,
        "final_received_samples_generated": 100 * 256 * 8,
        "final_information_bits_generated": 100 * 512,
        "current_paired_helper_decoder_passes_per_call": 2,
        "training_current_public_helper_passes_if_called_once_per_non_B_candidate": 40 * 8 * 2,
        "training_repeated_B_pass_overhead_under_that_wrapper": 40 * 7,
    }
    for key, expected in calculated.items():
        _require(workload.get(key), expected, name=f"workload.{key}")
    if workload.get("single_process") is not True or workload.get("multiprocessing") is not False:
        raise ValueError("M7b candidate workload must be single-process")
    if workload.get("runtime_or_rss_estimate") is not None:
        raise ValueError("M7a must not invent runtime or RSS estimates")
    resource = _mapping(root.get("resource_policy"), name="resource_policy")
    _require(resource.get("single_process"), True, name="resource_policy.single_process")
    _require(resource.get("multiprocessing"), False, name="resource_policy.multiprocessing")
    _require(
        resource.get("atomic_checkpoint_per_sequence"),
        True,
        name="resource_policy.atomic_checkpoint_per_sequence",
    )
    if "actual wall-clock and memory limits" not in str(resource.get("budget")):
        raise ValueError("M7a must reserve concrete resource limits for separate approval")
    return M7APolicyStudy(
        study_id=study_id,
        design_status="proposed",
        execution_authorized=False,
        execution_scope="none",
        candidate_ids=candidate_ids,
        training_sequence_count=40,
        validation_sequence_count=40,
        final_sequence_count=100,
        workload={**calculated},
    )


def _validate_bootstrap(value: object, *, name: str) -> None:
    bootstrap = _mapping(value, name=name)
    for key, expected in {
        "cluster_unit": "one complete TCM sequence",
        "paired_index_resampling": True,
        "replicates": 2000,
        "confidence_level": 0.95,
        "interval": "two-sided percentile",
        "quantile_method": "linear",
        "pool_raw_counts_per_replicate": True,
        "independent_bootstrap_namespace": True,
    }.items():
        _require(bootstrap.get(key), expected, name=f"{name}.{key}")


def load_m7a_policy_study(path: str | Path) -> M7APolicyStudy:
    """Load and validate the fixed proposed JSON draft; never execute it."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("M7a draft could not be loaded as valid JSON") from exc
    return validate_m7a_policy_study(value)


def guard_m7a_execution(
    value: object,
    *,
    callbacks: Mapping[str, Callable[[], object]],
) -> NoReturn:
    """Validate then block before any injected RNG, data, or receiver callback."""
    design = validate_m7a_policy_study(value)
    del callbacks
    if design.execution_authorized is False:
        raise M7AExecutionBlocked(
            "M7a execution is unauthorized; separate M7b approval is required"
        )
    raise M7AExecutionBlocked("M7a draft is never an executable run-specific authorization")
