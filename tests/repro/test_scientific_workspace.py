from __future__ import annotations

import json
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from threading import Event

import numpy as np
import pytest

from hf_tcm.repro.paired_experiment import (
    ExperimentConfig,
    run_paired_experiment,
    verify_experiment,
)
from hf_tcm.studio.scientific import (
    ScientificRunConfig,
    load_run_summary,
    run_scientific_run,
    trace_window,
)
from hf_tcm.studio.server import make_server


def test_scientific_config_rejects_unsupported_channel_and_frame() -> None:
    with pytest.raises(ValueError, match="channel_profile"):
        ScientificRunConfig.from_dict({"channel_profile": "magic"})
    with pytest.raises(ValueError, match="frame_symbols"):
        ScientificRunConfig(frame_symbols=0)


def _output_root() -> Path:
    path = Path("outputs/repro09/test-workspace") / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_identity_run_uses_one_observation_and_saves_real_traces() -> None:
    tmp_path = _output_root()
    config = ScientificRunConfig(
        run_id="identity-test",
        frame_symbols=32,
        source_seed=13,
        channel_seed=29,
        channel_profile="identity",
        output_root=str(tmp_path),
    )
    summary = run_scientific_run(config)

    assert summary["status"] == "completed"
    assert summary["joint"]["observation_sha256"] == summary["separate"]["observation_sha256"]
    assert summary["joint"]["compared_bits"] == summary["separate"]["compared_bits"] == 64
    assert summary["joint"]["bit_errors"] == summary["separate"]["bit_errors"] == 0
    assert summary["receiver_observation_sha256"]
    assert (tmp_path / "identity-test" / "traces.npz").is_file()
    assert (tmp_path / "identity-test" / "evaluation_truth.npz").is_file()
    manifest = json.loads((tmp_path / "identity-test" / "manifest.json").read_text())
    assert manifest["files"]["traces.npz"]

    loaded = load_run_summary(tmp_path / "identity-test")
    assert loaded["receiver_observation_sha256"] == summary["receiver_observation_sha256"]
    window = trace_window(tmp_path / "identity-test", start_symbol=2, symbol_count=3)
    assert window["sample_start"] == 16
    assert len(window["received_i"]) == 24
    assert len(window["information_bits"]) == 6
    assert np.isfinite(window["received_q"]).all()


def test_static_multipath_run_keeps_public_config_and_truth_separate() -> None:
    tmp_path = _output_root()
    config = ScientificRunConfig(
        run_id="static-pair",
        frame_symbols=32,
        source_seed=7,
        channel_seed=11,
        channel_profile="static_multipath",
        output_root=str(tmp_path),
        delays_samples=(0, 3),
        path_coefficients=((0.8, 0.0), (0.2, -0.1)),
    )
    summary = run_scientific_run(config)
    assert summary["channel"]["sample_count"] == 32 * 8 + 3
    assert summary["joint"]["observation_sha256"] == summary["separate"]["observation_sha256"]
    assert summary["channel"]["truth_is_receiver_input"] is False
    assert summary["joint"]["trellis_state_count"] == 17


def test_rician_gui_profile_runs_without_truth_input() -> None:
    root = _output_root()
    config = ScientificRunConfig(
        run_id="rician-test",
        frame_symbols=32,
        source_seed=101,
        channel_seed=303,
        channel_profile="rician_ar1_multipath",
        noise_variance=0.005,
        output_root=str(root),
        delays_samples=(0, 3),
    )
    summary = run_scientific_run(config)
    assert summary["paired_observation_verified"] is True
    assert summary["channel"]["truth_is_receiver_input"] is False
    assert summary["sample_count"] == 32 * 8 + 3
    assert np.isfinite(summary["joint"]["ber"])


def test_scientific_http_launch_polls_and_loads_real_saved_run() -> None:
    server = make_server("127.0.0.1", 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    address = f"http://127.0.0.1:{server.server_port}"
    run_id = f"http-{uuid.uuid4().hex[:12]}"
    try:
        with urllib.request.urlopen(f"{address}/scientific") as response:
            assert response.status == 200
            assert 'lang="uk"' in response.read().decode("utf-8")
        request = urllib.request.Request(
            f"{address}/api/scientific/run",
            data=json.dumps(
                {
                    "run_id": run_id,
                    "frame_symbols": 32,
                    "source_seed": 31,
                    "channel_seed": 32,
                    "channel_profile": "identity",
                    "noise_variance": 0,
                    "delays_samples": [0],
                    "path_coefficients": [[1, 0]],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            job_id = json.load(response)["job_id"]
        for _ in range(200):
            with urllib.request.urlopen(f"{address}/api/scientific/jobs/{job_id}") as response:
                job = json.load(response)
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert job["status"] == "completed", job
        with urllib.request.urlopen(f"{address}/api/scientific/runs/{run_id}") as response:
            summary = json.load(response)
        assert summary["paired_observation_verified"] is True
        with urllib.request.urlopen(
            f"{address}/api/scientific/traces?run_id={run_id}&start=1&count=2"
        ) as response:
            trace = json.load(response)
        assert trace["sample_start"] == 8
        assert len(trace["received_i"]) == 16
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_paired_runner_stop_and_resume_keeps_completed_pair_once() -> None:
    output = Path("outputs/repro09/test-monte-carlo") / uuid.uuid4().hex
    config = ExperimentConfig(
        experiment_id="resume-check",
        frame_symbols=32,
        noise_variances=(0.005,),
        trials_per_point=1,
        root_seed=991,
        output_dir=str(output),
        run_level="smoke",
        channel_profile="rician_ar1_multipath",
        max_trials=1,
        max_wall_seconds=120,
        bootstrap_replicates=100,
        diagnostics_level="summary_only",
    )
    stop = Event()
    stop.set()
    interrupted = run_paired_experiment(config, progress=False, stop_event=stop)
    assert interrupted["status"] == "incomplete"
    assert interrupted["completed_trials"] == 0

    resumed = run_paired_experiment(config, progress=False)
    assert resumed["status"] == "completed"
    assert resumed["completed_trials"] == 1
    assert len(resumed["completed_trial_record_sha256"]) == 1
    verified = verify_experiment(output / "resume-check")
    assert "summary.json" in verified
