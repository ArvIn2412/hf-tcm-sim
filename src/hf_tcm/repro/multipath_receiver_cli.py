"""Explicit CLI for the REPRO-06B static-known ISI-aware receiver."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import replace
from pathlib import Path
from typing import Sequence

import numpy as np

from hf_tcm.repro.channel_result import EvaluationTruth, readonly
from hf_tcm.repro.joint_receiver_cli import _repo_root
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_plot_adapter import write_multipath_receiver_plots
from hf_tcm.repro.multipath_receiver_config import MultipathReceiverConfig
from hf_tcm.repro.multipath_receiver_io import save_multipath_receiver_result
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.receiver_io import (
    load_receiver_observation,
    save_separate_receiver_result,
)
from hf_tcm.repro.separate_receiver import run_separate_receiver


def _output_path(value: Path) -> Path:
    allowed = (_repo_root() / "outputs" / "repro06b").resolve()
    resolved = value.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be inside outputs/repro06b/") from exc
    return resolved


def _load_evaluation_truth(directory: Path) -> EvaluationTruth:
    """Load an optional truth sidecar only for post-decode visualization."""
    config = json.loads((directory / "channel_config.json").read_text(encoding="utf-8"))
    with np.load(directory / "evaluation_truth.npz", allow_pickle=False) as archive:
        arrays = {name: np.array(archive[name], copy=True) for name in archive.files}
    required = {
        "transmitter_samples",
        "transmitter_information_bits",
        "transmitter_symbols",
        "source_sample_indices",
        "coefficients",
        "path_contributions",
        "faded_signal",
        "noise_samples",
    }
    if set(arrays) != required:
        raise ValueError("evaluation truth NPZ has missing or unexpected arrays")
    paths = config["paths"]
    return EvaluationTruth(
        transmitter_samples=readonly(arrays["transmitter_samples"]),
        transmitter_information_bits=readonly(arrays["transmitter_information_bits"]),
        transmitter_symbols=readonly(arrays["transmitter_symbols"]),
        path_delays_samples=tuple(int(row["delay_samples"]) for row in paths),
        path_average_powers=tuple(float(row["average_power"]) for row in paths),
        path_k_factors=tuple(float(row["k_factor"]) for row in paths),
        path_los_phases_rad=tuple(float(row["los_phase_rad"]) for row in paths),
        source_sample_indices=readonly(arrays["source_sample_indices"]),
        coefficients=readonly(arrays["coefficients"]),
        path_contributions=readonly(arrays["path_contributions"]),
        faded_signal=readonly(arrays["faded_signal"]),
        noise_samples=readonly(arrays["noise_samples"]),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a static-known ISI-aware Encoder A Euclidean receiver"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path, help="REPRO-03 observation bundle")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--decoder-mode", choices=("full_frame", "finite_depth"))
    parser.add_argument("--traceback-depth", type=int)
    parser.add_argument("--metric-profile", choices=("euclidean", "squared_euclidean"))
    parser.add_argument("--reference", type=Path, help="evaluation-only bits/phase JSON")
    parser.add_argument("--separate-config", type=Path, help="optional paired REPRO-04 config")
    parser.add_argument(
        "--evaluation-truth-dir",
        type=Path,
        help="optional REPRO-03 truth bundle, loaded only after receiver decoding for plots",
    )
    args = parser.parse_args(argv)
    try:
        config = MultipathReceiverConfig.from_json(args.config.read_text(encoding="utf-8"))
        changes = {}
        if args.decoder_mode is not None:
            changes["decoder_mode"] = args.decoder_mode
            if args.decoder_mode == "full_frame":
                changes["traceback_depth"] = None
        if args.traceback_depth is not None:
            changes["decoder_mode"] = "finite_depth"
            changes["traceback_depth"] = args.traceback_depth
        if args.metric_profile is not None:
            changes["metric_profile"] = args.metric_profile
        if changes:
            config = replace(config, **changes)
        observation = load_receiver_observation(args.input)
        separate_config = (
            SeparateReceiverConfig.from_json(args.separate_config.read_text(encoding="utf-8"))
            if args.separate_config is not None
            else None
        )
        if args.validate_only:
            print("Configuration and public observation valid; receiver was not run.")
            return 0
        if args.output is None:
            parser.error("--output is required unless --validate-only is selected")
        output = _output_path(args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    result = run_multipath_joint_receiver(observation, config)
    reference = None
    evaluation = None
    if args.reference is not None:
        raw = args.reference.read_bytes()
        reference = json.loads(raw)
        if set(reference) != {"information_bits", "phase_indices"}:
            parser.error("reference JSON must contain information_bits and phase_indices only")
        evaluation = evaluate_multipath_receiver(
            result,
            np.asarray(reference["information_bits"], dtype=np.int8),
            np.asarray(reference["phase_indices"], dtype=np.int8),
        )
    save_multipath_receiver_result(result, observation, output, evaluation=evaluation)

    separate_result = separate_evaluation = None
    if separate_config is not None:
        separate_result = run_separate_receiver(observation, separate_config)
        if separate_result.observation_sha256 != result.observation_sha256:
            raise RuntimeError("receiver arms did not consume the same observation")
        if reference is not None:
            separate_evaluation = evaluate_separate_receiver(
                separate_result,
                np.asarray(reference["information_bits"], dtype=np.int8),
                np.asarray(reference["phase_indices"], dtype=np.int8),
            )
        save_separate_receiver_result(
            separate_result,
            output / "paired_separate_hamming",
            evaluation=separate_evaluation,
        )
    truth = _load_evaluation_truth(args.evaluation_truth_dir) if args.evaluation_truth_dir else None
    plots = write_multipath_receiver_plots(
        observation,
        result,
        output / "plots",
        evaluation=evaluation,
        separate_result=separate_result,
        evaluation_truth=truth,
    )
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["plot_sha256"] = {
        path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in plots
    }
    if args.reference is not None:
        summary["evaluation_reference_sha256"] = hashlib.sha256(
            args.reference.read_bytes()
        ).hexdigest()
    if separate_result is not None:
        summary["paired_separate"] = {
            "observation_sha256": separate_result.observation_sha256,
            "same_observation": separate_result.observation_sha256 == result.observation_sha256,
            "evaluation_only": (
                {
                    "bit_errors": separate_evaluation.bit_errors,
                    "ber": separate_evaluation.ber,
                    "symbol_errors": separate_evaluation.symbol_errors,
                    "ser": separate_evaluation.ser,
                    "evidence_scope": separate_evaluation.evidence_scope,
                }
                if separate_evaluation is not None
                else None
            ),
        }
    summary["environment"] = {"python": platform.python_version(), "numpy": np.__version__}
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        file.relative_to(output).as_posix(): {
            "size_bytes": file.stat().st_size,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        for file in output.rglob("*")
        if file.is_file() and file.name != "manifest.json"
    }
    manifest["plot_sha256"] = summary["plot_sha256"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"REPRO-06B receiver output saved: {output}")
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
