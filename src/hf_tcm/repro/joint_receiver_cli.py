"""Explicit CLI for running the isolated REPRO-05 joint receiver."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Sequence

import numpy as np

from hf_tcm.repro.joint_evaluation import (
    compare_joint_and_separate,
    evaluate_joint_receiver,
)
from hf_tcm.repro.joint_plot_adapter import (
    write_dual_receiver_comparison_plot,
    write_joint_receiver_plots,
)
from hf_tcm.repro.joint_receiver import run_joint_receiver
from hf_tcm.repro.joint_receiver_config import JointReceiverConfig
from hf_tcm.repro.joint_receiver_io import save_joint_receiver_result
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_io import load_receiver_observation, save_separate_receiver_result
from hf_tcm.repro.separate_receiver import run_separate_receiver


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _output_path(value: Path) -> Path:
    allowed = (_repo_root() / "outputs" / "repro05").resolve()
    resolved = value.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be inside outputs/repro05/") from exc
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the REPRO-05 joint Euclidean receiver")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--input", required=True, type=Path, help="REPRO-03 observation output directory"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--decoder-mode", choices=("full_frame", "finite_depth"))
    parser.add_argument("--traceback-depth", type=int, help="finite traceback transitions, e.g. 20")
    parser.add_argument("--trace-output-mode", choices=("compact", "full"))
    parser.add_argument("--reference", type=Path, help="optional evaluation-only reference JSON")
    parser.add_argument(
        "--separate-config",
        type=Path,
        help="optional REPRO-04 config for paired same-observation comparison",
    )
    args = parser.parse_args(argv)
    try:
        config = JointReceiverConfig.from_json(args.config.read_text(encoding="utf-8"))
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
                    args.traceback_depth
                    if args.traceback_depth is not None
                    else config.traceback_depth
                )
                if mode == "finite_depth"
                else None,
                trace_output_mode=args.trace_output_mode or config.trace_output_mode,
            )
        observation = load_receiver_observation(args.input)
        separate_config = (
            SeparateReceiverConfig.from_json(args.separate_config.read_text(encoding="utf-8"))
            if args.separate_config is not None
            else None
        )
        if args.validate_only:
            print("Configuration and receiver observation valid; receiver was not run.")
            return 0
        if args.output is None:
            parser.error("--output is required unless --validate-only is selected")
        output = _output_path(args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = run_joint_receiver(observation, config)
    manifest = save_joint_receiver_result(result, output)
    plot_started = time.perf_counter()
    plots = write_joint_receiver_plots(observation, result, output / "plots")
    plot_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in plots}
    separate_result = (
        run_separate_receiver(observation, separate_config) if separate_config is not None else None
    )
    separate_manifest = None
    if separate_result is not None:
        separate_manifest = save_separate_receiver_result(
            separate_result, output / "paired_separate_receiver"
        )
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["plot_sha256"] = plot_hashes
    if args.reference is not None:
        raw = args.reference.read_bytes()
        reference = json.loads(raw)
        if set(reference) != {"information_bits", "phase_indices"}:
            parser.error("reference JSON must contain information_bits and phase_indices only")
        evaluation = evaluate_joint_receiver(
            result,
            np.asarray(reference["information_bits"]),
            np.asarray(reference["phase_indices"]),
        )
        summary["evaluation_only"] = {
            "reference_sha256": hashlib.sha256(raw).hexdigest(),
            "bit_errors": evaluation.bit_errors,
            "ber": evaluation.ber,
            "symbol_errors": evaluation.symbol_errors,
            "ser": evaluation.ser,
            "evidence_scope": evaluation.evidence_scope,
        }
        if separate_result is not None:
            comparison = compare_joint_and_separate(
                result,
                separate_result,
                np.asarray(reference["information_bits"]),
                np.asarray(reference["phase_indices"]),
            )
            summary["paired_comparison_evaluation_only"] = {
                "observation_sha256": comparison.observation_sha256,
                "compared_information_bit_count": comparison.compared_information_bit_count,
                "joint_bit_errors": comparison.joint_bit_errors,
                "separate_bit_errors": comparison.separate_bit_errors,
                "joint_ber": comparison.joint_ber,
                "separate_ber": comparison.separate_ber,
                "joint_ser": comparison.joint_ser,
                "separate_ser": comparison.separate_ser,
                "evidence_scope": comparison.evidence_scope,
            }
            comparison_path = write_dual_receiver_comparison_plot(
                result, separate_result, output / "plots" / "joint_separate_comparison.svg"
            )
            plot_hashes[comparison_path.name] = hashlib.sha256(
                comparison_path.read_bytes()
            ).hexdigest()
            plot_hashes.update(
                {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in write_joint_receiver_plots(
                        observation,
                        result,
                        output / "plots",
                        evaluation=evaluation,
                    )
                }
            )
            separate_manifest_path = output / "paired_separate_receiver" / "manifest.json"
            separate_manifest_path.write_text(
                json.dumps(separate_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest["paired_separate_manifest_sha256"] = hashlib.sha256(
                separate_manifest_path.read_bytes()
            ).hexdigest()
    elif separate_result is not None:
        comparison_path = write_dual_receiver_comparison_plot(
            result, separate_result, output / "plots" / "joint_separate_comparison.svg"
        )
        plot_hashes[comparison_path.name] = hashlib.sha256(comparison_path.read_bytes()).hexdigest()
    summary["plot_generation_seconds"] = time.perf_counter() - plot_started
    summary["plot_sha256"] = plot_hashes
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["files"]["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    manifest["plot_sha256"] = plot_hashes
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for _ in range(3):
        exact_size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        if summary.get("output_directory_size_bytes") == exact_size:
            break
        summary["output_directory_size_bytes"] = exact_size
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest["files"]["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"Joint receiver result saved: {output}")
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
