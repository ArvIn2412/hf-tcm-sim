import json

import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    MetricTrialSpec,
    _refresh_manifest,
    _save_trial,
    run_metric_study,
    run_metric_trial,
)
from hf_tcm.studio.metric_trace import load_metric_trace


@pytest.mark.parametrize("variance", [0.0, 0.1])
@pytest.mark.parametrize("frontend", ["awgn_direct_control", "pilot_equalized"])
def test_saved_trace_replays_bits_and_real_rx(tmp_path, variance, frontend):
    config = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1, 0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain" if variance else "none",
        noise_complex_variance=variance,
        reveal_noise_variance=True,
        fading_seed=11,
        noise_seed=22,
    )
    result = run_metric_trial(MetricTrialSpec("test", 32, 331, config, frontend))
    folder = tmp_path / "live"
    _save_trial(folder, 0, 0, result)
    (folder / "config.json").write_text(
        json.dumps(
            {
                "frontend_mode": frontend,
                "preamble_symbols": 4,
                "pilot_period": 32,
                "pilot_burst_symbols": 4,
            }
        )
    )
    _refresh_manifest(folder, "live", "test")
    trace = load_metric_trace(tmp_path, "live", limit=256)
    assert trace["replay_verified"] and trace["pairing_verified"]
    rx = np.array([p["i"] + 1j * p["q"] for p in trace["received"]])
    np.testing.assert_array_equal(rx, result.received_samples[:256])
    residual = np.abs(rx - result.transmitted_samples)
    assert (np.max(residual) == 0) if variance == 0 else (np.max(residual) > 0)
    assert len(trace["arms"]["hamming"]["survivors"]) == 20
    for arm in ("hamming", "euclidean"):
        assert trace["arms"][arm]["bits"] == getattr(result, f"decoded_{arm}_pairs")[:20].tolist()
    (folder / "trials/p000-t0000.npz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        load_metric_trace(tmp_path, "live")


def test_trace_rejects_path_escape(tmp_path):
    with pytest.raises(ValueError, match="study ID"):
        load_metric_trace(tmp_path, "../archive")


def test_noiseless_study_keeps_counts_without_finite_energy_gain(tmp_path):
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1, 0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="none",
        noise_complex_variance=0,
        fading_seed=11,
        noise_seed=22,
        reveal_noise_variance=True,
    )
    config = MetricStudyConfig(
        experiment_id="ui-zero",
        scenario="awgn",
        phase="validation",
        frame_symbols=32,
        energy_grid_db=(0.0,),
        trials_per_point=1,
        root_seed=123,
        target_ber=0.05,
        time_budget_seconds=10,
        sweep="amplitude",
        amplitude=1,
        channel_config=channel.to_dict(),
        frontend_mode="awgn_direct_control",
        bootstrap_replicates=100,
    )
    summary = run_metric_study(config, tmp_path)
    assert summary["completed_trials"] == 1
    assert summary["status"] == "completed"
    assert summary["aggregates"] == []


def test_energy_grid_groups_roundoff_by_declared_point_not_payload_phase(tmp_path):
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1, 0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.05,
        fading_seed=11,
        noise_seed=22,
        reveal_noise_variance=True,
    )
    config = MetricStudyConfig(
        experiment_id="ui-grouping",
        scenario="awgn",
        phase="validation",
        frame_symbols=64,
        energy_grid_db=(-17.0, -15.0),
        trials_per_point=20,
        root_seed=134001,
        target_ber=0.05,
        time_budget_seconds=30,
        sweep="amplitude",
        amplitude=1,
        channel_config=channel.to_dict(),
        frontend_mode="awgn_direct_control",
        bootstrap_replicates=100,
    )
    result = run_metric_study(config, tmp_path)
    assert len(result["aggregates"]) == 2
    assert [r["trials"] for r in result["aggregates"]] == [20, 20]
