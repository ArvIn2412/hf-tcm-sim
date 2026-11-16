"""Small paired Monte Carlo composition for the M5e B/C receiver modes."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.evaluation.error_metrics import ErrorCounts, calculate_ber_ser
from hf_tcm.evaluation.paired_cluster_bootstrap import (
    PairedClusterBootstrapResult,
    PairedPointEstimates,
    PairedRunCounts,
    paired_cluster_bootstrap,
)
from hf_tcm.evaluation.reconstruction_adaptive_diagnostics import (
    run_adaptive_estimator_diagnostic,
)
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.reconstruction_config import validate_reconstructed_offline_config

PAIRED_MONTE_CARLO_STATUS = (
    "isolated paired Monte Carlo and cluster-bootstrap evaluation for "
    "reconstructed_offline single-path receiver, NOT validated performance advantage, "
    "NOT paper-exact receiver, NOT reproduction of paper results"
)
_CONFIG_KEYS = {
    "experiment_id",
    "number_of_independent_runs",
    "symbols_per_run",
    "real_channel_gain",
    "sigma_squared",
    "data_rng_master_seed",
    "noise_rng_master_seed",
    "bootstrap_seed",
    "bootstrap_replicates",
    "confidence_level",
    "beta",
    "initial_fluctuating_iq",
    "initial_full_iq",
    "alpha_prime_c",
    "k_tilde_c",
    "mu0_c",
    "absolute_sample_origin",
    "absolute_symbol_origin",
    "initial_estimator_time_index",
    "reconstruction_profile",
    "receiver_profile_version",
    "profile_provenance",
    "reconstruction_configuration",
}


def _integer(value: object, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return result


def _real(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real value")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result <= minimum):
        qualifier = f" > {minimum}" if minimum is not None else ""
        raise ValueError(f"{name} must be finite{qualifier}")
    return result


def _iq_pair(value: object, *, name: str) -> tuple[float, float]:
    array = np.asarray(value)
    if array.shape != (2,) or np.iscomplexobj(array) or array.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be a finite real pair")
    try:
        pair = tuple(float(item) for item in array)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real pair") from exc
    if not all(math.isfinite(item) for item in pair):
        raise ValueError(f"{name} must be a finite real pair")
    return pair


@dataclass(frozen=True, slots=True)
class PairedMonteCarloConfig:
    """Fully explicit configuration for one fixed-profile exploratory study."""

    experiment_id: str
    number_of_independent_runs: int
    symbols_per_run: int
    real_channel_gain: float
    sigma_squared: float
    data_rng_master_seed: int
    noise_rng_master_seed: int
    bootstrap_seed: int
    bootstrap_replicates: int
    confidence_level: float
    beta: float
    initial_fluctuating_iq: tuple[float, float]
    initial_full_iq: tuple[float, float]
    alpha_prime_c: float
    k_tilde_c: tuple[float, float]
    mu0_c: tuple[float, float]
    absolute_sample_origin: int
    absolute_symbol_origin: int
    initial_estimator_time_index: int
    reconstruction_profile: str
    receiver_profile_version: str
    profile_provenance: str
    reconstruction_configuration_json: str

    @property
    def reconstruction_configuration(self) -> dict[str, Any]:
        return json.loads(self.reconstruction_configuration_json)


def validate_paired_monte_carlo_config(data: object) -> PairedMonteCarloConfig:
    """Validate every M5f field and the embedded inactive M4 profile."""
    if not isinstance(data, Mapping) or set(data) != _CONFIG_KEYS:
        missing = _CONFIG_KEYS.difference(data) if isinstance(data, Mapping) else _CONFIG_KEYS
        extra = set(data).difference(_CONFIG_KEYS) if isinstance(data, Mapping) else set()
        raise ValueError(
            f"configuration keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    experiment_id = data["experiment_id"]
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("experiment_id must be nonempty")
    profile = data["reconstruction_profile"]
    receiver_version = data["receiver_profile_version"]
    provenance = data["profile_provenance"]
    if profile != "reconstructed_offline":
        raise ValueError("reconstruction_profile must be 'reconstructed_offline'")
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("profile_provenance must be explicit and nonempty")
    if not isinstance(receiver_version, str) or not receiver_version.strip():
        raise ValueError("receiver_profile_version must be explicit and nonempty")

    runs = _integer(
        data["number_of_independent_runs"], name="number_of_independent_runs", minimum=1
    )
    symbols = _integer(data["symbols_per_run"], name="symbols_per_run", minimum=1)
    gain = _real(data["real_channel_gain"], name="real_channel_gain", minimum=0.0)
    variance = _real(data["sigma_squared"], name="sigma_squared", minimum=0.0)
    data_seed = _integer(data["data_rng_master_seed"], name="data_rng_master_seed", minimum=0)
    noise_seed = _integer(data["noise_rng_master_seed"], name="noise_rng_master_seed", minimum=0)
    if data_seed == noise_seed:
        raise ValueError("data and noise master seeds must use separate RNG streams")
    bootstrap_seed = _integer(data["bootstrap_seed"], name="bootstrap_seed", minimum=0)
    bootstrap_replicates = _integer(
        data["bootstrap_replicates"], name="bootstrap_replicates", minimum=1
    )
    confidence = _real(data["confidence_level"], name="confidence_level", minimum=0.0)
    if confidence >= 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    beta = _real(data["beta"], name="beta", minimum=0.0)
    initial_fluctuating = _iq_pair(data["initial_fluctuating_iq"], name="initial_fluctuating_iq")
    initial_full = _iq_pair(data["initial_full_iq"], name="initial_full_iq")
    if np.array_equal(initial_full, np.asarray([gain, gain], dtype=np.float64)):
        raise ValueError("initial full_iq must be explicitly mismatched from the real channel gain")
    alpha = _real(data["alpha_prime_c"], name="alpha_prime_c")
    k_tilde = _iq_pair(data["k_tilde_c"], name="k_tilde_c")
    mu0 = _iq_pair(data["mu0_c"], name="mu0_c")
    if not any(value != 0.0 for value in k_tilde):
        raise ValueError("K_tilde_C must be explicitly nonzero for adaptive mode C")
    if any(value != 0.0 for value in mu0):
        raise ValueError(
            "mu0_C must be zero in this paired frozen-B design so B stays frozen "
            "with the shared initial state"
        )
    if not np.allclose(
        initial_full, np.asarray(initial_fluctuating) + np.asarray(mu0), rtol=0.0, atol=1e-12
    ):
        raise ValueError("initial full_iq must equal initial fluctuating_iq + mu0_C")
    sample_origin = _integer(
        data["absolute_sample_origin"], name="absolute_sample_origin", minimum=0
    )
    symbol_origin = _integer(
        data["absolute_symbol_origin"], name="absolute_symbol_origin", minimum=0
    )
    estimator_time = _integer(
        data["initial_estimator_time_index"], name="initial_estimator_time_index", minimum=0
    )

    raw_profile_configuration = data["reconstruction_configuration"]
    profile_configuration = validate_reconstructed_offline_config(raw_profile_configuration)
    estimator = profile_configuration["estimator"]
    timebase = profile_configuration["timebase"]
    likelihood = profile_configuration["likelihood"]
    estimates = estimator["initial_estimates"]
    if profile_configuration["profile"] != profile:
        raise ValueError("embedded profile does not match reconstruction_profile")
    if (
        profile_configuration["labeling"]["name"] != "assumed_natural_binary"
        or tuple(profile_configuration["labeling"]["bit_order"]) != ("c2", "c1", "c0")
        or tuple(profile_configuration["labeling"]["output_to_b"]) != tuple(range(8))
        or timebase["path_count"] != 1
        or tuple(timebase["path_delays_samples"]) != (0,)
        or timebase["samples_per_symbol"] != 8
        or timebase["name"] != "approximate_rectangular_8sps"
        or profile_configuration["observation_model"]["kind"] != "adr012_l1_real_mean8"
    ):
        raise ValueError("embedded profile must match the accepted ADR-012 L=1 scope")
    if not math.isclose(float(likelihood["beta"]), beta, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("embedded profile beta must match explicit beta")
    if timebase["symbol_origin_sample"] != sample_origin:
        raise ValueError(
            "embedded profile sample origin must match explicit absolute sample origin"
        )
    if estimator["initial_time_index"] != estimator_time:
        raise ValueError("embedded profile estimator time must match explicit estimator time")
    if not np.array_equal(estimates["fluctuating_iq"], [list(initial_fluctuating)]):
        raise ValueError("embedded profile fluctuating estimate must match explicit initial state")
    if not np.array_equal(estimates["full_iq"], [list(initial_full)]):
        raise ValueError("embedded profile full estimate must match explicit initial state")
    if not math.isclose(estimator["alpha_prime"], alpha, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("embedded profile alpha_prime must match explicit adaptive alpha_prime_C")
    if not np.array_equal(estimator["k_tilde"], [list(k_tilde)]):
        raise ValueError("embedded profile K_tilde must match explicit K_tilde_C")
    if not np.array_equal(estimator["mu0"], [list(mu0)]):
        raise ValueError("embedded profile mu0 must match explicit mu0_C")
    profile_json = json.dumps(profile_configuration, sort_keys=True, separators=(",", ":"))
    return PairedMonteCarloConfig(
        experiment_id=experiment_id.strip(),
        number_of_independent_runs=runs,
        symbols_per_run=symbols,
        real_channel_gain=gain,
        sigma_squared=variance,
        data_rng_master_seed=data_seed,
        noise_rng_master_seed=noise_seed,
        bootstrap_seed=bootstrap_seed,
        bootstrap_replicates=bootstrap_replicates,
        confidence_level=confidence,
        beta=beta,
        initial_fluctuating_iq=initial_fluctuating,
        initial_full_iq=initial_full,
        alpha_prime_c=alpha,
        k_tilde_c=k_tilde,
        mu0_c=mu0,
        absolute_sample_origin=sample_origin,
        absolute_symbol_origin=symbol_origin,
        initial_estimator_time_index=estimator_time,
        reconstruction_profile=profile,
        receiver_profile_version=receiver_version.strip(),
        profile_provenance=provenance.strip(),
        reconstruction_configuration_json=profile_json,
    )


def load_paired_monte_carlo_config(path: str | Path) -> PairedMonteCarloConfig:
    """Read and validate an explicit JSON M5f experiment configuration."""
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read paired Monte Carlo configuration: {exc}") from exc
    return validate_paired_monte_carlo_config(value)


@dataclass(frozen=True, slots=True)
class PairedMonteCarloRunRecord:
    """Immutable evaluation-side raw paired counts and run provenance."""

    experiment_id: str
    run_id: str
    symbols_per_run: int
    b_counts: ErrorCounts
    c_counts: ErrorCounts
    b_hypothesis_path: tuple[int, ...]
    c_hypothesis_path: tuple[int, ...]
    b_decoded_information_bits: tuple[int, ...]
    c_decoded_information_bits: tuple[int, ...]
    b_ber: float
    c_ber: float
    b_ser: float
    c_ser: float
    delta_ber_run: float
    delta_ser_run: float
    data_seed: int
    data_spawn_key: tuple[int, ...]
    data_seed_provenance: str
    noise_seed: int
    noise_spawn_key: tuple[int, ...]
    noise_seed_provenance: str
    real_channel_gain: float
    sigma_squared: float
    effective_discrete_gamma_b: float
    beta: float
    initial_fluctuating_iq: tuple[float, float]
    initial_full_iq: tuple[float, float]
    alpha_prime_b: float
    k_tilde_b: tuple[float, float]
    mu0_b: tuple[float, float]
    alpha_prime_c: float
    k_tilde_c: tuple[float, float]
    mu0_c: tuple[float, float]
    initial_csi_provenance: str
    absolute_sample_indices: tuple[int, ...]
    absolute_symbol_indices: tuple[int, ...]
    estimator_time_indices: tuple[int, ...]
    received_sha256: str
    b_received_sha256: str
    c_received_sha256: str
    b_state_unchanged: bool
    c_state_changed: bool
    c_final_full_iq: tuple[float, float]
    c_final_deviation_from_initial: float
    c_max_coefficient_error_norm: float
    profile: str
    receiver_profile_version: str
    profile_provenance: str
    status: str
    warnings: tuple[str, ...]

    @property
    def total_bits(self) -> int:
        return self.b_counts.total_bits

    @property
    def total_symbols(self) -> int:
        return self.b_counts.total_symbols

    @property
    def b_bit_errors(self) -> int:
        return self.b_counts.bit_errors

    @property
    def c_bit_errors(self) -> int:
        return self.c_counts.bit_errors

    @property
    def b_symbol_errors(self) -> int:
        return self.b_counts.symbol_errors

    @property
    def c_symbol_errors(self) -> int:
        return self.c_counts.symbol_errors


@dataclass(frozen=True, slots=True)
class PairedMonteCarloResult:
    """Complete small paired experiment and its exploratory cluster intervals."""

    experiment_id: str
    status: str
    config: PairedMonteCarloConfig
    runs: tuple[PairedMonteCarloRunRecord, ...]
    point_estimates: PairedPointEstimates
    bootstrap: PairedClusterBootstrapResult
    warning_flags: tuple[str, ...]


def _derive_run_seeds(master_seed: int, count: int) -> tuple[tuple[int, tuple[int, ...]], ...]:
    children = np.random.SeedSequence(master_seed).spawn(count)
    result = tuple(
        (int(child.generate_state(1, dtype=np.uint64)[0]), tuple(int(x) for x in child.spawn_key))
        for child in children
    )
    seeds = [seed for seed, _ in result]
    if len(set(seeds)) != len(seeds):
        raise ValueError("derived run seeds collided; choose another explicit master seed")
    return result


def run_paired_monte_carlo(config: PairedMonteCarloConfig) -> PairedMonteCarloResult:
    """Execute one fixed small paired B/C experiment and cluster bootstrap."""
    if not isinstance(config, PairedMonteCarloConfig):
        raise ValueError("config must be a validated PairedMonteCarloConfig")
    data_seeds = _derive_run_seeds(config.data_rng_master_seed, config.number_of_independent_runs)
    noise_seeds = _derive_run_seeds(config.noise_rng_master_seed, config.number_of_independent_runs)
    if set(seed for seed, _ in data_seeds).intersection(seed for seed, _ in noise_seeds):
        raise ValueError("data and noise seed streams collided; choose separate master seeds")
    initial_state = ReconstructionEstimatorState(
        [config.initial_fluctuating_iq],
        [config.initial_full_iq],
        config.initial_estimator_time_index,
    )
    template = config.reconstruction_configuration
    records: list[PairedMonteCarloRunRecord] = []
    seen_run_ids: set[str] = set()
    for index, ((data_seed, data_spawn), (noise_seed, noise_spawn)) in enumerate(
        zip(data_seeds, noise_seeds, strict=True)
    ):
        run_id = f"{config.experiment_id}-run-{index + 1:03d}"
        if run_id in seen_run_ids:
            raise ValueError("duplicate run_id generated")
        seen_run_ids.add(run_id)
        data_rng = np.random.Generator(np.random.PCG64(data_seed))
        reference_bits = data_rng.integers(0, 2, size=2 * config.symbols_per_run, dtype=np.int8)
        profile_configuration = json.loads(json.dumps(template))
        adaptive = profile_configuration["estimator"]
        adaptive["alpha_prime"] = config.alpha_prime_c
        adaptive["k_tilde"] = [list(config.k_tilde_c)]
        adaptive["mu0"] = [list(config.mu0_c)]
        adaptive["initial_estimates"] = {
            "fluctuating_iq": [list(config.initial_fluctuating_iq)],
            "full_iq": [list(config.initial_full_iq)],
        }
        profile_configuration["likelihood"]["beta"] = config.beta
        profile_configuration["timebase"]["symbol_origin_sample"] = config.absolute_sample_origin
        profile_configuration["estimator"]["initial_time_index"] = (
            config.initial_estimator_time_index
        )
        profile_configuration = validate_reconstructed_offline_config(profile_configuration)
        diagnostic = run_adaptive_estimator_diagnostic(
            run_id=run_id,
            reference_information_bits=reference_bits,
            real_channel_gain=config.real_channel_gain,
            sigma_squared=config.sigma_squared,
            noise=None,
            noise_seed=noise_seed,
            noise_stream_id=f"{config.experiment_id}:noise:{noise_spawn}",
            noise_provenance=(
                f"ADR-015 PCG64; master={config.noise_rng_master_seed}; "
                f"spawn_key={noise_spawn}; derived_seed={noise_seed}"
            ),
            symbol_origin_sample=config.absolute_sample_origin,
            first_symbol_index=config.absolute_symbol_origin,
            initial_estimator_time_index=config.initial_estimator_time_index,
            configuration=profile_configuration,
            mismatched_initial_state=initial_state,
            adaptive_alpha_prime=config.alpha_prime_c,
            adaptive_k_tilde=np.asarray([config.k_tilde_c], dtype=np.float64),
            adaptive_mu0=np.asarray([config.mu0_c], dtype=np.float64),
            receiver_mode="monolithic",
            segment_partition=None,
        )
        b_mode, c_mode = diagnostic.mismatched_frozen, diagnostic.mismatched_adaptive
        if (
            diagnostic.received_sha256 != b_mode.received_sha256
            or diagnostic.received_sha256 != c_mode.received_sha256
        ):
            raise RuntimeError("B and C did not preserve paired received-buffer identity")
        if (
            b_mode.initial_state.time_index != c_mode.initial_state.time_index
            or not np.array_equal(
                b_mode.initial_state.fluctuating_iq, c_mode.initial_state.fluctuating_iq
            )
            or not np.array_equal(b_mode.initial_state.full_iq, c_mode.initial_state.full_iq)
        ):
            raise RuntimeError("B and C must share the same initial estimator state")
        if any(
            not np.array_equal(row.pre_state.full_iq, row.post_state.full_iq)
            or not np.array_equal(row.pre_state.fluctuating_iq, row.post_state.fluctuating_iq)
            for row in b_mode.history
        ):
            raise RuntimeError("frozen mode B changed estimator state")
        if diagnostic.beta != config.beta:
            raise RuntimeError("run beta differs from the explicit experiment config")
        b_counts = b_mode.evaluation.counts
        c_counts = c_mode.evaluation.counts
        validate_hypothesis_edge_path(b_mode.decoded_hypothesis_path, initial_state=(0, 0))
        validate_hypothesis_edge_path(c_mode.decoded_hypothesis_path, initial_state=(0, 0))
        if (
            len(b_mode.decoded_information_bits) != 2 * config.symbols_per_run
            or len(c_mode.decoded_information_bits) != 2 * config.symbols_per_run
        ):
            raise RuntimeError("B/C decoder outputs must contain exactly 2F information bits")
        if (
            b_counts.total_bits != c_counts.total_bits
            or b_counts.total_symbols != c_counts.total_symbols
        ):
            raise RuntimeError("B/C run denominators differ")
        data_provenance = (
            f"SeedSequence(master={config.data_rng_master_seed}, spawn_key={data_spawn}) "
            f"-> PCG64(seed={data_seed})"
        )
        noise_provenance = (
            f"SeedSequence(master={config.noise_rng_master_seed}, spawn_key={noise_spawn}) "
            f"-> ADR-015 PCG64(seed={noise_seed})"
        )
        records.append(
            PairedMonteCarloRunRecord(
                experiment_id=config.experiment_id,
                run_id=run_id,
                symbols_per_run=config.symbols_per_run,
                b_counts=b_counts,
                c_counts=c_counts,
                b_hypothesis_path=tuple(b_mode.decoded_hypothesis_path),
                c_hypothesis_path=tuple(c_mode.decoded_hypothesis_path),
                b_decoded_information_bits=tuple(
                    int(value) for value in b_mode.decoded_information_bits
                ),
                c_decoded_information_bits=tuple(
                    int(value) for value in c_mode.decoded_information_bits
                ),
                b_ber=calculate_ber_ser(b_counts).ber,
                c_ber=calculate_ber_ser(c_counts).ber,
                b_ser=calculate_ber_ser(b_counts).ser,
                c_ser=calculate_ber_ser(c_counts).ser,
                delta_ber_run=calculate_ber_ser(c_counts).ber - calculate_ber_ser(b_counts).ber,
                delta_ser_run=calculate_ber_ser(c_counts).ser - calculate_ber_ser(b_counts).ser,
                data_seed=data_seed,
                data_spawn_key=data_spawn,
                data_seed_provenance=data_provenance,
                noise_seed=noise_seed,
                noise_spawn_key=noise_spawn,
                noise_seed_provenance=noise_provenance,
                real_channel_gain=config.real_channel_gain,
                sigma_squared=config.sigma_squared,
                effective_discrete_gamma_b=diagnostic.effective_discrete_gamma_b,
                beta=config.beta,
                initial_fluctuating_iq=config.initial_fluctuating_iq,
                initial_full_iq=config.initial_full_iq,
                alpha_prime_b=1.0,
                k_tilde_b=(0.0, 0.0),
                mu0_b=(0.0, 0.0),
                alpha_prime_c=config.alpha_prime_c,
                k_tilde_c=config.k_tilde_c,
                mu0_c=config.mu0_c,
                initial_csi_provenance="same explicit non-oracle mismatched state for B and C",
                absolute_sample_indices=diagnostic.absolute_sample_indices,
                absolute_symbol_indices=diagnostic.absolute_symbol_indices,
                estimator_time_indices=tuple(row.estimator_time_index for row in c_mode.history),
                received_sha256=diagnostic.received_sha256,
                b_received_sha256=b_mode.received_sha256,
                c_received_sha256=c_mode.received_sha256,
                b_state_unchanged=True,
                c_state_changed=any(
                    not np.array_equal(row.pre_state.full_iq, row.post_state.full_iq)
                    or not np.array_equal(
                        row.pre_state.fluctuating_iq, row.post_state.fluctuating_iq
                    )
                    for row in c_mode.history
                ),
                c_final_full_iq=tuple(float(value) for value in c_mode.final_state.full_iq[0]),
                c_final_deviation_from_initial=float(
                    np.linalg.norm(
                        c_mode.final_state.full_iq[0]
                        - np.asarray(config.initial_full_iq, dtype=np.float64)
                    )
                ),
                c_max_coefficient_error_norm=max(
                    row.full_estimate_error_norm for row in c_mode.history
                ),
                profile=config.reconstruction_profile,
                receiver_profile_version=config.receiver_profile_version,
                profile_provenance=config.profile_provenance,
                status="complete",
                warnings=tuple(
                    warning
                    for condition, warning in (
                        (
                            b_counts.bit_errors == 0 and b_counts.symbol_errors == 0,
                            "no_B_errors_in_run",
                        ),
                        (
                            c_counts.bit_errors == 0 and c_counts.symbol_errors == 0,
                            "no_C_errors_in_run",
                        ),
                    )
                    if condition
                ),
            )
        )

    paired_counts = tuple(
        PairedRunCounts(record.run_id, record.b_counts, record.c_counts) for record in records
    )
    bootstrap = paired_cluster_bootstrap(
        paired_counts,
        bootstrap_replicates=config.bootstrap_replicates,
        confidence_level=config.confidence_level,
        bootstrap_seed=config.bootstrap_seed,
    )
    return PairedMonteCarloResult(
        experiment_id=config.experiment_id,
        status=PAIRED_MONTE_CARLO_STATUS,
        config=config,
        runs=tuple(records),
        point_estimates=bootstrap.point_estimates,
        bootstrap=bootstrap,
        warning_flags=bootstrap.warning_flags,
    )
