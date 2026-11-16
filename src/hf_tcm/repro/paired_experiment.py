"""Paired REPRO-07 experiments using the existing transmitter/channel/receivers."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event
from typing import Any, Callable, Literal

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter

EXPERIMENT_SCHEMA = "repro07-paired-experiment-v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


@dataclass(frozen=True, slots=True)
class TrialSeeds:
    bits: int
    fading: int
    noise: int


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    experiment_id: str
    frame_symbols: int
    noise_variances: tuple[float, ...]
    trials_per_point: int
    root_seed: int
    output_dir: str
    run_level: Literal["smoke", "pilot", "long_frame"] = "pilot"
    experiment_label: str = "paired joint versus separate receivers"
    preset_mode: Literal["custom_research", "article_oriented"] = "custom_research"
    channel_profile: Literal[
        "identity",
        "static_single_path",
        "rician_single_path",
        "known_static_multipath",
        "unknown_static_multipath",
        "slow_fading_multipath",
        "rician_ar1_multipath",
    ] = "rician_ar1_multipath"
    path_delays_samples: tuple[int, ...] = (0, 3)
    path_powers: tuple[float, ...] = (1.0, 0.25)
    rician_k_factors: tuple[float, ...] = (4.0, 1.0)
    los_phases_rad: tuple[float, ...] = (0.0, 0.7)
    fading_correlation: float = 0.98
    samples_per_symbol: int = 8
    decoder_mode: Literal["finite_depth"] = "finite_depth"
    traceback_depth: int = 20
    confidence_level: float = 0.95
    bootstrap_replicates: int = 5000
    bootstrap_seed: int = 90107
    max_wall_seconds: float = 900.0
    max_trials: int = 60
    max_disk_bytes: int = 2_000_000_000
    diagnostics_level: Literal["summary_only", "selected_trials", "full_trace"] = "selected_trials"
    selected_trial_indices: tuple[int, ...] = (0,)
    snr_convention: str = "sample_domain_complex_noise_variance"
    schema_version: str = EXPERIMENT_SCHEMA

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.experiment_id):
            raise ValueError("experiment_id must be a safe filesystem identifier")
        if type(self.frame_symbols) is not int or self.frame_symbols < 1:
            raise ValueError("frame_symbols must be a positive integer")
        if self.run_level == "pilot" and self.trials_per_point < 20:
            raise ValueError("pilot requires at least 20 independent trials per point")
        minimum_trials = 1
        if type(self.trials_per_point) is not int or self.trials_per_point < minimum_trials:
            raise ValueError("trials_per_point must be a positive integer")
        if type(self.root_seed) is not int or not 0 <= self.root_seed < 2**64:
            raise ValueError("root_seed must be an unsigned 64-bit integer")
        if not self.noise_variances or any(
            not np.isfinite(v) or v < 0 for v in self.noise_variances
        ):
            raise ValueError("noise_variances must be a nonempty finite sample-domain grid")
        if len(set(self.noise_variances)) != len(self.noise_variances):
            raise ValueError("noise_variances must be unique")
        if self.snr_convention != "sample_domain_complex_noise_variance":
            raise ValueError("only sample-domain noise is supported; physical Eb/N0 is undefined")
        if self.samples_per_symbol != 8 or self.traceback_depth != 20:
            raise ValueError("REPRO-07 paired receiver preset requires 8 samples/symbol and eta=20")
        if self.decoder_mode != "finite_depth":
            raise ValueError("paired research profile currently requires finite_depth decoding")
        if not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must lie strictly between 0 and 1")
        if type(self.bootstrap_replicates) is not int or self.bootstrap_replicates < 100:
            raise ValueError("bootstrap_replicates must be an integer >= 100")
        if type(self.bootstrap_seed) is not int or not 0 <= self.bootstrap_seed < 2**64:
            raise ValueError("bootstrap_seed must be an unsigned 64-bit integer")
        if not np.isfinite(self.max_wall_seconds) or self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be positive and finite")
        if type(self.max_trials) is not int or self.max_trials < 1:
            raise ValueError("max_trials must be a positive integer")
        if type(self.max_disk_bytes) is not int or self.max_disk_bytes < 1:
            raise ValueError("max_disk_bytes must be a positive integer")
        valid_profiles = {
            "identity",
            "static_single_path",
            "rician_single_path",
            "known_static_multipath",
            "unknown_static_multipath",
            "slow_fading_multipath",
            "rician_ar1_multipath",
        }
        if self.channel_profile not in valid_profiles:
            raise ValueError("unsupported channel_profile for paired runner")
        sizes = {
            len(self.path_delays_samples),
            len(self.path_powers),
            len(self.rician_k_factors),
            len(self.los_phases_rad),
        }
        if sizes != {len(self.path_delays_samples)} or not self.path_delays_samples:
            raise ValueError("path delay, power, K and phase lists must have equal nonzero length")
        if any(type(d) is not int or d < 0 for d in self.path_delays_samples):
            raise ValueError("path delays must be non-negative integer samples")
        if any(not np.isfinite(v) or v <= 0 for v in self.path_powers):
            raise ValueError("path powers must be positive and finite")
        if any(not np.isfinite(v) or v < 0 for v in self.rician_k_factors):
            raise ValueError("Rician K factors must be non-negative and finite")
        if not 0 <= self.fading_correlation < 1:
            raise ValueError("fading_correlation must be in [0, 1)")
        if self.channel_profile == "identity" and (
            self.path_delays_samples != (0,) or self.path_powers != (1.0,)
        ):
            raise ValueError("identity profile requires one zero-delay unit-power path")
        if (
            self.channel_profile in {"static_single_path", "rician_single_path"}
            and len(self.path_delays_samples) != 1
        ):
            raise ValueError("single-path profiles require exactly one path")
        if self.channel_profile == "slow_fading_multipath" and self.fading_correlation < 0.98:
            raise ValueError("slow_fading_multipath requires sample correlation rho >= 0.98")
        if self.run_level == "long_frame" and self.frame_symbols != 20_000:
            raise ValueError("long_frame preset requires exactly 20000 TCM symbols")
        if self.preset_mode == "article_oriented" and self.channel_profile != "identity":
            raise ValueError(
                "article-oriented mode cannot invent unspecified article channel/noise values; "
                "select verified source parameters explicitly"
            )
        if self.diagnostics_level not in {"summary_only", "selected_trials", "full_trace"}:
            raise ValueError("unsupported diagnostics_level")
        if any(type(i) is not int or i < 0 for i in self.selected_trial_indices):
            raise ValueError("selected_trial_indices must contain non-negative integers")
        if self.schema_version != EXPERIMENT_SCHEMA:
            raise ValueError("unsupported experiment schema_version")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in (
            "noise_variances",
            "path_delays_samples",
            "path_powers",
            "rician_k_factors",
            "los_phases_rad",
            "selected_trial_indices",
        ):
            result[key] = list(result[key])
        return result

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ExperimentConfig:
        if not isinstance(values, dict):
            raise ValueError("experiment config must be a JSON object")
        extra = set(values) - set(cls.__dataclass_fields__)
        if extra:
            raise ValueError(f"unexpected experiment config field: {sorted(extra)[0]}")
        data = dict(values)
        for key in (
            "noise_variances",
            "path_delays_samples",
            "path_powers",
            "rician_k_factors",
            "los_phases_rad",
            "selected_trial_indices",
        ):
            if key in data:
                data[key] = tuple(data[key])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid experiment config: {exc}") from exc


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def derive_trial_seeds(
    root_seed: int, experiment_id: str, point_index: int, trial_index: int
) -> TrialSeeds:
    """Derive independent stream seeds without relying on global RNG state."""

    def one(domain: str) -> int:
        payload = f"repro07-v1|{root_seed}|{experiment_id}|{point_index}|{trial_index}|{domain}"
        return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")

    return TrialSeeds(one("bits"), one("fading"), one("noise"))


def _completed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("status") == "completed"]


def aggregate_trials(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _completed(records)
    if not rows:
        return {"completed_trials": 0, "status": "no_completed_trials"}
    fields = (
        "compared_bits",
        "compared_symbols",
        "joint_bit_errors",
        "separate_bit_errors",
        "joint_pair_symbol_errors",
        "separate_pair_symbol_errors",
        "joint_phase_symbol_errors",
        "separate_phase_symbol_errors",
    )
    totals = {key: sum(int(row[key]) for row in rows) for key in fields}
    if totals["compared_bits"] <= 0 or totals["compared_symbols"] <= 0:
        raise ValueError("completed trial denominators must be positive")
    if any(row["compared_bits"] != row["compared_bits_separate"] for row in rows):
        raise ValueError("paired arms must compare the same information-bit count")
    joint_ber = totals["joint_bit_errors"] / totals["compared_bits"]
    separate_ber = totals["separate_bit_errors"] / totals["compared_bits"]
    joint_ser = totals["joint_pair_symbol_errors"] / totals["compared_symbols"]
    separate_ser = totals["separate_pair_symbol_errors"] / totals["compared_symbols"]
    return {
        "status": "completed",
        "completed_trials": len(rows),
        "total_compared_bits": totals["compared_bits"],
        "total_compared_pair_symbols": totals["compared_symbols"],
        "joint_bit_errors": totals["joint_bit_errors"],
        "separate_bit_errors": totals["separate_bit_errors"],
        "joint_ber": joint_ber,
        "separate_ber": separate_ber,
        "delta_ber_joint_minus_separate": joint_ber - separate_ber,
        "absolute_ber_difference": abs(joint_ber - separate_ber),
        "relative_error_reduction_joint_vs_separate": (
            None if separate_ber == 0 else (separate_ber - joint_ber) / separate_ber
        ),
        "joint_pair_symbol_errors": totals["joint_pair_symbol_errors"],
        "separate_pair_symbol_errors": totals["separate_pair_symbol_errors"],
        "joint_pair_ser": joint_ser,
        "separate_pair_ser": separate_ser,
        "delta_pair_ser_joint_minus_separate": joint_ser - separate_ser,
        "joint_phase_symbol_errors": totals["joint_phase_symbol_errors"],
        "separate_phase_symbol_errors": totals["separate_phase_symbol_errors"],
        "joint_phase_ser": totals["joint_phase_symbol_errors"] / totals["compared_symbols"],
        "separate_phase_ser": totals["separate_phase_symbol_errors"] / totals["compared_symbols"],
        "total_bits_per_receiver": totals["compared_bits"],
    }


def paired_cluster_bootstrap(
    records: list[dict[str, Any]],
    *,
    confidence_level: float,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    """Ratio-of-sums bootstrap with the paired trial as the sampling unit."""
    rows = _completed(records)
    if len(rows) < 2:
        return {
            "status": "exploratory_too_few_independent_trials",
            "independent_trials": len(rows),
            "resampling_unit": "paired_trial",
            "joint_ber_ci": None,
            "separate_ber_ci": None,
            "delta_ber_ci": None,
        }
    if not 0 < confidence_level < 1 or type(replicates) is not int or replicates < 100:
        raise ValueError("invalid bootstrap confidence or replicate count")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("bootstrap seed must be unsigned 64-bit")
    errors_a = np.asarray([r["joint_bit_errors"] for r in rows], dtype=np.int64)
    errors_b = np.asarray([r["separate_bit_errors"] for r in rows], dtype=np.int64)
    denoms = np.asarray([r["compared_bits"] for r in rows], dtype=np.int64)
    pair_a = np.asarray([r["joint_pair_symbol_errors"] for r in rows], dtype=np.int64)
    pair_b = np.asarray([r["separate_pair_symbol_errors"] for r in rows], dtype=np.int64)
    symbol_denoms = np.asarray([r["compared_symbols"] for r in rows], dtype=np.int64)
    if np.any(denoms <= 0) or any(r["compared_bits"] != r["compared_bits_separate"] for r in rows):
        raise ValueError("paired bootstrap requires positive equal denominators within each trial")
    if np.any(symbol_denoms <= 0):
        raise ValueError("paired bootstrap requires positive symbol denominators")
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(0, len(rows), size=(replicates, len(rows)))
    sampled_denoms = denoms[indices].sum(axis=1)
    ber_a = errors_a[indices].sum(axis=1) / sampled_denoms
    ber_b = errors_b[indices].sum(axis=1) / sampled_denoms
    delta = ber_a - ber_b
    sampled_symbols = symbol_denoms[indices].sum(axis=1)
    ser_a = pair_a[indices].sum(axis=1) / sampled_symbols
    ser_b = pair_b[indices].sum(axis=1) / sampled_symbols
    alpha = (1 - confidence_level) / 2

    def interval(values: np.ndarray) -> list[float]:
        low, high = np.quantile(values, [alpha, 1 - alpha], method="linear")
        return [float(low), float(high)]

    return {
        "status": "computed_trial_cluster_bootstrap",
        "confidence_level": confidence_level,
        "bootstrap_replicates": replicates,
        "bootstrap_seed": seed,
        "independent_trials": len(rows),
        "resampling_unit": "paired_trial",
        "aggregation": "ratio_of_sums",
        "joint_ber_ci": interval(ber_a),
        "separate_ber_ci": interval(ber_b),
        "delta_ber_ci": interval(delta),
        "joint_pair_ser_ci": interval(ser_a),
        "separate_pair_ser_ci": interval(ser_b),
        "delta_pair_ser_ci": interval(ser_a - ser_b),
        "zero_error_trials": int(np.count_nonzero((errors_a == 0) & (errors_b == 0))),
        "degenerate_all_zero_differences": bool(np.all(errors_a == errors_b)),
    }


@dataclass(frozen=True, slots=True)
class PairedTrialResult:
    record: dict[str, Any]
    diagnostics: dict[str, np.ndarray] | None = None


def _receiver_config_hash(config: Any) -> str:
    return digest_json(config.to_dict())


def run_paired_trial(
    config: ExperimentConfig, point_index: int, trial_index: int
) -> PairedTrialResult:
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be ExperimentConfig")
    if not 0 <= point_index < len(config.noise_variances):
        raise ValueError("noise point index outside configured grid")
    if not 0 <= trial_index < config.trials_per_point:
        raise ValueError("trial index outside configured count")
    seeds = derive_trial_seeds(config.root_seed, config.experiment_id, point_index, trial_index)
    noise_variance = float(config.noise_variances[point_index])
    tx_config = TransmitterConfig(
        source_mode="seeded_random",
        frame_symbols=config.frame_symbols,
        seed=seeds.bits,
        termination_policy="none",
    )
    tx = run_transmitter(tx_config)
    known_static_control = config.channel_profile == "known_static_multipath"
    adaptive_paths: tuple[AdaptivePathConfig, ...] | None
    adaptive_mode: str | None
    rho = config.fading_correlation
    if config.channel_profile in {"identity", "static_single_path", "known_static_multipath"}:
        if config.channel_profile == "identity":
            delays, powers, phases = (0,), (1.0,), (0.0,)
        elif config.channel_profile == "static_single_path":
            delays, powers, phases = (
                config.path_delays_samples,
                config.path_powers,
                config.los_phases_rad,
            )
        else:
            delays, powers, phases = (
                config.path_delays_samples,
                config.path_powers,
                config.los_phases_rad,
            )
        static_paths = tuple(
            ChannelPathConfig(
                delay,
                power,
                0.0,
                phase,
                constant_coefficient=complex(np.sqrt(power) * np.exp(1j * phase)),
            )
            for delay, power, phase in zip(delays, powers, phases, strict=True)
        )
        channel_config = ChannelConfig(
            profile_id=f"repro07_{config.channel_profile}_smoke_v1",
            paths=static_paths,
            fading_mode="constant",
            noise_model="none" if noise_variance == 0 else "complex_awgn_sample_domain",
            noise_complex_variance=noise_variance,
            fading_seed=seeds.fading,
            noise_seed=seeds.noise,
        )
        adaptive_paths = (
            None
            if known_static_control
            else tuple(
                AdaptivePathConfig(
                    delay_samples=path.delay_samples,
                    prior_mean=(1 + 0j) if config.channel_profile == "identity" else 0j,
                    prior_variance=0.25
                    if config.channel_profile == "identity"
                    else path.average_power,
                )
                for path in static_paths
            )
        )
        adaptive_mode = None if known_static_control else "unknown_static"
    else:
        channel_fading_mode = (
            "rician_static"
            if config.channel_profile == "unknown_static_multipath"
            else "rician_ar1"
        )
        channel_paths = tuple(
            ChannelPathConfig(delay, power, k, phase)
            for delay, power, k, phase in zip(
                config.path_delays_samples,
                config.path_powers,
                config.rician_k_factors,
                config.los_phases_rad,
                strict=True,
            )
        )
        channel_config = ChannelConfig(
            profile_id=f"repro07_{config.channel_profile}_sample_noise_v1",
            paths=channel_paths,
            fading_mode=channel_fading_mode,
            correlation=(config.fading_correlation if channel_fading_mode == "rician_ar1" else 0.0),
            noise_model="none" if noise_variance == 0 else "complex_awgn_sample_domain",
            noise_complex_variance=noise_variance,
            fading_seed=seeds.fading,
            noise_seed=seeds.noise,
        )
        if config.channel_profile == "unknown_static_multipath":
            adaptive_paths = tuple(
                AdaptivePathConfig(
                    delay_samples=p.delay_samples,
                    prior_mean=0j,
                    prior_variance=p.average_power,
                )
                for p in channel_paths
            )
            adaptive_mode = "unknown_static"
            rho = 1.0
        else:
            adaptive_paths = tuple(
                AdaptivePathConfig(
                    delay_samples=p.delay_samples,
                    average_power=p.average_power,
                    k_factor=p.k_factor,
                    los_phase_rad=p.los_phase_rad,
                )
                for p in channel_paths
            )
            adaptive_mode = (
                "slow_fading_rician_ar1"
                if config.channel_profile == "slow_fading_multipath"
                else "rician_ar1"
            )
    channel = run_channel(tx, channel_config)
    observation = channel.receiver_observation
    observation_hash = observation.sha256
    if known_static_control:
        known_paths = tuple(
            MultipathPathConfig(path.delay_samples, path.constant_coefficient or 0j)
            for path in channel_config.paths
        )
        joint_config: Any = MultipathReceiverConfig(
            expected_symbol_count=config.frame_symbols,
            paths=known_paths,
            initial_state=tx_config.initial_state,
            termination_policy="none",
            decoder_mode="finite_depth",
            traceback_depth=20,
            trace_output_mode="compact",
            profile_id="repro07_known_static_06b_control_eta20_v1",
        )
        started = time.perf_counter()
        joint = run_multipath_joint_receiver(observation, joint_config)
        joint_profile_id = joint.receiver_profile_id
        joint_is_adaptive = False
        joint_seconds = time.perf_counter() - started
    else:
        assert adaptive_paths is not None and adaptive_mode is not None
        joint_config = AdaptiveMultipathReceiverConfig(
            expected_symbol_count=config.frame_symbols,
            paths=adaptive_paths,
            channel_mode=adaptive_mode,
            observation_noise_variance=noise_variance,
            correlation=rho,
            decoder_mode="finite_depth",
            traceback_depth=20,
            initial_state=tx_config.initial_state,
            termination_policy="none",
            profile_id=f"repro07_joint_{config.channel_profile}_eta20_v1",
        )
        started = time.perf_counter()
        joint = run_adaptive_multipath_receiver(observation, joint_config)
        joint_profile_id = joint.receiver_profile_id
        joint_is_adaptive = True
        joint_seconds = time.perf_counter() - started
    separate_config = SeparateReceiverConfig.article_oriented(
        expected_symbol_count=config.frame_symbols,
        initial_state=tx_config.initial_state,
        termination_policy="none",
        trace_output_mode="compact",
    )
    started = time.perf_counter()
    separate = run_separate_receiver(observation, separate_config)
    separate_seconds = time.perf_counter() - started
    ref_bits = np.asarray(tx.information_bits, dtype=np.int8)
    ref_pairs = ref_bits.reshape((-1, 2))
    decoded_joint = np.asarray(joint.decoded_information_bits, dtype=np.int8)
    decoded_separate = np.asarray(separate.decoded_information_bits, dtype=np.int8)
    if decoded_joint.shape != ref_bits.shape or decoded_separate.shape != ref_bits.shape:
        raise ValueError("receiver outputs do not match the paired payload boundary")
    joint_pairs = decoded_joint.reshape((-1, 2))
    separate_pairs = decoded_separate.reshape((-1, 2))
    joint_phase_by_edge = np.asarray(
        [4 * edge[3][0] + 2 * edge[3][1] + edge[3][2] for edge in transition_table()],
        dtype=np.int8,
    )
    joint_phases = joint_phase_by_edge[np.asarray(joint.decoded_edge_ids, dtype=np.int64)]
    ref_phases = np.asarray(tx.phase_indices, dtype=np.int8)
    eval_sep = evaluate_separate_receiver(separate, ref_bits, ref_phases)
    eval_joint = (
        evaluate_multipath_receiver(joint, ref_bits, ref_phases) if known_static_control else None
    )
    errors_joint = decoded_joint != ref_bits
    errors_sep = decoded_separate != ref_bits
    if eval_sep.bit_errors != int(np.count_nonzero(errors_sep)):
        raise ValueError(
            "REPRO-04 evaluation adapter disagrees with paired information-bit recount"
        )
    if eval_joint is not None and eval_joint.bit_errors != int(np.count_nonzero(errors_joint)):
        raise ValueError("REPRO-06B evaluation adapter disagrees with paired bit recount")
    pair_errors_joint = np.any(joint_pairs != ref_pairs, axis=1)
    pair_errors_sep = np.any(separate_pairs != ref_pairs, axis=1)
    phase_errors_joint = joint_phases != ref_phases
    phase_errors_sep = np.asarray(separate.hard_phase_indices) != ref_phases
    ref_hash = hashlib.sha256(
        ref_bits.tobytes() + np.ascontiguousarray(tx.phase_indices).tobytes()
    ).hexdigest()
    tx_hash = hashlib.sha256(np.ascontiguousarray(tx.tx_samples).tobytes()).hexdigest()
    joint_config_hash = _receiver_config_hash(joint_config)
    separate_config_hash = _receiver_config_hash(separate_config)
    if (
        joint.observation_sha256 != separate.observation_sha256
        or observation_hash != joint.observation_sha256
    ):
        raise ValueError("paired receiver observation SHA-256 mismatch")
    record: dict[str, Any] = {
        "schema_version": "repro07-paired-trial-v1",
        "status": "completed",
        "experiment_id": config.experiment_id,
        "experiment_config_sha256": digest_json(config.to_dict()),
        "point_index": point_index,
        "trial_index": trial_index,
        "noise_variance_complex_per_sample": noise_variance,
        "snr_convention": config.snr_convention,
        "seeds": asdict(seeds),
        "transmitter_reference_sha256": ref_hash,
        "transmitter_samples_sha256": tx_hash,
        "transmitter_config_sha256": digest_json(tx_config.to_dict()),
        "channel_config_sha256": digest_json(channel_config.to_dict()),
        "joint_receiver_config_sha256": joint_config_hash,
        "joint_receiver_profile_id": joint_profile_id,
        "joint_receiver_kind": "known_static_06b_control"
        if known_static_control
        else "adaptive_06c",
        "separate_receiver_config_sha256": separate_config_hash,
        "joint_observation_sha256": joint.observation_sha256,
        "separate_observation_sha256": separate.observation_sha256,
        "observation_sha256": observation_hash,
        "compared_bits": int(ref_bits.size),
        "compared_bits_separate": int(ref_bits.size),
        "joint_bit_errors": int(np.count_nonzero(errors_joint)),
        "separate_bit_errors": int(np.count_nonzero(errors_sep)),
        "compared_symbols": int(ref_pairs.shape[0]),
        "joint_pair_symbol_errors": int(np.count_nonzero(pair_errors_joint)),
        "separate_pair_symbol_errors": int(np.count_nonzero(pair_errors_sep)),
        "joint_phase_symbol_errors": int(np.count_nonzero(phase_errors_joint)),
        "separate_phase_symbol_errors": int(np.count_nonzero(phase_errors_sep)),
        "joint_bit_error_positions": np.flatnonzero(errors_joint).astype(int).tolist(),
        "separate_bit_error_positions": np.flatnonzero(errors_sep).astype(int).tolist(),
        "joint_pair_error_positions": np.flatnonzero(pair_errors_joint).astype(int).tolist(),
        "separate_pair_error_positions": np.flatnonzero(pair_errors_sep).astype(int).tolist(),
        "joint_phase_error_positions": np.flatnonzero(phase_errors_joint).astype(int).tolist(),
        "separate_phase_error_positions": np.flatnonzero(phase_errors_sep).astype(int).tolist(),
        "joint_decoder_mode": joint.decoder_mode,
        "separate_decoder_mode": separate.traceback_mode,
        "traceback_depth": 20,
        "frame_boundary_policy": "unterminated_zero_extension_channel_tail_scored_in_final_symbol",
        "joint_seconds": joint_seconds,
        "separate_seconds": separate_seconds,
        "channel_profile": config.channel_profile,
        "receiver_comparison_scope": "two_complete_receiver_algorithms_not_metric_only",
    }
    diagnostics = None
    if config.diagnostics_level in {"selected_trials", "full_trace"} and (
        config.diagnostics_level == "full_trace" or trial_index in config.selected_trial_indices
    ):
        diagnostics = {
            "received_samples": np.asarray(observation.received_samples),
            "joint_decoded_bits": decoded_joint,
            "separate_decoded_bits": decoded_separate,
            "reference_bits": ref_bits,
            "true_channel_coefficients_evaluation_only": np.asarray(
                channel.evaluation_truth.coefficients
            ),
            "transmitted_samples_evaluation_only": np.asarray(
                channel.evaluation_truth.transmitter_samples
            ),
        }
        if joint_is_adaptive:
            diagnostics["joint_estimator_mean"] = np.asarray(joint.estimator_mean_by_symbol_node)
            diagnostics["joint_branch_metrics"] = np.asarray(joint.branch_metric_rows)
    return PairedTrialResult(record, diagnostics)


def _atomic_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
    return hashlib.sha256(data).hexdigest()


def _record_digest(record: dict[str, Any]) -> str:
    clean = {key: value for key, value in record.items() if key != "record_sha256"}
    return digest_json(clean)


def _validate_trial_record(path: Path, config_hash: str) -> dict[str, Any]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot resume from invalid trial record {path}") from exc
    if record.get("experiment_config_sha256") != config_hash:
        raise ValueError("completed trial belongs to a different experiment config")
    if record.get("record_sha256") != _record_digest(record):
        raise ValueError("trial record SHA-256 mismatch; refusing to skip corrupted result")
    if record.get("diagnostics_sha256") is not None:
        diagnostics_path = path.parent / "diagnostics.npz"
        if (
            not diagnostics_path.is_file()
            or hashlib.sha256(diagnostics_path.read_bytes()).hexdigest()
            != record["diagnostics_sha256"]
        ):
            raise ValueError(
                "trial diagnostics SHA-256 mismatch; refusing to skip corrupted result"
            )
    return record


def _tree_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _write_trial(output: Path, result: PairedTrialResult, config_hash: str) -> dict[str, Any]:
    record = dict(result.record)
    if result.diagnostics is not None:
        npz = output / "diagnostics.npz"
        temp = output / "diagnostics.npz.tmp"
        with temp.open("wb") as stream:
            np.savez_compressed(stream, **result.diagnostics)
        os.replace(temp, npz)
        record["diagnostics_sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
    record["experiment_config_sha256"] = config_hash
    record["record_sha256"] = _record_digest(record)
    _atomic_json(output / "trial.json", record)
    return record


def run_paired_experiment(
    config: ExperimentConfig,
    *,
    resume: bool = True,
    progress: bool = True,
    stop_event: Event | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be ExperimentConfig")
    if not resume:
        raise ValueError("overwrite is not enabled; choose a new experiment_id/output directory")
    base = Path(config.output_dir).resolve()
    root = base / config.experiment_id
    root.mkdir(parents=True, exist_ok=True)
    config_dict = config.to_dict()
    config_hash = digest_json(config_dict)
    config_path = root / "experiment_config.json"
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if digest_json(existing) != config_hash:
            raise ValueError("existing experiment ID has a different frozen configuration")
    else:
        _atomic_json(config_path, config_dict)
    started = time.monotonic()
    completed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    all_count = len(config.noise_variances) * config.trials_per_point
    attempted = 0
    stop_reason: str | None = None
    for point_index, noise_variance in enumerate(config.noise_variances):
        for trial_index in range(config.trials_per_point):
            if stop_event is not None and stop_event.is_set():
                stop_reason = "user_requested_stop_after_completed_pair"
                break
            trial_dir = root / f"point_{point_index:02d}" / f"trial_{trial_index:04d}"
            record_path = trial_dir / "trial.json"
            if record_path.exists():
                record = _validate_trial_record(record_path, config_hash)
                if record["status"] == "completed":
                    completed.append(record)
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "completed_trials": len(completed),
                                "planned_trials": all_count,
                                "point_index": point_index,
                                "trial_index": trial_index,
                                "resumed": True,
                            }
                        )
                    continue
            if attempted >= config.max_trials:
                stop_reason = "max_trials_budget"
                break
            if time.monotonic() - started >= config.max_wall_seconds:
                stop_reason = "wall_clock_budget"
                break
            if _tree_size(root) >= config.max_disk_bytes:
                stop_reason = "disk_budget"
                break
            attempted += 1
            trial_dir.mkdir(parents=True, exist_ok=True)
            try:
                result = run_paired_trial(config, point_index, trial_index)
                if result.diagnostics is not None:
                    diagnostic_bytes = sum(
                        int(array.nbytes) for array in result.diagnostics.values()
                    )
                    if _tree_size(root) + diagnostic_bytes > config.max_disk_bytes:
                        stop_reason = "disk_budget_before_trial_commit"
                        break
                record = _write_trial(trial_dir, result, config_hash)
                completed.append(record)
                if progress_callback is not None:
                    progress_callback(
                        {
                            "completed_trials": len(completed),
                            "planned_trials": all_count,
                            "point_index": point_index,
                            "trial_index": trial_index,
                            "resumed": False,
                        }
                    )
            except Exception as exc:
                failure = {
                    "status": "failed",
                    "experiment_config_sha256": config_hash,
                    "point_index": point_index,
                    "trial_index": trial_index,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                failures.append(failure)
                failure_path = trial_dir / "failure.json"
                if failure_path.exists():
                    old = json.loads(failure_path.read_text(encoding="utf-8"))
                    history = old.get("attempts", [])
                else:
                    history = []
                history.append(failure)
                _atomic_json(failure_path, {"attempts": history})
                if progress_callback is not None:
                    progress_callback(
                        {
                            "completed_trials": len(completed),
                            "planned_trials": all_count,
                            "point_index": point_index,
                            "trial_index": trial_index,
                            "failed_attempts": len(failures),
                        }
                    )
            if progress:
                elapsed = time.monotonic() - started
                avg = elapsed / attempted if attempted else 0.0
                remaining = max(0, all_count - len(completed) - len(failures))
                print(
                    f"REPRO-07 {len(completed)}/{all_count} completed; "
                    f"{remaining * avg:.1f}s estimated remaining",
                    flush=True,
                )
        if stop_reason:
            break
    by_point: list[dict[str, Any]] = []
    for point_index, variance in enumerate(config.noise_variances):
        point_rows = [r for r in completed if r["point_index"] == point_index]
        aggregate = aggregate_trials(point_rows)
        aggregate["noise_variance_complex_per_sample"] = float(variance)
        aggregate["confidence_intervals"] = paired_cluster_bootstrap(
            point_rows,
            confidence_level=config.confidence_level,
            replicates=config.bootstrap_replicates,
            seed=(config.bootstrap_seed + point_index) % 2**64,
        )
        by_point.append(aggregate)
    finished = len(completed) == all_count
    summary = {
        "schema_version": "repro07-experiment-result-v1",
        "experiment_id": config.experiment_id,
        "experiment_config_sha256": config_hash,
        "status": "completed" if finished else "incomplete",
        "planned_trials": all_count,
        "completed_trials": len(completed),
        "failed_attempts_this_run": len(failures),
        "stop_reason": stop_reason,
        "elapsed_seconds_this_run": time.monotonic() - started,
        "noise_convention": config.snr_convention,
        "receiver_comparison_scope": "two complete receiver algorithms, not metric-only ablation",
        "points": by_point,
        "completed_trial_record_sha256": [r["record_sha256"] for r in completed],
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
    }
    _atomic_json(root / "summary.json", summary)
    files = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file() and p.name != "manifest.json" and not p.name.endswith(".tmp")
    }
    _atomic_json(root / "manifest.json", {"schema_version": "repro07-manifest-v1", "files": files})
    if not finished:
        return summary
    return summary


def verify_experiment(output_dir: str | Path) -> dict[str, str]:
    root = Path(output_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise ValueError("invalid REPRO-07 manifest")
    for name in expected:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe path in REPRO-07 manifest")
    actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in expected}
    if actual != expected:
        raise ValueError("REPRO-07 experiment manifest SHA-256 mismatch")
    return actual
