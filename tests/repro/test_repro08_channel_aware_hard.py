from __future__ import annotations

import math

import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.repro08_channel_aware_hard import (
    PublicStaticTap,
    Repro08HardReceiverConfig,
    run_channel_aware_hard_receiver,
)
from hf_tcm.repro.transmitter import run_transmitter


def observation(samples: np.ndarray, *, sps: int = 8) -> ReceiverObservation:
    indexes = np.arange(samples.size, dtype=np.int64)
    return ReceiverObservation(
        received_samples=np.asarray(samples, dtype=np.complex128),
        absolute_sample_index=indexes,
        sample_symbol_index=indexes // sps,
        sample_local_index=indexes % sps,
        samples_per_symbol=sps,
        profile_id="test_public_static_channel",
        model_id="test_model",
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy="zero_extension",
        output_length_policy="tx_plus_max_delay",
        noise_model="none",
        noise_complex_variance=0.0,
    )


def test_b1_recovers_all_eight_phase_symbols_with_public_complex_rotation():
    phases = np.arange(8, dtype=np.int8)
    symbols = np.exp(1j * phases * (math.pi / 4))
    gain = 0.73 * np.exp(1j * 0.61)
    samples = np.repeat(gain * symbols, 8)
    cfg = Repro08HardReceiverConfig(
        expected_symbol_count=8,
        taps=(PublicStaticTap(0, gain),),
    )

    result = run_channel_aware_hard_receiver(observation(samples), cfg)

    np.testing.assert_array_equal(result.hard_phase_indices, phases)
    assert result.observation_sha256 == observation(samples).sha256
    assert result.receiver_profile_id == "repro08_public_static_channel_hard_v1"


def test_b1_feedback_prediction_uses_previous_symbol_for_delay_three():
    tx = run_transmitter(
        TransmitterConfig(source_mode="seeded_random", frame_symbols=32, seed=9142)
    )
    h0 = 0.82 * np.exp(1j * 0.25)
    h1 = 0.31 * np.exp(-1j * 0.4)
    channel = run_channel(
        tx,
        ChannelConfig(
            profile_id="known_static_delay3_fixture",
            paths=(
                ChannelPathConfig(0, abs(h0) ** 2, 0.0, constant_coefficient=h0),
                ChannelPathConfig(3, abs(h1) ** 2, 0.0, constant_coefficient=h1),
            ),
            fading_mode="constant",
            noise_model="none",
            noise_complex_variance=0.0,
            fading_seed=17,
            noise_seed=19,
        ),
    )
    cfg = Repro08HardReceiverConfig(
        expected_symbol_count=32,
        taps=(PublicStaticTap(0, h0), PublicStaticTap(3, h1)),
    )

    result = run_channel_aware_hard_receiver(channel.receiver_observation, cfg)

    np.testing.assert_array_equal(result.hard_phase_indices, tx.phase_indices)
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    assert result.processed_symbol_count == 32
    assert result.processed_sample_count == 259
    assert result.unprocessed_sample_count == 0


def test_b1_delay_three_uses_independent_hand_calculated_samples():
    # Build y[n] directly from the stated discrete two-tap equation, without
    # invoking the production REPRO-03 channel implementation.
    phases = np.asarray([1, 6, 3, 0, 5, 2, 7, 4], dtype=np.int8)
    symbols = np.exp(1j * phases * (math.pi / 4.0))
    tx = np.repeat(symbols, 8)
    h0 = 0.9 * np.exp(1j * 0.2)
    h1 = 0.24 * np.exp(-1j * 0.37)
    received = np.empty(tx.size + 3, dtype=np.complex128)
    for n in range(received.size):
        direct = tx[n] if n < tx.size else 0j
        delayed = tx[n - 3] if 0 <= n - 3 < tx.size else 0j
        received[n] = h0 * direct + h1 * delayed
    cfg = Repro08HardReceiverConfig(
        expected_symbol_count=len(phases),
        taps=(PublicStaticTap(0, h0), PublicStaticTap(3, h1)),
    )

    result = run_channel_aware_hard_receiver(observation(received), cfg)

    np.testing.assert_array_equal(result.hard_phase_indices, phases)
    assert result.processed_sample_count == tx.size + 3


def test_b1_rejects_delay_outside_one_symbol_history():
    with pytest.raises(ValueError, match="delays must be less than samples_per_symbol"):
        Repro08HardReceiverConfig(
            expected_symbol_count=4,
            taps=(PublicStaticTap(0, 1 + 0j), PublicStaticTap(8, 0.2 + 0j)),
        )


def test_b1_rejects_channel_result_so_evaluation_truth_cannot_leak():
    tx = run_transmitter(TransmitterConfig(source_mode="seeded_random", frame_symbols=8, seed=21))
    channel = run_channel(
        tx,
        ChannelConfig(
            profile_id="identity_truth_isolation",
            paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            noise_model="none",
            noise_complex_variance=0.0,
            fading_seed=1,
            noise_seed=2,
        ),
    )
    cfg = Repro08HardReceiverConfig(expected_symbol_count=8, taps=(PublicStaticTap(0, 1 + 0j),))

    with pytest.raises(TypeError, match="ReceiverObservation only"):
        run_channel_aware_hard_receiver(channel, cfg)
