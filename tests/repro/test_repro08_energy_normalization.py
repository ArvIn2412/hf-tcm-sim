from __future__ import annotations

import math

import pytest

from hf_tcm.repro.repro08_energy import (
    discrete_energy_per_information_bit,
    discrete_gamma_b_db,
    noise_variance_for_discrete_gamma_b_db,
)


def test_rectangular_zoh_discrete_bit_energy_matches_hand_calculation():
    assert discrete_energy_per_information_bit(samples_per_symbol=8, amplitude=1.0) == 4.0
    assert discrete_energy_per_information_bit(samples_per_symbol=8, amplitude=0.5) == 1.0


def test_discrete_gamma_and_noise_variance_are_inverse_without_physical_label():
    for gamma_db in (-3.0, 0.0, 6.0, 10.0):
        variance = noise_variance_for_discrete_gamma_b_db(
            gamma_db, samples_per_symbol=8, amplitude=1.0
        )
        assert math.isclose(
            discrete_gamma_b_db(variance, samples_per_symbol=8, amplitude=1.0),
            gamma_db,
            rel_tol=0,
            abs_tol=1e-12,
        )


def test_energy_convention_rejects_invalid_physical_or_zero_parameters():
    with pytest.raises(ValueError, match="positive"):
        discrete_energy_per_information_bit(samples_per_symbol=8, amplitude=0.0)
    with pytest.raises(ValueError, match="positive"):
        discrete_gamma_b_db(0.0, samples_per_symbol=8, amplitude=1.0)
