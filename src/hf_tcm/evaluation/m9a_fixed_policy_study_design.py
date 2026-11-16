"""Validation and execution guard for the proposed M9a fixed-policy study.

This module validates a design only. It never materializes SeedSequence child
streams, generates observations, or invokes a receiver/decoder.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class M9AExecutionBlocked(RuntimeError):
    """Raised when the unauthorized M9a draft is offered for execution."""


@dataclass(frozen=True, slots=True)
class M9APolicy:
    candidate_id: str
    alpha_prime: float
    k_tilde: tuple[float, float]
    mu0: tuple[float, float]
    initial_fluctuating_iq: tuple[float, float]
    initial_full_iq: tuple[float, float]
    beta: float


@dataclass(frozen=True, slots=True)
class M9AStudyDesign:
    study_id: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    run_count: int
    symbols_per_sequence: int
    policies: tuple[M9APolicy, ...]
    expected_decoder_calls: int
    expected_policy_records: int
    expected_received_samples: int


_STUDY_ID = "m9_fixed_anchored_vs_frozen_v1"
_PROTOCOL_WORD = 1295337521
_PARTITION_CODE = 901
_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37, "metadata": 41}
_SEED_ROOTS = {
    "data": 2027020101,
    "noise": 2027020102,
    "bootstrap": 2027020103,
    "metadata": 2027020104,
}
_FORBIDDEN_ROOTS = frozenset(
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
        2027011001,
        2027011002,
        2027011003,
        2027011004,
        2027012001,
        2027012002,
        2027012003,
        2027012004,
        2027013001,
        2027013002,
        2027013003,
        2027013004,
    }
)


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _equal(actual: object, expected: object, *, name: str) -> None:
    if actual != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def _pair(value: object, *, name: str) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"{name} must be an I/Q pair")
    result: list[float] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, int | float):
            raise ValueError(f"{name} must contain finite numbers")
        number = float(component)
        if not math.isfinite(number):
            raise ValueError(f"{name} must contain finite numbers")
        result.append(number)
    return result[0], result[1]


def validate_m9a_fixed_policy_study(value: object) -> M9AStudyDesign:
    """Validate the fixed M9a draft without creating random streams."""
    root = _mapping(value, name="M9a design")
    _equal(root.get("schema_version"), "m9a.fixed-policy-study.v1", name="schema_version")
    _equal(root.get("experiment_id"), _STUDY_ID, name="experiment_id")
    _equal(root.get("design_status"), "proposed", name="design_status")
    _equal(root.get("execution_authorized"), False, name="execution_authorized")
    _equal(root.get("execution_scope"), "none", name="execution_scope")

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
        "author_mapping_status": "SOURCE_UNRESOLVED",
        "open_science_questions": ["SCI-02", "SCI-03", "SCI-METRIC-02"],
    }.items():
        _equal(scientific.get(key), expected, name=f"scientific_status.{key}")

    profile = _mapping(root.get("profile"), name="profile")
    for key, expected in {
        "model": "reconstructed_offline",
        "channel_memory_L": 1,
        "delay_samples": 0,
        "modulation": "normalized_8PSK",
        "pulse_shape": "rectangular_ZOH",
        "samples_per_symbol": 8,
        "mapping": "ADR-002 reconstructed mapping",
        "likelihood": "ADR-005 reconstructed pseudo-likelihood",
        "observation": "ADR-012 observed IQ",
        "decoder": "ADR-013 conditional full Viterbi",
        "noise": "ADR-015 independent circular complex AWGN",
        "physical_hf_ebn0": False,
        "channel_truth_passed_to_receiver": False,
    }.items():
        _equal(profile.get(key), expected, name=f"profile.{key}")
    if profile.get("real_channel_gain") != 0.75 or profile.get("gamma_b_eff_db") != 5.0:
        raise ValueError("gain/gamma profile mismatch")
    sigma = profile.get("sigma_squared")
    expected_sigma = 4.0 * 0.75**2 / 10 ** (5.0 / 10.0)
    if (
        isinstance(sigma, bool)
        or not isinstance(sigma, int | float)
        or not math.isclose(float(sigma), expected_sigma, rel_tol=0.0, abs_tol=1e-15)
    ):
        raise ValueError("sigma_squared violates ADR-015 scaling")
    sequence = _mapping(root.get("sequence_design"), name="sequence_design")
    _equal(sequence.get("run_count"), 100, name="run_count")
    _equal(sequence.get("symbols_per_sequence_F"), 256, name="F")
    _equal(sequence.get("information_bits_per_sequence"), 512, name="information bits")
    _equal(sequence.get("same_received_buffer_for_both_policies"), True, name="paired received")
    _equal(sequence.get("decoder_calls_per_policy_sequence"), 1, name="decode count")
    _equal(sequence.get("absolute_sample_origin"), 0, name="sample origin")
    _equal(sequence.get("absolute_symbol_origin"), 0, name="symbol origin")
    _equal(sequence.get("estimator_tick_origin"), 0, name="estimator tick origin")

    policy_rows = root.get("policies")
    expected_rows = [
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
    if policy_rows != expected_rows:
        raise ValueError("policies must be exactly the fixed B and anch_a085_k025 pair")
    policies = tuple(
        M9APolicy(
            candidate_id=str(row["candidate_id"]),
            alpha_prime=float(row["alpha_prime"]),
            k_tilde=_pair(row["k_tilde"], name="k_tilde"),
            mu0=_pair(row["mu0"], name="mu0"),
            initial_fluctuating_iq=_pair(row["initial_fluctuating_iq"], name="initial state"),
            initial_full_iq=_pair(row["initial_full_iq"], name="full state"),
            beta=float(row["beta"]),
        )
        for row in policy_rows
    )
    if any(policy.initial_full_iq != (0.42, 0.91) for policy in policies):
        raise ValueError("both policies must share the initial full estimate")

    partition = _mapping(root.get("partition"), name="partition")
    _equal(partition.get("name"), "evaluation", name="partition name")
    _equal(partition.get("run_count"), 100, name="run_count")
    _equal(partition.get("seed_namespaces"), _SEED_ROOTS, name="seed namespace roots")
    roots = list(_SEED_ROOTS.values())
    if len(set(roots)) != 4 or set(roots).intersection(_FORBIDDEN_ROOTS):
        raise ValueError("M9 seed namespaces must be distinct from M5-M8 roots")
    derivation = _mapping(root.get("seed_derivation"), name="seed_derivation")
    for key, expected in {
        "generator": "PCG64",
        "protocol_version_word": _PROTOCOL_WORD,
        "partition_code": _PARTITION_CODE,
        "stream_codes": _STREAM_CODES,
        "run_index_origin": 0,
        "run_order": "ascending run_index 0..99",
        "child_streams_materialized_in_M9a": False,
    }.items():
        _equal(derivation.get(key), expected, name=f"seed_derivation.{key}")

    planned_runs = partition.get("planned_runs")
    if not isinstance(planned_runs, list) or len(planned_runs) != 100:
        raise ValueError("planned_runs must contain exactly 100 explicit run IDs")
    expected_ids: set[str] = set()
    for index, run in enumerate(planned_runs):
        row = _mapping(run, name=f"planned_runs[{index}]")
        expected_id = f"{_STUDY_ID}:evaluation:run-{index + 1:03d}"
        _equal(row.get("run_index"), index, name="run_index")
        _equal(row.get("run_id"), expected_id, name="run_id/order")
        if expected_id in expected_ids:
            raise ValueError("planned run IDs must be unique")
        expected_ids.add(expected_id)
        streams = _mapping(row.get("streams"), name="run streams")
        _equal(set(streams), {"data", "noise", "metadata"}, name="run stream set")
        for stream in ("data", "noise", "metadata"):
            entry = _mapping(streams[stream], name=f"{stream} provenance")
            expected_key = [_PROTOCOL_WORD, _PARTITION_CODE, index, _STREAM_CODES[stream]]
            _equal(entry.get("master_seed"), _SEED_ROOTS[stream], name=f"{stream} root")
            _equal(entry.get("spawn_key"), expected_key, name=f"{stream} spawn key")
            _equal(
                entry.get("child_stream_materialized"), False, name="child stream materialization"
            )
            if "derived_seed" in entry:
                raise ValueError("M9a must not materialize derived child seeds")
    bootstrap = _mapping(partition.get("bootstrap_stream"), name="bootstrap_stream")
    _equal(bootstrap.get("master_seed"), _SEED_ROOTS["bootstrap"], name="bootstrap root")
    _equal(
        bootstrap.get("spawn_key"),
        [_PROTOCOL_WORD, _PARTITION_CODE, 0, _STREAM_CODES["bootstrap"]],
        name="bootstrap spawn key",
    )
    _equal(bootstrap.get("child_stream_materialized"), False, name="bootstrap materialization")

    statistics = _mapping(root.get("statistics"), name="statistics")
    for key, expected in {
        "primary_estimand": "pooled raw-count BER(anchor) - BER(frozen_B)",
        "secondary_estimand": "pooled raw-count SER(anchor) - SER(frozen_B)",
        "cluster_unit": "one complete independent coded sequence",
        "bootstrap_method": "ADR-014 paired cluster bootstrap",
        "bootstrap_replicates": 2000,
        "confidence_level": 0.95,
        "interval": "percentile",
        "quantile_method": "numpy.quantile(method='linear')",
        "individual_bits_are_not_independent_clusters": True,
        "equivalence_or_noninferiority_claim": False,
    }.items():
        _equal(statistics.get(key), expected, name=f"statistics.{key}")

    failure = _mapping(root.get("failure_policy"), name="failure_policy")
    for key, expected in {
        "complete_valid_pairs_required": 100,
        "incomplete_or_invalid_sequence": "report explicitly; blocks full-design inference",
        "replace_seed_or_sequence": False,
        "data_dependent_stopping": False,
        "zero_error_handling": "retain valid zero counts without correction",
        "finite_high_error_trajectory": "retain",
        "policy_replacement_or_fallback": False,
        "missing_output_imputation": False,
    }.items():
        _equal(failure.get(key), expected, name=f"failure_policy.{key}")

    workload = _mapping(root.get("workload"), name="workload")
    for key, expected in {
        "unique_received_buffers": 100,
        "decoder_passes": 200,
        "policy_records": 200,
        "information_bits_per_policy": 51200,
        "coded_symbols_per_policy": 25600,
        "unique_received_samples": 204800,
        "single_process": True,
        "multiprocessing": False,
        "atomic_checkpoint_per_sequence": True,
        "proposed_runtime_budget_seconds": 900,
        "proposed_periodic_rss_monitoring_bytes": 1610612736,
        "runtime_or_rss_is_measured_in_M9a": False,
    }.items():
        _equal(workload.get(key), expected, name=f"workload.{key}")

    limitations = _mapping(root.get("scientific_limitations"), name="scientific_limitations")
    for key, expected in {
        "policy_selected_posthoc_from_M8": True,
        "M9_preregistered_before_M8": False,
        "M8_runner_up_interval_is_confirmatory": False,
        "M5j_is_independent_validation_for_M9": False,
        "constant_gain_generalizes_to_variable_or_physical_HF": False,
        "source_faithful_claim": False,
    }.items():
        _equal(limitations.get(key), expected, name=f"scientific_limitations.{key}")

    auth = _mapping(root.get("authorization"), name="authorization")
    _equal(auth.get("run_specific_approval_required"), True, name="approval gate")
    _equal(auth.get("approved_run_config_created"), False, name="approved config")
    _equal(
        root.get("output_namespace"),
        "outputs/m9_fixed_policy_comparison/m9_fixed_anchored_vs_frozen_v1",
        name="output namespace",
    )
    return M9AStudyDesign(
        study_id=_STUDY_ID,
        design_status="proposed",
        execution_authorized=False,
        execution_scope="none",
        run_count=100,
        symbols_per_sequence=256,
        policies=policies,
        expected_decoder_calls=200,
        expected_policy_records=200,
        expected_received_samples=204800,
    )


def guard_m9a_execution(
    value: object,
    *,
    callbacks: Mapping[str, Callable[[], object]],
    executor: Callable[[], object],
) -> None:
    """Validate authorization before any supplied side-effect callback."""
    try:
        design = validate_m9a_fixed_policy_study(value)
    except (TypeError, ValueError) as exc:
        raise M9AExecutionBlocked("M9a draft failed validation") from exc
    if (
        design.design_status != "approved"
        or design.execution_authorized is not True
        or design.execution_scope != "m9_fixed_policy_only"
    ):
        raise M9AExecutionBlocked(
            f"M9a execution blocked: {design.design_status} / "
            f"{str(design.execution_authorized).lower()} / {design.execution_scope}"
        )
    del callbacks, executor
    raise M9AExecutionBlocked("M9a draft is a design artifact, not an executable approval")
