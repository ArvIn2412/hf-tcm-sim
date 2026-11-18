"""Smoke the UI adapter against existing channel and paired-decoder APIs."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hf_tcm.repro.channel_config import ChannelConfig
from hf_tcm.repro.metric_experiment import MetricStudyConfig, MetricTrialSpec, run_metric_trial


@pytest.fixture(scope="module")
def channels():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the UI-to-Python configuration smoke")
    root = Path(__file__).resolve().parents[2]
    script = """
const {build} = require('./src/hf_tcm/studio/static/channel_controls.js');
const rows = [];
for (const fading of ['none', 'rician', 'rayleigh'])
  for (const rays of [1, 2, 3]) for (const awgn of [false, true]) {
    const config = build({fading, rays, awgn, variance: 0.05, seed: 123, rho: 0.98,
      delays: [0,3,6].slice(0,rays), powers: [1,.25,.125].slice(0,rays),
      factors: [4,1,1].slice(0,rays), phases: [0,.7,1.4].slice(0,rays),
      frontend: 'pilot_equalized'});
    rows.push({fading, rays, awgn, config});
  }
console.log(JSON.stringify(rows));
"""
    result = subprocess.run(
        [node, "-e", script], cwd=root, capture_output=True, text=True, check=True, timeout=15
    )
    return json.loads(result.stdout)


def test_all_control_combinations_validate_in_existing_python_configuration(channels):
    for row in channels:
        channel = ChannelConfig.from_dict(row["config"])
        scenario = "rician" if row["fading"] != "none" else "awgn" if row["rays"] == 1 else "static"
        study = MetricStudyConfig(
            experiment_id="ui-controls-smoke",
            scenario=scenario,
            phase="validation",
            frame_symbols=32,
            energy_grid_db=(0.0,),
            trials_per_point=1,
            root_seed=123,
            target_ber=0.05,
            time_budget_seconds=10,
            sweep="amplitude",
            amplitude=1.0,
            channel_config=row["config"],
            frontend_mode="pilot_equalized",
        )
        assert len(channel.paths) == row["rays"]
        if not row["awgn"]:
            with pytest.raises(ValueError, match="positive base complex-noise"):
                MetricStudyConfig.from_dict({**study.to_dict(), "sweep": "noise"})


@pytest.mark.parametrize("fading", ["none", "rician", "rayleigh"])
@pytest.mark.parametrize("awgn", [False, True])
def test_three_ray_single_frame_replay_is_deterministic_and_paired(channels, fading, awgn):
    row = next(
        r for r in channels if r["fading"] == fading and r["rays"] == 3 and r["awgn"] == awgn
    )
    spec = MetricTrialSpec(
        "ui-controls-smoke", 32, 123, ChannelConfig.from_dict(row["config"]), "pilot_equalized"
    )
    first = run_metric_trial(spec).summary
    second = run_metric_trial(spec).summary
    assert first["observation_sha256"] == second["observation_sha256"]
    assert first["observation_sha256"] == first["paired_observation_sha256"]
    assert first["frontend_output_sha256_euclidean"] == first["frontend_output_sha256_hamming"]
    for arm in ("euclidean", "hamming"):
        assert first[arm]["bit_errors"] == second[arm]["bit_errors"]
