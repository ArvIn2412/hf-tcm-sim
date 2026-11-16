"""Channel-only REPRO-03 CLI; default invocation never starts a simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Sequence

from hf_tcm.repro.channel_config import ChannelConfig
from hf_tcm.repro.channel_io import load_transmitter_result
from hf_tcm.repro.channel_plot_adapter import write_channel_plots
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.channel_serialization import save_channel_result
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.transmitter import run_transmitter


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _output(path: Path) -> Path:
    allowed = (_root() / "outputs" / "repro03").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be inside outputs/repro03/") from exc
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hf_tcm.repro.channel_cli",
        description="Run only the REPRO-03 channel; no receiver or BER/SER is invoked.",
    )
    parser.add_argument("--config", help="strict REPRO-03 JSON channel configuration")
    parser.add_argument("--transmitter-dir", help="verified saved REPRO-02 output directory")
    parser.add_argument("--transmitter-config", help="REPRO-02 config to form a transmitter result")
    parser.add_argument("--output", help="output directory under outputs/repro03/")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    args_list = list(argv) if argv is not None else None
    if args_list == [] or (args_list is None and not __import__("sys").argv[1:]):
        parser.print_help()
        return 0
    args = parser.parse_args(args_list)
    if not args.config:
        parser.error("--config is required")
    try:
        channel_config = ChannelConfig.from_json(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.validate_only:
        if args.print_summary:
            print(json.dumps(channel_config.to_dict(), ensure_ascii=False, indent=2))
        print("Configuration valid; channel was not run.")
        return 0
    if bool(args.transmitter_dir) == bool(args.transmitter_config):
        parser.error("provide exactly one of --transmitter-dir or --transmitter-config")
    if not args.output:
        parser.error("--output is required unless --validate-only is selected")
    try:
        output = _output(Path(args.output))
    except ValueError as exc:
        parser.error(str(exc))
    if args.transmitter_dir:
        try:
            transmitter = load_transmitter_result(args.transmitter_dir)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        tx_source = str(Path(args.transmitter_dir))
    else:
        try:
            tx_config = TransmitterConfig.from_json(
                Path(args.transmitter_config).read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        transmitter = run_transmitter(tx_config)
        tx_source = str(Path(args.transmitter_config))
    started = time.perf_counter()
    result = run_channel(transmitter, channel_config)
    channel_seconds = time.perf_counter() - started
    manifest = save_channel_result(result, output)
    plot_started = time.perf_counter()
    plot_paths = write_channel_plots(result, output / "plots")
    plot_seconds = time.perf_counter() - plot_started
    plot_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in plot_paths.values()
    }
    performance = {
        "measurement": "single channel-only wall-clock run; not a benchmark",
        "channel_seconds": channel_seconds,
        "plot_seconds": plot_seconds,
        "array_storage_bytes": result.array_storage_bytes,
        "input_sample_count": len(transmitter.tx_samples),
        "output_sample_count": len(result.receiver_observation.received_samples),
        "path_count": len(channel_config.paths),
        "note": "array storage is reported; NumPy native allocator peak RSS is not measured",
    }
    (output / "performance.json").write_text(
        json.dumps(performance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["transmitter_source"] = tx_source
    summary["performance"] = performance
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["plot_files"] = plot_hashes
    manifest["performance_sha256"] = hashlib.sha256(
        (output / "performance.json").read_bytes()
    ).hexdigest()
    manifest["transmitter_source"] = tx_source
    manifest["files"] = {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in (
            "channel_config.json",
            "receiver_observation.npz",
            "receiver_observation.json",
            "evaluation_truth.npz",
            "summary.json",
        )
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Channel result saved: {output}")
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
