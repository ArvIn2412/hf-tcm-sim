"""Watterson/ITU Gaussian-Doppler fading mode (defense plan P0-3)."""

from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.repro.channel_config import (
    ITU_HF_DOPPLER_SPREAD_HZ,
    ChannelConfig,
    ChannelPathConfig,
    itu_hf_doppler_profile,
    multipath_rician_awgn_profile,
)
from hf_tcm.repro.metric_experiment import MetricTrialSpec, run_metric_trial
from hf_tcm.repro.rician_fading import (
    gaussian_doppler_autocorrelation,
    gaussian_doppler_process,
)


def _doppler(**overrides: object) -> ChannelConfig:
    values: dict[str, object] = {
        "profile_id": "doppler_test",
        "paths": (ChannelPathConfig(0, 0.5, 0.0), ChannelPathConfig(3, 0.5, 0.0)),
        "fading_mode": "rician_doppler",
        "noise_model": "complex_awgn_sample_domain",
        "noise_complex_variance": 0.2,
        "fading_seed": 5,
        "noise_seed": 6,
        "reveal_noise_variance": True,
        "doppler_spread_hz": 1.0,
        "symbol_rate_baud": 2400.0,
    }
    values.update(overrides)
    return ChannelConfig(**values)  # type: ignore[arg-type]


def test_config_validation_and_round_trip() -> None:
    config = _doppler()
    data = config.to_dict()
    assert data["doppler_spread_hz"] == 1.0 and data["symbol_rate_baud"] == 2400.0
    assert ChannelConfig.from_dict(data) == config
    with pytest.raises(ValueError):
        _doppler(doppler_spread_hz=0.0)
    with pytest.raises(ValueError):
        _doppler(symbol_rate_baud=0.5, doppler_spread_hz=1.0)
    with pytest.raises(ValueError):
        _doppler(correlation=0.5)


def test_legacy_modes_keep_their_serialisation() -> None:
    data = multipath_rician_awgn_profile().to_dict()
    assert "doppler_spread_hz" not in data and "symbol_rate_baud" not in data
    with pytest.raises(ValueError):
        ChannelConfig.from_dict(data | {"doppler_spread_hz": 1.0})


def test_gaussian_doppler_ensemble_statistics() -> None:
    rate, spread = 19_200.0, 2.0
    lag = int(rate * 0.3 / spread)
    samples = np.array(
        [
            gaussian_doppler_process(
                lag + 10,
                doppler_spread_hz=spread,
                sample_rate_hz=rate,
                rng=np.random.default_rng(s),
            )[[5, 5 + lag]]
            for s in range(1500)
        ]
    )
    power = float(np.mean(np.abs(samples[:, 0]) ** 2))
    correlation = abs(np.mean(samples[:, 1] * np.conj(samples[:, 0]))) / power
    assert power == pytest.approx(1.0, abs=0.08)
    assert correlation == pytest.approx(
        gaussian_doppler_autocorrelation(lag / rate, spread), abs=0.06
    )


def test_slow_doppler_is_nearly_constant_over_a_symbol() -> None:
    process = gaussian_doppler_process(
        8 * 512, doppler_spread_hz=0.5, sample_rate_hz=19_200.0, rng=np.random.default_rng(1)
    )
    symbol_means = process.reshape(512, 8).mean(axis=1, keepdims=True)
    within = np.abs(process.reshape(512, 8) - symbol_means)
    assert float(np.max(within)) < 1e-3


@pytest.mark.parametrize("condition", sorted(ITU_HF_DOPPLER_SPREAD_HZ))
def test_itu_profiles_run_in_known_channel_metric_trial(condition: str) -> None:
    profile = itu_hf_doppler_profile(
        condition, noise_complex_variance=0.1, fading_seed=11, noise_seed=12
    )
    assert profile.paths[1].delay_samples == 3
    result = run_metric_trial(
        MetricTrialSpec(
            f"itu-{condition}", 128, 3, profile, "known_channel", euclidean_metric="csi_weighted"
        )
    )
    assert result.summary["frontend_mode"] == "known_channel_csi"
    assert result.summary["euclidean"]["bits"] > 0
