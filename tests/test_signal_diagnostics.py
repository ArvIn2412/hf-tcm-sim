from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.evaluation.signal_diagnostics import (
    complex_sample_energy,
    complex_sample_mean,
    discrete_block_energies,
    empirical_component_powers,
    mean_complex_power_from_covariance,
)
from hf_tcm.modulation.psk8 import constellation
from hf_tcm.receiver.iq import symbols_to_iq_waveform


@pytest.mark.parametrize("gain", [0.75, 2.0])
def test_normalized_8psk_and_zoh_discrete_energy(gain: float) -> None:
    symbols = constellation()
    assert np.allclose(np.abs(symbols), 1.0, rtol=0.0, atol=1e-15)

    in_phase, quadrature = symbols_to_iq_waveform(symbols, samples_per_symbol=8)
    received = gain * (in_phase + 1j * quadrature)
    energies = discrete_block_energies(received, samples_per_block=8)

    assert energies.shape == (8,)
    assert np.allclose(energies, np.full(8, 8.0 * gain**2), rtol=0.0, atol=1e-12)
    for phase_index, symbol in enumerate(symbols):
        assert np.array_equal(
            received[8 * phase_index : 8 * (phase_index + 1)], np.full(8, gain * symbol)
        )
    assert np.allclose(np.abs(received[::8]) ** 2, gain**2, rtol=0.0, atol=1e-12)
    assert complex_sample_energy(received[:8]) == pytest.approx(8.0 * gain**2)


def test_sample_mean_and_empirical_component_powers_are_explicit() -> None:
    noise = np.array([1.0 + 2.0j, -2.0 + 0.5j, 0.0 - 1.0j])
    original = noise.copy()

    assert complex_sample_mean(noise) == pytest.approx((-1.0 / 3.0) + 0.5j)
    complex_power, real_power, imag_power = empirical_component_powers(noise)
    assert complex_power == pytest.approx((5.0 + 4.25 + 1.0) / 3.0)
    assert real_power == pytest.approx((1.0 + 4.0) / 3.0)
    assert imag_power == pytest.approx((4.0 + 0.25 + 1.0) / 3.0)
    assert np.array_equal(noise, original)


def test_independent_complex_noise_mean_variance_from_diagonal_covariance() -> None:
    covariance = np.eye(8, dtype=np.complex128) * 0.6
    assert mean_complex_power_from_covariance(covariance) == pytest.approx(0.6 / 8.0)


def test_correlated_complex_noise_mean_variance_uses_all_covariances() -> None:
    indices = np.arange(8)
    covariance = (0.4 ** np.abs(indices[:, None] - indices[None, :])).astype(np.complex128)
    expected = float(np.real(np.sum(covariance)) / 64.0)

    assert mean_complex_power_from_covariance(covariance) == pytest.approx(expected)
    assert expected > 1.0 / 8.0


@pytest.mark.parametrize(
    "operation, values",
    [
        (complex_sample_energy, np.array([], dtype=np.complex128)),
        (complex_sample_mean, np.array([[1.0 + 0.0j]])),
        (empirical_component_powers, np.array([complex(np.nan, 0.0)])),
        (empirical_component_powers, np.array([complex(0.0, np.inf)])),
    ],
)
def test_sample_diagnostics_reject_invalid_arrays(operation, values) -> None:
    with pytest.raises(ValueError):
        operation(values)


def test_block_energy_rejects_incomplete_or_nonfinite_data() -> None:
    with pytest.raises(ValueError, match="divisible"):
        discrete_block_energies(np.ones(9, dtype=np.complex128), samples_per_block=8)
    with pytest.raises(ValueError):
        discrete_block_energies(
            np.array([complex(1.0, 0.0), complex(np.inf, 0.0)]), samples_per_block=1
        )
    with pytest.raises(ValueError):
        discrete_block_energies(np.ones(8, dtype=np.complex128), samples_per_block=0)


@pytest.mark.parametrize(
    "covariance",
    [
        np.ones((7, 8)),
        np.full((8, 8), np.nan),
        np.eye(8, dtype=np.complex128) + 1j * np.ones((8, 8)),
    ],
)
def test_covariance_mean_power_rejects_invalid_matrices(covariance) -> None:
    with pytest.raises(ValueError):
        mean_complex_power_from_covariance(covariance)


def test_diagnostics_module_does_not_access_channel_truth() -> None:
    import ast
    from pathlib import Path

    module_path = Path(__file__).parents[1] / "src/hf_tcm/evaluation/signal_diagnostics.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    assert "ChannelTruth" not in names | attributes
    assert "truth" not in names | attributes
