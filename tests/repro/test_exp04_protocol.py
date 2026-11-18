"""SCIENTIFIC-EXP-04 protocol, common random numbers and approval gating."""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.repro.energy_statistics import analyze_energy_records
from hf_tcm.repro.exp04_protocol import (
    DEFAULT_PROTOCOL,
    cell_config,
    load_protocol,
    preflight,
    reference_gamma_db,
    run_cells,
)
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    _trial_config_for_point,
    run_metric_study,
)


def test_protocol_cells_build_valid_configs() -> None:
    protocol, digest, _status = load_protocol(DEFAULT_PROTOCOL)
    ids = [cell["id"] for cell in protocol["cells"]]
    assert len(ids) == len(set(ids))
    for cell_id in ids:
        config = cell_config(protocol, cell_id, digest)
        assert config.phase == "confirmatory"
        assert config.protocol_sha256 == digest
        assert config.common_random_numbers
        assert len(config.energy_grid_db) <= 21


def test_reference_gamma_matches_awgn_direct_convention() -> None:
    cell = {"frontend_mode": "awgn_direct_control"}
    assert reference_gamma_db(cell, 512, {}) == pytest.approx(10 * np.log10(4.0))


def test_crn_reuses_seeds_across_energy_points() -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = cell_config(protocol, "A3-itu-moderate", digest, phase="range_finding")
    first = _trial_config_for_point(config, config.energy_grid_db[0], 0, 7)
    last = _trial_config_for_point(config, config.energy_grid_db[-1], 20, 7)
    assert first.source_seed == last.source_seed
    assert first.channel_config.fading_seed == last.channel_config.fading_seed
    assert first.channel_config.noise_seed == last.channel_config.noise_seed
    assert first.amplitude < last.amplitude
    independent = dataclasses.replace(config, common_random_numbers=False)
    other = _trial_config_for_point(independent, independent.energy_grid_db[-1], 20, 7)
    assert other.source_seed != first.source_seed


def test_confirmatory_requires_protocol_digest_and_defaults_keep_hash() -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = cell_config(protocol, "A1-awgn", digest, phase="range_finding")
    with pytest.raises(ValueError):
        dataclasses.replace(config, phase="confirmatory", protocol_sha256="")
    plain = dataclasses.replace(config, common_random_numbers=False)
    data = plain.to_dict()
    assert "common_random_numbers" not in data and "protocol_sha256" not in data
    assert MetricStudyConfig.from_dict(config.to_dict()) == config


def _rows(errors_h: list[list[int]], errors_e: list[list[int]]) -> list[dict]:
    rows = []
    for point, gamma in enumerate((0.0, 2.0, 4.0)):
        for trial in range(len(errors_h[point])):
            rows.append(
                {
                    "scenario": "awgn",
                    "sweep": "amplitude",
                    "phase": "range_finding",
                    "gamma_db": gamma,
                    "trial_index": trial,
                    "bits": 1000,
                    "pairs": 500,
                    "bit_errors": {
                        "joint": errors_e[point][trial],
                        "hamming": errors_h[point][trial],
                    },
                    "pair_errors": {
                        "joint": errors_e[point][trial],
                        "hamming": errors_h[point][trial],
                    },
                }
            )
    return rows


def test_common_cluster_bootstrap_requires_matching_trials() -> None:
    rng = np.random.default_rng(3)
    h = [
        list(rng.integers(150, 250, 30)),
        list(rng.integers(60, 120, 30)),
        list(rng.integers(10, 40, 30)),
    ]
    e = [
        list(rng.integers(60, 120, 30)),
        list(rng.integers(10, 40, 30)),
        list(rng.integers(0, 5, 30)),
    ]
    result = analyze_energy_records(
        _rows(h, e), 0.05, arm="hamming", replicates=300, seed=1, common_clusters=True
    )
    assert result["bootstrap"]["method"].endswith("common_clusters_across_gamma")
    assert result["gain_db"] is not None and result["gain_db"] > 0
    broken = _rows(h, e)
    broken[0]["trial_index"] = 99
    with pytest.raises(ValueError):
        analyze_energy_records(broken, 0.05, arm="hamming", replicates=50, common_clusters=True)


def test_run_cells_refuses_unfrozen_or_unapproved(tmp_path: Path) -> None:
    protocol_copy = tmp_path / DEFAULT_PROTOCOL.name
    shutil.copyfile(DEFAULT_PROTOCOL, protocol_copy)
    with pytest.raises(PermissionError):
        run_cells(protocol_copy, ["A1-awgn"], approve_sha256="0" * 64, output_root=tmp_path)
    protocol, digest, _ = load_protocol(protocol_copy)
    protocol_copy.with_name(protocol_copy.name + ".sha256").write_text(digest, encoding="utf-8")
    assert load_protocol(protocol_copy)[2] == "FROZEN"
    with pytest.raises(PermissionError):
        run_cells(protocol_copy, ["A1-awgn"], approve_sha256="f" * 64, output_root=tmp_path)


def test_tiny_crn_study_has_monotone_curves(tmp_path: Path) -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = dataclasses.replace(
        cell_config(protocol, "A1-awgn", digest, phase="range_finding"),
        experiment_id="exp04-tiny",
        frame_symbols=64,
        energy_grid_db=(-4.0, 0.0, 4.0),
        trials_per_point=3,
        bootstrap_replicates=100,
    )
    summary = run_metric_study(config, tmp_path)
    assert summary["status"] == "completed"
    for arm in ("hamming", "joint"):
        errors = [row["bit_errors"][arm] for row in summary["aggregates"]]
        assert errors == sorted(errors, reverse=True)
    assert summary["confirmatory_series_executed"] is False
    saved = json.loads((tmp_path / "exp04-tiny" / "config.json").read_text(encoding="utf-8"))
    assert saved["common_random_numbers"] is True


def test_preflight_runs_no_series() -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    small = dict(protocol, cells=[protocol["cells"][0]])
    report = preflight(small, digest, timing_trials=1)
    assert report["series_executed"] is False
    assert report["cells"][0]["eb_n0_axis_ok"]


def test_compact_array_policy_keeps_recount_and_blocks_trace(tmp_path: Path) -> None:
    from hf_tcm.studio.metric_trace import load_metric_trace

    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = dataclasses.replace(
        cell_config(protocol, "A1-awgn", digest, phase="range_finding"),
        experiment_id="exp04-compact",
        frame_symbols=64,
        energy_grid_db=(0.0,),
        trials_per_point=3,
        bootstrap_replicates=100,
        full_array_stride=2,
    )
    summary = run_metric_study(config, tmp_path)
    assert summary["recount"]["count_replay"] == "PASS"
    trials = tmp_path / "exp04-compact" / "trials"
    policies = [
        json.loads((trials / f"p000-t{i:04d}.json").read_text(encoding="utf-8"))["array_policy"]
        for i in range(3)
    ]
    assert policies == ["full", "compact_recount_only", "full"]
    assert load_metric_trace(tmp_path, "exp04-compact", trial=0, compact=True)["replay_verified"]
    with pytest.raises(ValueError, match="compact recount arrays"):
        load_metric_trace(tmp_path, "exp04-compact", trial=1)


def test_incomplete_crn_study_writes_summary_and_resumes(tmp_path: Path) -> None:
    protocol, digest, _ = load_protocol(DEFAULT_PROTOCOL)
    config = dataclasses.replace(
        cell_config(protocol, "A1-awgn", digest, phase="range_finding"),
        experiment_id="exp04-resume",
        frame_symbols=64,
        energy_grid_db=(-4.0, 0.0),
        trials_per_point=3,
        bootstrap_replicates=100,
    )
    import threading

    stop = threading.Event()
    calls = {"n": 0}

    def progress(_: dict) -> None:
        calls["n"] += 1
        if calls["n"] == 4:
            stop.set()

    partial = run_metric_study(config, tmp_path, stop_event=stop, progress_callback=progress)
    assert partial["status"] == "incomplete"
    assert partial["gain_analysis"]["reason"].startswith("INCOMPLETE_CRN_DESIGN")
    final = run_metric_study(config, tmp_path)
    assert final["status"] == "completed"
    assert final["completed_trials"] == 6
    assert "bootstrap" in final["gain_analysis"]
