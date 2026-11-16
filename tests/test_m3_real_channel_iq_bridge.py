from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.modulation.psk8 import constellation
from hf_tcm.receiver.iq import combine_iq, split_iq, symbols_to_iq_waveform
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
    predict_reconstructed_aggregate_iq,
)


def _test_only_bridge_from_received(received: np.ndarray) -> np.ndarray:
    """Apply the proposed real-channel rotation using only received samples."""
    real, imag = split_iq(received)
    return np.column_stack((-imag, real))


def _output_bits(b: int) -> tuple[int, int, int]:
    return ((b >> 2) & 1, (b >> 1) & 1, b & 1)


def _forward_for_equal_real_coefficients(a: float) -> np.ndarray:
    return predict_reconstructed_aggregate_iq(
        candidate_output_bits=tuple(_output_bits(b) for b in range(8)),
        estimated_path_coefficients=np.asarray([[a, a]]),
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


@pytest.mark.parametrize("a", (0.75, 2.0))
def test_real_single_path_bridge_matches_a5_for_all_eight_phases(a: float) -> None:
    # This is an explicit noiseless simulation fixture for z=a*x, not a
    # ChannelOutput or estimated-receiver input containing channel truth.
    transmitted = constellation()
    in_phase, quadrature = symbols_to_iq_waveform(transmitted, samples_per_symbol=8)
    received = a * combine_iq(in_phase, quadrature)
    real, imag = split_iq(received)
    observed = _test_only_bridge_from_received(received)

    theta = np.arange(8, dtype=np.float64) * np.pi / 4.0
    manual_a5 = np.column_stack((-a * np.sin(theta), a * np.cos(theta)))
    expected_all_samples = np.repeat(manual_a5, 8, axis=0)
    direct_a5 = np.asarray([iq_quadratures_from_index(b, a, a) for b in range(8)])
    forward = _forward_for_equal_real_coefficients(a)

    np.testing.assert_allclose(received, a * np.repeat(transmitted, 8))
    np.testing.assert_allclose(real, received.real)
    np.testing.assert_allclose(imag, received.imag)
    np.testing.assert_allclose(direct_a5, manual_a5, atol=1e-14)
    np.testing.assert_allclose(observed, expected_all_samples, atol=1e-14)
    np.testing.assert_allclose(forward, expected_all_samples, atol=1e-14)


@pytest.mark.parametrize("h", (1.0 + 1.0j, 2.0 - 0.5j))
def test_complex_channel_control_is_a_counterexample_to_real_channel_identity(
    h: complex,
) -> None:
    transmitted = constellation()
    received = h * transmitted
    observed = _test_only_bridge_from_received(received)
    theta = np.arange(8, dtype=np.float64) * np.pi / 4.0
    a5_for_equal_magnitude_coefficients = np.column_stack(
        (-abs(h) * np.sin(theta), abs(h) * np.cos(theta))
    )

    assert not np.allclose(observed, a5_for_equal_magnitude_coefficients)
    # At b=0 the nonzero imaginary channel component appears in observed U1,
    # while the [A](5) sine term is zero.
    np.testing.assert_allclose(observed[0], (-h.imag, h.real))
    np.testing.assert_allclose(a5_for_equal_magnitude_coefficients[0], (0.0, abs(h)))
