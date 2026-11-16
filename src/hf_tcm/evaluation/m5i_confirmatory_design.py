"""Non-executing M5i confirmatory design validation and seed manifest planning."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import numpy as np

from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

_PROTOCOL_VERSION_WORD = 0x4D354831
_EXPECTED_CONFIG_FINGERPRINT = "6e42b5003e3804c89266cd78dcf3702d9d8159ed4ed46b81acf962bbff4db1e4"
_EVALUATION_PARTITION_CODE = 211
_STREAM_CODES = {"data": 11, "noise": 23, "bootstrap": 37}
_EVALUATION_MASTER_SEEDS = {"data": 2026110101, "noise": 2026110102, "bootstrap": 2026110103}
_REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "study_id",
    "design_id",
    "design_version",
    "design_status",
    "execution_authorized",
    "execution_scope",
    "purpose",
    "phase_distinction",
    "scientific_profile",
    "primary_condition",
    "run_design",
    "compute_workload",
    "sample_origins",
    "receiver_policies",
    "pairing_contract",
    "primary_estimand",
    "secondary_analyses",
    "tuning_policy",
    "scientific_claim_boundary",
    "sample_size_basis",
    "bootstrap_contract",
    "seed_derivation",
    "numerical_failure_policy",
    "stopping_rule",
    "future_execution_budget",
    "authorization",
    "output_contract",
    "pilot_evidence_provenance",
    "reconstruction_configuration",
    "limitations",
}
_REQUIRED_MANIFEST_KEYS = {
    "study_id",
    "design_id",
    "design_version",
    "design_fingerprint",
    "partition",
    "primary_condition",
    "run_count",
    "seed_namespace_master_seeds",
    "seed_derivation",
    "prng",
    "python_version",
    "numpy_version",
    "code_revision_identifier",
    "code_revision_status",
    "source_fingerprint",
    "bootstrap",
    "planned_runs",
    "manifest_status",
}
_CODE_FINGERPRINT_PATHS = (
    "src/hf_tcm/evaluation/m5i_confirmatory_design.py",
    "src/hf_tcm/evaluation/m5h_pilot_protocol.py",
    "src/hf_tcm/evaluation/m5h_pilot_runner.py",
    "src/hf_tcm/evaluation/reconstruction_paired_monte_carlo.py",
    "src/hf_tcm/evaluation/reconstruction_adaptive_diagnostics.py",
    "src/hf_tcm/evaluation/paired_cluster_bootstrap.py",
    "src/hf_tcm/evaluation/error_metrics.py",
    "src/hf_tcm/reconstruction_config.py",
    "src/hf_tcm/receiver/reconstruction_forward.py",
)


class M5IExecutionBlocked(RuntimeError):
    """Raised when non-authorized M5i design is passed to an execution path."""


@dataclass(frozen=True, slots=True)
class M5IConfirmatoryDesign:
    """Validated immutable snapshot of a proposed, non-executable M5i design."""

    canonical_json: str
    fingerprint: str
    design_status: str
    execution_authorized: bool
    execution_scope: str
    study_id: str
    design_version: str
    run_count: int
    symbols_per_run: int
    primary_gamma_db: float
    sigma_squared: float

    def as_dict(self) -> dict[str, Any]:
        """Return a fresh mutable JSON object without exposing internal state."""
        return json.loads(self.canonical_json)


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} keys mismatch; missing={missing}, extra={extra}")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _equal(actual: object, expected: object, *, name: str) -> None:
    if isinstance(actual, bool) != isinstance(expected, bool) or actual != expected:
        raise ValueError(f"{name} must equal frozen M5i value {expected!r}")


def validate_m5i_confirmatory_design(value: object) -> M5IConfirmatoryDesign:
    """Validate a fully explicit M5i draft; validation never generates data."""
    root = _mapping(value, name="M5i confirmatory design")
    _exact_keys(root, _REQUIRED_TOP_LEVEL_KEYS, name="M5i confirmatory design")
    _equal(root["schema_version"], 1, name="schema_version")
    _equal(root["design_status"], "proposed_confirmatory", name="design_status")
    _equal(root["execution_authorized"], False, name="execution_authorized")
    _equal(root["execution_scope"], "none", name="execution_scope")
    for key in ("study_id", "design_id", "design_version", "purpose"):
        if not isinstance(root[key], str) or not root[key].strip():
            raise ValueError(f"{key} must be explicit and nonempty")

    profile = _mapping(root["scientific_profile"], name="scientific_profile")
    _equal(profile.get("profile"), "reconstructed_offline", name="scientific_profile.profile")
    _equal(profile.get("path_count"), 1, name="scientific_profile.path_count")
    _equal(profile.get("real_channel_gain_a"), 0.75, name="real_channel_gain_a")
    _equal(profile.get("path_delays_samples"), [0], name="path_delays_samples")
    _equal(profile.get("modulation"), "normalized_8PSK", name="modulation")
    _equal(profile.get("waveform"), "rectangular_ZOH", name="waveform")
    _equal(profile.get("samples_per_symbol"), 8, name="samples_per_symbol")
    _equal(
        profile.get("noise_axis_label"),
        "effective discrete gamma_b; not physical HF Eb/N0",
        name="noise_axis_label",
    )
    _equal(
        profile.get("noise_model"), "ADR-015 independent circular complex AWGN", name="noise_model"
    )
    _equal(
        profile.get("accepted_adr"),
        [
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
        ],
        name="accepted_adr",
    )
    _equal(profile.get("proposed_adr"), ["ADR-009", "ADR-011"], name="proposed_adr")
    _equal(
        profile.get("open_science_questions"),
        ["SCI-02", "SCI-03", "SCI-METRIC-02"],
        name="open_science_questions",
    )
    _equal(profile.get("paper_exact"), False, name="paper_exact")
    _equal(profile.get("receiver_enabled"), False, name="receiver_enabled")

    condition = _mapping(root["primary_condition"], name="primary_condition")
    _equal(condition.get("gamma_b_eff_db"), 5.0, name="primary gamma")
    _equal(condition.get("role"), "sole primary confirmatory stratum", name="primary role")
    expected_gamma = 10 ** (5.0 / 10.0)
    _equal(condition.get("gamma_b_eff_linear"), expected_gamma, name="gamma_b_eff_linear")
    expected_sigma = 4.0 * 0.75 * 0.75 / expected_gamma
    sigma = condition.get("sigma_squared")
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)):
        raise ValueError("sigma_squared must be an explicit real number")
    if not math.isclose(float(sigma), expected_sigma, rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("sigma_squared violates ADR-015 at the frozen 5 dB stratum")
    _equal(
        condition.get("sigma_squared_formula"),
        "4*a*a / 10^(gamma_b_eff_dB/10)",
        name="sigma formula",
    )

    run_design = _mapping(root["run_design"], name="run_design")
    expected_workload = {
        "independent_cluster": "one complete coded TCM sequence",
        "run_count": 100,
        "symbols_per_run_F": 256,
        "total_independent_sequences": 100,
        "total_tcm_symbols": 25_600,
        "total_information_bits": 51_200,
        "total_received_complex_samples": 204_800,
        "minimum_B_C_decoder_passes": 200,
        "strata_count": 1,
        "planned_run_id_count": 100,
    }
    _exact_keys(run_design, set(expected_workload), name="run_design")
    for key, expected in expected_workload.items():
        _equal(run_design[key], expected, name=f"run_design.{key}")
    _equal(
        root["compute_workload"],
        {
            "independent_sequences": 100,
            "tcm_symbols": 25_600,
            "information_bits": 51_200,
            "received_complex_samples": 204_800,
            "decoder_passes_minimum": 200,
        },
        name="compute_workload",
    )

    _equal(
        root["sample_origins"],
        {
            "absolute_sample_origin": 0,
            "absolute_symbol_origin": 0,
            "initial_estimator_time_index": 0,
            "samples_per_symbol": 8,
        },
        name="sample_origins",
    )
    policies = _mapping(root["receiver_policies"], name="receiver_policies")
    _equal(
        policies,
        {
            "shared": {
                "initial_full_iq": [0.42, 0.91],
                "initial_fluctuating_iq": [0.42, 0.91],
                "beta": 0.7,
                "mu0": [0.0, 0.0],
            },
            "B": {"policy": "frozen", "alpha_prime": 1.0, "K_tilde": [0.0, 0.0], "mu0": [0.0, 0.0]},
            "C": {
                "policy": "adaptive",
                "alpha_prime": 0.85,
                "K_tilde": [0.35, -0.2],
                "mu0": [0.0, 0.0],
            },
            "only_difference": "estimator update policy",
        },
        name="receiver_policies",
    )
    pair = _mapping(root["pairing_contract"], name="pairing_contract")
    _equal(pair.get("only_difference"), "estimator update policy", name="pairing only_difference")
    for key in (
        "identical_reference_input_bits",
        "identical_noisy_received_buffer",
        "identical_initial_estimator_state",
        "identical_beta",
        "identical_symbol_and_time_origins",
        "same_trellis_and_termination_rules",
    ):
        _equal(pair.get(key), True, name=f"pairing_contract.{key}")

    secondary = _mapping(root["secondary_analyses"], name="secondary_analyses")
    _equal(
        secondary.get("historical_gamma_diagnostics_db"),
        [0, 10, 15],
        name="historical pilot gamma diagnostics",
    )
    _equal(secondary.get("run_secondary_gamma_strata_in_M5j"), False, name="secondary M5j strata")
    _equal(secondary.get("simultaneous_four_point_inference"), False, name="simultaneous inference")
    _equal(secondary.get("general_adaptive_advantage_claim"), False, name="general adaptive claim")
    _equal(
        root["tuning_policy"],
        {
            "automatic_tuning": False,
            "parameters_frozen": True,
            "select_parameters_using_M5f_or_M5h_outcomes": False,
            "change_R_after_confirmatory_outcome_review": False,
        },
        name="tuning_policy",
    )
    claim_boundary = _mapping(root["scientific_claim_boundary"], name="scientific_claim_boundary")
    for key in (
        "general_HF_claim",
        "paper_exact_joint_receiver_claim",
        "physical_EbN0_gain_claim",
        "complex_fading_or_multipath_claim",
        "AR1_claim",
        "optimality_claim",
        "universal_adaptation_claim",
        "1_5_dB_reproduction_claim",
    ):
        _equal(claim_boundary.get(key), False, name=f"scientific_claim_boundary.{key}")
    _equal(
        claim_boundary.get("permitted_future_claim"),
        "performance difference between specified frozen and adaptive reconstructed receivers under the fixed ADR-015 single-path discrete-AWGN experimental profile",
        name="permitted claim boundary",
    )

    estimand = _mapping(root["primary_estimand"], name="primary_estimand")
    _equal(estimand.get("name"), "DeltaBER", name="primary estimand name")
    _equal(
        estimand.get("definition"),
        "pooled BER_C - pooled BER_B",
        name="primary estimand definition",
    )
    _equal(
        estimand.get("condition"),
        "5 dB effective discrete gamma_b",
        name="primary estimand condition",
    )
    _equal(estimand.get("precision_target_95pct_ci_half_width"), 0.02, name="epsilon target")
    _equal(
        estimand.get("precision_target_role"),
        "planning target only; not a stopping rule",
        name="precision target role",
    )

    basis = _mapping(root["sample_size_basis"], name="sample_size_basis")
    for key, expected in {
        "pilot_study_id": "M5h-independent-pilot-candidate",
        "primary_gamma_b_eff_db": 5.0,
        "pilot_runs": 30,
        "pilot_s_d": 0.053093594133490844,
        "pilot_R_approx": 28,
        "recommended_confirmatory_R": 100,
        "reference_is_runtime_guarantee": False,
        "R_is_precision_guarantee": False,
        "R_change_after_confirmatory_outcomes": False,
    }.items():
        _equal(basis.get(key), expected, name=f"sample_size_basis.{key}")
    _equal(root["bootstrap_contract"].get("replicates"), 2000, name="bootstrap replicates")
    _equal(root["bootstrap_contract"].get("confidence_level"), 0.95, name="bootstrap confidence")
    _equal(
        root["bootstrap_contract"].get("quantile_method"),
        "numpy.quantile(method='linear')",
        name="bootstrap quantile",
    )
    _equal(
        root["bootstrap_contract"].get("paired_same_index_B_C_resampling"),
        True,
        name="paired bootstrap",
    )
    _equal(
        root["bootstrap_contract"].get("interval"),
        "two-sided percentile",
        name="bootstrap interval",
    )
    _equal(
        root["bootstrap_contract"].get("pooled_integer_counts"), True, name="pooled integer counts"
    )
    _equal(
        root["bootstrap_contract"].get("explicit_independent_bootstrap_seed"),
        True,
        name="explicit bootstrap seed",
    )
    _equal(
        root["bootstrap_contract"].get("preserve_warning_flags"), True, name="bootstrap warnings"
    )
    expected_metrics = ["ber_b", "ber_c", "delta_ber", "ser_b", "ser_c", "delta_ser"]
    _equal(root["bootstrap_contract"].get("metrics"), expected_metrics, name="bootstrap metrics")

    seed = _mapping(root["seed_derivation"], name="seed_derivation")
    _equal(seed.get("partition"), "evaluation", name="seed partition")
    _equal(seed.get("partition_code"), _EVALUATION_PARTITION_CODE, name="evaluation partition code")
    _equal(
        seed.get("master_seeds"), _EVALUATION_MASTER_SEEDS, name="evaluation seed namespace roots"
    )
    _equal(seed.get("pilot_namespaces_used"), False, name="pilot namespace isolation")
    _equal(seed.get("stream_codes"), _STREAM_CODES, name="seed stream codes")
    _equal(seed.get("stratum_index_for_primary_5db"), 1, name="primary seed stratum index")
    _equal(seed.get("protocol_version_word"), _PROTOCOL_VERSION_WORD, name="seed protocol word")
    if seed.get("planned_run_index_origin") != 1:
        raise ValueError("planned run ID display index must start at 1")

    failure = _mapping(root["numerical_failure_policy"], name="numerical_failure_policy")
    for key in (
        "zero_or_max_error_imputation",
        "silent_exclusion",
        "retry_with_new_seed",
        "receiver_parameter_change",
    ):
        _equal(failure.get(key), False, name=f"numerical_failure_policy.{key}")
    _equal(
        failure.get("full_design_completeness_required"),
        True,
        name="failure completeness requirement",
    )
    _equal(
        failure.get("finite_unstable_trajectory"),
        "retain valid decoded output and diagnostics",
        name="finite unstable policy",
    )
    _equal(failure.get("high_BER"), "retain all observed errors", name="high BER policy")
    _equal(
        failure.get("missing_valid_B_or_C_output"),
        "retain failure; block full-design inference",
        name="missing decoder output policy",
    )
    _equal(
        failure.get("completed_only_pooled_metrics"),
        "descriptive only and explicitly labeled with missing-output count",
        name="incomplete stratum summary policy",
    )
    _equal(
        failure.get("resume"),
        "same planned IDs, original seeds, identical config/code fingerprint only",
        name="resume failure policy",
    )

    stopping = _mapping(root["stopping_rule"], name="stopping_rule")
    _equal(stopping.get("planned_run_count"), 100, name="fixed planned run count")
    _equal(stopping.get("complete_every_planned_run"), True, name="complete all planned runs")
    for key in (
        "result_dependent_early_stop",
        "early_stop_on_DeltaBER_or_CI",
        "automatic_run_count_increase",
        "extend_R_after_outcome_review",
        "precision_target_is_stopping_rule",
    ):
        _equal(stopping.get(key), False, name=f"stopping_rule.{key}")

    budget = _mapping(root["future_execution_budget"], name="future_execution_budget")
    _equal(budget.get("wall_clock_limit_seconds"), 900, name="M5j wall-clock limit")
    _equal(budget.get("worker_processes"), 1, name="M5j worker count")
    _equal(budget.get("multiprocessing"), False, name="M5j multiprocessing")
    _equal(budget.get("rss_budget_bytes"), 1_610_612_736, name="M5j RSS budget")
    _equal(
        budget.get("resume_requires_same_config_manifest_and_code_fingerprint"),
        True,
        name="resume fingerprint",
    )
    _equal(budget.get("no_duplicate_run_ids"), True, name="duplicate run guard")
    _equal(budget.get("no_silent_resume_after_code_change"), True, name="code-change resume guard")
    _equal(
        budget.get("wall_clock_interruption"),
        "stop before starting the next independent run; keep completed checkpoints and mark design incomplete",
        name="wall-clock interruption",
    )
    if "polling is not a hard OS limit" not in budget.get("rss_enforcement", ""):
        raise ValueError("RSS budget must not be represented as a hard limit when polling")

    auth = _mapping(root["authorization"], name="authorization")
    _equal(auth.get("M5i_may_execute"), False, name="M5i authorization")
    _equal(
        auth.get("future_M5j_requires_new_immutable_run_specific_config"),
        True,
        name="M5j authorization",
    )
    _equal(auth.get("reuse_M5h_pilot_authorization"), False, name="pilot authorization reuse")
    _equal(
        root["output_contract"].get("reference_bits_or_ChannelTruth_passed_to_decoder"),
        False,
        name="reference leakage",
    )
    _equal(
        root["output_contract"].get("pilot_records_enter_confirmatory_sample"),
        False,
        name="pilot data exclusion",
    )
    _equal(
        root["output_contract"].get("planned_manifest_contains_generated_data_or_noise"),
        False,
        name="no generated data/noise",
    )

    profile_configuration = validate_reconstructed_offline_config(
        root["reconstruction_configuration"]
    )
    _equal(profile_configuration["profile"], "reconstructed_offline", name="reconstruction profile")
    _equal(profile_configuration["paper_exact"], False, name="embedded paper_exact")
    _equal(profile_configuration["receiver_enabled"], False, name="embedded receiver_enabled")
    _equal(profile_configuration["timebase"]["path_count"], 1, name="embedded path count")
    _equal(
        profile_configuration["timebase"]["path_delays_samples"], [0], name="embedded path delay"
    )
    _equal(profile_configuration["timebase"]["samples_per_symbol"], 8, name="embedded sps")
    _equal(
        profile_configuration["timebase"]["name"],
        "approximate_rectangular_8sps",
        name="embedded waveform",
    )
    _equal(
        profile_configuration["observation_model"]["kind"],
        "adr012_l1_real_mean8",
        name="embedded ADR-012 observation",
    )
    _equal(profile_configuration["likelihood"]["beta"], 0.7, name="embedded beta")
    estimator = profile_configuration["estimator"]
    _equal(estimator["alpha_prime"], 0.85, name="embedded C alpha")
    _equal(estimator["k_tilde"], [[0.35, -0.2]], name="embedded C K")
    _equal(estimator["mu0"], [[0.0, 0.0]], name="embedded C mu0")
    _equal(estimator["initial_time_index"], 0, name="embedded time origin")
    _equal(
        estimator["initial_estimates"]["full_iq"],
        [[0.42, 0.91]],
        name="embedded initial full state",
    )
    _equal(
        estimator["initial_estimates"]["fluctuating_iq"],
        [[0.42, 0.91]],
        name="embedded initial fluctuating state",
    )

    canonical = json.dumps(root, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = _sha256(canonical.encode("utf-8"))
    if (
        _EXPECTED_CONFIG_FINGERPRINT
        != "9b7954de303896f4f7c69e25628032760d3bfe11d63c36ae25640e0173b792a0"
        and fingerprint != _EXPECTED_CONFIG_FINGERPRINT
    ):
        raise ValueError("M5i config differs from its immutable candidate snapshot")
    return M5IConfirmatoryDesign(
        canonical_json=canonical,
        fingerprint=fingerprint,
        design_status="proposed_confirmatory",
        execution_authorized=False,
        execution_scope="none",
        study_id=str(root["study_id"]),
        design_version=str(root["design_version"]),
        run_count=100,
        symbols_per_run=256,
        primary_gamma_db=5.0,
        sigma_squared=float(sigma),
    )


def load_m5i_confirmatory_design(path: str | Path) -> M5IConfirmatoryDesign:
    """Load and validate the complete explicit JSON design draft."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read M5i confirmatory design: {exc}") from exc
    return validate_m5i_confirmatory_design(value)


def _derive_seed(
    master_seed: int, *, stratum_index: int, run_index: int, stream: str
) -> tuple[int, tuple[int, ...]]:
    spawn_key = (
        _PROTOCOL_VERSION_WORD,
        _EVALUATION_PARTITION_CODE,
        stratum_index,
        run_index,
        _STREAM_CODES[stream],
    )
    child = np.random.SeedSequence(master_seed, spawn_key=spawn_key)
    return int(child.generate_state(1, dtype=np.uint64)[0]), spawn_key


def _source_fingerprint() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    result: dict[str, str] = {}
    for relative in _CODE_FINGERPRINT_PATHS:
        path = root / relative
        result[relative] = _sha256(path.read_bytes())
    return result


def build_m5i_seed_manifest(design: M5IConfirmatoryDesign) -> dict[str, Any]:
    """Derive only planned seed metadata; no data/noise/decoder is invoked."""
    if not isinstance(design, M5IConfirmatoryDesign):
        raise ValueError("design must be a validated immutable M5IConfirmatoryDesign")
    data = design.as_dict()
    roots = data["seed_derivation"]["master_seeds"]
    stratum_index = data["seed_derivation"]["stratum_index_for_primary_5db"]
    runs: list[dict[str, Any]] = []
    used_seeds: set[int] = set()
    run_ids: set[str] = set()
    bootstrap_seed, bootstrap_spawn = _derive_seed(
        roots["bootstrap"], stratum_index=stratum_index, run_index=0, stream="bootstrap"
    )
    used_seeds.add(bootstrap_seed)
    for run_index in range(design.run_count):
        run_id = f"{design.study_id}:evaluation:gamma-5dB:run-{run_index + 1:03d}"
        if run_id in run_ids:
            raise ValueError(f"duplicate planned run ID: {run_id}")
        run_ids.add(run_id)
        streams: dict[str, dict[str, Any]] = {}
        for name in ("data", "noise"):
            seed, spawn_key = _derive_seed(
                roots[name],
                stratum_index=stratum_index,
                run_index=run_index,
                stream=name,
            )
            if seed in used_seeds:
                raise ValueError("derived seed collision across evaluation streams")
            used_seeds.add(seed)
            streams[name] = {
                "master_seed": roots[name],
                "spawn_key": list(spawn_key),
                "derived_seed": seed,
                "bit_generator": "PCG64",
            }
        runs.append(
            {
                "run_id": run_id,
                "partition": "evaluation",
                "stratum_id": "gamma-5dB",
                "stratum_index": stratum_index,
                "run_index": run_index,
                "F": design.symbols_per_run,
                "gamma_b_eff_db": design.primary_gamma_db,
                "sigma_squared": design.sigma_squared,
                "origins": {
                    "sample": 0,
                    "symbol": 0,
                    "estimator_time": 0,
                },
                "data": streams["data"],
                "noise": streams["noise"],
            }
        )
    return {
        "study_id": design.study_id,
        "design_id": data["design_id"],
        "design_version": design.design_version,
        "design_fingerprint": design.fingerprint,
        "partition": "evaluation",
        "primary_condition": {
            "stratum_id": "gamma-5dB",
            "stratum_index": stratum_index,
            "gamma_b_eff_db": design.primary_gamma_db,
            "sigma_squared": design.sigma_squared,
        },
        "run_count": design.run_count,
        "seed_namespace_master_seeds": dict(roots),
        "seed_derivation": {
            "algorithm": "numpy.random.SeedSequence(master_seed, spawn_key).generate_state(1, dtype=uint64)[0]",
            "spawn_key_fields": [
                "protocol_version_word",
                "partition_code",
                "stratum_index",
                "zero_based_run_index",
                "stream_code",
            ],
            "protocol_version_word": _PROTOCOL_VERSION_WORD,
            "partition_code": _EVALUATION_PARTITION_CODE,
            "stream_codes": dict(_STREAM_CODES),
            "seed_bits": 64,
        },
        "prng": "numpy.random.PCG64",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "code_revision_identifier": None,
        "code_revision_status": "unavailable: workspace is not a Git worktree",
        "source_fingerprint": _source_fingerprint(),
        "bootstrap": {
            "namespace": "evaluation.bootstrap",
            "master_seed": roots["bootstrap"],
            "spawn_key": list(bootstrap_spawn),
            "derived_seed": bootstrap_seed,
            "bit_generator": "PCG64",
        },
        "planned_runs": runs,
        "manifest_status": "planned IDs and seed provenance only; no data/noise generated",
    }


def validate_m5i_seed_manifest(manifest: object, design: M5IConfirmatoryDesign) -> None:
    """Validate the 100 planned IDs and every seed child against the design."""
    if not isinstance(design, M5IConfirmatoryDesign):
        raise ValueError("design must be a validated immutable M5IConfirmatoryDesign")
    root = _mapping(manifest, name="M5i seed manifest")
    _exact_keys(root, _REQUIRED_MANIFEST_KEYS, name="M5i seed manifest")
    _equal(root["study_id"], design.study_id, name="manifest study_id")
    _equal(root["design_version"], design.design_version, name="manifest design_version")
    _equal(root["design_fingerprint"], design.fingerprint, name="manifest design fingerprint")
    _equal(root["partition"], "evaluation", name="manifest partition")
    _equal(root["run_count"], 100, name="manifest run_count")
    _equal(
        root["seed_namespace_master_seeds"],
        _EVALUATION_MASTER_SEEDS,
        name="manifest evaluation roots",
    )
    planned = root["planned_runs"]
    if not isinstance(planned, list) or len(planned) != 100:
        raise ValueError("manifest must contain exactly 100 planned runs")
    ids = [item.get("run_id") for item in planned if isinstance(item, Mapping)]
    if len(ids) != 100:
        raise ValueError("each planned manifest entry must be an object with a run_id")
    if len(set(ids)) != len(ids):
        raise ValueError("manifest contains duplicate planned run IDs")
    expected = build_m5i_seed_manifest(design)
    if root != expected:
        raise ValueError("manifest differs from deterministic M5i seed derivation")


def guard_m5i_execution(
    design: M5IConfirmatoryDesign,
    *,
    callbacks: Mapping[str, Callable[[], object]],
) -> NoReturn:
    """Reject execution before accessing or invoking data/noise/decoder callbacks."""
    if not isinstance(design, M5IConfirmatoryDesign):
        raise M5IExecutionBlocked("M5i execution blocked: design is not validated")
    if (
        design.design_status != "proposed_confirmatory"
        or design.execution_authorized is not False
        or design.execution_scope != "none"
    ):
        raise M5IExecutionBlocked("M5i execution blocked: explicit M5j approval required")
    # Deliberately do not inspect or invoke the injected callbacks in M5i.
    del callbacks
    raise M5IExecutionBlocked("M5i execution blocked: no M5j run-specific authorization")
