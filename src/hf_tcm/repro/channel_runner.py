"""Discrete complex-baseband multipath/fading/noise channel runner."""

from __future__ import annotations

import hashlib

import numpy as np

from hf_tcm.repro.channel_config import CHANNEL_SCHEMA_VERSION, ChannelConfig
from hf_tcm.repro.channel_result import (
    ChannelResult,
    EvaluationTruth,
    ReceiverObservation,
    readonly,
)
from hf_tcm.repro.multipath_channel import apply_integer_delay_paths
from hf_tcm.repro.noise import generate_complex_noise
from hf_tcm.repro.rician_fading import generate_path_coefficients
from hf_tcm.repro.transmitter import TransmitterResult

CHANNEL_MODEL_ID = "repro03_discrete_complex_baseband_v1"


def _validate_transmitter(result: TransmitterResult) -> None:
    if not isinstance(result, TransmitterResult):
        raise TypeError("transmitter_result must be a REPRO-02 TransmitterResult")
    if result.receiver_enabled or result.paper_exact:
        raise ValueError("REPRO-02 transmitter fidelity flags are inconsistent")
    samples = np.asarray(result.tx_samples)
    if samples.ndim != 1 or samples.size == 0 or not np.all(np.isfinite(samples)):
        raise ValueError("TransmitterResult.tx_samples must be a nonempty finite vector")
    if result.samples_per_symbol != 8 or samples.size != len(result.phase_indices) * 8:
        raise ValueError("TransmitterResult sample/symbol alignment is invalid")
    expected = np.arange(samples.size, dtype=np.int64)
    if not np.array_equal(result.absolute_sample_index, expected):
        raise ValueError("TransmitterResult absolute sample indices must start at zero")
    if not np.array_equal(result.sample_symbol_index, expected // result.samples_per_symbol):
        raise ValueError("TransmitterResult symbol sample indices are inconsistent")
    if not np.array_equal(result.sample_local_index, expected % result.samples_per_symbol):
        raise ValueError("TransmitterResult local sample indices are inconsistent")


def _path_seeds(root_seed: int, count: int) -> tuple[int, ...]:
    children = np.random.SeedSequence(root_seed).spawn(count)
    return tuple(int(child.generate_state(1, dtype=np.uint64)[0]) for child in children)


def run_channel(
    transmitter_result: TransmitterResult, channel_config: ChannelConfig
) -> ChannelResult:
    """Apply integer-delay channel, then independent sample-domain complex noise."""
    _validate_transmitter(transmitter_result)
    if not isinstance(channel_config, ChannelConfig):
        raise TypeError("channel_config must be a ChannelConfig")

    tx = np.asarray(transmitter_result.tx_samples, dtype=np.complex128)
    max_delay = max(path.delay_samples for path in channel_config.paths)
    output_length = len(tx) + max_delay
    time_index = np.arange(output_length, dtype=np.int64)
    coefficient_seeds = _path_seeds(channel_config.fading_seed, len(channel_config.paths))
    coefficients = np.vstack(
        [
            generate_path_coefficients(
                output_length,
                path,
                fading_mode=channel_config.fading_mode,
                correlation=channel_config.correlation,
                seed=seed,
                doppler_spread_hz=channel_config.doppler_spread_hz,
                sample_rate_hz=8.0 * channel_config.symbol_rate_baud,
            )
            for path, seed in zip(channel_config.paths, coefficient_seeds, strict=True)
        ]
    )
    contributions, faded, source_indices = apply_integer_delay_paths(
        tx,
        coefficients,
        tuple(path.delay_samples for path in channel_config.paths),
    )
    if channel_config.noise_model == "none":
        noise = np.zeros(output_length, dtype=np.complex128)
    else:
        noise = generate_complex_noise(
            output_length,
            complex_variance=channel_config.noise_complex_variance,
            seed=channel_config.noise_seed,
        )
    received = faded + noise
    if not np.all(np.isfinite(received)):
        raise ValueError("channel output contains non-finite samples")

    sps = transmitter_result.samples_per_symbol
    public_variance = (
        channel_config.noise_complex_variance if channel_config.reveal_noise_variance else None
    )
    observation = ReceiverObservation(
        received_samples=readonly(received),
        absolute_sample_index=readonly(time_index),
        sample_symbol_index=readonly(time_index // sps),
        sample_local_index=readonly(time_index % sps),
        samples_per_symbol=sps,
        profile_id=channel_config.profile_id,
        model_id=CHANNEL_MODEL_ID,
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy=channel_config.boundary_policy,
        output_length_policy=channel_config.output_length_policy,
        noise_model=channel_config.noise_model,
        noise_complex_variance=public_variance,
    )
    truth = EvaluationTruth(
        transmitter_samples=readonly(tx.copy()),
        transmitter_information_bits=readonly(transmitter_result.information_bits.copy()),
        transmitter_symbols=readonly(transmitter_result.symbols.copy()),
        path_delays_samples=tuple(path.delay_samples for path in channel_config.paths),
        path_average_powers=tuple(float(path.average_power) for path in channel_config.paths),
        path_k_factors=tuple(float(path.k_factor) for path in channel_config.paths),
        path_los_phases_rad=tuple(float(path.los_phase_rad) for path in channel_config.paths),
        source_sample_indices=readonly(source_indices),
        coefficients=readonly(coefficients),
        path_contributions=readonly(contributions),
        faded_signal=readonly(faded),
        noise_samples=readonly(noise),
    )
    metadata = {
        "schema_version": CHANNEL_SCHEMA_VERSION,
        "rng_algorithm": channel_config.rng_algorithm,
        "root_fading_seed": channel_config.fading_seed,
        "path_fading_seeds": list(coefficient_seeds),
        "noise_seed": channel_config.noise_seed,
        "fading_rng_streams_independent_by_path": True,
        "noise_rng_independent_of_fading": True,
        "receiver_observation_sha256": observation.sha256,
        "zero_extension": True,
        "transmitter_source_fingerprint": transmitter_result.source_fingerprint,
        "transmitter_mapping_fingerprint": transmitter_result.mapping_fingerprint,
        "transmitter_source_file_sha256": transmitter_result.source_file_sha256,
        "transmitter_samples_sha256": hashlib.sha256(
            np.ascontiguousarray(tx).tobytes()
        ).hexdigest(),
        "transmitter_information_bits_sha256": hashlib.sha256(
            np.ascontiguousarray(transmitter_result.information_bits).tobytes()
        ).hexdigest(),
    }
    return ChannelResult(
        receiver_observation=observation,
        evaluation_truth=truth,
        config_snapshot=channel_config.to_dict(),
        reproducibility_metadata=metadata,
        channel_model_id=CHANNEL_MODEL_ID,
    )
