"""Validation and fail-closed guard for the proposed M10a study design.

Validation is deterministic and read-only. It does not materialize SeedSequence
children, initialize generators, generate observations, or call a receiver.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DRAFT_PATH = ROOT / "configs/m10a_variable_gain_study_draft.json"
STUDY_ID = "m10_controlled_piecewise_gain_v1"
PROFILE_IDS = ("P0_CONSTANT", "P1_HIGH_TO_LOW", "P2_LOW_TO_HIGH")
POLICY_IDS = ("historical_frozen_B", "anch_a085_k025")
EXPECTED_SIGMA_SQUARED = 0.7115124735378853
EXPECTED_HIGH_GAIN = math.sqrt(0.765)
EXPECTED_SEED_ROOTS = {
    "data": 2027030101,
    "noise": 2027030102,
    "bootstrap": 2027030103,
    "metadata": 2027030104,
}
EXPECTED_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37, "metadata": 41}
PROTOCOL_WORD = 1295337521
PARTITION_CODE = 1001


class M10AExecutionBlocked(RuntimeError):
    """Raised when M10a is offered for stochastic execution without approval."""


@dataclass(frozen=True, slots=True)
class M10AStudyDesign:
    study_id: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    run_count: int
    symbols_per_sequence: int
    profile_ids: tuple[str, ...]
    policy_ids: tuple[str, ...]
    expected_decoder_calls: int
    expected_policy_records: int
    expected_received_samples: int


def _equal(actual: object, expected: object, *, name: str, message: str | None = None) -> None:
    if actual != expected:
        raise ValueError(message or f"{name} must equal {expected!r}")


def _object(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _is_close(actual: object, expected: float, *, name: str, atol: float = 1e-15) -> None:
    if (
        isinstance(actual, bool)
        or not isinstance(actual, int | float)
        or not math.isfinite(float(actual))
        or not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=atol)
    ):
        raise ValueError(f"{name} must equal {expected!r} within {atol}")


def _expected_policy_rows() -> list[dict[str, object]]:
    return [
        {
            "candidate_id": "historical_frozen_B",
            "alpha_prime": 1.0,
            "k_tilde": [0.0, 0.0],
            "mu0": [0.0, 0.0],
            "initial_fluctuating_iq": [0.42, 0.91],
            "initial_full_iq": [0.42, 0.91],
            "beta": 0.7,
        },
        {
            "candidate_id": "anch_a085_k025",
            "alpha_prime": 0.85,
            "k_tilde": [0.0875, -0.05],
            "mu0": [0.42, 0.91],
            "initial_fluctuating_iq": [0.0, 0.0],
            "initial_full_iq": [0.42, 0.91],
            "beta": 0.7,
        },
    ]


def validate_m10a_variable_gain_study(value: object) -> M10AStudyDesign:
    """Validate exact P0/P1/P2, fixed policies, pairing, seeds, and statistics."""
    root = _object(value, name="M10a draft")
    _equal(root.get("schema_version"), "m10a.variable-gain-study.v1", name="schema_version")
    _equal(root.get("experiment_id"), STUDY_ID, name="experiment_id")
    _equal(root.get("design_status"), "proposed", name="design_status")
    _equal(root.get("execution_authorized"), False, name="execution_authorized")
    _equal(root.get("execution_scope"), "none", name="execution_scope")

    scientific = _object(root.get("scientific_status"), name="scientific_status")
    _equal(scientific.get("paper_exact"), False, name="paper_exact")
    _equal(scientific.get("receiver_enabled"), False, name="receiver_enabled")
    _equal(
        scientific.get("channel_profile_status"),
        "proposed experimental extension; no new ADR accepted",
        name="channel_profile_status",
    )
    _equal(
        scientific.get("author_mapping_status"), "SOURCE_UNRESOLVED", name="author_mapping_status"
    )

    profile = _object(root.get("channel_profile"), name="channel_profile")
    for key, expected in {
        "profile_id": "controlled_piecewise_real_gain_v1",
        "model_scope": "evaluation-side real positive gain schedule; separate from reconstructed_offline constant-gain profile",
        "equation": "y[n] = a[floor(n/8)] * x[n] + w[n], n=0..2047",
        "channel_memory_L": 1,
        "zero_delay": True,
        "memory": False,
        "multipath": False,
        "complex_fading": False,
        "normalized_8psk": True,
        "rectangular_zoh": True,
        "samples_per_symbol": 8,
        "frame_symbols": 256,
        "frame_samples": 2048,
        "switch_after_symbol_index": 127,
        "switch_symbol_index": 128,
        "switch_sample_index": 1024,
        "mean_squared_gain_target": 0.5625,
        "no_oracle_reset_at_switch": True,
        "switch_index_not_passed_to_receiver": True,
        "channel_truth_not_passed_to_receiver": True,
    }.items():
        _equal(profile.get(key), expected, name=f"channel_profile.{key}")
    for key, expected in {"nominal_gain": 0.75, "low_gain": 0.60}.items():
        _is_close(profile.get(key), expected, name=f"channel_profile.{key}")
    _is_close(profile.get("high_gain"), EXPECTED_HIGH_GAIN, name="high gain")
    _equal(
        profile.get("high_gain_formula"),
        "sqrt(2*(0.75**2)-(0.60**2)) = sqrt(0.765)",
        name="high_gain_formula",
    )
    profiles = _object(profile.get("profiles"), name="channel_profile.profiles")
    if tuple(profiles) != PROFILE_IDS:
        raise ValueError("exactly the ordered P0/P1/P2 gain profiles are required")
    expected_segments = {
        "P0_CONSTANT": [{"symbol_start": 0, "symbol_stop_exclusive": 256, "gain": 0.75}],
        "P1_HIGH_TO_LOW": [
            {"symbol_start": 0, "symbol_stop_exclusive": 128, "gain": EXPECTED_HIGH_GAIN},
            {"symbol_start": 128, "symbol_stop_exclusive": 256, "gain": 0.60},
        ],
        "P2_LOW_TO_HIGH": [
            {"symbol_start": 0, "symbol_stop_exclusive": 128, "gain": 0.60},
            {"symbol_start": 128, "symbol_stop_exclusive": 256, "gain": EXPECTED_HIGH_GAIN},
        ],
    }
    for profile_id in PROFILE_IDS:
        row = _object(profiles[profile_id], name=f"profile {profile_id}")
        segments = row.get("segments")
        if not isinstance(segments, list) or len(segments) != len(expected_segments[profile_id]):
            raise ValueError(f"{profile_id} profile segments are invalid")
        for segment_index, (segment, expected) in enumerate(
            zip(segments, expected_segments[profile_id], strict=True)
        ):
            actual = _object(segment, name=f"{profile_id} segment {segment_index}")
            for key in ("symbol_start", "symbol_stop_exclusive"):
                if actual.get(key) != expected[key]:
                    raise ValueError(f"{profile_id} switch/segment boundary mismatch")
            _is_close(
                actual.get("gain"), float(expected["gain"]), name=f"{profile_id} segment gain"
            )
    _equal(
        profile.get("gain_noise_coupling"),
        "none; noise power is held fixed for all profiles",
        name="gain/noise coupling",
    )
    _equal(
        profile.get("interpretation_limits"),
        [
            "equal frame-average a^2 does not imply equal per-symbol SNR",
            "P1/P2 share a gain-value histogram but differ in temporal order",
            "P0 comparison also changes gain distribution, not only transition count",
            "the design does not isolate every causal aspect of nonstationarity",
        ],
        name="interpretation_limits",
    )

    noise = _object(root.get("noise"), name="noise")
    _equal(noise.get("sigma_squared"), EXPECTED_SIGMA_SQUARED, name="sigma_squared")
    _is_close(
        noise.get("real_component_variance"), EXPECTED_SIGMA_SQUARED / 2, name="real variance"
    )
    _is_close(
        noise.get("imaginary_component_variance"),
        EXPECTED_SIGMA_SQUARED / 2,
        name="imaginary variance",
    )
    _equal(noise.get("nominal_reference_gamma_b_eff_db"), 5.0, name="nominal gamma")
    _equal(noise.get("physical_hf_ebn0_claim"), False, name="physical HF claim")
    _equal(noise.get("automatic_received_normalization"), False, name="received normalization")

    receiver_profile = _object(root.get("receiver_profile"), name="receiver_profile")
    for key, expected in {
        "profile": "reconstructed_offline",
        "channel_memory_L": 1,
        "zero_delay": True,
        "normalized_8psk": True,
        "rectangular_zoh": True,
        "samples_per_symbol": 8,
        "mapping": "ADR-002 reconstructed mapping",
        "likelihood": "ADR-005 pseudo-likelihood",
        "observation": "ADR-012 observed-IQ",
        "decoder": "ADR-013 conditional full Viterbi",
        "noise": "ADR-015 independent circular complex AWGN",
        "initial_full_iq": [0.42, 0.91],
        "physical_hf_ebn0_interpretation": False,
    }.items():
        _equal(receiver_profile.get(key), expected, name=f"receiver_profile.{key}")
    _is_close(receiver_profile.get("nominal_real_gain"), 0.75, name="receiver nominal gain")
    _is_close(receiver_profile.get("beta"), 0.7, name="receiver beta")

    policy_rows = root.get("receiver_policies")
    if policy_rows != _expected_policy_rows():
        raise ValueError(
            "exactly the unchanged frozen-B and anchored receiver policies are required"
        )
    receiver_contract = _object(root.get("receiver_contract"), name="receiver_contract")
    for key in (
        "oracle_gain_reset",
        "switch_index_provided_to_receiver",
        "channel_truth_or_gain_schedule_provided_to_receiver",
        "reference_bits_or_true_path_provided_to_receiver",
    ):
        _equal(receiver_contract.get(key), False, name=f"receiver_contract.{key}")
    _equal(
        receiver_contract.get("clocks"),
        {"absolute_sample_origin": 0, "absolute_symbol_origin": 0, "estimator_tick_origin": 0},
        name="receiver clocks",
    )

    study = _object(root.get("study_design"), name="study_design")
    for key, expected in {
        "run_count": 100,
        "symbols_per_sequence": 256,
        "information_bits_per_sequence": 512,
        "profiles_per_run": 3,
        "policies_per_profile": 2,
        "paired_bits_within_run": True,
        "one_waveform_per_run": True,
        "one_noise_vector_per_run_shared_across_profiles": True,
        "same_profile_specific_received_buffer_shared_by_B_and_anchored": True,
        "independent_cluster": "one complete run containing all three profiles and both policies",
        "planned_received_buffers": 300,
        "planned_policy_records": 600,
        "planned_decoder_calls": 600,
        "unique_received_samples": 614400,
        "policy_symbol_passes": 153600,
        "no_data_dependent_stopping": True,
    }.items():
        _equal(study.get(key), expected, name=f"study_design.{key}")

    statistics = _object(root.get("statistics"), name="statistics")
    _equal(statistics.get("primary_profile"), "P1_HIGH_TO_LOW", name="primary profile")
    _equal(
        statistics.get("primary_estimand"),
        "pooled raw-count DeltaBER_P1 = BER(anch_a085_k025, P1_HIGH_TO_LOW) - BER(historical_frozen_B, P1_HIGH_TO_LOW)",
        name="primary estimand",
    )
    if statistics.get("bootstrap_replicates") != 2000 or statistics.get("confidence_level") != 0.95:
        raise ValueError(
            "bootstrap replicate count and confidence level are fixed at 2000 and 0.95"
        )
    _equal(
        statistics.get("same_run_indices_across_profiles_and_policies"),
        True,
        name="paired bootstrap indices",
    )
    _equal(statistics.get("individual_bits_or_symbols_are_clusters"), False, name="cluster unit")
    for key, expected in {
        "secondary_estimands": [
            "DeltaBER_P0 = BER(anchor,P0)-BER(B,P0), descriptive",
            "DeltaBER_P2 = BER(anchor,P2)-BER(B,P2), descriptive",
            "DeltaSER_P0/P1/P2, descriptive",
            "DeltaBER_P1-DeltaBER_P0, descriptive",
            "DeltaBER_P2-DeltaBER_P1, descriptive",
        ],
        "bootstrap_method": "ADR-014 paired cluster bootstrap over full run clusters",
        "quantile_method": "numpy.quantile(method='linear')",
        "multiplicity_policy": "primary inference only for DeltaBER_P1; all other profile contrasts descriptive",
    }.items():
        _equal(statistics.get(key), expected, name=f"statistics.{key}")
    _equal(statistics.get("interval"), "percentile", name="bootstrap interval")

    partition = _object(root.get("partition"), name="partition")
    _equal(partition.get("partition_code"), PARTITION_CODE, name="partition code")
    _equal(
        partition.get("seed_namespaces"),
        EXPECTED_SEED_ROOTS,
        name="seed namespaces",
        message="M10 seed namespaces must be the distinct proposed roots",
    )
    if len(set(EXPECTED_SEED_ROOTS.values())) != 4:
        raise ValueError("M10 seed roots must be mutually distinct")
    planned = partition.get("planned_runs")
    expected_runs = [
        {"run_id": f"{STUDY_ID}:evaluation:run-{index + 1:03d}", "run_index": index}
        for index in range(100)
    ]
    if planned != expected_runs:
        raise ValueError("exactly 100 deterministic M10 run IDs and indices 0..99 are required")
    _equal(
        partition.get("planned_run_id_format"),
        "m10_controlled_piecewise_gain_v1:evaluation:run-{run_number:03d}, run_number 001..100",
        name="run ID format",
    )
    derivation = _object(partition.get("seed_derivation"), name="seed_derivation")
    for key, expected in {
        "protocol_version_word": PROTOCOL_WORD,
        "partition_code": PARTITION_CODE,
        "stream_codes": EXPECTED_STREAM_CODES,
        "run_index_semantics": "zero-based 0..99",
        "child_seeds_materialized": False,
        "rng_initialized": False,
    }.items():
        _equal(derivation.get(key), expected, name=f"seed_derivation.{key}")
    _equal(partition.get("no_M5_M9_root_overlap"), True, name="historical root isolation")
    _equal(partition.get("no_M9_observation_reuse"), True, name="M9 observation isolation")

    failure = _object(root.get("failure_policy"), name="failure_policy")
    _equal(
        failure.get("all_100_complete_joint_profile_runs_required"),
        True,
        name="complete run requirement",
    )
    _equal(failure.get("replace_seed_or_run"), False, name="seed replacement")
    _equal(failure.get("impute_missing_as_zero"), False, name="missing-value imputation")
    _equal(failure.get("data_dependent_stopping"), False, name="data-dependent stopping")
    _equal(
        failure.get("finite_high_error_trajectories"),
        "retain",
        name="finite high-error records",
    )
    _equal(
        failure.get("missing_output"),
        "record and block complete-design joint-profile inference",
        name="missing-output policy",
    )

    workload = _object(root.get("workload"), name="workload")
    _equal(workload.get("receiver_policy_decodes"), 600, name="decoder workload")
    _equal(workload.get("atomic_checkpoint_per_run"), True, name="checkpoint policy")
    _equal(workload.get("proposed_wall_clock_budget_seconds"), 900, name="wall-clock proposal")
    _equal(workload.get("proposed_periodic_rss_monitoring_bytes"), 1610612736, name="RSS proposal")
    _equal(workload.get("single_process"), True, name="single process")
    _equal(workload.get("multiprocessing"), False, name="multiprocessing")
    _equal(workload.get("received_samples"), 614400, name="received sample budget")
    _equal(workload.get("policy_symbol_passes"), 153600, name="symbol-pass budget")

    decision = _object(
        root.get("proposed_scientific_decision"), name="proposed_scientific_decision"
    )
    _equal(decision.get("status"), "PROPOSED_NOT_ACCEPTED", name="scientific decision status")
    _equal(decision.get("existing_ADR_015_modified"), False, name="ADR-015 mutation")
    _equal(decision.get("production_channel_integration"), False, name="production integration")
    authorization = _object(root.get("authorization_gates"), name="authorization_gates")
    _equal(
        authorization.get("m10b_requires_separate_explicit_authorization"),
        True,
        name="M10b authorization",
    )
    _equal(
        authorization.get("M10a_generates_no_RNG_or_observations"), True, name="M10a no-RNG gate"
    )

    return M10AStudyDesign(
        study_id=STUDY_ID,
        design_status="proposed",
        execution_authorized=False,
        execution_scope="none",
        run_count=100,
        symbols_per_sequence=256,
        profile_ids=PROFILE_IDS,
        policy_ids=POLICY_IDS,
        expected_decoder_calls=600,
        expected_policy_records=600,
        expected_received_samples=614400,
    )


def guard_m10a_execution(
    value: object,
    *,
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> None:
    """Validate proposal, then block before all supplied side-effect callbacks."""
    try:
        design = validate_m10a_variable_gain_study(value)
    except (TypeError, ValueError) as exc:
        raise M10AExecutionBlocked("M10a execution blocked: draft failed validation") from exc
    if (
        design.design_status != "approved"
        or design.execution_authorized is not True
        or design.execution_scope != "m10b_evaluation_only"
    ):
        raise M10AExecutionBlocked(
            f"M10b execution blocked: {design.design_status} / "
            f"{str(design.execution_authorized).lower()} / {design.execution_scope}"
        )
    del callbacks, executor
    raise M10AExecutionBlocked("M10a design artifact is not an executable approval")
