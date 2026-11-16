from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import hf_tcm.studio.energy as energy_adapter
from hf_tcm.studio.energy import (
    EnergyStudyConfig,
    calculate_single_run_energy_metrics,
    load_energy_study,
    run_energy_study,
)
from hf_tcm.studio.historical_energy import load_historical_energy_study


def test_energy_checkpoint_retries_transient_windows_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    original_replace = energy_adapter.os.replace
    attempts = 0

    def replace_with_transient_lock(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("transient file lock")
        original_replace(source, destination)

    monkeypatch.setattr(energy_adapter.os, "replace", replace_with_transient_lock)
    energy_adapter._atomic_json(target, {"completed_trials": 2})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"completed_trials": 2}
    assert not target.with_suffix(".json.pending").exists()


def test_single_run_energy_uses_actual_samples_and_discrete_convention() -> None:
    amplitude = 0.75
    frame_symbols = 4
    tx = np.full(8 * frame_symbols, amplitude * (1 + 0j), dtype=np.complex128)

    result = calculate_single_run_energy_metrics(
        tx,
        information_bit_count=2 * frame_symbols,
        amplitude=amplitude,
        noise_variance=0.5,
    )

    assert result["tx_energy_discrete"] == pytest.approx(8 * frame_symbols * amplitude**2)
    assert result["energy_per_information_bit_discrete"] == pytest.approx(4 * amplitude**2)
    assert result["gamma_b_d_db"] == pytest.approx(10 * np.log10(4 * amplitude**2 / 0.5))
    assert result["information_bits_per_symbol"] == 2
    assert result["sample_count"] == 8 * frame_symbols
    assert result["energy_relation_valid"] is True


def test_single_run_energy_marks_gamma_undefined_for_zero_noise() -> None:
    tx = np.ones(16, dtype=np.complex128)
    result = calculate_single_run_energy_metrics(
        tx, information_bit_count=4, amplitude=1.0, noise_variance=0.0
    )

    assert result["gamma_b_d_db"] is None
    assert result["tx_energy_discrete"] == 16
    assert result["energy_per_information_bit_discrete"] == 4


def test_historical_energy_study_revalidates_provenance_and_recomputes_gain() -> None:
    summary = load_historical_energy_study(Path("outputs/scientific_exp_01"))

    assert summary["historical"] is True
    assert summary["target_ber"] == pytest.approx(0.05)
    assert summary["completed_trials"] == summary["planned_trials"] == 140
    assert summary["receiver_arms"] == ["joint", "b0", "b1"]
    assert summary["provenance"]["verified_trial_records"] == 140
    assert summary["provenance"]["verified_archive_sha256"]
    assert summary["analyses"]["b0"]["gain_db"] == pytest.approx(6.767791470844502)
    assert summary["analyses"]["b1"]["gain_db"] == pytest.approx(2.9641483046268267)
    assert summary["analyses"]["b0"]["bootstrap"]["confidence_interval_db"] == pytest.approx(
        [6.209755937566691, 7.518165405257755]
    )
    assert summary["analyses"]["b1"]["bootstrap"]["confidence_interval_db"] == pytest.approx(
        [2.71559718117933, 3.2287690090798518]
    )
    assert all(
        len(record["receiver_observation_hashes"]) == 3
        and len(set(record["receiver_observation_hashes"].values())) == 1
        for record in summary["records"]
    )


def test_historical_energy_study_rejects_missing_provenance(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provenance"):
        load_historical_energy_study(tmp_path)


def test_historical_energy_study_is_available_through_read_only_gui_route() -> None:
    import urllib.request

    from hf_tcm.studio.server import make_server

    server = make_server("127.0.0.1", 0, default_view="scientific")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        address = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(
            f"{address}/api/scientific/energy-studies/historical/static-amplitude-005"
        ) as response:
            result = json.load(response)
        assert result["historical"] is True
        assert result["analyses"]["b0"]["gain_db"] == pytest.approx(6.767791470844502)
        assert result["analyses"]["b1"]["gain_db"] == pytest.approx(2.9641483046268267)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_single_run_energy_rejects_misaligned_sample_or_payload_count() -> None:
    with pytest.raises(ValueError, match="eight samples per symbol"):
        calculate_single_run_energy_metrics(
            np.ones(15, dtype=np.complex128),
            information_bit_count=4,
            amplitude=1.0,
            noise_variance=1.0,
        )


def test_energy_study_config_rejects_b1_for_rician_profile() -> None:
    with pytest.raises(ValueError, match="B1"):
        EnergyStudyConfig(
            experiment_id="rician-b1",
            frame_symbols=8,
            gamma_grid_db=(0.0, 3.0),
            trials_per_point=2,
            root_seed=31,
            target_ber=0.05,
            time_budget_seconds=60,
            sweep="amplitude",
            receiver_arms=("joint", "b1"),
            channel_profile="rician_ar1_multipath",
            noise_variance=1.0,
            amplitude=1.0,
        )


def test_energy_study_stop_and_resume_keeps_each_trial_once(tmp_path: Path) -> None:
    config = EnergyStudyConfig(
        experiment_id="resume-gui-energy",
        frame_symbols=8,
        gamma_grid_db=(0.0,),
        trials_per_point=1,
        root_seed=41,
        target_ber=0.05,
        time_budget_seconds=60,
        sweep="amplitude",
        receiver_arms=("joint", "b0"),
        channel_profile="static_multipath",
        noise_variance=1.0,
        amplitude=1.0,
        delays_samples=(0, 3),
        path_coefficients=((0.8, 0.0), (0.2, -0.1)),
        path_powers=(0.64, 0.05),
        rician_k_factors=(4.0, 1.0),
        los_phases_rad=(0.0, 0.7),
    )
    stop = threading.Event()
    stop.set()

    stopped = run_energy_study(config, tmp_path, stop_event=stop)
    assert stopped["status"] == "incomplete"
    assert stopped["completed_trials"] == 0

    completed = run_energy_study(config, tmp_path)
    assert completed["status"] == "completed"
    assert completed["completed_trials"] == 1
    assert completed["exploratory"] is True
    assert "розвідувальна" in completed["energy_gain_status_uk"]
    assert (
        completed["records"][0]["receiver_observation_hashes"]["joint"]
        == completed["records"][0]["receiver_observation_hashes"]["b0"]
    )

    repeated = run_energy_study(config, tmp_path)
    assert repeated["completed_trials"] == 1
    assert len(list((tmp_path / config.experiment_id).rglob("t*/manifest.json"))) == 1
    resumed_with_larger_budget = run_energy_study(
        replace(config, time_budget_seconds=90, target_ber=0.01, bootstrap_replicates=100),
        tmp_path,
    )
    assert resumed_with_larger_budget["completed_trials"] == 1
    assert resumed_with_larger_budget["configuration_sha256"] == completed["configuration_sha256"]
    loaded = load_energy_study(tmp_path / config.experiment_id)
    assert loaded["configuration_sha256"] == completed["configuration_sha256"]
    assert (
        json.loads((tmp_path / config.experiment_id / "summary.json").read_text())[
            "completed_trials"
        ]
        == 1
    )


def test_single_run_summary_reports_measured_energy_for_selected_amplitude(tmp_path: Path) -> None:
    from hf_tcm.studio.scientific import ScientificRunConfig, run_scientific_run

    config = ScientificRunConfig(
        run_id="amplitude-energy",
        frame_symbols=8,
        source_seed=29,
        channel_seed=31,
        channel_profile="awgn",
        noise_variance=0.25,
        amplitude=0.5,
        output_root=str(tmp_path),
    )
    result = run_scientific_run(config)

    assert result["energy"]["tx_energy_discrete"] == pytest.approx(8 * 8 * 0.5**2)
    assert result["energy"]["energy_per_information_bit_discrete"] == pytest.approx(1.0)
    assert result["energy"]["gamma_b_d_db"] == pytest.approx(10 * np.log10(1 / 0.25))
    assert result["energy"]["energy_relation_valid"] is True


def test_energy_study_http_launch_poll_and_saved_load() -> None:
    import time
    import urllib.request

    from hf_tcm.studio.server import make_server

    server = make_server("127.0.0.1", 0, default_view="scientific")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    address = f"http://127.0.0.1:{server.server_port}"
    study_id = f"gui-energy-http-{Path.cwd().name[:4]}-{id(server):x}"
    payload = {
        "experiment_id": study_id,
        "frame_symbols": 8,
        "gamma_grid_db": [0.0, 3.0],
        "trials_per_point": 1,
        "root_seed": 519,
        "target_ber": 0.05,
        "time_budget_seconds": 120,
        "sweep": "noise",
        "receiver_arms": ["joint", "b0"],
        "channel_profile": "identity",
        "noise_variance": 0.0,
        "amplitude": 1.0,
        "delays_samples": [0],
        "path_coefficients": [[1.0, 0.0]],
        "path_powers": [1.0],
        "rician_k_factors": [4.0],
        "los_phases_rad": [0.0],
        "fading_correlation": 0.98,
        "bootstrap_replicates": 100,
    }
    try:
        with urllib.request.urlopen(f"{address}/scientific") as response:
            page = response.read().decode("utf-8")
        assert 'data-view="energy"' in page
        assert "Енергетична ефективність" in page
        request = urllib.request.Request(
            f"{address}/api/scientific/energy-studies",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            job_id = json.load(response)["job_id"]
        for _ in range(500):
            with urllib.request.urlopen(f"{address}/api/scientific/jobs/{job_id}") as response:
                job = json.load(response)
            if job["status"] in {"completed", "incomplete", "failed"}:
                break
            time.sleep(0.05)
        assert job["status"] == "completed", job
        with urllib.request.urlopen(
            f"{address}/api/scientific/energy-studies/{study_id}"
        ) as response:
            result = json.load(response)
        assert result["completed_trials"] == 2
        assert all(
            row["receiver_observation_hashes"]["joint"] == row["receiver_observation_hashes"]["b0"]
            for row in result["records"]
        )
        with urllib.request.urlopen(f"{address}/api/scientific/energy-studies") as response:
            studies = json.load(response)["studies"]
        assert any(row["experiment_id"] == study_id for row in studies)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
