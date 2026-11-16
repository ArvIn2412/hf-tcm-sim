"""Validation and non-execution guard for the proposed M8a study draft."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, NoReturn


class M8AExecutionBlocked(RuntimeError):
    """Raised when the proposed M8a draft is presented for execution."""


@dataclass(frozen=True, slots=True)
class M8APolicy:
    """One fixed M8 candidate/control row from the unapproved design."""

    candidate_id: str
    role: str
    alpha_prime: float
    k_scale: float
    k_tilde: tuple[float, float]
    mu0: tuple[float, float]
    initial_fluctuating_iq: tuple[float, float]
    initial_full_iq: tuple[float, float]


@dataclass(frozen=True, slots=True)
class M8AStudyDesign:
    """Validated immutable summary of M8a; this is not an executable plan."""

    study_id: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    candidates: tuple[M8APolicy, ...]
    training_sequence_count: int
    validation_sequence_count: int
    expected_training_decoder_passes: int
    proposed_seed_roots: tuple[int, ...]


_STUDY_ID = "m8_anchored_reconstructed_adaptation_v1"
_ANCHOR = (0.42, 0.91)
_ZERO = (0.0, 0.0)
_BASE_K = (0.35, -0.2)
_ALPHAS = (1.0, 0.95, 0.85)
_K_SCALES = (0.25, 0.5)
_EXPECTED_CANDIDATE_IDS = (
    "anch_a100_k025",
    "anch_a100_k050",
    "anch_a095_k025",
    "anch_a095_k050",
    "anch_a085_k025",
    "anch_a085_k050",
    "historical_frozen_B",
    "historical_combined_C",
)
_EXPECTED_PARTITIONS = {
    "training": (
        40,
        801,
        {
            "data": 2027011001,
            "noise": 2027011002,
            "bootstrap": 2027011003,
            "experiment_metadata": 2027011004,
        },
    ),
    "validation": (
        40,
        802,
        {
            "data": 2027012001,
            "noise": 2027012002,
            "bootstrap": 2027012003,
            "experiment_metadata": 2027012004,
        },
    ),
    "future_final": (
        None,
        803,
        {
            "data": 2027013001,
            "noise": 2027013002,
            "bootstrap": 2027013003,
            "experiment_metadata": 2027013004,
        },
    ),
}
_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37, "experiment_metadata": 41}
_FORBIDDEN_SEED_ROOTS = frozenset(
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
        2026120101,
        2026120102,
        2026120103,
        2026120104,
        2026120201,
        2026120202,
        2026120203,
        2026120204,
        2026120301,
        2026120302,
        2026120303,
        2026120304,
    }
)


def expected_sigma_squared() -> float:
    """Return the fixed ADR-015 variance for the M8 candidate profile."""

    return 4.0 * 0.75 * 0.75 / (10.0 ** (5.0 / 10.0))


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _require(actual: object, expected: object, *, name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def _require_close(actual: object, expected: float, *, name: str, atol: float = 1e-15) -> None:
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        raise ValueError(f"{name} must be a finite real number")
    value = float(actual)
    if not math.isfinite(value) or not math.isclose(value, expected, rel_tol=0.0, abs_tol=atol):
        raise ValueError(f"{name} violates the fixed M8 profile")


def _pair(value: object, *, name: str) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"{name} must be a two-component I/Q pair")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{name} must contain finite real values")
        component = float(item)
        if not math.isfinite(component):
            raise ValueError(f"{name} must contain finite real values")
        result.append(component)
    return result[0], result[1]


def _expected_policies() -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    for alpha in _ALPHAS:
        for scale in _K_SCALES:
            alpha_code = round(alpha * 100)
            scale_code = round(scale * 100)
            result.append(
                {
                    "candidate_id": f"anch_a{alpha_code:03d}_k{scale_code:03d}",
                    "role": "new_anchored_candidate",
                    "alpha_prime": alpha,
                    "k_scale": scale,
                    "k_tilde": [scale * _BASE_K[0], scale * _BASE_K[1]],
                    "mu0": list(_ANCHOR),
                    "initial_fluctuating_iq": list(_ZERO),
                    "initial_full_iq": list(_ANCHOR),
                }
            )
    result.extend(
        (
            {
                "candidate_id": "historical_frozen_B",
                "role": "historical_control",
                "alpha_prime": 1.0,
                "k_scale": 0.0,
                "k_tilde": [0.0, 0.0],
                "mu0": [0.0, 0.0],
                "initial_fluctuating_iq": list(_ANCHOR),
                "initial_full_iq": list(_ANCHOR),
            },
            {
                "candidate_id": "historical_combined_C",
                "role": "historical_control",
                "alpha_prime": 0.85,
                "k_scale": 1.0,
                "k_tilde": list(_BASE_K),
                "mu0": [0.0, 0.0],
                "initial_fluctuating_iq": list(_ANCHOR),
                "initial_full_iq": list(_ANCHOR),
            },
        )
    )
    return tuple(result)


def _validate_policy_grid(root: Mapping[str, Any]) -> tuple[M8APolicy, ...]:
    grid = _mapping(root.get("policy_grid"), name="policy_grid")
    _require(grid.get("base_k_tilde"), list(_BASE_K), name="base K_tilde")
    _require(grid.get("anchored_alpha_values"), list(_ALPHAS), name="anchored alpha grid")
    _require(grid.get("anchored_k_scales"), list(_K_SCALES), name="anchored K scale grid")
    policies = grid.get("candidate_policies")
    expected = _expected_policies()
    if not isinstance(policies, list) or policies != list(expected):
        raise ValueError("candidate policies must be the exact six anchored arms and B/C controls")
    ids = tuple(str(item["candidate_id"]) for item in policies)
    if len(ids) != 8 or len(set(ids)) != 8:
        raise ValueError("candidate IDs must contain eight unique arms")
    _require(ids, _EXPECTED_CANDIDATE_IDS, name="candidate ID/order")
    _require(grid.get("candidate_count"), 8, name="candidate_count")
    _require(grid.get("candidate_policies_are_author_algorithms"), False, name="author mode claim")
    _require(grid.get("historical_B_and_C_parameters_unchanged"), True, name="historical controls")
    _require(grid.get("parameter_search_in_prep"), False, name="M8a parameter search")
    return tuple(
        M8APolicy(
            candidate_id=str(item["candidate_id"]),
            role=str(item["role"]),
            alpha_prime=float(item["alpha_prime"]),
            k_scale=float(item["k_scale"]),
            k_tilde=_pair(item["k_tilde"], name=f"{item['candidate_id']}.k_tilde"),
            mu0=_pair(item["mu0"], name=f"{item['candidate_id']}.mu0"),
            initial_fluctuating_iq=_pair(
                item["initial_fluctuating_iq"],
                name=f"{item['candidate_id']}.initial_fluctuating_iq",
            ),
            initial_full_iq=_pair(
                item["initial_full_iq"], name=f"{item['candidate_id']}.initial_full_iq"
            ),
        )
        for item in policies
    )


def _validate_partitions(root: Mapping[str, Any]) -> tuple[tuple[int, ...], int, int]:
    partitions = _mapping(root.get("partitions"), name="partitions")
    roots: list[int] = []
    sequence_counts: dict[str, int] = {}
    for name, (expected_count, _expected_code, expected_roots) in _EXPECTED_PARTITIONS.items():
        partition = _mapping(partitions.get(name), name=f"partitions.{name}")
        _require(partition.get("sequence_count"), expected_count, name=f"{name}.sequence_count")
        if expected_count is not None:
            _require(partition.get("symbols_per_sequence_F"), 256, name=f"{name}.F")
        partition_label = (
            "final" if name == "future_final" else "train" if name == "training" else name
        )
        _require(
            partition.get("run_id_template"),
            f"{{study_id}}:{partition_label}:run-{{run_index:03d}}",
            name=f"{name}.run_id_template",
        )
        namespaces = _mapping(partition.get("seed_namespaces"), name=f"{name}.seed_namespaces")
        for stream, seed in namespaces.items():
            if isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0:
                raise ValueError(f"{name}.{stream} seed root must be a positive integer")
        provided_roots = list(namespaces.values())
        if len(provided_roots) != len(set(provided_roots)) or set(provided_roots).intersection(
            roots
        ):
            raise ValueError("all M8 partition seed roots must be distinct")
        if dict(namespaces) != expected_roots:
            raise ValueError(f"{name} seed namespaces must match the isolated M8a proposal")
        for seed in provided_roots:
            roots.append(seed)
        sequence_counts[name] = expected_count or 0
    if len(roots) != len(set(roots)):
        raise ValueError("all M8 partition seed roots must be distinct")
    if set(roots).intersection(_FORBIDDEN_SEED_ROOTS):
        raise ValueError("M8 seed roots must not overlap M5/M6/M7 namespaces")
    _require(
        partitions.get("historical_inputs_excluded"),
        ["M5f", "M5h", "M5j", "M6b", "M6g", "M6h", "M7b"],
        name="historical input exclusion",
    )
    validation = _mapping(partitions.get("validation"), name="partitions.validation")
    _require(
        validation.get("policies"),
        ["historical_frozen_B", "one_training_selected_anchored_policy"],
        name="validation policies",
    )
    _require(validation.get("new_independent_partition"), True, name="validation independence")
    _require(validation.get("selection_repeated"), False, name="validation selection")
    _require(
        validation.get("if_training_winner_is_B"),
        "do not execute validation; close negative exploratory result",
        name="B-winner validation gate",
    )
    future_final = _mapping(partitions.get("future_final"), name="partitions.future_final")
    _require(
        future_final.get("design_status"),
        "requires separate future design and explicit authorization",
        name="future final authorization",
    )
    _require(future_final.get("automatic_after_validation"), False, name="future final chaining")
    derivation = _mapping(root.get("seed_derivation"), name="seed_derivation")
    _require(derivation.get("protocol_version_word"), 1295337521, name="seed protocol word")
    _require(
        derivation.get("partition_codes"),
        {"training": 801, "validation": 802, "future_final": 803},
        name="partition codes",
    )
    _require(derivation.get("stream_codes"), _STREAM_CODES, name="stream codes")
    _require(derivation.get("displayed_run_index_origin"), 1, name="displayed run index origin")
    _require(derivation.get("spawned_run_index_origin"), 0, name="spawned run index origin")
    _require(derivation.get("streams_generated_in_M8a"), False, name="M8a RNG generation")
    _require(
        partitions.get("seed_roots_are_proposed_not_generated"), True, name="seed proposal status"
    )
    _require(partitions.get("historical_seed_roots_reused"), False, name="historical seed reuse")
    return tuple(roots), sequence_counts["training"], sequence_counts["validation"]


def validate_m8a_anchored_study(value: object) -> M8AStudyDesign:
    """Validate the exact M8a design; it does not create streams or run anything."""

    root = _mapping(value, name="M8a design")
    _require(root.get("schema_version"), "m8a.anchored-study.v1", name="schema_version")
    _require(root.get("study_id"), _STUDY_ID, name="study_id")
    _require(root.get("design_status"), "proposed", name="design_status")
    _require(root.get("execution_authorized"), False, name="execution_authorized")
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

    profile = _mapping(root.get("profile"), name="profile")
    for key, expected in {
        "model": "anchored_reconstructed_offline",
        "parent_reconstruction_profile": "reconstructed_offline",
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
        "source_alignment_claim": False,
    }.items():
        _require(profile.get(key), expected, name=f"profile.{key}")
    _require_close(profile.get("real_channel_gain"), 0.75, name="real channel gain")
    _require_close(profile.get("gamma_b_eff_db"), 5.0, name="effective gamma_b")
    _require_close(profile.get("gamma_b_eff_linear"), 10.0**0.5, name="linear gamma_b")
    _require_close(profile.get("sigma_squared"), expected_sigma_squared(), name="sigma_squared")
    _require(
        profile.get("sigma_squared_formula"),
        "4*a*a / 10^(gamma_b_eff_db/10)",
        name="sigma formula",
    )

    anchored = _mapping(root.get("anchored_profile"), name="anchored_profile")
    _require(anchored.get("nominal_prior_anchor_mu0"), list(_ANCHOR), name="anchor")
    _require(anchored.get("initial_fluctuating_iq"), list(_ZERO), name="anchored initial state")
    _require(anchored.get("initial_full_iq"), list(_ANCHOR), name="anchored initial full")
    _require(
        anchored.get("initial_full_equals_fluctuating_plus_anchor"),
        True,
        name="state decomposition",
    )
    _require(
        anchored.get("anchor_is_channel_truth_or_oracle_csi"), False, name="anchor truth claim"
    )
    _require(
        anchored.get("historical_zero_anchor_profile"),
        {
            "mu0": [0.0, 0.0],
            "initial_fluctuating_iq": [0.42, 0.91],
            "initial_full_iq": [0.42, 0.91],
        },
        name="historical profile",
    )
    _require_close(anchored.get("shared_beta"), 0.7, name="beta")
    _require(
        anchored.get("same_initial_predictions_expected"), True, name="initial prediction invariant"
    )

    sequence = _mapping(root.get("sequence_design"), name="sequence_design")
    for key, expected in {
        "symbols_per_run_F": 256,
        "information_bits_per_run": 512,
        "same_reference_sequence_across_all_arms_within_run": True,
        "one_noise_realization_per_run_shared_by_all_arms": True,
        "channel_truth_passed_to_receiver": False,
        "decoder_calls_per_arm_sequence_target": 1,
    }.items():
        _require(sequence.get(key), expected, name=f"sequence_design.{key}")

    policies = _validate_policy_grid(root)
    roots, training_count, validation_count = _validate_partitions(root)
    _require(
        root.get("classification"),
        "proposed reconstructed research design; not executed; not optimized; not performance evidence; not source-faithful",
        name="classification",
    )

    selection = _mapping(root.get("selection"), name="selection")
    for key, expected in {
        "training_only": True,
        "eligibility": "40 complete valid records for candidate; no completed-only pooling",
        "primary": "minimum pooled raw integer-count BER among eligible arms",
        "tie_break_order": [
            "lower pooled raw-count SER",
            "lower absolute K_scale",
            "alpha_prime closest to 1.0",
            "lexicographically lower candidate_id",
        ],
        "frozen_B_may_win": True,
        "if_frozen_B_wins": "end negative exploratory result; do not promote runner-up or run same-policy adaptive validation",
        "training_statistics": "exploratory selection only; not confirmatory",
    }.items():
        _require(selection.get(key), expected, name=f"selection.{key}")

    failure = _mapping(root.get("failure_policy"), name="failure_policy")
    for key, expected in {
        "retain_success_and_failure_records": True,
        "invalid_or_incomplete_candidate": "ineligible",
        "finite_high_error_trajectory": "retain all observed errors",
        "zero_error_imputation": False,
        "maximum_error_imputation": False,
        "silent_exclusion": False,
        "seed_replacement": False,
        "incomplete_frozen_B": "block paired winner selection",
    }.items():
        _require(failure.get(key), expected, name=f"failure_policy.{key}")

    workload = _mapping(root.get("workload"), name="workload")
    for key, expected in {
        "training_sequences": 40,
        "training_arms_per_sequence": 8,
        "training_decoder_passes": 320,
        "training_policy_symbol_passes": 81920,
        "training_unique_received_samples": 81920,
        "validation_sequences": 40,
        "validation_arms_per_sequence": 2,
        "validation_decoder_passes": 80,
        "validation_policy_symbol_passes": 20480,
        "validation_unique_received_samples": 81920,
        "single_process": True,
        "multiprocessing": False,
        "atomic_checkpoint_per_sequence": True,
        "runtime_or_rss_estimate": None,
        "actual_budget_requires_separate_approval": True,
    }.items():
        _require(workload.get(key), expected, name=f"workload.{key}")
    gates = _mapping(root.get("authorization_gates"), name="authorization_gates")
    for key, expected in {
        "M8a_execution_allowed": False,
        "M8b_requires_separate_run_specific_approval": True,
        "training_to_validation_automatic": False,
        "validation_to_final_automatic": False,
        "approved_config_created_in_M8a": False,
    }.items():
        _require(gates.get(key), expected, name=f"authorization_gates.{key}")

    return M8AStudyDesign(
        study_id=_STUDY_ID,
        design_status="proposed",
        execution_authorized=False,
        execution_scope="none",
        candidates=policies,
        training_sequence_count=training_count,
        validation_sequence_count=validation_count,
        expected_training_decoder_passes=training_count * len(policies),
        proposed_seed_roots=roots,
    )


def guard_m8a_execution(
    value: object,
    *,
    rng_callback: Callable[[], object],
    receiver_callback: Callable[[], object],
    data_callback: Callable[[], object],
) -> NoReturn:
    """Validate the draft, then block before any supplied execution callback."""

    validate_m8a_anchored_study(value)
    raise M8AExecutionBlocked(
        "M8a is an unauthorized preparation-only design; no data, RNG, or receiver execution is allowed"
    )
