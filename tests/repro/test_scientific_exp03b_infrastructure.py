from __future__ import annotations

import os
from pathlib import Path

import pytest

from hf_tcm.repro import energy_experiment, exp03b_runner
from hf_tcm.repro.atomic_io import atomic_replace_bytes
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.confirmatory_exp03b import (
    build_metric_trial_spec,
    build_system_trial_spec,
    derive_metric_stream_seeds,
    derive_system_stream_seeds,
    system_trial_seeds,
    validate_frozen_protocol,
)
from hf_tcm.repro.energy_experiment import EnergyTrialSpec, run_energy_trial
from hf_tcm.repro.exp03b_runner import (
    persist_metric_trial,
    run_metric_series,
    verify_metric_records,
)
from hf_tcm.repro.metric_experiment import MetricTrialSpec, run_metric_trial


def test_metric_seed_streams_are_deterministic_and_domain_separated() -> None:
    first = derive_metric_stream_seeds(831101, 1, 2, 3)
    replay = derive_metric_stream_seeds(831101, 1, 2, 3)
    different_trial = derive_metric_stream_seeds(831101, 1, 2, 4)
    different_scenario = derive_metric_stream_seeds(831101, 2, 2, 3)

    assert first == replay
    assert len(set(first)) == 3
    assert first != different_trial
    assert first != different_scenario


def test_atomic_replace_retries_windows_permission_error(tmp_path: Path) -> None:
    destination = tmp_path / "progress.json"
    attempts = 0

    def intermittently_locked(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("simulated OneDrive sharing lock")
        os.replace(source, target)

    atomic_replace_bytes(
        destination, b'{"completed":1}', replace_fn=intermittently_locked, sleep_fn=lambda _: None
    )

    assert attempts == 3
    assert destination.read_bytes() == b'{"completed":1}'
    assert not list(tmp_path.glob("*.pending"))


def test_atomic_replace_does_not_hide_non_permission_errors(tmp_path: Path) -> None:
    destination = tmp_path / "checkpoint.json"

    def failed_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("disk failure")

    with pytest.raises(OSError, match="disk failure"):
        atomic_replace_bytes(
            destination, b"record", replace_fn=failed_replace, sleep_fn=lambda _: None
        )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.pending"))


def test_system_receiver_checkpoint_json_uses_retrying_atomic_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "record.json"
    original = os.replace
    attempts = 0

    def intermittently_locked(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("simulated OneDrive lock")
        original(source, target)

    monkeypatch.setattr(energy_experiment.os, "replace", intermittently_locked)
    energy_experiment.atomic_json(destination, {"status": "completed"})

    assert attempts == 2
    assert destination.read_text(encoding="utf-8") == '{"status":"completed"}'


def test_frozen_protocol_declares_complete_metric_and_system_grids() -> None:
    import json

    protocol = json.loads(
        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json").read_text(encoding="utf-8")
    )
    counts = validate_frozen_protocol(protocol)

    assert counts == {
        "metric_cells_per_sweep": 38,
        "metric_confirmatory_trials": 22800,
        "system_cells": 83,
        "system_confirmatory_trials": 8300,
    }


def test_metric_trials_pair_random_streams_across_sweep_methods() -> None:
    import json

    protocol = json.loads(
        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json").read_text(encoding="utf-8")
    )
    amplitude = build_metric_trial_spec(
        protocol, "static_pilot", "amplitude_fixed_noise", 2, 7, "confirmatory"
    )
    noise = build_metric_trial_spec(
        protocol, "static_pilot", "noise_fixed_amplitude", 2, 7, "confirmatory"
    )

    assert amplitude.source_seed == noise.source_seed
    assert amplitude.channel_config.fading_seed == noise.channel_config.fading_seed
    assert amplitude.channel_config.noise_seed == noise.channel_config.noise_seed
    assert amplitude.amplitude != noise.amplitude
    assert (
        amplitude.channel_config.noise_complex_variance
        != noise.channel_config.noise_complex_variance
    )
    assert amplitude.traceback_depth == noise.traceback_depth == 20


def test_protocol_rejects_changed_confirmatory_sample_size() -> None:
    import json

    protocol = json.loads(
        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json").read_text(encoding="utf-8")
    )
    protocol["metric_isolation"]["confirmatory_trials_per_point"] = 20

    with pytest.raises(ValueError, match="sample size"):
        validate_frozen_protocol(protocol)


def test_full_system_trial_builder_uses_separate_block_and_fresh_seed_domain() -> None:
    import json

    protocol = json.loads(
        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json").read_text(encoding="utf-8")
    )
    joint_b0 = build_system_trial_spec(protocol, "static", 4, 9, "confirmatory")
    rician = build_system_trial_spec(protocol, "rician", 2, 9, "confirmatory")

    assert joint_b0.scenario == "static"
    assert joint_b0.receiver_arms == ("joint", "b0", "b1")
    assert joint_b0.gamma_db == 2.0
    assert joint_b0.frame_symbols == 256
    assert rician.receiver_arms == ("joint", "b0")
    assert rician.seeds != joint_b0.seeds
    assert derive_system_stream_seeds(
        joint_b0.root_seed, "static", 4, 9
    ) == derive_metric_stream_seeds(832102, 12, 4, 9)
    assert tuple(joint_b0.seeds) != derive_system_stream_seeds(832102, "static", 4, 9)
    assert system_trial_seeds(joint_b0, "static") == derive_system_stream_seeds(
        832102, "static", 4, 9
    )


def test_confirmatory_metric_record_is_hash_verified_and_independently_recounted(
    tmp_path: Path,
) -> None:
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.05,
        fading_seed=12,
        noise_seed=13,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="exp03b-test-awgn",
            frame_symbols=20,
            source_seed=11,
            channel_config=channel,
            frontend_mode="awgn_direct_control",
        )
    )

    persist_metric_trial(
        tmp_path, result, {"protocol_sha256": "a" * 64, "trial_id": "exp03b-test-awgn"}
    )
    verification = verify_metric_records(tmp_path)

    assert verification["record_count"] == 1
    assert verification["paired_observations"] == 1
    assert verification["independent_count_replay"] == "PASS"


def test_confirmatory_metric_record_rejects_corrupt_array_payload(tmp_path: Path) -> None:
    channel = ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.05,
        fading_seed=12,
        noise_seed=13,
        reveal_noise_variance=True,
    )
    result = run_metric_trial(
        MetricTrialSpec(
            trial_id="exp03b-test-corrupt",
            frame_symbols=20,
            source_seed=11,
            channel_config=channel,
            frontend_mode="awgn_direct_control",
        )
    )
    record = persist_metric_trial(
        tmp_path, result, {"protocol_sha256": "b" * 64, "trial_id": "exp03b-test-corrupt"}
    )
    Path(tmp_path, "trials", record["array_file"]).write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="SHA-256"):
        verify_metric_records(tmp_path)


def test_preflight_metric_runner_checkpoints_and_resumes_without_duplicate_trials(
    tmp_path: Path,
) -> None:
    protocol = Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json")
    first = run_metric_series(
        protocol,
        tmp_path,
        scenario_key="awgn_direct",
        sweep="amplitude_fixed_noise",
        stage="preflight",
    )
    resumed = run_metric_series(
        protocol,
        tmp_path,
        scenario_key="awgn_direct",
        sweep="amplitude_fixed_noise",
        stage="preflight",
    )

    assert first["completed_trials"] == first["planned_trials"] == 10
    assert resumed["completed_trials"] == 10
    assert resumed["duplicate_trials_skipped"] == 10
    assert resumed["verification"]["record_count"] == 10


def test_full_system_records_preserve_raw_wall_and_process_cpu_times(tmp_path: Path) -> None:
    row = run_energy_trial(
        EnergyTrialSpec(
            phase="validation",
            scenario="awgn",
            sweep="amplitude",
            gamma_db=6.0,
            point_index=0,
            trial_index=0,
            frame_symbols=32,
            receiver_arms=("joint", "b0"),
        ),
        tmp_path,
        seed_override=(101, 102, 103),
    )

    assert row["raw_wall_elapsed_seconds"] == row["elapsed_seconds"]
    assert row["process_cpu_seconds"] > 0


def test_system_runner_passes_frozen_seed_domain_to_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[int, ...]] = []

    def fake_trial(spec, output_root, *, seed_override):
        captured.append(tuple(seed_override))
        record_dir = (
            Path(output_root)
            / spec.phase
            / spec.scenario
            / spec.sweep
            / f"p{spec.point_index:02d}"
            / f"t{spec.trial_index:04d}"
        )
        record_dir.mkdir(parents=True, exist_ok=True)
        observation = "a" * 64
        record = {
            "observation_sha256": observation,
            "receiver_observation_hashes": {"joint": observation, "b0": observation},
            "seeds": {
                "bits": seed_override[0],
                "fading": seed_override[1],
                "noise": seed_override[2],
            },
        }
        record_path = record_dir / "record.json"
        array_path = record_dir / "arrays.npz"
        record_path.write_text("{}", encoding="utf-8")
        array_path.write_bytes(b"test arrays")
        manifest = {
            "files": {
                "record.json": exp03b_runner.sha256_file(record_path),
                "arrays.npz": exp03b_runner.sha256_file(array_path),
            }
        }
        (record_dir / "manifest.json").write_text(
            __import__("json").dumps(manifest), encoding="utf-8"
        )
        return record

    class StopAfterFirstCompletedTrial:
        checks = 0

        def is_set(self):
            self.checks += 1
            return self.checks > 1

    monkeypatch.setattr(exp03b_runner, "run_energy_trial", fake_trial)
    monkeypatch.setattr(
        exp03b_runner,
        "verify_system_records",
        lambda _root: {"record_count": 1, "paired_observation_hashes": "PASS"},
    )
    summary = exp03b_runner.run_system_series(
        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"),
        tmp_path,
        scenario="static",
        stage="preflight",
        stop_event=StopAfterFirstCompletedTrial(),
    )

    expected = derive_system_stream_seeds(830097, "static", 0, 0)
    assert captured == [expected]
    assert summary["status"] == "incomplete"
    assert summary["completed_trials"] == 1
