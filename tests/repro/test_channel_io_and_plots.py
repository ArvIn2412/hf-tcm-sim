from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from hf_tcm.repro.channel_cli import _output, main
from hf_tcm.repro.channel_config import ChannelConfig
from hf_tcm.repro.channel_io import load_transmitter_result
from hf_tcm.repro.channel_plot_adapter import write_channel_plots
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.channel_serialization import save_channel_result

ROOT = Path(__file__).resolve().parents[2]
TX_REFERENCE = ROOT / "outputs" / "repro02" / "reference_n_star"


def test_saved_repro02_reference_frame_loads_with_verified_arrays() -> None:
    result = load_transmitter_result(TX_REFERENCE)
    assert len(result.information_bits) == 40_000
    assert len(result.coded_triples) == 20_000
    assert len(result.tx_samples) == 160_000
    assert result.paper_exact is False and result.receiver_enabled is False


def test_channel_serialization_separates_receiver_and_truth() -> None:
    tx = load_transmitter_result(TX_REFERENCE)
    config = ChannelConfig.from_json((ROOT / "configs/repro03/identity.json").read_text())
    result = run_channel(tx, config)
    output = ROOT / "outputs/repro03/.test-serialization"
    manifest = save_channel_result(result, output)
    with np.load(output / "receiver_observation.npz", allow_pickle=False) as observation:
        assert set(observation.files) == {
            "received_samples",
            "absolute_sample_index",
            "sample_symbol_index",
            "sample_local_index",
        }
        np.testing.assert_array_equal(observation["received_samples"], tx.tx_samples)
    with np.load(output / "evaluation_truth.npz", allow_pickle=False) as truth:
        assert {"coefficients", "noise_samples", "transmitter_information_bits"} <= set(truth.files)
    public_json = json.loads((output / "receiver_observation.json").read_text())
    assert "coefficients" not in json.dumps(public_json)
    assert public_json["receiver_observation_sha256"] == result.receiver_observation.sha256
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected


def test_reference_frame_channel_output_length_and_identity() -> None:
    tx = load_transmitter_result(TX_REFERENCE)
    config = ChannelConfig.from_json((ROOT / "configs/repro03/identity.json").read_text())
    result = run_channel(tx, config)
    assert len(result.receiver_observation.received_samples) == 160_000
    np.testing.assert_array_equal(result.receiver_observation.received_samples, tx.tx_samples)
    assert result.array_storage_bytes < 24_000_000


def test_channel_plot_adapter_writes_sixteen_actual_svg_files() -> None:
    tx = load_transmitter_result(TX_REFERENCE)
    config = ChannelConfig.from_json(
        (ROOT / "configs/repro03/multipath_rician_awgn.json").read_text()
    )
    result = run_channel(tx, config)
    output = ROOT / "outputs/repro03/.test-plots"
    paths = write_channel_plots(result, output, selected_symbol=9_999)
    assert len(paths) == 16
    for path in paths.values():
        root = ET.parse(path).getroot()
        assert root.tag.endswith("svg")
        assert "symbol" in path.name or "received" in path.name or root.attrib.get("viewBox")
    assert "20" in (output / "15_sliding_20_symbol_window.svg").read_text(encoding="utf-8")


def test_cli_validate_only_and_output_namespace(capsys) -> None:
    config = ROOT / "configs/repro03/multipath_rician_awgn.json"
    assert main(["--config", str(config), "--validate-only", "--print-summary"]) == 0
    assert "Configuration valid" in capsys.readouterr().out
    try:
        _output(ROOT / "outputs" / "outside")
    except ValueError as exc:
        assert "outputs/repro03" in str(exc)
    else:
        raise AssertionError("channel CLI must reject output outside outputs/repro03")


def test_channel_cli_executes_channel_only_and_writes_complete_manifest(capsys) -> None:
    output = ROOT / "outputs/repro03/.test-cli-identity"
    config = ROOT / "configs/repro03/identity.json"
    assert (
        main(
            [
                "--config",
                str(config),
                "--transmitter-dir",
                str(TX_REFERENCE),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "Channel result saved" in capsys.readouterr().out
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    assert len(manifest["plot_files"]) == 16
    assert manifest["reproducibility"]["transmitter_samples_sha256"]
    assert manifest["reproducibility"]["transmitter_information_bits_sha256"]
    assert (
        manifest["receiver_observation_sha256"]
        == json.loads((output / "summary.json").read_text(encoding="utf-8"))[
            "receiver_observation_sha256"
        ]
    )


def test_channel_cli_can_form_a_transmitter_from_its_config(capsys) -> None:
    output = ROOT / "outputs/repro03/.test-cli-generated"
    assert (
        main(
            [
                "--config",
                str(ROOT / "configs/repro03/identity.json"),
                "--transmitter-config",
                str(ROOT / "configs/repro02/deterministic_example.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["sample_count"] == summary["transmitter_sample_count"]
    assert summary["sample_count"] > 0
