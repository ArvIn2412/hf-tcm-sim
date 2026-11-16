from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from hf_tcm.repro.cli import main
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.plots import write_transmitter_plots
from hf_tcm.repro.transmitter import run_transmitter

ROOT = Path(__file__).parents[2]


def test_plot_adapter_writes_ten_real_data_svg_files_with_window_metadata() -> None:
    result = run_transmitter(
        TransmitterConfig.from_dict(
            {"source_mode": "pattern", "frame_symbols": 24, "pattern_id": "alternating"}
        )
    )
    output = ROOT / "outputs/repro02/.test-plots"
    plots = write_transmitter_plots(
        result, output, selected_symbol=12, window_symbols=20, window_start_symbol=4
    )
    assert len(plots) == 10
    assert {Path(path).name for path in plots.values()} == {
        "01_information_bits.svg",
        "02_coded_bits.svg",
        "03_encoder_states.svg",
        "04_trellis_edges.svg",
        "05_phase_indices.svg",
        "06_8psk_constellation.svg",
        "07_symbol_phase.svg",
        "08_tx_i.svg",
        "09_tx_q.svg",
        "10_tx_samples_zoh.svg",
    }
    svg = Path(plots["10_tx_samples_zoh.svg"]).read_text(encoding="utf-8")
    assert 'data-selected-symbol="12"' in svg
    assert 'data-window-samples="32:191"' in svg
    assert "Абсолютний індекс відліку" in svg
    assert "Канал" not in svg
    assert not any("BER" in Path(path).read_text(encoding="utf-8") for path in plots.values())
    index = json.loads((output / "plot_index.json").read_text(encoding="utf-8"))
    assert index["plot_count"] == 10
    assert index["window_start_symbol"] == 4
    assert index["absolute_sample_window_inclusive"] == [32, 191]
    for path in plots.values():
        Path(path).unlink()
    (output / "plot_index.json").unlink()


def test_cli_without_arguments_prints_help_and_does_not_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "--config" in output
    assert "no channel or receiver" in output


def test_cli_validate_only_parses_configuration_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = ROOT / "configs/repro02/minimal.json"
    assert main(["--config", str(config_path), "--validate-only", "--print-summary"]) == 0
    output = capsys.readouterr().out
    assert "Configuration valid" in output
    assert '"samples_per_symbol": 8' in output


def test_cli_runs_transmitter_and_writes_manifest_arrays_and_plots(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = ROOT / "configs/repro02/minimal.json"
    output = ROOT / "outputs/repro02/.test-cli"
    assert (
        main(
            [
                "--config",
                str(config_path),
                "--output",
                str(output),
                "--print-summary",
            ]
        )
        == 0
    )
    capsys.readouterr()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["sample_count"] == 32
    assert summary["paper_exact"] is False
    assert summary["receiver_enabled"] is False
    assert len(manifest["plot_files"]) == 10
    assert (output / "arrays.npz").is_file()
    assert (output / "performance.json").is_file()
    for path in (output / "plots").glob("*.svg"):
        path.unlink()
    (output / "plots/plot_index.json").unlink(missing_ok=True)
    for filename in (
        "arrays.npz",
        "input_config.json",
        "mapping_table.json",
        "summary.json",
        "manifest.json",
        "performance.json",
    ):
        (output / filename).unlink(missing_ok=True)


def test_cli_refuses_output_outside_repro02_namespace() -> None:
    config_path = ROOT / "configs/repro02/minimal.json"
    outside = ROOT / "outputs/M5/forbidden"
    with pytest.raises(SystemExit) as error:
        main(["--config", str(config_path), "--output", str(outside)])
    assert error.value.code == 2


def test_transmitter_package_does_not_import_channel_or_receiver_modules() -> None:
    package = ROOT / "src/hf_tcm/repro"
    # REPRO-03 adds channel modules to the namespace. Guard the REPRO-02
    # transmitter dependency closure instead of forbidding its sibling channel.
    transmitter_modules = (
        "__init__.py",
        "config.py",
        "encoder.py",
        "identifiers.py",
        "labeling.py",
        "modulator.py",
        "source_bits.py",
        "waveform.py",
        "transmitter.py",
        "serialization.py",
        "plots.py",
        "cli.py",
    )
    for name in transmitter_modules:
        source = package / name
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    ("hf_tcm.receiver", "hf_tcm.channels", "hf_tcm.decoding")
                )
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("hf_tcm.receiver", "hf_tcm.channels", "hf_tcm.decoding"))
                    for alias in node.names
                )
