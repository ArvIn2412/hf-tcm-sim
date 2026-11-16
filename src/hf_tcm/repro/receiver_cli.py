"""Explicit REPRO-04 receiver CLI; no work is run on import."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_io import load_receiver_observation, save_separate_receiver_result
from hf_tcm.repro.receiver_plot_adapter import write_receiver_plots
from hf_tcm.repro.separate_receiver import run_separate_receiver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REPRO-04 separate hard 8PSK/Hamming receiver")
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--input", type=Path, help="directory containing receiver_observation.npz/json"
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/repro04/run"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--decoder-mode", choices=("full_frame", "finite_depth"))
    parser.add_argument("--traceback-depth", type=int, help="finite traceback transitions, e.g. 20")
    parser.add_argument("--trace-output-mode", choices=("compact", "full"))
    args = parser.parse_args(argv)
    if args.config is None or args.input is None:
        parser.print_help()
        return 0
    config = SeparateReceiverConfig.from_json(args.config.read_text(encoding="utf-8"))
    if (
        args.decoder_mode is not None
        or args.traceback_depth is not None
        or args.trace_output_mode is not None
    ):
        mode = args.decoder_mode or (
            "finite_depth" if args.traceback_depth is not None else config.decoder_mode
        )
        config = replace(
            config,
            decoder_mode=mode,
            traceback_depth=(
                args.traceback_depth if args.traceback_depth is not None else config.traceback_depth
            )
            if mode == "finite_depth"
            else None,
            trace_output_mode=args.trace_output_mode or config.trace_output_mode,
        )
    observation = load_receiver_observation(args.input)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "valid": True,
                    "observation_sha256": observation.sha256,
                    "config": config.to_dict(),
                },
                indent=2,
            )
        )
        return 0
    result = run_separate_receiver(observation, config)
    manifest = save_separate_receiver_result(result, args.output)
    plot_started = time.perf_counter()
    plot_files = write_receiver_plots(observation, result, args.output / "plots")
    plot_seconds = time.perf_counter() - plot_started
    output_file = args.output / "receiver_result.npz"
    performance = {
        **result.reproducibility_metadata,
        "plot_generation_seconds": plot_seconds,
        "receiver_result_file_bytes": output_file.stat().st_size,
        "plot_files": {
            path.name: {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
            for path in plot_files
        },
        "measurement_note": "one actual run; not a repeated performance benchmark",
    }
    performance_path = args.output / "performance.json"
    performance_path.write_text(
        json.dumps(performance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["files"].update(
        {f"plots/{path.name}": hashlib.sha256(path.read_bytes()).hexdigest() for path in plot_files}
    )
    manifest["files"]["performance.json"] = hashlib.sha256(
        performance_path.read_bytes()
    ).hexdigest()
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        "observation_sha256": result.observation_sha256,
        "output_arrays_sha256": result.reproducibility_metadata["output_arrays_sha256"],
        "output_manifest": manifest,
        "decoded_symbols": len(result.decoded_edge_ids),
        "decoded_information_bits": len(result.decoded_information_bits),
        "final_state": result.final_state,
        "path_metric": result.final_path_metric,
        "plots": [path.name for path in plot_files],
        "performance": performance,
        "receiver_enabled": False,
        "paper_exact": False,
    }
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
