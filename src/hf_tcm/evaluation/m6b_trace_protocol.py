"""Non-executable M6b fresh-seed trace protocol and trace JSON schema.

This module validates a proposed diagnostic and serializes already available
trace records. It does not construct RNG streams, generate data/noise, call a
receiver, or write run outputs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
from numpy.typing import NDArray

M6B_PROTOCOL_STATUS = (
    "validated fresh-seed causal trace protocol, NOT executed diagnostic experiment, "
    "NOT new BER evidence, NOT established root cause"
)
M6B_OUTPUT_ROOT = "outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1"
_CONFIG_KEYS = {
    "schema_version",
    "experiment_id",
    "design_version",
    "design_status",
    "execution_authorized",
    "execution_scope",
    "purpose",
    "scientific_scope",
    "run_design",
    "receiver_policies",
    "clock_contract",
    "seed_derivation",
    "trace_schema",
    "comparison",
    "storage",
    "resource_policy",
    "failure_policy",
    "claim_boundary",
    "authorization",
}
_ACCEPTED_ADRS = [
    "ADR-001",
    "ADR-002",
    "ADR-003",
    "ADR-004",
    "ADR-005",
    "ADR-006",
    "ADR-007",
    "ADR-008",
    "ADR-010",
    "ADR-012",
    "ADR-013",
    "ADR-014",
    "ADR-015",
]
_HISTORICAL_ROOTS = {
    2026102801,
    2026102802,
    2026102803,
    2026102901,
    2026102902,
    2026102903,
    2026110101,
    2026110102,
    2026110103,
    3940591365597190145,
}
_STREAM_CODES = {"data": 11, "noise": 23, "metadata": 41}
_MODE_KEYS = {
    "receiver_mode",
    "received_sha256",
    "initial_state",
    "symbol_trace",
    "frozen_metric_history",
    "final_state",
    "decoded_hypothesis_path",
    "decoded_information_bits",
    "best_conditional_path_cost",
    "decoded_path_valid",
    "decode_call_count",
}
_ROW_KEYS = {
    "absolute_symbol_index",
    "estimator_time_index",
    "sequence_local_position",
    "processing_segment_index",
    "processing_segment_local_position",
    "sample_window",
    "prediction_cutoff_sample_index",
    "observation_cutoff_sample_index",
    "pre_fluctuating_iq",
    "pre_full_iq",
    "mu0",
    "observed_iq_mean",
    "candidate_metrics",
    "hypothesis_ids",
    "phase_indices",
    "edge_mode",
    "posterior_input",
    "posterior_input_kind",
    "posterior_transition_provenance",
    "posterior",
    "transition_predicted_posterior_q",
    "predicted_iq",
    "alpha_prime",
    "k_tilde",
    "innovation_operand",
    "innovation_provenance",
    "post_fluctuating_iq",
    "post_full_iq",
    "fluctuating_increment",
    "full_increment",
    "posterior_sum",
    "posterior_normalized",
    "decoded_hypothesis_id",
}
_ARRAY_KEYS = {"dtype", "shape", "values"}
_B_POLICY = {
    "policy": "mismatched_frozen",
    "alpha_prime": 1.0,
    "K_tilde": [0.0, 0.0],
    "mu0": [0.0, 0.0],
}
_C_POLICY = {
    "policy": "mismatched_adaptive",
    "alpha_prime": 0.85,
    "K_tilde": [0.35, -0.2],
    "mu0": [0.0, 0.0],
}

FloatArray = NDArray[np.float64]
T = TypeVar("T")


class M6BExecutionBlocked(RuntimeError):
    """The proposed or incomplete diagnostic has not passed user authorization."""


@dataclass(frozen=True, slots=True)
class M6BTraceProtocol:
    experiment_id: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    canonical_json: str

    @property
    def run_ids(self) -> tuple[str, ...]:
        parsed = json.loads(self.canonical_json)
        return tuple(parsed["run_design"]["planned_run_ids"])

    @property
    def output_root(self) -> str:
        parsed = json.loads(self.canonical_json)
        return str(parsed["storage"]["root"])


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{name} keys mismatch; missing={sorted(expected.difference(value))}, "
            f"extra={sorted(set(value).difference(expected))}"
        )


def _finite_real(value: object, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return result


def _sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value} is forbidden")


def load_m6b_trace_diagnostic_config(path: str | Path) -> M6BTraceProtocol:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read M6b trace configuration: {exc}") from exc
    return validate_m6b_trace_diagnostic_config(value)


def validate_m6b_trace_diagnostic_config(value: object) -> M6BTraceProtocol:
    """Validate the complete proposed protocol without deriving RNG streams."""
    root = _mapping(value, name="M6b trace configuration")
    _exact_keys(root, _CONFIG_KEYS, name="M6b trace configuration")
    if root["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    experiment_id = root["experiment_id"]
    if experiment_id != "m6b_causal_trace_20261030_v1":
        raise ValueError("experiment_id must match the isolated M6b namespace")
    if root["design_version"] != "m6b-prep-1":
        raise ValueError("design_version must be m6b-prep-1")
    if root["purpose"] != M6B_PROTOCOL_STATUS:
        raise ValueError("purpose must preserve the M6b preparation evidence boundary")
    status = root["design_status"]
    if status not in ("proposed", "approved_diagnostic"):
        raise ValueError("design_status must be proposed or approved_diagnostic")
    if not isinstance(root["execution_authorized"], bool):
        raise ValueError("execution_authorized must be an explicit boolean")
    scope = root["execution_scope"]
    authorization = root["authorization"]
    if status == "proposed":
        if (
            root["execution_authorized"] is not False
            or scope != "none"
            or authorization is not None
        ):
            raise ValueError("proposed draft must remain unauthorized with scope none")
    else:
        if root["execution_authorized"] is not True or scope != "m6b_trace_only":
            raise ValueError("approved diagnostic requires explicit authorization and exact scope")
        approval = _mapping(authorization, name="authorization")
        _exact_keys(
            approval,
            {
                "explicit_user_approval",
                "authorization_id",
                "approved_at_utc",
                "source_draft_sha256",
                "authorization_provenance",
            },
            name="authorization",
        )
        if approval["explicit_user_approval"] is not True:
            raise ValueError("authorization must record explicit user approval")
        if (
            not isinstance(approval["authorization_id"], str)
            or not approval["authorization_id"].strip()
        ):
            raise ValueError("authorization_id must be explicit")
        if not isinstance(approval["approved_at_utc"], str) or not approval[
            "approved_at_utc"
        ].endswith("Z"):
            raise ValueError("approved_at_utc must be an explicit UTC timestamp ending in Z")
        _sha256(approval["source_draft_sha256"], name="source_draft_sha256")
        if approval["authorization_provenance"] != (
            "explicit user authorization provided through this M6b-run Codex instruction"
        ):
            raise ValueError("authorization provenance must identify this M6b-run instruction")

    science = _mapping(root["scientific_scope"], name="scientific_scope")
    if (
        science.get("profile") != "reconstructed_offline"
        or science.get("paper_exact") is not False
        or science.get("receiver_enabled") is not False
        or science.get("accepted_adrs") != _ACCEPTED_ADRS
        or science.get("proposed_adrs") != ["ADR-009", "ADR-011"]
        or science.get("open_questions") != ["SCI-02", "SCI-03", "SCI-METRIC-02"]
    ):
        raise ValueError("scientific scope must preserve accepted ADRs, open questions, and limits")
    channel = _mapping(science.get("channel"), name="scientific_scope.channel")
    waveform = _mapping(science.get("waveform"), name="scientific_scope.waveform")
    observation = _mapping(science.get("observation"), name="scientific_scope.observation")
    likelihood = _mapping(science.get("likelihood"), name="scientific_scope.likelihood")
    decoder = _mapping(science.get("decoder"), name="scientific_scope.decoder")
    noise = _mapping(science.get("noise"), name="scientific_scope.noise")
    if (
        channel != {"path_count": 1, "real_gain_a": 0.75, "path_delays_samples": [0]}
        or waveform
        != {"modulation": "normalized_8PSK", "pulse": "rectangular_zoh", "samples_per_symbol": 8}
        or observation
        != {
            "adr": "ADR-012",
            "profile_id": "adr012_l1_real_mean8",
            "iq_rule": "(-Im(received), Re(received))",
            "sample_reduction": "arithmetic_mean_exactly_8",
        }
        or likelihood
        != {
            "adr": "ADR-005",
            "kind": "exp_negative_beta_project_reconstruction_metric",
            "beta": 0.7,
        }
        or decoder
        != {"adr": "ADR-013", "kind": "conditional_full_viterbi_on_frozen_metric_history"}
        or noise.get("adr") != "ADR-015"
        or noise.get("distribution") != "independent_circular_complex_sample_awgn"
        or noise.get("gamma_b_eff_db") != 5.0
        or noise.get("physical_hf_eb_n0") is not False
    ):
        raise ValueError(
            "scientific profile or accepted reconstructed policy differs from M6b draft"
        )
    expected_sigma = 4.0 * 0.75**2 / (10.0 ** (5.0 / 10.0))
    sigma = _finite_real(noise.get("sigma_squared"), name="sigma_squared")
    if not math.isclose(sigma, expected_sigma, rel_tol=1e-14, abs_tol=0.0):
        raise ValueError("sigma_squared violates ADR-015 effective gamma conversion")

    design = _mapping(root["run_design"], name="run_design")
    _exact_keys(
        design,
        {
            "independent_sequences",
            "symbols_per_sequence_F",
            "information_bits_per_sequence",
            "planned_run_ids",
            "run_order",
            "same_received_buffer_for_B_and_C",
            "performance_estimand",
            "parameter_search",
        },
        name="run_design",
    )
    expected_ids = tuple(f"{experiment_id}:run-{index:03d}" for index in range(1, 4))
    if (
        design["independent_sequences"] != 3
        or design["symbols_per_sequence_F"] != 32
        or design["information_bits_per_sequence"] != 64
        or tuple(design["planned_run_ids"]) != expected_ids
        or len(set(design["planned_run_ids"])) != 3
        or design["run_order"] != "ascending run index; one process; fixed manifest order"
        or design["same_received_buffer_for_B_and_C"] is not True
        or design["performance_estimand"] is not None
        or design["parameter_search"] is not False
    ):
        raise ValueError("run design must be exactly three paired F=32 diagnostic sequences")

    policies = _mapping(root["receiver_policies"], name="receiver_policies")
    _exact_keys(
        policies,
        {"shared", "B", "C", "parity_required", "only_difference", "historical_policy_source"},
        name="receiver_policies",
    )
    shared = policies["shared"]
    if shared != {
        "initial_fluctuating_iq": [0.42, 0.91],
        "initial_full_iq": [0.42, 0.91],
        "beta": 0.7,
        "mu0": [0.0, 0.0],
    }:
        raise ValueError(
            "shared B/C initial state, beta, and mu0 must match the historical profile"
        )
    if policies["B"] != _B_POLICY or policies["C"] != _C_POLICY:
        raise ValueError("B/C policies must exactly match the M5j fixed comparison")
    if (
        policies["parity_required"] is not True
        or policies["only_difference"] != "registered coefficient update policy"
        or not isinstance(policies["historical_policy_source"], str)
        or "M5j" not in policies["historical_policy_source"]
    ):
        raise ValueError("B/C pairing and historical policy provenance must be explicit")

    clocks = _mapping(root["clock_contract"], name="clock_contract")
    if clocks != {
        "absolute_sample_origin": 0,
        "absolute_symbol_origin": 0,
        "initial_estimator_time_index": 0,
        "sequence_local_symbol_position_origin": 0,
        "processing_segment_policy": "one monolithic sequence; segment_index=0; no reset",
        "window_rule": "[O+8f, O+8f+7]",
        "prediction_cutoff_rule": "O+8f-1",
        "observation_cutoff_rule": "O+8f+7",
        "clocks_are_independent_labels": True,
    }:
        raise ValueError("clock contract must preserve exact 8sps absolute label semantics")

    seed = _mapping(root["seed_derivation"], name="seed_derivation")
    if (
        seed.get("algorithm")
        != "NumPy SeedSequence(master_seed, spawn_key=(protocol_version_word, diagnostic_namespace_code, zero_based_run_index, stream_code)).generate_state(1,dtype=uint64)[0]; initialize PCG64 with derived seed"
        or seed.get("protocol_version_word") != 1295337521
        or seed.get("diagnostic_namespace_code") != 306
        or seed.get("spawn_key_fields")
        != [
            "protocol_version_word",
            "diagnostic_namespace_code",
            "zero_based_run_index",
            "stream_code",
        ]
        or seed.get("stream_codes") != _STREAM_CODES
        or seed.get("run_index_origin") != 0
        or seed.get("generated_seed_bits") != 64
        or seed.get("bit_generator") != "PCG64"
        or seed.get("planned_seed_manifest_contains_samples") is not False
    ):
        raise ValueError("M6b seed derivation contract is incomplete or reordered")
    roots = _mapping(seed.get("master_seed_roots"), name="master_seed_roots")
    if set(roots) != {"data", "noise", "metadata"}:
        raise ValueError("M6b must use separate data, noise, and metadata seed namespaces")
    root_values = tuple(_integer(roots[key], name=f"{key} master seed", minimum=1) for key in roots)
    if len(set(root_values)) != 3 or set(root_values).intersection(_HISTORICAL_ROOTS):
        raise ValueError("M6b seed roots must be distinct from each other and historical roots")
    if set(seed.get("forbidden_historical_master_seeds", ())) != _HISTORICAL_ROOTS:
        raise ValueError("historical M5 seed roots must be explicitly reserved")
    if seed.get("paired_received_hash_rule") != (
        "SHA-256 of the exact contiguous complex128 received bytes consumed by M6a; B and C must record the same digest"
    ):
        raise ValueError("paired received hash policy must be explicit")

    trace_schema = _mapping(root["trace_schema"], name="trace_schema")
    if (
        trace_schema.get("schema_version") != 1
        or trace_schema.get("serialization")
        != "canonical UTF-8 JSON, sorted keys, compact separators, allow_nan=false"
        or trace_schema.get("array_encoding") != "object with dtype, exact shape, and nested values"
        or trace_schema.get("nonfinite_policy")
        != "reject the trace and write a failure record; never serialize NaN or Infinity"
        or trace_schema.get("transition_predicted_posterior_q")
        != {"status": "unavailable", "value": None}
        or trace_schema.get("received_samples_persisted") is not False
        or trace_schema.get("reference_bits_in_receiver_trace") is not False
    ):
        raise ValueError("trace schema must mark unavailable q and prohibit truth/sample leakage")
    if "innovation" not in trace_schema or set(trace_schema["innovation"]) != {
        "source",
        "formula",
    }:
        raise ValueError("derived innovation provenance/formula must be explicit")
    if trace_schema["required_run_fields"] != [
        "run_id",
        "config_sha256",
        "software_provenance",
        "received_sha256",
        "mode_B",
        "mode_C",
        "paired_comparison",
        "trace_integrity_status",
    ]:
        raise ValueError("required run trace fields are incomplete")
    if trace_schema.get("required_symbol_fields") != sorted(_ROW_KEYS):
        raise ValueError("required symbol trace fields must match the complete schema")

    comparison = _mapping(root["comparison"], name="comparison")
    if (
        comparison.get("floating_rtol") != 1e-12
        or comparison.get("floating_atol") != 1e-14
        or comparison.get("trace_difference_establishes_root_cause") is not False
        or comparison.get("required_divergence_labels")
        != [
            "first_post_state_divergence_symbol",
            "first_candidate_metric_divergence_symbol",
            "first_posterior_divergence_symbol",
            "decoded_path_divergence_positions",
        ]
    ):
        raise ValueError("comparison tolerances or divergence contract differ from draft")

    storage = _mapping(root["storage"], name="storage")
    if storage.get("root") != M6B_OUTPUT_ROOT or storage.get("raw_received_samples") != (
        "not persisted by the trace adapter; received_sha256 only"
    ):
        raise ValueError(
            "M6b outputs require a separate namespace and no persisted received samples"
        )
    resource = _mapping(root["resource_policy"], name="resource_policy")
    if (
        resource.get("candidate_processes") != 1
        or resource.get("multiprocessing") is not False
        or resource.get("sequences") != 3
        or resource.get("symbols_per_sequence") != 32
        or resource.get("full_per_symbol_B_C_trace") is not True
        or resource.get("atomic_checkpoint_per_run") is not True
        or resource.get("runtime_or_ram_estimate") is not None
        or resource.get("benchmark_run") is not False
    ):
        raise ValueError("resource policy must remain a small single-process candidate only")
    if status == "proposed":
        if resource.get("resource_limits") is not None:
            raise ValueError("proposed draft resource limits must remain unset")
    elif resource.get("resource_limits") != {
        "wall_clock_budget_seconds": 300,
        "process_rss_budget_bytes": 536870912,
        "rss_monitoring": "periodic_observational_not_hard_os_limit",
    }:
        raise ValueError(
            "approved diagnostic must preserve the explicitly authorized resource limits"
        )

    canonical = json.dumps(root, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return M6BTraceProtocol(
        experiment_id=experiment_id,
        design_status=str(status),
        execution_authorized=bool(root["execution_authorized"]),
        execution_scope=str(scope),
        canonical_json=canonical,
    )


def planned_m6b_seed_provenance(config: M6BTraceProtocol) -> tuple[dict[str, object], ...]:
    """Return metadata-only master roots and spawn keys; never create RNG streams."""
    raw = json.loads(config.canonical_json)
    seed = raw["seed_derivation"]
    roots = seed["master_seed_roots"]
    records: list[dict[str, object]] = []
    for zero_based_index, run_id in enumerate(raw["run_design"]["planned_run_ids"]):
        streams: dict[str, object] = {}
        for name, code in seed["stream_codes"].items():
            spawn_key = (
                seed["protocol_version_word"],
                seed["diagnostic_namespace_code"],
                zero_based_index,
                code,
            )
            streams[name] = {
                "master_seed": roots[name],
                "spawn_key": spawn_key,
                "bit_generator": "PCG64",
                "derived_seed": "derive only after separate execution authorization",
            }
        records.append(
            {
                "run_id": run_id,
                "zero_based_run_index": zero_based_index,
                "streams": streams,
            }
        )
    return tuple(records)


def guarded_m6b_execution(value: object, *, on_authorized: Callable[[M6BTraceProtocol], T]) -> T:
    """Run no work before approval; invoke the continuation only after all gates pass.

    This is an authorization boundary, not an M6b runner. The proposed draft
    always raises before the continuation can create RNG/data/noise or call a
    receiver.
    """
    config = validate_m6b_trace_diagnostic_config(value)
    if config.design_status != "approved_diagnostic":
        raise M6BExecutionBlocked("design_status must be approved_diagnostic")
    if config.execution_authorized is not True:
        raise M6BExecutionBlocked("execution_authorized must be true")
    if config.execution_scope != "m6b_trace_only":
        raise M6BExecutionBlocked("execution_scope must be m6b_trace_only")
    if not callable(on_authorized):
        raise ValueError("on_authorized must be a callable continuation")
    return on_authorized(config)


def _array(value: object, *, dtype: str, shape: tuple[int, ...], name: str) -> NDArray:
    wrapper = _mapping(value, name=name)
    _exact_keys(wrapper, _ARRAY_KEYS, name=name)
    if wrapper["dtype"] != dtype or tuple(wrapper["shape"]) != shape:
        raise ValueError(f"{name} must declare dtype={dtype} and shape={shape}")
    try:
        array = np.asarray(wrapper["values"], dtype=np.dtype(dtype))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name}.values do not match declared dtype/shape") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}.values must be finite with declared shape")
    return array


def _validate_symbol_row(row_value: object, *, index: int) -> Mapping[str, Any]:
    row = _mapping(row_value, name=f"symbol_trace[{index}]")
    _exact_keys(row, _ROW_KEYS, name=f"symbol_trace[{index}]")
    expected_window = tuple(range(index * 8, index * 8 + 8))
    if (
        row["absolute_symbol_index"] != index
        or row["estimator_time_index"] != index
        or row["sequence_local_position"] != index
        or row["processing_segment_index"] != 0
        or row["processing_segment_local_position"] != index
        or tuple(row["sample_window"]) != expected_window
        or row["prediction_cutoff_sample_index"] != index * 8 - 1
        or row["observation_cutoff_sample_index"] != index * 8 + 7
    ):
        raise ValueError("trace symbol/sample/estimator clocks or cutoffs are inconsistent")
    for key, shape in (
        ("pre_fluctuating_iq", (1, 2)),
        ("pre_full_iq", (1, 2)),
        ("mu0", (1, 2)),
        ("observed_iq_mean", (2,)),
        ("candidate_metrics", (16,)),
        ("posterior_input", (16,)),
        ("posterior", (16,)),
        ("predicted_iq", (16, 2)),
        ("k_tilde", (1, 2)),
        ("innovation_operand", (2,)),
        ("post_fluctuating_iq", (1, 2)),
        ("post_full_iq", (1, 2)),
        ("fluctuating_increment", (1, 2)),
        ("full_increment", (1, 2)),
    ):
        _array(row[key], dtype="float64", shape=shape, name=f"symbol_trace[{index}].{key}")
    if row["hypothesis_ids"] != list(range(16)):
        raise ValueError("trace hypotheses must preserve the canonical 16-edge order")
    phase_indices = row["phase_indices"]
    if (
        not isinstance(phase_indices, list)
        or len(phase_indices) != 16
        or any(
            isinstance(value, bool) or not isinstance(value, Integral) or not 0 <= value < 8
            for value in phase_indices
        )
    ):
        raise ValueError("phase_indices must preserve 16 actual 8PSK phase labels")
    expected_edge_mode = "first_edge" if index == 0 else "later_edge"
    expected_input_kind = "adr004_initial_prior" if index == 0 else "previous_posterior"
    expected_transition = (
        "none_first_edge" if index == 0 else "adr003_transition_then_current_metric_likelihood"
    )
    if (
        row["edge_mode"] != expected_edge_mode
        or row["posterior_input_kind"] != expected_input_kind
        or row["posterior_transition_provenance"] != expected_transition
    ):
        raise ValueError("edge mode, posterior input, and transition provenance are inconsistent")
    q = _mapping(row["transition_predicted_posterior_q"], name="transition_predicted_posterior_q")
    if q != {"status": "unavailable", "value": None}:
        raise ValueError("transition-predicted posterior q must remain marked unavailable")
    if row["innovation_provenance"] != ("derived_from_actual_B4c_posterior_observation_prediction"):
        raise ValueError("innovation must retain its derived B4c operand provenance")
    innovation = _array(
        row["innovation_operand"], dtype="float64", shape=(2,), name="innovation_operand"
    )
    observed = _array(row["observed_iq_mean"], dtype="float64", shape=(2,), name="observed_iq_mean")
    predicted = _array(row["predicted_iq"], dtype="float64", shape=(16, 2), name="predicted_iq")
    posterior = _array(row["posterior"], dtype="float64", shape=(16,), name="posterior")
    expected_innovation = np.sum(posterior[:, np.newaxis] * (observed - predicted), axis=0)
    if not np.allclose(innovation, expected_innovation, rtol=1e-12, atol=1e-14):
        raise ValueError("derived innovation does not match the declared actual B4c operands")
    if not isinstance(row["posterior_normalized"], bool) or not row["posterior_normalized"]:
        raise ValueError("complete trace rows must have a normalized finite posterior")
    posterior_sum = _finite_real(row["posterior_sum"], name="posterior_sum")
    if not math.isclose(
        float(posterior.sum()), 1.0, rel_tol=1e-10, abs_tol=1e-10
    ) or not math.isclose(posterior_sum, float(posterior.sum()), rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError("posterior values do not sum to one")
    _finite_real(row["alpha_prime"], name="alpha_prime")
    pre_fluctuating = _array(
        row["pre_fluctuating_iq"], dtype="float64", shape=(1, 2), name="pre_fluctuating_iq"
    )
    post_fluctuating = _array(
        row["post_fluctuating_iq"], dtype="float64", shape=(1, 2), name="post_fluctuating_iq"
    )
    post_full = _array(row["post_full_iq"], dtype="float64", shape=(1, 2), name="post_full_iq")
    mu0 = _array(row["mu0"], dtype="float64", shape=(1, 2), name="mu0")
    fluctuating_increment = _array(
        row["fluctuating_increment"],
        dtype="float64",
        shape=(1, 2),
        name="fluctuating_increment",
    )
    if not np.allclose(post_full, post_fluctuating + mu0, rtol=0.0, atol=1e-12):
        raise ValueError("post full_iq must equal fluctuating_iq + mu0")
    if not np.allclose(
        fluctuating_increment, post_fluctuating - pre_fluctuating, rtol=0.0, atol=1e-12
    ):
        raise ValueError("fluctuating increment must match the recorded pre/post states")
    if (
        isinstance(row["decoded_hypothesis_id"], bool)
        or not isinstance(row["decoded_hypothesis_id"], Integral)
        or not 0 <= int(row["decoded_hypothesis_id"]) < 16
    ):
        raise ValueError("decoded_hypothesis_id must be a canonical edge ID in [0,15]")
    return row


def validate_m6b_trace_payload(value: object) -> dict[str, Any]:
    """Validate one complete, compact, already computed B/C run payload."""
    payload = dict(_mapping(value, name="M6b trace payload"))
    _exact_keys(
        payload,
        {
            "schema_version",
            "experiment_id",
            "run_id",
            "config_sha256",
            "software_provenance",
            "received_sha256",
            "mode_B",
            "mode_C",
            "paired_comparison",
            "trace_integrity_status",
        },
        name="M6b trace payload",
    )
    if payload["schema_version"] != 1:
        raise ValueError("trace payload schema_version must be 1")
    if payload["experiment_id"] != "m6b_causal_trace_20261030_v1":
        raise ValueError("trace payload belongs to a different experiment namespace")
    expected_ids = {f"{payload['experiment_id']}:run-{i:03d}" for i in range(1, 4)}
    if payload["run_id"] not in expected_ids:
        raise ValueError("trace payload run_id is not in the planned diagnostic manifest")
    _sha256(payload["config_sha256"], name="config_sha256")
    received_digest = _sha256(payload["received_sha256"], name="received_sha256")
    software = _mapping(payload["software_provenance"], name="software_provenance")
    _exact_keys(
        software,
        {"python_version", "numpy_version", "platform", "file_sha256"},
        name="software_provenance",
    )
    fingerprints = _mapping(software["file_sha256"], name="software_provenance.file_sha256")
    if not fingerprints:
        raise ValueError("software provenance must include hashed source files")
    for name, digest in fingerprints.items():
        if not isinstance(name, str) or not name:
            raise ValueError("software fingerprint paths must be nonempty strings")
        _sha256(digest, name=f"software provenance {name}")
    for mode_key, expected_mode in (
        ("mode_B", "mismatched_frozen"),
        ("mode_C", "mismatched_adaptive"),
    ):
        mode = _mapping(payload[mode_key], name=mode_key)
        _exact_keys(mode, _MODE_KEYS, name=mode_key)
        if mode["receiver_mode"] != expected_mode or mode["received_sha256"] != received_digest:
            raise ValueError("B/C mode labels and received digest must match the paired run")
        state = _mapping(mode["initial_state"], name=f"{mode_key}.initial_state")
        _exact_keys(state, {"fluctuating_iq", "full_iq"}, name=f"{mode_key}.initial_state")
        for state_key in ("fluctuating_iq", "full_iq"):
            _array(state[state_key], dtype="float64", shape=(1, 2), name=state_key)
        rows_value = mode["symbol_trace"]
        if not isinstance(rows_value, list) or len(rows_value) != 32:
            raise ValueError("each B/C mode must contain all 32 ordered symbol rows")
        rows = [_validate_symbol_row(row, index=index) for index, row in enumerate(rows_value)]
        for row in rows:
            alpha = float(row["alpha_prime"])
            k_tilde = _array(row["k_tilde"], dtype="float64", shape=(1, 2), name="k_tilde")
            mu0 = _array(row["mu0"], dtype="float64", shape=(1, 2), name="mu0")
            if expected_mode == "mismatched_frozen":
                expected_k = np.zeros((1, 2), dtype=np.float64)
                if alpha != 1.0:
                    raise ValueError("frozen B trace alpha_prime must remain 1.0")
            else:
                expected_k = np.asarray([[0.35, -0.2]], dtype=np.float64)
                if alpha != 0.85:
                    raise ValueError("adaptive C trace alpha_prime must remain 0.85")
            if not np.array_equal(k_tilde, expected_k) or np.any(mu0 != 0.0):
                raise ValueError(
                    "trace coefficient operands differ from the frozen historical B/C policies"
                )
        metrics = _array(
            mode["frozen_metric_history"],
            dtype="float64",
            shape=(32, 16),
            name=f"{mode_key}.frozen_metric_history",
        )
        stacked = np.stack(
            [
                _array(
                    row["candidate_metrics"], dtype="float64", shape=(16,), name="candidate_metrics"
                )
                for row in rows
            ]
        )
        if not np.array_equal(metrics, stacked):
            raise ValueError("frozen metric matrix must equal the exact ordered per-symbol rows")
        path = mode["decoded_hypothesis_path"]
        bits = mode["decoded_information_bits"]
        if (
            not isinstance(path, list)
            or len(path) != 32
            or any(
                isinstance(item, bool) or not isinstance(item, Integral) or not 0 <= item < 16
                for item in path
            )
            or not isinstance(bits, list)
            or len(bits) != 64
            or any(isinstance(item, bool) or item not in (0, 1) for item in bits)
            or [row["decoded_hypothesis_id"] for row in rows] != path
        ):
            raise ValueError("decoded path/bits must align with the complete trace")
        final_state = _mapping(mode["final_state"], name=f"{mode_key}.final_state")
        _exact_keys(final_state, {"fluctuating_iq", "full_iq"}, name=f"{mode_key}.final_state")
        for state_key in ("fluctuating_iq", "full_iq"):
            _array(final_state[state_key], dtype="float64", shape=(1, 2), name=state_key)
        _finite_real(mode["best_conditional_path_cost"], name="best_conditional_path_cost")
        if mode["decoded_path_valid"] is not True or mode["decode_call_count"] != 1:
            raise ValueError("each mode must retain one valid final B5b decode")
        _sha256(mode["received_sha256"], name=f"{mode_key}.received_sha256")
    b_state = payload["mode_B"]["initial_state"]
    c_state = payload["mode_C"]["initial_state"]
    if b_state != c_state:
        raise ValueError("B/C initial estimator state must match exactly")
    comparison = _mapping(payload["paired_comparison"], name="paired_comparison")
    _exact_keys(
        comparison,
        {
            "rtol",
            "atol",
            "first_post_state_divergence_symbol",
            "first_candidate_metric_divergence_symbol",
            "first_posterior_divergence_symbol",
            "decoded_path_divergence_positions",
        },
        name="paired_comparison",
    )
    if comparison["rtol"] != 1e-12 or comparison["atol"] != 1e-14:
        raise ValueError("paired comparison tolerances differ from the frozen contract")
    for key in (
        "first_post_state_divergence_symbol",
        "first_candidate_metric_divergence_symbol",
        "first_posterior_divergence_symbol",
    ):
        item = comparison[key]
        if item is not None and (
            isinstance(item, bool) or not isinstance(item, Integral) or not 0 <= item < 32
        ):
            raise ValueError(f"{key} must be null or an absolute symbol label in [0,31]")
    positions = comparison["decoded_path_divergence_positions"]
    if not isinstance(positions, list) or any(
        isinstance(item, bool) or not isinstance(item, Integral) or not 0 <= item < 32
        for item in positions
    ):
        raise ValueError("decoded_path_divergence_positions must contain absolute labels in [0,31]")
    if payload["trace_integrity_status"] != "complete_valid_trace":
        raise ValueError("complete trace payload must have complete_valid_trace status")

    # The receiver trace must never contain reference arrays or ChannelTruth.
    forbidden = {
        "reference_bits",
        "reference_information_bits",
        "ChannelTruth",
        "true_channel_gain",
    }

    def scan_keys(node: object) -> None:
        if isinstance(node, Mapping):
            if forbidden.intersection(node):
                raise ValueError("receiver trace payload contains forbidden reference/truth data")
            for child in node.values():
                scan_keys(child)
        elif isinstance(node, list):
            for child in node:
                scan_keys(child)

    scan_keys(payload)
    # Normalize nested mapping types to JSON-compatible built-ins and reject NaN/Inf.
    json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return payload


def serialize_m6b_trace_payload(value: object) -> str:
    """Canonical JSON envelope with a SHA-256 of the canonical payload."""
    payload = validate_m6b_trace_payload(value)
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    integrity = {
        "algorithm": "sha256",
        "payload_sha256": hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest(),
    }
    return json.dumps(
        {"payload": payload, "integrity": integrity},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def deserialize_m6b_trace_payload(serialized: str) -> dict[str, Any]:
    """Parse, hash-check, and schema-check one canonical serialized run."""
    if not isinstance(serialized, str):
        raise ValueError("serialized trace must be a string")
    try:
        envelope = json.loads(serialized, parse_constant=_reject_nonstandard_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"serialized trace is invalid JSON: {exc}") from exc
    if not isinstance(envelope, Mapping) or set(envelope) != {"payload", "integrity"}:
        raise ValueError("serialized trace envelope keys are invalid")
    integrity = _mapping(envelope["integrity"], name="integrity")
    _exact_keys(integrity, {"algorithm", "payload_sha256"}, name="integrity")
    if integrity["algorithm"] != "sha256":
        raise ValueError("trace integrity algorithm must be sha256")
    try:
        canonical_payload = json.dumps(
            envelope["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"trace payload integrity serialization failed: {exc}") from exc
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    if integrity["payload_sha256"] != digest:
        raise ValueError("trace payload SHA-256 integrity check failed")
    return validate_m6b_trace_payload(envelope["payload"])
