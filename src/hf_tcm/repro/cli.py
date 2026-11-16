"""Command-line runner for transmitter-only REPRO artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Sequence

from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.plots import write_transmitter_plots
from hf_tcm.repro.serialization import save_transmitter_result
from hf_tcm.repro.transmitter import run_transmitter


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _allowed_output(path: Path) -> Path:
    root = _repository_root()
    allowed = (root / "outputs" / "repro02").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be inside the isolated outputs/repro02 directory") from exc
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hf_tcm.repro.transmitter",
        description="Build a transmitter-only REPRO-02 result; no channel or receiver is run.",
    )
    parser.add_argument("--config", help="path to strict JSON transmitter configuration")
    parser.add_argument("--output", help="new output directory inside outputs/repro02/")
    parser.add_argument(
        "--validate-only", action="store_true", help="validate config without a run"
    )
    parser.add_argument("--print-summary", action="store_true", help="print the run/config summary")
    args_list = list(argv) if argv is not None else None
    if args_list == [] or (args_list is None and not __import__("sys").argv[1:]):
        parser.print_help()
        return 0
    args = parser.parse_args(args_list)
    if not args.config:
        parser.error("--config is required")
    config_path = Path(args.config)
    try:
        config = TransmitterConfig.from_json(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.validate_only:
        if args.print_summary:
            print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
        print("Configuration valid; transmitter was not run.")
        return 0
    if not args.output:
        parser.error("--output is required unless --validate-only is selected")
    try:
        output = _allowed_output(Path(args.output))
    except ValueError as exc:
        parser.error(str(exc))
    started = time.perf_counter()
    result = run_transmitter(config)
    transmitter_seconds = time.perf_counter() - started
    manifest = save_transmitter_result(result, output)
    plot_started = time.perf_counter()
    plot_paths = write_transmitter_plots(result, output / "plots")
    plot_seconds = time.perf_counter() - plot_started
    plot_files = [
        {
            "file": str(Path(path).relative_to(output)),
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        }
        for path in plot_paths.values()
    ]
    performance = {
        "measurement": "single transmitter-only wall-clock run; not a statistical benchmark",
        "transmitter_seconds": transmitter_seconds,
        "plot_seconds": plot_seconds,
        "information_bit_count": len(result.information_bits),
        "encoded_step_count": len(result.coded_triples),
        "sample_count": len(result.tx_samples),
        "numeric_array_bytes": sum(
            int(getattr(result, name).nbytes)
            for name in (
                "information_bits",
                "payload_input_pairs",
                "input_pairs",
                "coded_triples",
                "pre_states",
                "post_states",
                "state_history",
                "edge_ids",
                "phase_indices",
                "phase_values_rad",
                "symbols",
                "symbol_i",
                "symbol_q",
                "symbol_energies",
                "tx_samples",
                "absolute_sample_index",
                "sample_symbol_index",
                "sample_local_index",
                "sample_tx_i",
                "sample_tx_q",
            )
        ),
    }
    (output / "performance.json").write_text(
        json.dumps(performance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest["plot_files"] = plot_files
    manifest["performance"] = performance
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    print(f"Transmitter result saved: {output}")
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0
