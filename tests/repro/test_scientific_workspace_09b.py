from __future__ import annotations

import subprocess
import sys
import threading
import urllib.request
import uuid
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.studio.scientific import (
    ScientificRunConfig,
    load_long_frame_archive,
    long_frame_viterbi_window,
    run_scientific_run,
    trace_sample_window,
    trace_window,
    viterbi_window,
)
from hf_tcm.studio.server import make_server


def test_scientific_launcher_root_serves_scientific_workspace() -> None:
    server = make_server(port=0, default_view="scientific")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
            body = response.read().decode("utf-8")
        assert 'id="view-parameters"' in body
        assert "Interactive Demo Studio" not in body
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_b1_is_available_for_public_static_multipath_and_paired() -> None:
    run_id = f"test09b-b1-{uuid.uuid4().hex}"
    result = run_scientific_run(
        ScientificRunConfig(
            run_id=run_id,
            frame_symbols=32,
            source_seed=31,
            channel_seed=47,
            channel_profile="static_multipath",
            noise_variance=0.0,
            delays_samples=(0, 3),
            path_coefficients=((0.8, 0.0), (0.2, -0.1)),
            include_b1=True,
            output_root="outputs/repro09",
        )
    )

    assert result["paired_observation_verified"] is True
    assert result["b1"]["observation_sha256"] == result["receiver_observation_sha256"]
    assert result["b1"]["profile_id"] == "repro08_public_static_channel_hard_v1"
    assert result["b1"]["compared_bits"] == 64
    assert result["b1"]["channel_information"] == "explicit_public_static_taps"
    assert result["receiver_inputs_excluded_evaluation_truth"] is True


def test_b1_rejects_time_varying_profiles_before_receiver_invocation() -> None:
    with pytest.raises(ValueError, match="B1 supports only public static channel profiles"):
        ScientificRunConfig(channel_profile="rician_ar1_multipath", include_b1=True)


def test_trace_window_keeps_symbol_and_sample_indices_aligned() -> None:
    run_id = f"test09b-window-{uuid.uuid4().hex}"
    run_scientific_run(
        ScientificRunConfig(
            run_id=run_id,
            frame_symbols=32,
            source_seed=53,
            channel_seed=59,
            channel_profile="static_multipath",
            delays_samples=(0, 3),
            path_coefficients=((0.8, 0.0), (0.2, -0.1)),
            output_root="outputs/repro09",
        )
    )
    run_dir = Path("outputs/repro09") / run_id
    window = trace_window(run_dir, start_symbol=3, symbol_count=2)
    assert window["start_symbol"] == 3
    assert window["sample_start"] == 24
    assert window["sample_stop"] == 40
    assert window["absolute_sample_indices"] == list(range(24, 40))
    assert (
        np.asarray(window["information_bits"], dtype=np.int8).reshape(-1, 2).tolist()
        == window["input_pairs"]
    )
    trellis = viterbi_window(run_dir, receiver="joint", symbol_index=19, traceback_depth=20)
    assert trellis["available"] is True
    assert trellis["traceback_window_transitions"] == 20
    assert trellis["sample_start"] == 8 * 19
    assert len(trellis["transitions"]) == 68
    assert len(trellis["traceback_local_survivor_path"]) == 20
    assert len(trellis["traceback_steps"]) == 20
    assert len(trellis["traceback_steps"][-1]["survivor_edge_ids_by_destination"]) == 17
    decision = trellis["emitted_decision_on_this_arrival"]
    assert decision["symbol_index"] == 0
    assert decision["decision_available_at"] == 19
    assert decision["traceback_depth_used"] == 20
    survivor_16 = viterbi_window(
        run_dir, receiver="joint", symbol_index=19, traceback_depth=20, survivor_state=16
    )
    assert survivor_16["endpoint_state_id"] == 16
    assert survivor_16["traceback_local_survivor_path"][-1]["target_node_id"] == 16
    b0 = viterbi_window(run_dir, receiver="b0", symbol_index=19, traceback_depth=20)
    assert len(b0["transitions"]) == 16


def test_twenty_sample_zoom_keeps_absolute_indices_and_marks_channel_tail() -> None:
    run_id = f"test09b-sample-tail-{uuid.uuid4().hex}"
    run_scientific_run(
        ScientificRunConfig(
            run_id=run_id,
            frame_symbols=32,
            source_seed=61,
            channel_seed=67,
            channel_profile="static_multipath",
            delays_samples=(0, 3),
            path_coefficients=((0.8, 0.0), (0.2, -0.1)),
            output_root="outputs/repro09",
        )
    )
    samples = trace_sample_window(
        Path("outputs/repro09") / run_id, sample_start=8 * 31, sample_count=20
    )
    assert samples["absolute_sample_indices"] == list(range(248, 259))
    assert samples["symbol_indices"][:8] == [31] * 8
    assert samples["tail_sample"] == [False] * 8 + [True] * 3
    assert len(samples["received_i"]) == 11


def test_verified_long_frame_archives_keep_observation_sources_separate() -> None:
    archive = load_long_frame_archive()
    assert archive["status"] == "verified"
    assert archive["repro08_metrics"]["frame_symbols"] == 20_000
    assert archive["repro08_metrics"]["compared_bits"] == 40_000
    assert archive["repro06c_trace"]["trellis_state_count"] == 17
    assert archive["repro06c_trace"]["trellis_edge_count"] == 68
    assert archive["same_observation"] is False
    trace = long_frame_viterbi_window(symbol_index=19_999, traceback_depth=20)
    assert trace["available"] is True
    assert trace["symbol_index"] == 19_999
    assert trace["traceback_window_transitions"] == 20
    assert trace["sample_start"] == 159_992
    assert trace["sample_stop"] == 160_003
    assert trace["signal_samples_available"] is False


def test_scientific_workspace_has_separate_launcher_and_legacy_cli_stays_demo_only() -> None:
    scientific = subprocess.run(
        [sys.executable, "-m", "hf_tcm.repro.scientific_studio", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    legacy = subprocess.run(
        [sys.executable, "-m", "hf_tcm.demo_studio", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Scientific Workspace" in scientific.stdout
    assert "--view" not in legacy.stdout
