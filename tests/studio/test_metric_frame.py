"""Whole-frame view behind «Канал у часі» and «Декодування»."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.repro.exp04_protocol import DEFAULT_PROTOCOL, cell_config, load_protocol
from hf_tcm.repro.metric_experiment import run_metric_study
from hf_tcm.studio.metric_frame import error_events, load_metric_frame
from hf_tcm.studio.metric_trace import load_metric_trace


def test_error_events_are_maximal_runs_of_wrong_edges() -> None:
    sent = np.array([0, 1, 2, 3, 4, 5, 6, 7])
    decoded = np.array([0, 9, 9, 3, 4, 9, 6, 9])
    assert error_events(decoded, sent) == [
        {"start": 1, "stop": 3},
        {"start": 5, "stop": 6},
        {"start": 7, "stop": 8},
    ]
    assert error_events(sent, sent) == []


@pytest.fixture(scope="module")
def noisy_study(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = dataclasses.replace(
        cell_config(protocol, "A3-itu-moderate", digest, phase="range_finding"),
        experiment_id="frame-view",
        frame_symbols=256,
        energy_grid_db=(4.0,),
        trials_per_point=1,
        full_array_stride=1,
        bootstrap_replicates=100,
    )
    root = tmp_path_factory.mktemp("studies")
    assert run_metric_study(config, root)["status"] == "completed"
    return root, "frame-view"


def test_frame_view_is_consistent_with_the_symbol_trace(noisy_study: tuple[Path, str]) -> None:
    root, study = noisy_study
    frame = load_metric_frame(root, study, bins=128)
    trace = load_metric_trace(root, study, start=0, count=80)
    size = frame["size"]
    assert size == 256 and frame["replay_verified"]
    for key in ("payload_mask", "true_states", "effective_snr_db", "offset", "hard_correct"):
        assert len(frame[key]) == size
    for arm in ("hamming", "euclidean"):
        view = frame["arms"][arm]
        assert view["pair_errors"] == trace["arms"][arm]["pair_error_mask"]
        assert len(view["decoded_states"]) == size
        # every symbol error lies inside an event (path left the transmitted path)
        inside = np.zeros(size, bool)
        for event in view["events"]:
            inside[event["start"] : event["stop"]] = True
        assert not np.any(np.asarray(view["pair_errors"]) & ~inside)
    # hard decisions agree with the per-symbol stage block of the trace
    window = trace["frontend_window"]
    tx_phases = trace["tx_phases"]
    for k, stage in enumerate(window):
        assert frame["hard_correct"][k] == (stage["hard_phase"] == tx_phases[k])
    assert len(frame["rx_i"]) <= 128 + 1


def test_frame_view_rejects_bad_requests(noisy_study: tuple[Path, str]) -> None:
    root, study = noisy_study
    with pytest.raises(ValueError):
        load_metric_frame(root, study, bins=10)
    with pytest.raises(ValueError):
        load_metric_frame(root, "../escape")
