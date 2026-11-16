from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.channels.multipath import MultipathConfig, PathSpec, apply_multipath
from hf_tcm.channels.rician import generate_rician_coefficients
from hf_tcm.modulation.psk8 import constellation
from hf_tcm.receiver.iq import combine_iq, split_iq, symbols_to_iq_waveform
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
    predict_reconstructed_aggregate_iq,
)

_CHANNEL_SEED = 613
_CHANNEL_CONFIG = MultipathConfig(
    paths=(
        PathSpec(
            delay_samples=0,
            average_power=1.7,
            k_factor=2.5,
            los_phase_rad=0.31,
        ),
    ),
    fading_mode="static",
)
_CONTROL_COEFFICIENTS = ((1.7, 0.6), (0.45, 2.3))


def _bits_for_phase_index(index: int) -> tuple[int, int, int]:
    return ((index >> 2) & 1, (index >> 1) & 1, index & 1)


def _m3_single_path_samples() -> tuple[np.ndarray, complex]:
    symbols = constellation()
    in_phase, quadrature = symbols_to_iq_waveform(symbols, samples_per_symbol=8)
    transmitted = combine_iq(in_phase, quadrature)

    # Independently reconstruct the deterministic static test coefficient
    # from the explicit simulation controls; never read ChannelOutput.truth.
    control_coefficients = generate_rician_coefficients(
        len(transmitted),
        average_power=1.7,
        k_factor=2.5,
        rng=np.random.default_rng(_CHANNEL_SEED),
        mode="static",
        los_phase_rad=0.31,
    )
    output = apply_multipath(
        transmitted,
        _CHANNEL_CONFIG,
        rng=np.random.default_rng(_CHANNEL_SEED),
    )
    return output.received, complex(control_coefficients[0])


def _manual_a5(phase_index: int, coefficients: tuple[float, float]) -> np.ndarray:
    angle = phase_index * np.pi / 4.0
    mu1, mu2 = coefficients
    return np.asarray((-mu1 * np.sin(angle), mu2 * np.cos(angle)))


def _forward_all_phases(coefficients: tuple[float, float]) -> np.ndarray:
    output = predict_reconstructed_aggregate_iq(
        candidate_output_bits=tuple(_bits_for_phase_index(b) for b in range(8)),
        estimated_path_coefficients=np.asarray([coefficients]),
        path_delays_samples=(0,),
        symbol_origin_sample=0,
        frame_start_sample=0,
        frame_sample_count=64,
        labeling_profile="assumed_natural_binary",
        bit_order=("c2", "c1", "c0"),
        timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
        symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
        edge_policy="zero_padding",
    )
    return output.reshape(8, 8, 2)


@pytest.mark.parametrize("coefficients", _CONTROL_COEFFICIENTS)
def test_m3_static_baseband_maps_to_a5_and_forward_for_every_phase(
    coefficients: tuple[float, float],
) -> None:
    received, channel_control = _m3_single_path_samples()
    baseband_i, baseband_q = split_iq(received)
    normalized_baseband = received / channel_control
    normalized_iq = np.column_stack((normalized_baseband.real, normalized_baseband.imag))
    manual = np.asarray([_manual_a5(b, coefficients) for b in range(8)])
    direct_api = np.asarray(
        [iq_quadratures_from_index(b, coefficients[0], coefficients[1]) for b in range(8)]
    )
    forward = _forward_all_phases(coefficients)

    np.testing.assert_allclose(received, channel_control * np.repeat(constellation(), 8))
    np.testing.assert_allclose(baseband_i, received.real)
    np.testing.assert_allclose(baseband_q, received.imag)
    np.testing.assert_allclose(
        normalized_iq[::8],
        np.column_stack((np.cos(np.arange(8) * np.pi / 4), np.sin(np.arange(8) * np.pi / 4))),
        atol=1e-14,
    )
    np.testing.assert_allclose(direct_api, manual, atol=1e-14)
    np.testing.assert_allclose(
        forward,
        np.broadcast_to(manual[:, np.newaxis, :], forward.shape),
        atol=1e-14,
    )

    # For z = h(cos(theta) + j sin(theta)), the exact fixed real conversion
    # to [A](5), given this explicit control h and coefficient pair, is:
    # U1=(mu1*Im(h)*I - mu1*Re(h)*Q)/|h|^2;
    # U2=(mu2*Re(h)*I + mu2*Im(h)*Q)/|h|^2.
    h_real, h_imag = channel_control.real, channel_control.imag
    denominator = abs(channel_control) ** 2
    observed_pairs = np.column_stack((baseband_i[::8], baseband_q[::8]))
    converted = np.column_stack(
        (
            (
                coefficients[0] * h_imag * observed_pairs[:, 0]
                - coefficients[0] * h_real * observed_pairs[:, 1]
            )
            / denominator,
            (
                coefficients[1] * h_real * observed_pairs[:, 0]
                + coefficients[1] * h_imag * observed_pairs[:, 1]
            )
            / denominator,
        )
    )
    np.testing.assert_allclose(converted, manual, atol=1e-14)
    assert not np.allclose(observed_pairs, manual)


def test_m3_to_paper5_conversion_has_explicit_control_scales() -> None:
    received, channel_control = _m3_single_path_samples()
    in_phase, quadrature = split_iq(received)
    recovered = received / channel_control
    phase_pairs = np.column_stack((recovered.real[::8], recovered.imag[::8]))

    for mu1, mu2 in _CONTROL_COEFFICIENTS:
        expected = np.column_stack((-mu1 * phase_pairs[:, 1], mu2 * phase_pairs[:, 0]))
        expected = np.broadcast_to(expected[:, np.newaxis, :], (8, 8, 2))
        np.testing.assert_allclose(expected, _forward_all_phases((mu1, mu2)), atol=1e-14)

    assert in_phase.shape == quadrature.shape == (64,)
