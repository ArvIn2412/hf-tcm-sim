"""Paired validation trials for the isolated Euclidean/Hamming contrast."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import Event
from typing import Any, Callable, Literal

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.atomic_io import atomic_replace_bytes
from hf_tcm.repro.channel_config import ChannelConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.energy_statistics import aggregate_energy_records, analyze_energy_records
from hf_tcm.repro.metric_isolation import (
    MetricFrontendResult,
    PilotSchedule,
    build_pilot_schedule,
    euclidean_branch_metric_rows,
    hamming_branch_metric_rows,
    pilot_constrained_metric_rows,
    run_awgn_direct_frontend,
    run_metric_viterbi,
    run_oracle_csi_frontend,
    run_pilot_frontend,
)
from hf_tcm.repro.transmitter import run_transmitter

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
FrontendMode = Literal["awgn_direct_control", "pilot_equalized", "oracle_csi", "known_channel"]
EuclideanMetricKind = Literal["unweighted", "csi_weighted"]
_FRONTEND_MODES = frozenset(
    {"awgn_direct_control", "pilot_equalized", "oracle_csi", "known_channel"}
)
_EUCLIDEAN_METRICS = frozenset({"unweighted", "csi_weighted"})
_ORACLE_FRONTEND_LABELS = frozenset({"diagnostic_oracle_csi", "known_channel_csi"})
_PHASE_BY_EDGE = np.asarray(
    [4 * row[3][0] + 2 * row[3][1] + row[3][2] for row in transition_table()],
    dtype=np.int8,
)


@dataclass(frozen=True, slots=True)
class MetricTrialSpec:
    trial_id: str
    frame_symbols: int
    source_seed: int
    channel_config: ChannelConfig
    frontend_mode: FrontendMode
    amplitude: float = 1.0
    preamble_symbols: int = 4
    pilot_period: int = 32
    pilot_burst_symbols: int = 4
    traceback_depth: int = 20
    euclidean_metric: EuclideanMetricKind = "unweighted"

    def __post_init__(self) -> None:
        if not isinstance(self.trial_id, str) or not _SAFE_ID.fullmatch(self.trial_id):
            raise ValueError("trial_id must be a safe identifier")
        if type(self.frame_symbols) is not int or self.frame_symbols < 4:
            raise ValueError("frame_symbols must be an integer >= 4")
        if type(self.source_seed) is not int or not 0 <= self.source_seed < 2**64:
            raise ValueError("source_seed must be an unsigned 64-bit seed")
        if not isinstance(self.channel_config, ChannelConfig):
            raise TypeError("channel_config must be ChannelConfig")
        if self.frontend_mode not in _FRONTEND_MODES:
            raise ValueError("unsupported metric-isolation frontend mode")
        if self.euclidean_metric not in _EUCLIDEAN_METRICS:
            raise ValueError("euclidean_metric must be unweighted or csi_weighted")
        if not math.isfinite(self.amplitude) or self.amplitude <= 0:
            raise ValueError("amplitude must be finite and positive")
        if self.traceback_depth != 20:
            raise ValueError("the frozen controlled metric comparison uses eta=20")
        if self.frontend_mode == "awgn_direct_control":
            if (
                self.channel_config.profile_id != "awgn"
                or self.channel_config.fading_mode != "constant"
                or len(self.channel_config.paths) != 1
                or self.channel_config.paths[0].delay_samples != 0
                or self.channel_config.paths[0].constant_coefficient != 1 + 0j
                or self.channel_config.noise_model not in {"none", "complex_awgn_sample_domain"}
            ):
                raise ValueError(
                    "the no-equalizer control requires unit-gain AWGN or noiseless identity"
                )
        elif max(path.delay_samples for path in self.channel_config.paths) >= 8:
            raise ValueError("the common clean-tail frontend requires delays below eight samples")
        if self.channel_config.noise_model == "complex_awgn_sample_domain" and not (
            self.channel_config.reveal_noise_variance
        ):
            raise ValueError("the declared AWGN variance must be public to the receiver frontend")


@dataclass(frozen=True, slots=True)
class MetricTrialResult:
    summary: dict[str, Any]
    reference_payload_pairs: NDArray[np.int8]
    decoded_euclidean_pairs: NDArray[np.int8]
    decoded_hamming_pairs: NDArray[np.int8]
    transmitted_samples: NDArray[np.complex128]
    received_samples: NDArray[np.complex128]
    equalized_symbols: NDArray[np.complex128]
    euclidean_branch_metrics: NDArray[np.float64]
    hamming_branch_metrics: NDArray[np.int8]
    schedule: PilotSchedule | None
    frontend: MetricFrontendResult


def _hash_arrays(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _truth_diagnostics(
    frontend: MetricFrontendResult,
    transmitter: Any,
    channel: Any,
    schedule: PilotSchedule | None,
) -> dict[str, Any]:
    """Read EvaluationTruth after decoding only, for evaluator-side diagnostics."""
    truth = channel.evaluation_truth
    indices = np.asarray(frontend.selected_sample_indices, dtype=np.int64)
    composite = np.sum(np.asarray(truth.coefficients)[:, indices], axis=0)
    tx_symbols = np.asarray(transmitter.symbols[: len(indices)], dtype=np.complex128)
    expected_clean = tx_symbols[:, None] * composite
    clean_received = np.asarray(truth.faded_signal)[indices]
    clean_residual = clean_received - expected_clean
    composite_centered = composite - np.mean(composite, axis=1, keepdims=True)
    within_symbol_gain_variation = float(np.sqrt(np.mean(np.square(np.abs(composite_centered)))))

    updates = np.asarray(frontend.gain_update_mask, dtype=bool)
    gain_rmse = None
    if np.any(updates):
        true_pilot_gain = np.mean(composite, axis=1)
        error = np.asarray(frontend.estimated_composite_gain)[updates] - true_pilot_gain[updates]
        gain_rmse = float(np.sqrt(np.mean(np.square(np.abs(error)))))

    noise_samples = np.asarray(truth.noise_samples)[indices]
    noise_component = np.zeros(len(indices), dtype=np.complex128)
    valid = np.asarray(frontend.valid_symbol_mask, dtype=bool)
    estimated_gain = np.asarray(frontend.estimated_composite_gain)
    for symbol_index in np.flatnonzero(valid):
        sample_noise = noise_samples[symbol_index]
        if frontend.mode in _ORACLE_FRONTEND_LABELS:
            weight = composite[symbol_index]
            denominator = float(np.vdot(weight, weight).real)
            if denominator > 0:
                noise_component[symbol_index] = np.vdot(weight, sample_noise) / denominator
        elif frontend.mode == "awgn_direct_control":
            noise_component[symbol_index] = np.mean(sample_noise)
        else:
            gain = estimated_gain[symbol_index]
            denominator = len(sample_noise) * abs(gain) ** 2
            if denominator > 0:
                noise_component[symbol_index] = (
                    np.vdot(np.full(len(sample_noise), gain, dtype=np.complex128), sample_noise)
                    / denominator
                )

    selected_noise = noise_component[valid]
    empirical_variance = (
        float(np.mean(np.square(np.abs(selected_noise)))) if selected_noise.size else None
    )
    lag_one_correlation = None
    if selected_noise.size > 1:
        denominator = float(np.mean(np.square(np.abs(selected_noise))))
        if denominator > 0:
            lag_one_correlation = complex(
                np.mean(selected_noise[:-1] * np.conjugate(selected_noise[1:])) / denominator
            )
            lag_one_correlation = [float(lag_one_correlation.real), float(lag_one_correlation.imag)]

    data_symbols = valid.copy()
    if schedule is not None:
        data_symbols &= np.asarray(schedule.payload_mask, dtype=bool)
    estimated_signal_error = np.asarray(frontend.symbols)[data_symbols] - tx_symbols[data_symbols]
    residual_lag_one = None
    adjacent = data_symbols[:-1] & data_symbols[1:]
    if np.any(adjacent):
        residual_left = np.asarray(frontend.symbols[:-1])[adjacent] - tx_symbols[:-1][adjacent]
        residual_right = np.asarray(frontend.symbols[1:])[adjacent] - tx_symbols[1:][adjacent]
        residual_power = float(
            0.5
            * (
                np.mean(np.square(np.abs(residual_left)))
                + np.mean(np.square(np.abs(residual_right)))
            )
        )
        if residual_power > 0:
            residual_lag_one = complex(
                np.mean(residual_left * np.conjugate(residual_right)) / residual_power
            )
            residual_lag_one = [float(residual_lag_one.real), float(residual_lag_one.imag)]
    valid_variances = np.asarray(frontend.output_noise_variance)[valid]
    valid_ages = np.asarray(frontend.gain_age_symbols)[data_symbols]
    return {
        "clean_region_residual_isi_rms": float(np.sqrt(np.mean(np.square(np.abs(clean_residual))))),
        "composite_gain_within_clean_window_rms_evaluator_only": within_symbol_gain_variation,
        "pilot_composite_gain_rmse_evaluator_only": gain_rmse,
        "equalized_signal_residual_rms_evaluator_only": (
            float(np.sqrt(np.mean(np.square(np.abs(estimated_signal_error)))))
            if estimated_signal_error.size
            else None
        ),
        "equalizer_output_noise_variance_empirical_evaluator_only": empirical_variance,
        "equalizer_output_noise_lag1_correlation_evaluator_only": lag_one_correlation,
        "equalizer_output_noise_variance_conditional_mean_evaluator_only": (
            float(np.mean(valid_variances)) if valid_variances.size else None
        ),
        "equalized_symbol_error_lag1_correlation_evaluator_only": residual_lag_one,
        "payload_gain_age_mean_symbols_evaluator_only": (
            float(np.mean(valid_ages)) if valid_ages.size else None
        ),
        "payload_gain_age_max_symbols_evaluator_only": (
            int(np.max(valid_ages)) if valid_ages.size else None
        ),
        "noise_samples_used_for_diagnostics_only": int(selected_noise.size),
        "truth_access_stage": "after_both_decoders_completed",
    }


def run_metric_trial(spec: MetricTrialSpec) -> MetricTrialResult:
    """Run one paired A-E/A-H trial on a single generated observation."""
    if not isinstance(spec, MetricTrialSpec):
        raise TypeError("spec must be MetricTrialSpec")
    schedule = None
    if spec.frontend_mode == "awgn_direct_control":
        payload_mask = np.ones(spec.frame_symbols, dtype=bool)
        input_pairs = None
    else:
        schedule = build_pilot_schedule(
            frame_symbols=spec.frame_symbols,
            preamble_symbols=spec.preamble_symbols,
            pilot_period=spec.pilot_period,
            pilot_burst_symbols=spec.pilot_burst_symbols,
        )
        payload_mask = np.asarray(schedule.payload_mask, dtype=bool)
        input_pairs = np.empty((spec.frame_symbols, 2), dtype=np.int8)
        input_pairs[np.asarray(schedule.pilot_mask)] = np.asarray(schedule.pilot_input_pairs)[
            np.asarray(schedule.pilot_mask)
        ]
        rng = np.random.Generator(np.random.PCG64(spec.source_seed))
        payload_pairs = rng.integers(
            0, 2, size=(int(np.count_nonzero(payload_mask)), 2), dtype=np.int8
        )
        input_pairs[payload_mask] = payload_pairs

    if input_pairs is None:
        rng = np.random.Generator(np.random.PCG64(spec.source_seed))
        payload_pairs = rng.integers(0, 2, size=(spec.frame_symbols, 2), dtype=np.int8)
        input_pairs = payload_pairs.copy()
    bits_text = "".join(str(int(bit)) for bit in input_pairs.reshape(-1))
    transmitter = run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=spec.frame_symbols,
            manual_bits=bits_text,
            initial_state=(0, 0),
            termination_policy="none",
            amplitude=spec.amplitude,
        )
    )
    reference_pairs = np.asarray(input_pairs[payload_mask], dtype=np.int8)
    if schedule is not None:
        known = np.asarray(schedule.phase_known_mask, dtype=bool)
        if not np.array_equal(
            np.asarray(transmitter.phase_indices)[known],
            np.asarray(schedule.known_phase_indices)[known],
        ):
            raise RuntimeError("pilot phase schedule disagrees with encoded known transitions")

    channel = run_channel(transmitter, spec.channel_config)
    observation = channel.receiver_observation
    path_delays = tuple(path.delay_samples for path in spec.channel_config.paths)
    noise_variance = float(spec.channel_config.noise_complex_variance)
    if spec.frontend_mode == "awgn_direct_control":
        frontend = run_awgn_direct_frontend(observation, symbol_count=spec.frame_symbols)
    elif spec.frontend_mode == "pilot_equalized":
        assert schedule is not None
        frontend = run_pilot_frontend(
            observation,
            schedule,
            amplitude=spec.amplitude,
            path_delays_samples=path_delays,
            assumed_noise_variance=noise_variance,
        )
    else:
        assert schedule is not None
        frontend = run_oracle_csi_frontend(
            observation,
            schedule,
            amplitude=spec.amplitude,
            path_delays_samples=path_delays,
            path_coefficients_by_sample=channel.evaluation_truth.coefficients,
            assumed_noise_variance=noise_variance,
            mode_label=(
                "known_channel_csi"
                if spec.frontend_mode == "known_channel"
                else "diagnostic_oracle_csi"
            ),
        )

    euclidean_rows = euclidean_branch_metric_rows(
        frontend.symbols,
        amplitude=spec.amplitude,
        csi_weights=(frontend.combiner_power if spec.euclidean_metric == "csi_weighted" else None),
    )
    hamming_rows = hamming_branch_metric_rows(frontend.symbols, amplitude=spec.amplitude)
    if schedule is None:
        euclidean_metrics, hamming_metrics = euclidean_rows, hamming_rows
        constraints = None
    else:
        euclidean_metrics, constraints = pilot_constrained_metric_rows(euclidean_rows, schedule)
        hamming_metrics, hamming_constraints = pilot_constrained_metric_rows(hamming_rows, schedule)
        if not np.array_equal(constraints, hamming_constraints):
            raise RuntimeError("metric arms received different pilot edge constraints")

    euclidean_start = time.perf_counter()
    decoded_e = run_metric_viterbi(
        euclidean_metrics,
        allowed_input_pairs=constraints,
        traceback_depth=spec.traceback_depth,
    )
    euclidean_seconds = time.perf_counter() - euclidean_start
    hamming_start = time.perf_counter()
    decoded_h = run_metric_viterbi(
        hamming_metrics,
        allowed_input_pairs=constraints,
        traceback_depth=spec.traceback_depth,
    )
    hamming_seconds = time.perf_counter() - hamming_start

    ref_bits = reference_pairs.reshape(-1)
    dec_e_pairs = np.asarray(decoded_e.information_pairs[payload_mask], dtype=np.int8)
    dec_h_pairs = np.asarray(decoded_h.information_pairs[payload_mask], dtype=np.int8)
    err_e = dec_e_pairs != reference_pairs
    err_h = dec_h_pairs != reference_pairs
    bit_errors_e, bit_errors_h = int(np.count_nonzero(err_e)), int(np.count_nonzero(err_h))
    pair_errors_e = int(np.count_nonzero(np.any(err_e, axis=1)))
    pair_errors_h = int(np.count_nonzero(np.any(err_h, axis=1)))
    payload_bit_count = int(ref_bits.size)
    payload_pair_count = int(len(reference_pairs))
    tx_samples = np.asarray(transmitter.tx_samples, dtype=np.complex128)
    symbol_energy = np.sum(np.square(np.abs(tx_samples.reshape(spec.frame_symbols, 8))), axis=1)
    total_energy = float(np.sum(symbol_energy))
    pilot_energy = float(np.sum(symbol_energy[~payload_mask]))
    payload_energy = float(np.sum(symbol_energy[payload_mask]))
    eb_per_payload_bit = total_energy / payload_bit_count
    gamma_db = (
        10.0 * math.log10(eb_per_payload_bit / noise_variance) if noise_variance > 0 else None
    )
    observation_hash = observation.sha256
    if observation_hash != frontend.observation_sha256:
        raise RuntimeError("metric frontend did not retain the input observation provenance")
    diagnostics = _truth_diagnostics(frontend, transmitter, channel, schedule)
    summary: dict[str, Any] = {
        "schema_version": "scientific-exp03a-metric-trial-v1",
        "contrast_id": "metric_isolation",
        "trial_id": spec.trial_id,
        "frame_symbols_total": spec.frame_symbols,
        "payload_symbols": payload_pair_count,
        "pilot_symbols": int(np.count_nonzero(~payload_mask)),
        "pilot_symbols_used_for_gain_updates": int(np.count_nonzero(frontend.gain_update_mask)),
        "pilot_symbols_per_known_phase": (
            int(np.count_nonzero(schedule.phase_known_mask)) if schedule is not None else 0
        ),
        "payload_information_bits": payload_bit_count,
        "nominal_bits_per_signal_symbol": 2,
        "useful_information_bits_per_transmitted_symbol": payload_bit_count / spec.frame_symbols,
        "amplitude": float(spec.amplitude),
        "noise_complex_variance": noise_variance,
        "transmit_energy_discrete": total_energy,
        "payload_energy_discrete": payload_energy,
        "pilot_energy_discrete": pilot_energy,
        "energy_per_payload_bit_discrete": eb_per_payload_bit,
        "gamma_b_discrete_db": gamma_db,
        "observation_sha256": observation_hash,
        "paired_observation_sha256": observation_hash,
        "frontend_mode": frontend.mode,
        "frontend_output_sha256_euclidean": frontend.frontend_output_sha256,
        "frontend_output_sha256_hamming": frontend.frontend_output_sha256,
        "pilot_schedule_sha256": schedule.sha256 if schedule is not None else None,
        "traceback_depth_transitions": spec.traceback_depth,
        "euclidean_metric": spec.euclidean_metric,
        "initial_state": [0, 0],
        "euclidean": {
            "bit_errors": bit_errors_e,
            "pair_errors": pair_errors_e,
            "bits": payload_bit_count,
            "pairs": payload_pair_count,
            "ber": bit_errors_e / payload_bit_count,
            "ser_information_pairs": pair_errors_e / payload_pair_count,
            "fer": int(bit_errors_e > 0),
            "runtime_seconds": euclidean_seconds,
        },
        "hamming": {
            "bit_errors": bit_errors_h,
            "pair_errors": pair_errors_h,
            "bits": payload_bit_count,
            "pairs": payload_pair_count,
            "ber": bit_errors_h / payload_bit_count,
            "ser_information_pairs": pair_errors_h / payload_pair_count,
            "fer": int(bit_errors_h > 0),
            "runtime_seconds": hamming_seconds,
        },
        "decoder_edge_table_sha256": hashlib.sha256(
            repr(transition_table()).encode("ascii")
        ).hexdigest(),
        "diagnostics_evaluator_only": diagnostics,
        "scientific_limitations": [
            "project reconstructed encoder/phase mapping",
            "sample-domain complex AWGN, not physical Eb/N0",
            (
                "CSI-weighted squared Euclidean cost P_k|z_k-s|^2 (sample-domain ML equivalent)"
                if spec.euclidean_metric == "csi_weighted"
                else "unweighted squared Euclidean cost under pilot-equalizer residual uncertainty"
            ),
            "Rician AR(1) is the configured project approximation, not Jakes/Doppler",
        ],
    }
    return MetricTrialResult(
        summary=summary,
        reference_payload_pairs=reference_pairs.copy(),
        decoded_euclidean_pairs=np.asarray(decoded_e.information_pairs, dtype=np.int8).copy(),
        decoded_hamming_pairs=np.asarray(decoded_h.information_pairs, dtype=np.int8).copy(),
        transmitted_samples=tx_samples.copy(),
        received_samples=np.asarray(observation.received_samples, dtype=np.complex128).copy(),
        equalized_symbols=np.asarray(frontend.symbols, dtype=np.complex128).copy(),
        euclidean_branch_metrics=np.asarray(euclidean_metrics, dtype=np.float64).copy(),
        hamming_branch_metrics=np.asarray(hamming_metrics, dtype=np.int8).copy(),
        schedule=schedule,
        frontend=frontend,
    )


@dataclass(frozen=True, slots=True)
class MetricStudyConfig:
    """Bounded paired metric study; validation/range runs only in this phase."""

    experiment_id: str
    scenario: Literal["awgn", "static", "rician"]
    phase: Literal["validation", "range_finding", "confirmatory"]
    frame_symbols: int
    energy_grid_db: tuple[float, ...]
    trials_per_point: int
    root_seed: int
    target_ber: float
    time_budget_seconds: float
    sweep: Literal["amplitude", "noise"]
    amplitude: float
    channel_config: dict[str, Any]
    frontend_mode: FrontendMode
    preamble_symbols: int = 4
    pilot_period: int = 32
    pilot_burst_symbols: int = 4
    bootstrap_replicates: int = 500
    euclidean_metric: EuclideanMetricKind = "unweighted"
    # Common random numbers: the same trial index reuses source/fading/noise
    # seeds at every energy point (only the swept scale changes).
    common_random_numbers: bool = False
    # Confirmatory runs must cite the SHA-256 of a frozen protocol file.
    protocol_sha256: str = ""
    # Raw signal arrays are stored for trial indices divisible by this stride;
    # the others keep only the compact arrays needed for the independent recount.
    full_array_stride: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not _SAFE_ID.fullmatch(self.experiment_id):
            raise ValueError("experiment_id must be a safe identifier")
        if self.scenario not in {"awgn", "static", "rician"}:
            raise ValueError("scenario must be awgn, static, or rician")
        if self.phase not in {"validation", "range_finding", "confirmatory"}:
            raise ValueError("phase must be validation, range_finding or confirmatory")
        if not isinstance(self.protocol_sha256, str) or (
            self.protocol_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.protocol_sha256)
        ):
            raise ValueError("protocol_sha256 must be empty or a lowercase SHA-256 hex digest")
        if self.phase == "confirmatory" and not self.protocol_sha256:
            raise ValueError("confirmatory studies require the frozen protocol SHA-256")
        if type(self.full_array_stride) is not int or not 1 <= self.full_array_stride <= 1000:
            raise ValueError("full_array_stride must be an integer in [1,1000]")
        if type(self.common_random_numbers) is not bool:
            raise ValueError("common_random_numbers must be boolean")
        if type(self.frame_symbols) is not int or not 20 <= self.frame_symbols <= 20_000:
            raise ValueError("frame_symbols must be in [20,20000]")
        if not self.energy_grid_db or len(self.energy_grid_db) > 21:
            raise ValueError("energy_grid_db must contain 1 to 21 levels")
        if any(not math.isfinite(float(value)) for value in self.energy_grid_db):
            raise ValueError("energy_grid_db values must be finite")
        if len(set(self.energy_grid_db)) != len(self.energy_grid_db):
            raise ValueError("energy_grid_db values must be unique")
        if type(self.trials_per_point) is not int or not 1 <= self.trials_per_point <= 1000:
            raise ValueError("trials_per_point must be in [1,1000]")
        if type(self.root_seed) is not int or not 0 <= self.root_seed < 2**64:
            raise ValueError("root_seed must be an unsigned 64-bit seed")
        if not 0 < self.target_ber < 1:
            raise ValueError("target_ber must be in (0,1)")
        if not math.isfinite(self.time_budget_seconds) or self.time_budget_seconds <= 0:
            raise ValueError("time_budget_seconds must be finite and positive")
        if self.sweep not in {"amplitude", "noise"}:
            raise ValueError("sweep must be amplitude or noise")
        if not math.isfinite(self.amplitude) or self.amplitude <= 0:
            raise ValueError("amplitude must be finite and positive")
        if self.frontend_mode not in _FRONTEND_MODES:
            raise ValueError("unsupported frontend_mode")
        if self.euclidean_metric not in _EUCLIDEAN_METRICS:
            raise ValueError("euclidean_metric must be unweighted or csi_weighted")
        if self.frontend_mode == "awgn_direct_control" and self.scenario != "awgn":
            raise ValueError("the no-equalizer frontend is an AWGN-only control")
        if type(self.bootstrap_replicates) is not int or self.bootstrap_replicates < 100:
            raise ValueError("bootstrap_replicates must be an integer >= 100")
        parsed = ChannelConfig.from_dict(self.channel_config)
        profile_scenario = (
            "rician"
            if parsed.fading_mode in {"rician_ar1", "rician_doppler"}
            else "awgn"
            if parsed.profile_id in {"awgn", "identity"}
            else "static"
        )
        if profile_scenario != self.scenario:
            raise ValueError("channel configuration does not match scenario")
        if self.sweep == "noise" and parsed.noise_complex_variance <= 0:
            raise ValueError("noise sweep requires a positive base complex-noise variance")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> MetricStudyConfig:
        if not isinstance(values, dict):
            raise ValueError("metric study config must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        extra = set(values) - allowed
        if extra:
            raise ValueError(f"unexpected metric study field: {sorted(extra)[0]}")
        data = dict(values)
        if "energy_grid_db" in data:
            data["energy_grid_db"] = tuple(float(value) for value in data["energy_grid_db"])
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"invalid metric study config: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["energy_grid_db"] = list(self.energy_grid_db)
        # Keep config hashes of historical studies unchanged: omit defaults of
        # fields added after SCIENTIFIC-EXP-03B.
        if data["euclidean_metric"] == "unweighted":
            del data["euclidean_metric"]
        if not data["common_random_numbers"]:
            del data["common_random_numbers"]
        if not data["protocol_sha256"]:
            del data["protocol_sha256"]
        if data["full_array_stride"] == 1:
            del data["full_array_stride"]
        return data


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    atomic_replace_bytes(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_metric_study(study_dir: str | Path) -> dict[str, Any]:
    """Verify all saved metric-study files against the checkpoint manifest."""
    root = Path(study_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "scientific-exp03a-metric-manifest-v1":
        raise ValueError("unsupported metric study manifest")
    listed = manifest.get("files")
    if not isinstance(listed, dict) or not listed:
        raise ValueError("metric study manifest has no file list")
    for relative, expected in listed.items():
        candidate = (root / relative).resolve()
        if root not in candidate.parents:
            raise ValueError("metric study manifest path escapes its directory")
        if not candidate.is_file() or _sha256_file(candidate) != expected:
            raise ValueError(f"metric study file failed SHA-256 verification: {relative}")
    return manifest


def load_metric_study(study_dir: str | Path) -> dict[str, Any]:
    """Load a saved metric series only after provenance and file hashes pass."""
    root = Path(study_dir).resolve()
    verify_metric_study(root)
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if summary.get("contrast_id") != "metric_isolation":
        raise ValueError("saved study is not a metric-isolation contrast")
    if summary.get("experiment_id") != config.get("experiment_id"):
        raise ValueError("saved metric study config/summary provenance mismatch")
    summary["configuration"] = config
    return summary


def list_metric_studies(studies_root: str | Path) -> list[dict[str, Any]]:
    root = Path(studies_root)
    if not root.is_dir():
        return []
    studies = []
    for candidate in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not candidate.is_dir() or not (candidate / "summary.json").is_file():
            continue
        try:
            summary = load_metric_study(candidate)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        studies.append(
            {
                key: summary[key]
                for key in (
                    "experiment_id",
                    "phase",
                    "status",
                    "planned_trials",
                    "completed_trials",
                    "contrast_id",
                )
            }
        )
    return studies[:100]


def _refresh_manifest(
    root: Path,
    experiment_id: str,
    config_hash: str,
    cache: dict[str, str] | None = None,
) -> None:
    """Rewrite the manifest. With ``cache`` (relative path -> SHA-256 of
    write-once trial files) only new or mutable files are hashed again."""
    files: dict[str, str] = {}
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file() or candidate.name == "manifest.json":
            continue
        if candidate.suffix in {".pending", ".tmp"}:
            continue
        relative = candidate.relative_to(root).as_posix()
        write_once = relative.startswith("trials/")
        if cache is not None and write_once and relative in cache:
            files[relative] = cache[relative]
            continue
        files[relative] = _sha256_file(candidate)
        if cache is not None and write_once:
            cache[relative] = files[relative]
    _atomic_json(
        root / "manifest.json",
        {
            "schema_version": "scientific-exp03a-metric-manifest-v1",
            "experiment_id": experiment_id,
            "contrast_id": "metric_isolation",
            "config_sha256": config_hash,
            "files": files,
        },
    )


def _trial_seeds(root_seed: int, point_index: int, trial_index: int) -> tuple[int, int, int]:
    sequence = np.random.SeedSequence([root_seed, 0x03A, point_index, trial_index])
    return tuple(int(value) for value in sequence.generate_state(3, dtype=np.uint64))


def _trial_config_for_point(
    config: MetricStudyConfig, level_db: float, point_index: int, trial_index: int
) -> MetricTrialSpec:
    source_seed, fading_seed, noise_seed = _trial_seeds(
        config.root_seed, 0 if config.common_random_numbers else point_index, trial_index
    )
    base = ChannelConfig.from_dict(config.channel_config)
    amplitude = config.amplitude
    noise_variance = float(base.noise_complex_variance)
    if config.sweep == "amplitude":
        amplitude *= 10.0 ** (float(level_db) / 20.0)
    else:
        noise_variance *= 10.0 ** (-float(level_db) / 10.0)
    noise_model = "complex_awgn_sample_domain" if noise_variance > 0 else "none"
    channel = replace(
        base,
        noise_complex_variance=noise_variance,
        noise_model=noise_model,
        fading_seed=fading_seed,
        noise_seed=noise_seed,
        reveal_noise_variance=True,
    )
    return MetricTrialSpec(
        trial_id=f"metric-p{point_index:03d}-t{trial_index:04d}",
        frame_symbols=config.frame_symbols,
        source_seed=source_seed,
        channel_config=channel,
        frontend_mode=config.frontend_mode,
        amplitude=amplitude,
        preamble_symbols=config.preamble_symbols,
        pilot_period=config.pilot_period,
        pilot_burst_symbols=config.pilot_burst_symbols,
        traceback_depth=20,
        euclidean_metric=config.euclidean_metric,
    )


def _save_trial(
    root: Path,
    point_index: int,
    trial_index: int,
    result: MetricTrialResult,
    *,
    full_arrays: bool = True,
) -> None:
    trial_dir = root / "trials"
    trial_dir.mkdir(parents=True, exist_ok=True)
    stem = f"p{point_index:03d}-t{trial_index:04d}"
    npz_path = trial_dir / f"{stem}.npz"
    temporary = npz_path.with_suffix(".npz.pending")
    schedule = result.schedule
    payload_mask = (
        np.ones(result.summary["frame_symbols_total"], dtype=bool)
        if schedule is None
        else schedule.payload_mask
    )
    with temporary.open("wb") as stream:
        if not full_arrays:
            np.savez_compressed(
                stream,
                reference_payload_pairs=result.reference_payload_pairs,
                decoded_euclidean_pairs=result.decoded_euclidean_pairs,
                decoded_hamming_pairs=result.decoded_hamming_pairs,
                payload_mask=payload_mask,
            )
        else:
            np.savez_compressed(
                stream,
                reference_payload_pairs=result.reference_payload_pairs,
                decoded_euclidean_pairs=result.decoded_euclidean_pairs,
                decoded_hamming_pairs=result.decoded_hamming_pairs,
                transmitted_samples=result.transmitted_samples,
                received_samples=result.received_samples,
                equalized_symbols=result.equalized_symbols,
                euclidean_branch_metrics=result.euclidean_branch_metrics,
                hamming_branch_metrics=result.hamming_branch_metrics,
                payload_mask=(
                    np.ones(result.summary["frame_symbols_total"], dtype=bool)
                    if schedule is None
                    else schedule.payload_mask
                ),
                pilot_mask=(
                    np.zeros(result.summary["frame_symbols_total"], dtype=bool)
                    if schedule is None
                    else schedule.pilot_mask
                ),
                known_phase_indices=(
                    np.full(result.summary["frame_symbols_total"], -1, dtype=np.int8)
                    if schedule is None
                    else schedule.known_phase_indices
                ),
                selected_sample_indices=result.frontend.selected_sample_indices,
                estimated_composite_gain=result.frontend.estimated_composite_gain,
                output_noise_variance=result.frontend.output_noise_variance,
                gain_update_mask=result.frontend.gain_update_mask,
                gain_age_symbols=result.frontend.gain_age_symbols,
            )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, npz_path)
    metadata = {
        "schema_version": "scientific-exp03a-metric-trial-record-v1",
        "point_index": point_index,
        "trial_index": trial_index,
        "array_file": npz_path.name,
        "array_file_sha256": _sha256_file(npz_path),
        "array_policy": "full" if full_arrays else "compact_recount_only",
        **result.summary,
    }
    _atomic_json(trial_dir / f"{stem}.json", metadata)


def _read_trial_records(root: Path) -> list[dict[str, Any]]:
    records = []
    trial_dir = root / "trials"
    if not trial_dir.is_dir():
        return records
    for path in sorted(trial_dir.glob("p*-t*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        array_path = trial_dir / row["array_file"]
        if not array_path.is_file() or _sha256_file(array_path) != row["array_file_sha256"]:
            raise ValueError(f"metric trial arrays fail integrity check: {array_path.name}")
        if row.get("contrast_id") != "metric_isolation":
            raise ValueError("whole-receiver output cannot be loaded as a metric-isolation trial")
        if row.get("observation_sha256") != row.get("paired_observation_sha256"):
            raise ValueError("paired metric arms have unlike observation hashes")
        if row.get("frontend_output_sha256_euclidean") != row.get("frontend_output_sha256_hamming"):
            raise ValueError("paired metric arms have unlike frontend hashes")
        records.append(row)
    ids = [row["trial_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate metric trial IDs found")
    return records


def _recount_metric_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    counted = 0
    for row in records:
        root = Path(row["_array_path"])
        with np.load(root, allow_pickle=False) as arrays:
            pairs = arrays["reference_payload_pairs"]
            payload_mask = arrays["payload_mask"].astype(bool)
            for arm, decoded_name in (
                ("euclidean", "decoded_euclidean_pairs"),
                ("hamming", "decoded_hamming_pairs"),
            ):
                decoded = arrays[decoded_name][payload_mask]
                errors = decoded != pairs
                bits = int(np.count_nonzero(errors))
                pairs_errors = int(np.count_nonzero(np.any(errors, axis=1)))
                if bits != int(row[arm]["bit_errors"]) or pairs_errors != int(
                    row[arm]["pair_errors"]
                ):
                    raise ValueError(f"independent metric recount differs for {arm}")
                if not pairs_errors <= bits <= 2 * pairs_errors:
                    raise ValueError("BER and information-pair SER counts are inconsistent")
            counted += 1
    return {"trial_records_recounted": counted, "count_replay": "PASS"}


def run_metric_study(
    config: MetricStudyConfig,
    output_root: str | Path,
    *,
    stop_event: Event | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run/resume a bounded paired validation or range-finding series."""
    if not isinstance(config, MetricStudyConfig):
        raise TypeError("config must be MetricStudyConfig")
    stop_event = stop_event or Event()
    root = Path(output_root).resolve() / config.experiment_id
    root.mkdir(parents=True, exist_ok=True)
    config_value = config.to_dict()
    config_bytes = _canonical_json(config_value)
    config_hash = _sha256_bytes(config_bytes)
    config_path = root / "config.json"
    if config_path.exists():
        if config_path.read_bytes() != config_bytes:
            raise ValueError("immutable metric-study configuration mismatch")
        verify_metric_study(root)
    else:
        if any(root.iterdir()):
            raise ValueError("cannot resume a directory without a verified metric-study config")
        config_path.write_bytes(config_bytes)
        _refresh_manifest(root, config.experiment_id, config_hash)

    records = _read_trial_records(root)
    for row in records:
        row["_array_path"] = str(root / "trials" / row["array_file"])
    expected = {
        f"metric-p{point:03d}-t{trial:04d}"
        for point in range(len(config.energy_grid_db))
        for trial in range(config.trials_per_point)
    }
    existing = {row["trial_id"] for row in records}
    duplicate_trials_skipped = len(existing)
    unexpected = existing - expected
    if unexpected:
        raise ValueError("checkpoint contains trials outside the frozen study design")
    started = time.perf_counter()
    planned = len(expected)
    completed = len(existing)
    manifest_cache: dict[str, str] = {}
    _refresh_manifest(root, config.experiment_id, config_hash, manifest_cache)
    last_manifest_write = time.perf_counter()
    for point_index, level_db in enumerate(config.energy_grid_db):
        for trial_index in range(config.trials_per_point):
            trial_id = f"metric-p{point_index:03d}-t{trial_index:04d}"
            if trial_id in existing:
                continue
            if stop_event.is_set() or time.perf_counter() - started >= config.time_budget_seconds:
                break
            spec = _trial_config_for_point(config, level_db, point_index, trial_index)
            result = run_metric_trial(spec)
            result.summary.update(
                {
                    "experiment_id": config.experiment_id,
                    "phase": config.phase,
                    "scenario": config.scenario,
                    "sweep": config.sweep,
                    "sweep_offset_db": float(level_db),
                    "point_index": point_index,
                    "trial_index": trial_index,
                    "root_seed": config.root_seed,
                    "derived_seeds": list(
                        _trial_seeds(
                            config.root_seed,
                            0 if config.common_random_numbers else point_index,
                            trial_index,
                        )
                    ),
                    "common_random_numbers": config.common_random_numbers,
                    "protocol_sha256": config.protocol_sha256 or None,
                    "algorithm_versions_sha256": {
                        "metric_isolation": _sha256_file(
                            Path(__file__).with_name("metric_isolation.py")
                        ),
                        "metric_experiment": _sha256_file(Path(__file__)),
                    },
                }
            )
            _save_trial(
                root,
                point_index,
                trial_index,
                result,
                full_arrays=trial_index % config.full_array_stride == 0,
            )
            records.append(
                {
                    "_array_path": str(
                        root / "trials" / f"p{point_index:03d}-t{trial_index:04d}.npz"
                    ),
                    "array_file": f"p{point_index:03d}-t{trial_index:04d}.npz",
                    **result.summary,
                }
            )
            existing.add(trial_id)
            completed += 1
            # Trial JSON already binds its NPZ SHA-256; the manifest is a
            # periodic checkpoint (every 30 s) and is always rewritten at the end.
            if time.perf_counter() - last_manifest_write >= 30.0:
                _refresh_manifest(root, config.experiment_id, config_hash, manifest_cache)
                last_manifest_write = time.perf_counter()
            if progress_callback is not None:
                progress_callback(
                    {
                        "completed_trials": completed,
                        "planned_trials": planned,
                        "trial_id": trial_id,
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                )
        if stop_event.is_set() or time.perf_counter() - started >= config.time_budget_seconds:
            break

    disk_records = _read_trial_records(root)
    for row in disk_records:
        row["_array_path"] = str(root / "trials" / row["array_file"])
    recount = _recount_metric_records(disk_records)
    # Fixed design points must not split into separate energy cells because
    # phase-dependent floating point summation changes gamma by a few ulps.
    # Preserve every measured raw value, and reject meaningful energy drift.
    gamma_by_point = {}
    for point in range(len(config.energy_grid_db)):
        measured = [
            float(row["gamma_b_discrete_db"])
            for row in disk_records
            if row["point_index"] == point and row["gamma_b_discrete_db"] is not None
        ]
        if measured:
            if max(measured) - min(measured) > 1e-9:
                raise ValueError("measured energy varies within declared design point")
            gamma_by_point[point] = float(np.median(measured))
    rows_for_analysis = []
    for row in disk_records:
        # A noiseless control has no finite gamma coordinate; keep its raw
        # counts and trace, but it cannot enter a finite energy curve.
        if row["gamma_b_discrete_db"] is None:
            continue
        rows_for_analysis.append(
            {
                "scenario": config.scenario,
                "sweep": config.sweep,
                "phase": config.phase,
                "gamma_db": gamma_by_point[row["point_index"]],
                "trial_index": int(row["trial_index"]),
                "bits": int(row["payload_information_bits"]),
                "pairs": int(row["payload_symbols"]),
                "bit_errors": {
                    "joint": int(row["euclidean"]["bit_errors"]),
                    "hamming": int(row["hamming"]["bit_errors"]),
                },
                "pair_errors": {
                    "joint": int(row["euclidean"]["pair_errors"]),
                    "hamming": int(row["hamming"]["pair_errors"]),
                },
            }
        )
    analysis: dict[str, Any] = {"status": "NOT_ESTIMABLE", "reason": "no complete paired trials"}
    aggregates: list[dict[str, Any]] = []
    crn_incomplete = config.common_random_numbers and completed != planned
    if rows_for_analysis:
        aggregates = aggregate_energy_records(rows_for_analysis)
    if rows_for_analysis and crn_incomplete:
        analysis = {
            "status": "NOT_ESTIMABLE",
            "reason": "INCOMPLETE_CRN_DESIGN: resume the study with the identical configuration",
            "target_ber": config.target_ber,
            "gain_db": None,
        }
    elif rows_for_analysis:
        analysis = analyze_energy_records(
            rows_for_analysis,
            config.target_ber,
            arm="hamming",
            replicates=config.bootstrap_replicates,
            seed=config.root_seed ^ 0x03A03A,
            common_clusters=config.common_random_numbers,
        )
        analysis["interpretation"] = (
            "confirmatory_frozen_protocol_discrete_eb_n0"
            if config.phase == "confirmatory"
            else "exploratory_project_discrete_energy_only"
        )
        analysis["physical_ebn0"] = None
    status = "completed" if completed == planned else "incomplete"
    result_summary = {
        "schema_version": "scientific-exp03a-metric-study-summary-v1",
        "experiment_id": config.experiment_id,
        "contrast_id": "metric_isolation",
        "phase": config.phase,
        "status": status,
        "planned_trials": planned,
        "completed_trials": completed,
        "duplicate_trials_skipped": duplicate_trials_skipped,
        "paired_hashes_valid": all(
            row["observation_sha256"] == row["paired_observation_sha256"]
            and row["frontend_output_sha256_euclidean"] == row["frontend_output_sha256_hamming"]
            for row in disk_records
        ),
        "recount": recount,
        "aggregates": aggregates,
        "gain_analysis": analysis,
        "energy_axis_grouping": "declared_point_index_median_measured_gamma_tolerance_1e-9_db",
        "trial_ids": sorted(row["trial_id"] for row in disk_records),
        "runtime_seconds_this_invocation": time.perf_counter() - started,
        "config_sha256": config_hash,
        "confirmatory_series_executed": config.phase == "confirmatory",
        "protocol_sha256": config.protocol_sha256 or None,
        "paper_exact": False,
    }
    _atomic_json(root / "summary.json", result_summary)
    _refresh_manifest(root, config.experiment_id, config_hash)
    verify_metric_study(root)
    return result_summary
