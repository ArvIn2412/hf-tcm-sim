"""M3 I/Q representation and explicit approximate 8-sample waveform checks."""

import numpy as np
import pytest

from hf_tcm.channels.multipath import MultipathConfig, PathSpec, apply_multipath
from hf_tcm.receiver.iq import (
    IQ_WAVEFORM_PROFILE,
    combine_iq,
    split_iq,
    symbols_to_iq_waveform,
)


def test_iq_split_and_combine_round_trip() -> None:
    samples = np.asarray([1.0 + 2.0j, -0.25 + 0.75j, 0.0 - 1.0j])

    in_phase, quadrature = split_iq(samples)

    assert np.array_equal(in_phase, samples.real)
    assert np.array_equal(quadrature, samples.imag)
    assert np.array_equal(combine_iq(in_phase, quadrature), samples)


def test_symbols_expand_to_eight_rectangular_iq_samples() -> None:
    symbols = np.asarray([1.0 + 2.0j, -1.0 + 0.5j])

    in_phase, quadrature = symbols_to_iq_waveform(symbols)

    assert in_phase.shape == quadrature.shape == (16,)
    assert np.array_equal(combine_iq(in_phase, quadrature), np.repeat(symbols, 8))
    assert IQ_WAVEFORM_PROFILE == "approximate_rectangular"


def test_8_sample_iq_waveform_runs_through_configured_multipath() -> None:
    symbols = np.asarray([1.0 + 1.0j, -1.0 + 0.5j])
    in_phase, quadrature = symbols_to_iq_waveform(symbols)
    waveform = combine_iq(in_phase, quadrature)
    channel = apply_multipath(
        waveform,
        MultipathConfig(paths=(PathSpec(0, 1.0, 0.0),)),
        rng=np.random.default_rng(10),
    )
    rx_i, rx_q = split_iq(channel.received)

    assert rx_i.shape == rx_q.shape == waveform.shape
    assert np.array_equal(combine_iq(rx_i, rx_q), channel.received)


def test_iq_functions_reject_invalid_shapes_and_sample_counts() -> None:
    with pytest.raises(ValueError, match="finite 1-D"):
        split_iq(np.ones((2, 2), dtype=np.complex128))
    with pytest.raises(ValueError, match="same shape"):
        combine_iq(np.ones(2), np.ones(3))
    with pytest.raises(ValueError, match="samples_per_symbol"):
        symbols_to_iq_waveform(np.ones(2, dtype=np.complex128), samples_per_symbol=0)
