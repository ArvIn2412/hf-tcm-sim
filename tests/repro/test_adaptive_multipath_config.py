from __future__ import annotations

import json

import pytest

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)


def test_static_and_rician_profiles_round_trip_without_realization_fields() -> None:
    static = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=32,
        paths=(AdaptivePathConfig(0, prior_mean=0j, prior_variance=100.0),),
        channel_mode="unknown_static",
        observation_noise_variance=0.0,
        decoder_mode="finite_depth",
        traceback_depth=20,
    )
    rician = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=32,
        paths=(AdaptivePathConfig(0, average_power=1.0, k_factor=3.0, los_phase_rad=0.2),),
        channel_mode="rician_ar1",
        correlation=0.99,
        observation_noise_variance=0.01,
    )

    restored_static = AdaptiveMultipathReceiverConfig.from_json(json.dumps(static.to_dict()))
    restored_rician = AdaptiveMultipathReceiverConfig.from_json(json.dumps(rician.to_dict()))
    assert restored_static.to_dict() == static.to_dict()
    assert restored_rician.to_dict() == rician.to_dict()
    assert "coefficients" not in json.dumps(rician.to_dict())
    assert "EvaluationTruth" not in json.dumps(rician.to_dict())


def test_profile_validation_requires_complete_priors_and_sample_level_rho() -> None:
    with pytest.raises(ValueError, match="prior_mean and prior_variance"):
        AdaptivePathConfig(0)
    with pytest.raises(ValueError, match="Rician public parameters"):
        AdaptivePathConfig(3, average_power=1.0)
    with pytest.raises(ValueError, match="rho must be"):
        AdaptiveMultipathReceiverConfig(
            expected_symbol_count=8,
            paths=(AdaptivePathConfig(0, average_power=1.0, k_factor=2.0),),
            channel_mode="rician_ar1",
            correlation=1.0,
            observation_noise_variance=0.1,
        )
    with pytest.raises(ValueError, match="rho >= 0.98"):
        AdaptiveMultipathReceiverConfig(
            expected_symbol_count=8,
            paths=(AdaptivePathConfig(0, average_power=1.0, k_factor=2.0),),
            channel_mode="slow_fading_rician_ar1",
            correlation=0.95,
            observation_noise_variance=0.1,
        )


def test_config_refuses_truth_fields_and_unsupported_delay_memory() -> None:
    base = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=8,
        paths=(AdaptivePathConfig(0, prior_mean=0j, prior_variance=1.0),),
        channel_mode="unknown_static",
        observation_noise_variance=0.0,
    ).to_dict()
    with pytest.raises(ValueError, match="unexpected adaptive receiver config field"):
        AdaptiveMultipathReceiverConfig.from_dict({**base, "evaluation_truth": {}})
    with pytest.raises(ValueError, match="requires more than 2 previous symbols"):
        AdaptiveMultipathReceiverConfig(
            expected_symbol_count=8,
            paths=(AdaptivePathConfig(17, prior_mean=0j, prior_variance=1.0),),
            channel_mode="unknown_static",
            observation_noise_variance=0.0,
        )
