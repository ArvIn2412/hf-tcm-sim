from __future__ import annotations

import pytest

from hf_tcm.repro.energy_gain import estimate_energy_gain_db


def test_energy_gain_uses_measured_brackets_and_explicit_linear_ber() -> None:
    result = estimate_energy_gain_db(
        [(0.0, 0.2), (2.0, 0.0)],
        [(0.0, 0.4), (4.0, 0.0)],
        target_ber=0.1,
        x_axis_unit="physical_snr_db",
        physical_snr_defined=True,
    )
    assert result.snr_joint_db == pytest.approx(1.0)
    assert result.snr_separate_db == pytest.approx(3.0)
    assert result.gain_db == pytest.approx(2.0)


def test_energy_gain_rejects_sample_domain_scale_and_extrapolation() -> None:
    with pytest.raises(ValueError, match="physically defined SNR"):
        estimate_energy_gain_db(
            [(0, 0.2), (1, 0.1)],
            [(0, 0.2), (1, 0.1)],
            target_ber=0.15,
            x_axis_unit="sample_domain_noise_variance",
            physical_snr_defined=False,
        )
    with pytest.raises(ValueError, match="no extrapolation"):
        estimate_energy_gain_db(
            [(0, 0.2), (1, 0.1)],
            [(0, 0.2), (1, 0.1)],
            target_ber=0.01,
            x_axis_unit="physical_snr_db",
            physical_snr_defined=True,
        )
