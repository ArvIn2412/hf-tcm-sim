"""Known-channel mode and CSI-weighted Euclidean metric (defense plan P0-1/P0-2)."""

from __future__ import annotations

import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    MetricTrialSpec,
    run_metric_trial,
)
from hf_tcm.repro.metric_isolation import euclidean_branch_metric_rows


def _rician(seed: int, variance: float, correlation: float = 0.9999) -> ChannelConfig:
    return ChannelConfig(
        profile_id="rician_known_test",
        paths=(
            ChannelPathConfig(0, 0.8, 4.0, 0.0),
            ChannelPathConfig(3, 0.2, 1.0, 0.7),
        ),
        fading_mode="rician_ar1",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=variance,
        fading_seed=seed,
        noise_seed=seed + 1,
        correlation=correlation,
        reveal_noise_variance=True,
    )


def _awgn(variance: float) -> ChannelConfig:
    return ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=variance,
        fading_seed=1,
        noise_seed=2,
        reveal_noise_variance=True,
    )


def test_weighted_cost_matches_sample_domain_ml_up_to_candidate_constant() -> None:
    rng = np.random.default_rng(5)
    taps = rng.standard_normal(5) + 1j * rng.standard_normal(5)
    received = rng.standard_normal(5) + 1j * rng.standard_normal(5)
    power = float(np.vdot(taps, taps).real)
    combined = np.vdot(taps, received) / power
    weighted = euclidean_branch_metric_rows(
        np.array([combined]), amplitude=1.0, csi_weights=np.array([power])
    )[0]
    phases = np.exp(1j * np.pi / 4 * np.arange(8))
    from hf_tcm.repro.metric_isolation import _EDGE_PHASES

    ml = np.array([np.sum(np.abs(received - taps * phases[p]) ** 2) for p in _EDGE_PHASES])
    difference = ml - weighted
    assert np.allclose(difference, difference[0])


def test_weights_validation() -> None:
    with pytest.raises(ValueError):
        euclidean_branch_metric_rows(np.ones(3), amplitude=1.0, csi_weights=np.ones(2))
    with pytest.raises(ValueError):
        euclidean_branch_metric_rows(np.ones(2), amplitude=1.0, csi_weights=np.array([1.0, -1]))


def test_constant_weight_keeps_awgn_decisions_identical() -> None:
    results = {
        metric: run_metric_trial(
            MetricTrialSpec(
                "awgn-weight",
                256,
                41,
                _awgn(0.6),
                "awgn_direct_control",
                euclidean_metric=metric,  # type: ignore[arg-type]
            )
        )
        for metric in ("unweighted", "csi_weighted")
    }
    assert np.array_equal(
        results["unweighted"].decoded_euclidean_pairs,
        results["csi_weighted"].decoded_euclidean_pairs,
    )
    assert results["csi_weighted"].summary["euclidean_metric"] == "csi_weighted"
    assert results["unweighted"].summary["euclidean_metric"] == "unweighted"


def test_known_channel_runs_on_rician_and_is_labelled() -> None:
    result = run_metric_trial(
        MetricTrialSpec(
            "known-rician",
            256,
            7,
            _rician(11, 0.3),
            "known_channel",
            euclidean_metric="csi_weighted",
        )
    )
    assert result.summary["frontend_mode"] == "known_channel_csi"
    assert np.all(result.frontend.combiner_power[result.frontend.valid_symbol_mask] > 0)
    # Hamming arm is unchanged by the weighting: same hard decisions on the same z.
    unweighted = run_metric_trial(
        MetricTrialSpec("known-rician", 256, 7, _rician(11, 0.3), "known_channel")
    )
    assert np.array_equal(result.hamming_branch_metrics, unweighted.hamming_branch_metrics)
    assert result.frontend.frontend_output_sha256 == unweighted.frontend.frontend_output_sha256


def test_known_channel_soft_metric_beats_hard_hamming_in_rician() -> None:
    soft = hard = 0
    for index in range(4):
        result = run_metric_trial(
            MetricTrialSpec(
                f"known-{index}",
                512,
                300 + index,
                _rician(400 + index, 0.5),
                "known_channel",
                euclidean_metric="csi_weighted",
            )
        )
        soft += result.summary["euclidean"]["bit_errors"]
        hard += result.summary["hamming"]["bit_errors"]
    assert soft < hard


def _study(**overrides: object) -> MetricStudyConfig:
    values: dict[str, object] = {
        "experiment_id": "known-test",
        "scenario": "rician",
        "phase": "validation",
        "frame_symbols": 64,
        "energy_grid_db": (0.0,),
        "trials_per_point": 1,
        "root_seed": 3,
        "target_ber": 0.05,
        "time_budget_seconds": 60.0,
        "sweep": "noise",
        "amplitude": 1.0,
        "channel_config": _rician(1, 0.5).to_dict(),
        "frontend_mode": "known_channel",
    }
    values.update(overrides)
    return MetricStudyConfig(**values)  # type: ignore[arg-type]


def test_study_config_hash_compatibility() -> None:
    assert "euclidean_metric" not in _study().to_dict()
    weighted = _study(euclidean_metric="csi_weighted").to_dict()
    assert weighted["euclidean_metric"] == "csi_weighted"
    assert MetricStudyConfig.from_dict(weighted).euclidean_metric == "csi_weighted"
    with pytest.raises(ValueError):
        _study(euclidean_metric="bogus")
