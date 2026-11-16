"""Validated, authorization-gated preparation for the proposed M5h pilot."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37}
_PARTITION_CODES = {"pilot": 101, "evaluation": 211}
_PROTOCOL_VERSION_WORD = 0x4D354831
_REQUIRED_KEYS = {
    "study_id",
    "design_version",
    "design_status",
    "execution_authorized",
    "purpose",
    "phase_distinction",
    "scope",
    "run_design",
    "receiver_policies",
    "sample_origins",
    "run_id_template",
    "seed_derivation",
    "failure_policy",
    "output_provenance",
    "bootstrap_contract",
    "sample_size_plan",
    "compute_workload",
    "resource_measurement_after_authorization",
    "limitations",
    "reconstruction_configuration",
}
_AUTHORIZATION_KEYS = {
    "execution_scope",
    "authorization_provenance",
    "source_draft_sha256",
    "code_fingerprint",
    "execution_limits",
    "approved_parameter_snapshot",
}


class M5HPilotExecutionBlocked(RuntimeError):
    """Raised when the proposed pilot does not pass its explicit run gate."""


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return result


def _real(value: object, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        missing = sorted(expected.difference(value))
        extra = sorted(set(value).difference(expected))
        raise ValueError(f"{name} keys mismatch; missing={missing}, extra={extra}")


def approved_parameter_snapshot(data: Mapping[str, Any]) -> dict[str, object]:
    """Return the exact approved parameter subset from a run config."""
    design = _mapping(data.get("run_design"), name="run_design")
    return {
        "real_channel_gain_a": design.get("real_channel_gain_a"),
        "gamma_grid": design.get("gamma_grid"),
        "primary_gamma_b_eff_db": design.get("primary_gamma_b_eff_db"),
        "runs_per_stratum": design.get("runs_per_stratum"),
        "symbols_per_run_F": design.get("symbols_per_run_F"),
        "receiver_policies": data.get("receiver_policies"),
        "sample_origins": data.get("sample_origins"),
    }


@dataclass(frozen=True, slots=True)
class M5HPilotStratum:
    gamma_db: float
    gamma_linear: float
    sigma_squared: float
    role: str


@dataclass(frozen=True, slots=True)
class M5HPilotConfig:
    study_id: str
    design_version: str
    design_status: str
    execution_authorized: bool
    execution_scope: str | None
    real_channel_gain: float
    symbols_per_run: int
    run_count_per_stratum: int
    primary_gamma_db: float
    strata: tuple[M5HPilotStratum, ...]
    samples_per_symbol: int
    sample_origin: int
    symbol_origin: int
    estimator_time_origin: int
    pilot_seed_roots_json: str
    evaluation_seed_roots_json: str
    reconstruction_configuration_json: str
    run_id_template: str
    bootstrap_seed_pilot: int
    bootstrap_seed_evaluation: int
    authorization_provenance_json: str | None
    source_draft_sha256: str | None
    code_fingerprint_json: str | None
    execution_limits_json: str | None
    approved_parameter_snapshot_json: str | None
    _source_json: str

    @property
    def gamma_grid_db(self) -> tuple[float, ...]:
        return tuple(stratum.gamma_db for stratum in self.strata)

    @property
    def b_policy(self) -> dict[str, object]:
        return {"alpha_prime": 1.0, "K_tilde": (0.0, 0.0), "mu0": (0.0, 0.0)}

    @property
    def c_policy(self) -> dict[str, object]:
        return {
            "alpha_prime": 0.85,
            "K_tilde": (0.35, -0.2),
            "mu0": (0.0, 0.0),
        }

    @property
    def workload(self) -> dict[str, int]:
        sequences = len(self.strata) * self.run_count_per_stratum
        symbols = sequences * self.symbols_per_run
        return {
            "independent_sequences": sequences,
            "tcm_symbols": symbols,
            "information_bits": 2 * symbols,
            "received_samples": self.samples_per_symbol * symbols,
            "decoder_passes_minimum": 2 * sequences,
        }

    def stratum(self, gamma_db: float) -> M5HPilotStratum:
        for stratum in self.strata:
            if stratum.gamma_db == float(gamma_db):
                return stratum
        raise KeyError(gamma_db)


@dataclass(frozen=True, slots=True)
class M5HRunProvenance:
    study_partition: str
    stratum_id: str
    run_id: str
    run_index: int
    gamma_db: float
    sigma_squared: float
    data_master_seed: int
    data_spawn_key: tuple[int, ...]
    data_seed: int
    noise_master_seed: int
    noise_spawn_key: tuple[int, ...]
    noise_seed: int
    bootstrap_seed: int
    sample_origin: int
    symbol_origin: int
    estimator_time_origin: int


@dataclass(frozen=True, slots=True)
class M5HPilotFailureRecord:
    run_id: str
    stratum_id: str
    exception_type: str
    detail: str
    last_valid_state: object | None = None
    last_valid_time_index: int | None = None
    diagnostics: object | None = None


@dataclass(frozen=True, slots=True)
class M5HPilotResult:
    completed_records: tuple[object, ...]
    failure_records: tuple[M5HPilotFailureRecord, ...]
    pooled_metrics_status: str
    skipped_run_count: int = 0
    status: str = "complete"


def validate_m5h_pilot_config(data: object) -> M5HPilotConfig:
    """Validate a fully explicit candidate; this function never executes it."""
    root = _mapping(data, name="pilot configuration")
    status = root.get("design_status")
    if status == "approved_for_pilot":
        _exact_keys(root, _REQUIRED_KEYS | _AUTHORIZATION_KEYS, name="approved pilot config")
    else:
        _exact_keys(root, _REQUIRED_KEYS, name="pilot configuration")
    for key in ("study_id", "design_version", "run_id_template"):
        if not isinstance(root[key], str) or not root[key].strip():
            raise ValueError(f"{key} must be explicit and nonempty")
    if status not in ("proposed", "approved_for_pilot"):
        raise ValueError("design_status must be 'proposed' or 'approved_for_pilot'")
    if not isinstance(root["execution_authorized"], bool):
        raise ValueError("execution_authorized must be an explicit boolean")
    execution_scope: str | None = None
    authorization_json: str | None = None
    source_hash: str | None = None
    code_fingerprint_json: str | None = None
    limits_json: str | None = None
    snapshot_json: str | None = None
    if status == "approved_for_pilot":
        if root["execution_authorized"] is not True:
            raise ValueError("approved_for_pilot config requires execution_authorized=true")
        if root["execution_scope"] != "m5h_pilot_only":
            raise ValueError("execution_scope must be 'm5h_pilot_only'")
        execution_scope = "m5h_pilot_only"
        source_hash_value = root["source_draft_sha256"]
        if not isinstance(source_hash_value, str) or not re.fullmatch(
            r"[0-9a-f]{64}", source_hash_value
        ):
            raise ValueError("source_draft_sha256 must be an explicit SHA-256 digest")
        source_hash = source_hash_value
        snapshot = _mapping(root["approved_parameter_snapshot"], name="approved_parameter_snapshot")
        if dict(snapshot) != approved_parameter_snapshot(root):
            raise ValueError("approved parameter snapshot differs from candidate parameters")
        snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        provenance = _mapping(root["authorization_provenance"], name="authorization_provenance")
        _exact_keys(
            provenance,
            {
                "explicit_user_approval",
                "design_version",
                "source_draft_identifier",
                "source_draft_sha256",
                "execution_date_time_utc",
                "code_revision_identifier",
                "code_revision_status",
                "code_fingerprint",
            },
            name="authorization_provenance",
        )
        required_provenance = {
            "explicit_user_approval": "explicit user approval through the current Codex execution instruction",
            "design_version": root["design_version"],
            "source_draft_identifier": root["study_id"],
            "source_draft_sha256": source_hash,
            "code_revision_identifier": None,
            "code_revision_status": "unavailable: workspace is not a Git worktree",
        }
        if any(provenance.get(key) != value for key, value in required_provenance.items()):
            raise ValueError("authorization provenance is incomplete or inconsistent")
        run_time = provenance.get("execution_date_time_utc")
        try:
            parsed_time = datetime.fromisoformat(run_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("execution_date_time_utc must be an ISO-8601 timestamp") from exc
        if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
            raise ValueError("execution_date_time_utc must include a UTC offset")
        authorization_json = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
        fingerprint = _mapping(root["code_fingerprint"], name="code_fingerprint")
        if not fingerprint or any(
            not isinstance(name, str)
            or not name
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in fingerprint.items()
        ):
            raise ValueError("code_fingerprint must map paths to SHA-256 digests")
        code_fingerprint_json = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
        if provenance.get("code_fingerprint") != dict(fingerprint):
            raise ValueError("authorization provenance code fingerprint differs from run config")
        limits = _mapping(root["execution_limits"], name="execution_limits")
        expected_limits = {
            "wall_clock_budget_seconds": 1800,
            "rss_ceiling_bytes": 1_610_612_736,
            "resource_poll_interval_seconds": 0.25,
            "available_memory_measurement": "Windows GlobalMemoryStatusEx",
            "decoding_workers": 1,
            "output_size_target_bytes": 100 * 1024 * 1024,
            "limit_semantics": "observed by 0.25-second parent monitor; not an OS hard cap",
        }
        if any(limits.get(key) != value for key, value in expected_limits.items()):
            raise ValueError("execution limits differ from the authorized budget")
        available_memory = _integer(
            limits.get("available_memory_before_bytes"),
            name="available_memory_before_bytes",
            minimum=1,
        )
        if available_memory < 2 * 1024**3:
            raise ValueError("available memory is below the recommended 2 GiB minimum")
        limits_json = json.dumps(limits, sort_keys=True, separators=(",", ":"))
    elif root["execution_authorized"] is not False:
        raise ValueError("proposed config must keep execution_authorized=false")
    expected_purpose = (
        "authorized independent planning pilot, NOT confirmatory performance evidence, "
        "NOT paper-exact receiver, NOT physical HF Eb/N0 comparison"
        if status == "approved_for_pilot"
        else "validated pilot execution preparation, NOT executed pilot, "
        "NOT new BER evidence, NOT performance claim"
    )
    if root["purpose"] != expected_purpose:
        raise ValueError("purpose must preserve the appropriate pilot evidence boundary")
    phase_distinction = _mapping(root["phase_distinction"], name="phase_distinction")
    if phase_distinction != {
        "pilot_records": "pilot_only_never_evaluation",
        "evaluation_records": "separately_seeded_confirmatory_only",
        "m5f": "historical_exploratory_experiment_excluded_from_pilot_and_evaluation",
    }:
        raise ValueError("pilot/evaluation/M5f record separation must be explicit")

    scope = _mapping(root["scope"], name="scope")
    accepted = [f"ADR-{number:03d}" for number in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13, 14, 15)]
    if (
        scope.get("profile") != "reconstructed_offline"
        or scope.get("path_count") != 1
        or scope.get("samples_per_symbol") != 8
        or scope.get("noise_axis") != "effective discrete gamma_b, NOT physical HF Eb/N0"
        or scope.get("accepted_adrs") != accepted
        or scope.get("proposed_adrs") != ["ADR-009", "ADR-011"]
        or scope.get("open_questions") != ["SCI-02", "SCI-03", "SCI-METRIC-02"]
        or scope.get("paper_exact") is not False
        or scope.get("receiver_enabled") is not False
    ):
        raise ValueError("scope must preserve accepted ADRs, open questions, and profile limits")

    design = _mapping(root["run_design"], name="run_design")
    gain = _real(design.get("real_channel_gain_a"), name="real_channel_gain_a")
    if gain != 0.75:
        raise ValueError("real_channel_gain_a must match the candidate value 0.75")
    symbols = _integer(design.get("symbols_per_run_F"), name="symbols_per_run_F", minimum=1)
    runs = _integer(design.get("runs_per_stratum"), name="runs_per_stratum", minimum=1)
    if symbols != 256 or runs != 30 or design.get("strata_count") != 4:
        raise ValueError("F, run count, or stratum count differs from the explicit candidate")
    if design.get("total_independent_sequences") != runs * design["strata_count"]:
        raise ValueError("total independent sequence count does not match strata and runs")
    if design.get("independent_cluster") != "one complete coded sequence":
        raise ValueError("independent cluster must be one complete coded sequence")
    if design.get("same_received_buffer_for_B_and_C") is not True:
        raise ValueError("B/C must share one received buffer per run")

    raw_strata = design.get("gamma_grid")
    if not isinstance(raw_strata, list) or len(raw_strata) != 4:
        raise ValueError("gamma_grid must explicitly contain four strata")
    strata: list[M5HPilotStratum] = []
    for item in raw_strata:
        row = _mapping(item, name="gamma stratum")
        _exact_keys(
            row,
            {"gamma_b_eff_db", "gamma_b_eff_linear", "sigma_squared", "role"},
            name="gamma stratum",
        )
        gamma_db = _real(row.get("gamma_b_eff_db"), name="gamma_b_eff_db")
        gamma_linear = _real(row.get("gamma_b_eff_linear"), name="gamma_b_eff_linear")
        sigma = _real(row.get("sigma_squared"), name="sigma_squared")
        if gamma_linear <= 0 or sigma <= 0:
            raise ValueError("gamma linear and sigma_squared must be positive")
        expected_linear = 10 ** (gamma_db / 10)
        expected_sigma = 4 * gain * gain / expected_linear
        if not math.isclose(gamma_linear, expected_linear, rel_tol=1e-13, abs_tol=0.0):
            raise ValueError("gamma_b_eff_linear does not match gamma_b_eff_db")
        if not math.isclose(sigma, expected_sigma, rel_tol=1e-13, abs_tol=0.0):
            raise ValueError("sigma_squared violates accepted ADR-015 gamma conversion")
        role = row.get("role")
        if role not in ("primary", "secondary_descriptive"):
            raise ValueError("stratum role must be explicit")
        strata.append(M5HPilotStratum(gamma_db, gamma_linear, sigma, role))
    if tuple(item.gamma_db for item in strata) != (0.0, 5.0, 10.0, 15.0):
        raise ValueError("gamma strata must be ordered 0, 5, 10, 15 dB")
    primary = _real(design.get("primary_gamma_b_eff_db"), name="primary_gamma_b_eff_db")
    if primary != 5.0 or sum(item.role == "primary" for item in strata) != 1:
        raise ValueError("the unique primary stratum must be 5 dB")
    if next(item for item in strata if item.role == "primary").gamma_db != primary:
        raise ValueError("primary role must be assigned to the 5 dB stratum")

    policies = _mapping(root["receiver_policies"], name="receiver_policies")
    shared = _mapping(policies.get("shared"), name="receiver_policies.shared")
    policy_b = _mapping(policies.get("B"), name="receiver_policies.B")
    policy_c = _mapping(policies.get("C"), name="receiver_policies.C")
    if (
        shared.get("initial_fluctuating_iq") != [0.42, 0.91]
        or shared.get("initial_full_iq") != [0.42, 0.91]
        or shared.get("beta") != 0.7
        or shared.get("mu0") != [0.0, 0.0]
        or policy_b.get("alpha_prime") != 1.0
        or policy_b.get("K_tilde") != [0.0, 0.0]
        or policy_b.get("mu0") != [0.0, 0.0]
        or policy_c.get("alpha_prime") != 0.85
        or policy_c.get("K_tilde") != [0.35, -0.2]
        or policy_c.get("mu0") != [0.0, 0.0]
        or policy_c.get("beta_shared") != shared.get("beta")
        or policies.get("parity_required") is not True
        or policies.get("only_difference") != "registered coefficient update policy"
    ):
        raise ValueError("candidate B/C policies are incomplete or violate required parity")

    origins = _mapping(root["sample_origins"], name="sample_origins")
    _exact_keys(
        origins,
        {
            "absolute_sample_origin",
            "absolute_symbol_origin",
            "initial_estimator_time_index",
            "samples_per_symbol",
        },
        name="sample_origins",
    )
    sample_origin = _integer(origins["absolute_sample_origin"], name="absolute_sample_origin")
    symbol_origin = _integer(origins["absolute_symbol_origin"], name="absolute_symbol_origin")
    time_origin = _integer(
        origins["initial_estimator_time_index"], name="initial_estimator_time_index"
    )
    sps = _integer(origins["samples_per_symbol"], name="samples_per_symbol", minimum=1)
    if sps != 8 or scope["samples_per_symbol"] != sps:
        raise ValueError("8 samples/symbol must agree across scope and time origins")

    seed_data = _mapping(root["seed_derivation"], name="seed_derivation")
    if seed_data.get("algorithm") != (
        "NumPy SeedSequence with domain-separated entropy and explicit spawn_key; PCG64"
    ):
        raise ValueError("unsupported seed derivation algorithm")
    if seed_data.get("spawn_key_fields") != [
        "protocol_version_word",
        "study_namespace_code",
        "stratum_index",
        "run_index",
        "stream_code",
    ]:
        raise ValueError("seed spawn-key fields are incomplete or reordered")
    if seed_data.get("generated_seed_bits") != 64:
        raise ValueError("seed derivation must record 64-bit child seeds")
    if any(
        seed_data.get(key) is not True
        for key in (
            "record_master_seed_spawn_key_derived_seed_and_bit_generator",
            "pilot_evaluation_records_disjoint",
            "bootstrap_independent_of_data_noise",
        )
    ):
        raise ValueError("seed provenance separation requirements must be explicit")
    namespaces = _mapping(seed_data.get("namespace_scheme"), name="namespace_scheme")
    if set(namespaces) != {"pilot", "evaluation"}:
        raise ValueError("pilot and evaluation seed namespaces must both be explicit")
    roots: dict[str, dict[str, int]] = {}
    all_roots: list[int] = []
    for partition in ("pilot", "evaluation"):
        raw = _mapping(namespaces[partition], name=f"{partition} namespace")
        if set(raw) != set(_STREAM_CODES):
            raise ValueError(f"{partition} namespace requires data, noise, and bootstrap roots")
        roots[partition] = {
            stream: _integer(raw[stream], name=f"{partition}_{stream}_root")
            for stream in _STREAM_CODES
        }
        all_roots.extend(roots[partition].values())
    if len(all_roots) != len(set(all_roots)):
        raise ValueError("seed namespace roots conflict; all six roots must be distinct")
    generated_run_ids: set[str] = set()
    try:
        for stratum in strata:
            for run_index in range(1, runs + 1):
                run_id = root["run_id_template"].format(
                    study_id=root["study_id"],
                    partition="pilot",
                    gamma_db=stratum.gamma_db,
                    run_index=run_index,
                )
                if run_id in generated_run_ids:
                    raise ValueError("run_id_template does not produce unique run IDs")
                generated_run_ids.add(run_id)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"invalid run_id_template: {exc}") from exc

    bootstrap = _mapping(root["bootstrap_contract"], name="bootstrap_contract")
    if (
        bootstrap.get("adr") != "ADR-014"
        or bootstrap.get("independent_cluster") != "one coded sequence"
        or bootstrap.get("same_index_paired_B_C_resampling") is not True
        or bootstrap.get("replicates") != 2000
        or bootstrap.get("confidence_level") != 0.95
        or bootstrap.get("interval") != "two-sided percentile"
        or bootstrap.get("quantile_method") != "numpy.quantile(method='linear')"
        or bootstrap.get("pooled_raw_counts") is not True
        or bootstrap.get("explicit_bootstrap_namespace_and_seed_required") is not True
    ):
        raise ValueError("bootstrap contract must match accepted ADR-014")

    failure = _mapping(root["failure_policy"], name="failure_policy")
    required_failure_values = {
        "invalid_configuration": "reject before any generation or decoding",
        "numerical_decoder_failure": "retain failure record; no zero-error imputation; no silent deletion; pooled metrics blocked if receiver outputs are missing",
        "finite_unstable_trajectory": "retain numerically valid run and attach diagnostics",
        "valid_high_ber": "retain all observed errors without exception",
        "classification_required": True,
    }
    if any(failure.get(key) != value for key, value in required_failure_values.items()):
        raise ValueError("failure handling policy is incomplete")

    output = _mapping(root["output_provenance"], name="output_provenance")
    required_output_fields = {
        "study_id",
        "partition",
        "stratum_id",
        "run_id",
        "F",
        "gamma_b_eff_db",
        "sigma_squared",
        "data/noise namespace and seed provenance",
        "sample/symbol/time origins",
        "B/C policies",
        "paired received-buffer identity",
        "raw B/C integer error counts",
        "trajectory diagnostics",
        "failure classification",
    }
    if (
        output.get("raw_record_unit") != "one paired B/C coded sequence"
        or set(output.get("required", ())) != required_output_fields
        or output.get("pilot_records_must_not_enter_evaluation") is not True
        or output.get("reference_bits_or_ChannelTruth_passed_to_decoder") is not False
    ):
        raise ValueError("output provenance or reference-data boundary is incomplete")

    sample_size = _mapping(root["sample_size_plan"], name="sample_size_plan")
    if (
        sample_size.get("primary_estimand") != "pooled BER_C - pooled BER_B at 5 dB"
        or sample_size.get("candidate_absolute_95pct_ci_half_width") != 0.02
        or sample_size.get("target_status") != "candidate_requires_user_approval"
        or sample_size.get("paired_run_difference") != "(bit_errors_C - bit_errors_B)/(2F)"
        or sample_size.get("normal_approximation") != "R_approx=ceil((1.96*s_d/epsilon)^2)"
        or sample_size.get("approved_run_count") is not None
        or sample_size.get("confirmatory_gate")
        != "BLOCKED pending pilot review, approved precision, and compute budget"
    ):
        raise ValueError("sample-size candidate or BLOCKED status is incomplete")

    workload = _mapping(root["compute_workload"], name="compute_workload")
    candidate_workload = {
        "independent_sequences": runs * len(strata),
        "tcm_symbols": runs * len(strata) * symbols,
        "information_bits": 2 * runs * len(strata) * symbols,
        "received_samples": sps * runs * len(strata) * symbols,
        "decoder_passes_minimum": 2 * runs * len(strata),
    }
    if any(workload.get(key) != value for key, value in candidate_workload.items()):
        raise ValueError("compute workload does not match strata, F, and B/C passes")
    if workload.get("runtime") != "not estimated" or workload.get("memory") != "not benchmarked":
        raise ValueError("runtime and memory must remain unestimated")
    if (
        not isinstance(root["resource_measurement_after_authorization"], str)
        or not root["resource_measurement_after_authorization"].strip()
    ):
        raise ValueError("bounded future resource measurement method must be explicit")
    if not isinstance(root["limitations"], list) or not root["limitations"]:
        raise ValueError("limitations must be explicit")

    profile = validate_reconstructed_offline_config(root["reconstruction_configuration"])
    estimator = profile["estimator"]
    timebase = profile["timebase"]
    if (
        profile["profile"] != "reconstructed_offline"
        or profile["paper_exact"] is not False
        or profile["receiver_enabled"] is not False
        or timebase["samples_per_symbol"] != 8
        or timebase["path_count"] != 1
        or timebase["path_delays_samples"] != [0]
        or timebase["symbol_origin_sample"] != sample_origin
        or estimator["initial_time_index"] != time_origin
        or estimator["initial_estimates"]["fluctuating_iq"] != [[0.42, 0.91]]
        or estimator["initial_estimates"]["full_iq"] != [[0.42, 0.91]]
        or estimator["alpha_prime"] != 0.85
        or estimator["k_tilde"] != [[0.35, -0.2]]
        or estimator["mu0"] != [[0.0, 0.0]]
        or profile["likelihood"]["beta"] != 0.7
    ):
        raise ValueError("embedded receiver profile does not match the explicit candidate")

    pilot_roots = json.dumps(roots["pilot"], sort_keys=True, separators=(",", ":"))
    evaluation_roots = json.dumps(roots["evaluation"], sort_keys=True, separators=(",", ":"))
    return M5HPilotConfig(
        study_id=root["study_id"].strip(),
        design_version=root["design_version"].strip(),
        design_status=root["design_status"],
        execution_authorized=root["execution_authorized"],
        execution_scope=execution_scope,
        real_channel_gain=gain,
        symbols_per_run=symbols,
        run_count_per_stratum=runs,
        primary_gamma_db=primary,
        strata=tuple(strata),
        samples_per_symbol=sps,
        sample_origin=sample_origin,
        symbol_origin=symbol_origin,
        estimator_time_origin=time_origin,
        pilot_seed_roots_json=pilot_roots,
        evaluation_seed_roots_json=evaluation_roots,
        reconstruction_configuration_json=json.dumps(
            profile, sort_keys=True, separators=(",", ":")
        ),
        run_id_template=root["run_id_template"],
        bootstrap_seed_pilot=roots["pilot"]["bootstrap"],
        bootstrap_seed_evaluation=roots["evaluation"]["bootstrap"],
        authorization_provenance_json=authorization_json,
        source_draft_sha256=source_hash,
        code_fingerprint_json=code_fingerprint_json,
        execution_limits_json=limits_json,
        approved_parameter_snapshot_json=snapshot_json,
        _source_json=json.dumps(root, sort_keys=True, separators=(",", ":")),
    )


def load_m5h_pilot_config(path: str | Path) -> M5HPilotConfig:
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read M5h pilot configuration: {exc}") from exc
    return validate_m5h_pilot_config(value)


def _derive_seed(
    master_seed: int, *, partition: str, stratum_index: int, run_index: int, stream: str
) -> tuple[int, tuple[int, ...]]:
    spawn_key = (
        _PROTOCOL_VERSION_WORD,
        _PARTITION_CODES[partition],
        stratum_index,
        run_index,
        _STREAM_CODES[stream],
    )
    sequence = np.random.SeedSequence(master_seed, spawn_key=spawn_key)
    child_seed = int(sequence.generate_state(1, dtype=np.uint64)[0])
    return child_seed, spawn_key


def derive_m5h_run_provenance(
    config: M5HPilotConfig, *, partition: str = "pilot"
) -> tuple[M5HRunProvenance, ...]:
    if not isinstance(config, M5HPilotConfig):
        raise ValueError("config must be a validated M5HPilotConfig")
    if partition not in _PARTITION_CODES:
        raise ValueError("partition must be 'pilot' or 'evaluation'")
    roots = json.loads(
        config.pilot_seed_roots_json if partition == "pilot" else config.evaluation_seed_roots_json
    )
    all_roots = {
        "pilot": json.loads(config.pilot_seed_roots_json),
        "evaluation": json.loads(config.evaluation_seed_roots_json),
    }
    all_derived: dict[int, tuple[str, str, int, int]] = {}
    for partition_name, partition_roots in all_roots.items():
        for stratum_index in range(len(config.strata)):
            bootstrap_seed, _ = _derive_seed(
                partition_roots["bootstrap"],
                partition=partition_name,
                stratum_index=stratum_index,
                run_index=0,
                stream="bootstrap",
            )
            if bootstrap_seed in all_derived:
                raise ValueError(
                    "derived seed collision across pilot/evaluation/data/noise/bootstrap"
                )
            all_derived[bootstrap_seed] = (partition_name, "bootstrap", stratum_index, 0)
            for run_index in range(config.run_count_per_stratum):
                for stream in ("data", "noise"):
                    child_seed, _ = _derive_seed(
                        partition_roots[stream],
                        partition=partition_name,
                        stratum_index=stratum_index,
                        run_index=run_index,
                        stream=stream,
                    )
                    location = (partition_name, stream, stratum_index, run_index)
                    if child_seed in all_derived:
                        raise ValueError(
                            "derived seed collision across pilot/evaluation/data/noise/bootstrap"
                        )
                    all_derived[child_seed] = location
    provenance: list[M5HRunProvenance] = []
    run_ids: set[str] = set()
    derived: set[int] = set()
    for stratum_index, stratum in enumerate(config.strata):
        stratum_id = f"gamma-{stratum.gamma_db:g}dB"
        bootstrap_seed, _ = _derive_seed(
            roots["bootstrap"],
            partition=partition,
            stratum_index=stratum_index,
            run_index=0,
            stream="bootstrap",
        )
        for run_index in range(config.run_count_per_stratum):
            data_seed, data_spawn = _derive_seed(
                roots["data"],
                partition=partition,
                stratum_index=stratum_index,
                run_index=run_index,
                stream="data",
            )
            noise_seed, noise_spawn = _derive_seed(
                roots["noise"],
                partition=partition,
                stratum_index=stratum_index,
                run_index=run_index,
                stream="noise",
            )
            run_id = config.run_id_template.format(
                study_id=config.study_id,
                partition=partition,
                gamma_db=stratum.gamma_db,
                run_index=run_index + 1,
            )
            if run_id in run_ids:
                raise ValueError(f"duplicate run ID generated: {run_id}")
            run_ids.add(run_id)
            for child_seed in (data_seed, noise_seed):
                if child_seed in derived:
                    raise ValueError("derived seed collision across data/noise streams")
                derived.add(child_seed)
            provenance.append(
                M5HRunProvenance(
                    study_partition=partition,
                    stratum_id=stratum_id,
                    run_id=run_id,
                    run_index=run_index,
                    gamma_db=stratum.gamma_db,
                    sigma_squared=stratum.sigma_squared,
                    data_master_seed=roots["data"],
                    data_spawn_key=data_spawn,
                    data_seed=data_seed,
                    noise_master_seed=roots["noise"],
                    noise_spawn_key=noise_spawn,
                    noise_seed=noise_seed,
                    bootstrap_seed=bootstrap_seed,
                    sample_origin=config.sample_origin,
                    symbol_origin=config.symbol_origin,
                    estimator_time_origin=config.estimator_time_origin,
                )
            )
    return tuple(provenance)


@dataclass(frozen=True, slots=True)
class _PilotRunRequest:
    provenance: M5HRunProvenance
    symbols_per_run: int
    samples_per_symbol: int
    b_policy: Mapping[str, object]
    c_policy: Mapping[str, object]
    reconstruction_configuration: Mapping[str, object]


def run_m5h_pilot(
    config: M5HPilotConfig,
    *,
    execute_run: Callable[[_PilotRunRequest], object],
    completed_run_ids: tuple[str, ...] = (),
    on_run_start: Callable[[M5HRunProvenance], None] | None = None,
    on_checkpoint: Callable[[M5HRunProvenance, str, object], None] | None = None,
) -> M5HPilotResult:
    """Execute only an approved and explicitly authorized pilot configuration.

    The checked-in candidate fails this gate before provenance generation and
    before the injected callback can generate data/noise or invoke a decoder.
    """
    if not isinstance(config, M5HPilotConfig):
        raise M5HPilotExecutionBlocked("pilot configuration is not validated")
    try:
        canonical = validate_m5h_pilot_config(json.loads(config._source_json))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise M5HPilotExecutionBlocked("pilot configuration failed revalidation") from exc
    if config != canonical:
        raise M5HPilotExecutionBlocked("pilot configuration differs from its validated source")
    if config.execution_authorized is not True:
        raise M5HPilotExecutionBlocked("execution_authorized must be true before execution")
    if config.design_status != "approved_for_pilot":
        raise M5HPilotExecutionBlocked("design_status must be approved_for_pilot before execution")
    if config.execution_scope != "m5h_pilot_only":
        raise M5HPilotExecutionBlocked("execution_scope must be m5h_pilot_only")
    if not callable(execute_run):
        raise M5HPilotExecutionBlocked("an explicit per-run executor is required")

    provenance = derive_m5h_run_provenance(config, partition="pilot")
    if len(completed_run_ids) != len(set(completed_run_ids)):
        raise M5HPilotExecutionBlocked("duplicate completed run IDs were supplied")
    expected_run_ids = {item.run_id for item in provenance}
    unknown_ids = set(completed_run_ids).difference(expected_run_ids)
    if unknown_ids:
        raise M5HPilotExecutionBlocked(f"unknown completed run IDs: {sorted(unknown_ids)}")
    skipped = set(completed_run_ids)
    completed: list[object] = []
    failures: list[M5HPilotFailureRecord] = []
    for item in provenance:
        if item.run_id in skipped:
            continue
        if on_run_start is not None:
            on_run_start(item)
        request = _PilotRunRequest(
            provenance=item,
            symbols_per_run=config.symbols_per_run,
            samples_per_symbol=config.samples_per_symbol,
            b_policy=config.b_policy,
            c_policy=config.c_policy,
            reconstruction_configuration=json.loads(config.reconstruction_configuration_json),
        )
        try:
            record = execute_run(request)
        except Exception as exc:  # Numerical/runtime failures are retained as records.
            failure = M5HPilotFailureRecord(
                run_id=item.run_id,
                stratum_id=item.stratum_id,
                exception_type=type(exc).__name__,
                detail=str(exc),
                last_valid_state=getattr(exc, "last_valid_state", None),
                last_valid_time_index=getattr(exc, "last_valid_time_index", None),
                diagnostics=getattr(exc, "diagnostics", None),
            )
            if on_checkpoint is not None:
                on_checkpoint(item, "numerical_failure", failure)
            failures.append(failure)
        else:
            if on_checkpoint is not None:
                on_checkpoint(item, "completed", record)
            completed.append(record)
    return M5HPilotResult(
        completed_records=tuple(completed),
        failure_records=tuple(failures),
        pooled_metrics_status=(
            "blocked_numerical_failures" if failures else "not_computed_by_pilot_runner"
        ),
        skipped_run_count=len(skipped),
    )
