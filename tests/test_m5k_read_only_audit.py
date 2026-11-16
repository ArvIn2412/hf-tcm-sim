from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import hf_tcm.evaluation.m5j_confirmatory_runner as runner
from hf_tcm.evaluation.error_metrics import ErrorCounts
from hf_tcm.evaluation.paired_cluster_bootstrap import PairedRunCounts, paired_cluster_bootstrap

ROOT = Path(__file__).resolve().parents[1]
M5J = ROOT / "outputs/m5j_confirmatory/20261029T-run"
M5H = ROOT / "outputs/m5h_independent_pilot"
M5F_RECORDS = ROOT / "outputs/m5f_paired_monte_carlo_records.json"
M5F_CONFIG = ROOT / "configs/m5f_paired_monte_carlo.json"
M5F_REPORT = ROOT / "docs/M5_PAIRED_MONTE_CARLO_REPORT.md"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _m5j_records() -> list[dict]:
    return [
        _json(path)
        for path in sorted((M5J / "checkpoints").glob("run-*.json"), key=lambda p: p.name)
    ]


def _paired_counts(records: list[dict]) -> list[PairedRunCounts]:
    def counts(record: dict, mode: str) -> ErrorCounts:
        value = record[f"{mode}_counts"]
        return ErrorCounts(
            bit_errors=value["bit_errors"],
            total_bits=value["total_bits"],
            symbol_errors=value["symbol_errors"],
            total_symbols=value["total_symbols"],
        )

    return [
        PairedRunCounts(
            run_id=record["run_id"],
            b_counts=counts(record, "b"),
            c_counts=counts(record, "c"),
        )
        for record in records
    ]


def _tree_sha256(root: Path) -> str:
    pairs = [
        f"{path.relative_to(root).as_posix()} {hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in sorted(path for path in root.rglob("*") if path.is_file())
    ]
    return hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()


def test_saved_checkpoint_counts_replay_without_receiver_or_new_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "_run_one", lambda *args, **kwargs: pytest.fail("receiver run"))
    monkeypatch.setattr(
        runner,
        "run_adaptive_estimator_diagnostic",
        lambda *args, **kwargs: pytest.fail("receiver/noise generation"),
    )
    records = _m5j_records()
    runs = _paired_counts(records)
    aggregate = paired_cluster_bootstrap(
        runs,
        bootstrap_replicates=2000,
        confidence_level=0.95,
        bootstrap_seed=3940591365597190145,
    ).point_estimates

    assert len(records) == len(runs) == 100
    assert len({record["run_id"] for record in records}) == 100
    assert aggregate.b_counts == ErrorCounts(1079, 51200, 1003, 25600)
    assert aggregate.c_counts == ErrorCounts(19793, 51200, 17956, 25600)
    assert aggregate.ber_b == pytest.approx(0.02107421875, abs=0.0)
    assert aggregate.ber_c == pytest.approx(0.38658203125, abs=0.0)
    assert aggregate.delta_ber == pytest.approx(0.3655078125, abs=1e-16)


def test_saved_count_bootstrap_reproduces_all_six_intervals() -> None:
    records = _m5j_records()
    runs = _paired_counts(records)
    first = paired_cluster_bootstrap(
        runs,
        bootstrap_replicates=2000,
        confidence_level=0.95,
        bootstrap_seed=3940591365597190145,
    )
    replay = paired_cluster_bootstrap(
        runs,
        bootstrap_replicates=2000,
        confidence_level=0.95,
        bootstrap_seed=3940591365597190145,
    )

    assert first.ordered_run_ids == tuple(record["run_id"] for record in records)
    assert first.ordered_run_ids == replay.ordered_run_ids
    assert first.resample_indices.shape == (2000, 100)
    assert first.resample_indices.tobytes() == replay.resample_indices.tobytes()
    assert first.replicate_estimates.tobytes() == replay.replicate_estimates.tobytes()
    expected = {
        "ber_b": (0.017265625, 0.02498193359375),
        "ber_c": (0.37710888671875, 0.395900390625),
        "delta_ber": (0.35548681640625, 0.37578173828125),
        "ser_b": (0.032734375, 0.045705078125),
        "ser_c": (0.6882421875, 0.7135244140625),
        "delta_ser": (0.6474599609375, 0.6771494140625),
    }
    for metric, bounds in expected.items():
        interval = first.interval(metric)
        assert interval.lower == pytest.approx(bounds[0], abs=2e-16)
        assert interval.upper == pytest.approx(bounds[1], abs=2e-16)
    assert first.warning_flags == ()
    assert first.quantile_method == "numpy.quantile(method='linear')"


def test_saved_run_ids_seed_provenance_and_receiver_input_boundary() -> None:
    records = _m5j_records()
    manifest = _json(ROOT / "configs/m5i_confirmatory_run_manifest_draft.json")
    planned = manifest["planned_runs"]

    assert [record["run_id"] for record in records] == [item["run_id"] for item in planned]
    assert len({record["received_sha256"] for record in records}) == 100
    for record, planned_run in zip(records, planned, strict=True):
        assert record["partition"] == "evaluation"
        assert record["seed_provenance"]["data"] == planned_run["data"]
        assert record["seed_provenance"]["noise"] == planned_run["noise"]
        assert record["status"] == "complete_valid_output"
        encoded_keys = json.dumps(record, sort_keys=True)
        for forbidden in (
            "reference_information_bits",
            "reference_bits",
            "ChannelTruth",
            "received_samples",
            "noise_samples",
        ):
            assert forbidden not in encoded_keys


def test_m5f_m5h_and_m5j_historical_outputs_keep_baseline_bytes() -> None:
    expected_files = {
        ROOT
        / "configs/m5j_confirmatory_approved_run.json": "8a9cb4c2d42a0b7014a40d5b83b9da13e7d1a65fe2fa3a68e1d90d5a53607840",
        ROOT
        / "configs/m5i_confirmatory_run_manifest_draft.json": "6b63e12f6463680af603944a43e576afa15e08b1b84155273fbbbc42c4fb5b15",
        M5F_RECORDS: "93d5993cbad256eaf4363118c4b3a44b01fb14da82ca9450520213eda4dfc2e6",
        M5F_CONFIG: "cca939a2ea1e0e8668f2197c709d3b210c0cf0fb735f1d15b2f9d6128f8cde8e",
        M5F_REPORT: "da8038f373aca4c43f24821d46b3d0dbda4b630878ffc266e17e8457a899f7c1",
    }
    for path, expected in expected_files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    assert _tree_sha256(M5H) == "81ccf68090c2e64a0ddc90b25033cd73e073cfaaa93c5522ccf6e02105d38dc7"
    assert _tree_sha256(ROOT / "outputs/m5j_confirmatory") == (
        "a14f2e59725d060d4114bc34f48c0d130e5be8716716b2f7efaa6e68585fa600"
    )


def test_m5j_stored_summary_matches_checkpoint_inventory_and_counts() -> None:
    summary = _json(M5J / "summary.json")
    verification = _json(M5J / "independent_verification.json")
    records = _m5j_records()

    assert summary["status"] == "complete"
    assert summary["planned_run_count"] == len(records) == 100
    assert summary["completed_valid_run_count"] == 100
    assert summary["failure_record_count"] == 0
    assert summary["not_completed_count"] == 0
    assert verification["run_count"] == 100
    assert verification["unique_run_ids"] == 100
    assert verification["unique_received_hashes"] == 100
    assert verification["paired_received_per_run"] is True
    assert verification["all_seed_provenance_matches_manifest"] is True
    assert verification["pooled_B_recomputed"]["bit_errors"] == 1079
    assert verification["pooled_C_recomputed"]["bit_errors"] == 19793
