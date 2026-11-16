"""CLI for resumable REPRO-07 paired receiver experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Sequence

from hf_tcm.repro.paired_experiment import (
    ExperimentConfig,
    run_paired_experiment,
    verify_experiment,
)
from hf_tcm.repro.paired_experiment_plots import (
    write_experiment_plots,
    write_selected_trial_plots,
)


def _load_config(path: Path) -> ExperimentConfig:
    try:
        return ExperimentConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read experiment config: {path}") from exc


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run paired REPRO-07 receiver experiments")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="override output root from config")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)
    config = _load_config(args.config)
    if args.output:
        values = config.to_dict()
        values["output_dir"] = str(args.output)
        config = ExperimentConfig.from_dict(values)
    total = len(config.noise_variances) * config.trials_per_point
    print(
        json.dumps(
            {
                "experiment_id": config.experiment_id,
                "config_sha256": hashlib.sha256(
                    json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ).hexdigest(),
                "planned_trials": total,
                "planned_receiver_pair_frames": total,
                "frame_symbols": config.frame_symbols,
                "noise_variances_complex_per_sample": config.noise_variances,
                "decoder_mode": config.decoder_mode,
                "traceback_depth": config.traceback_depth,
                "snr_convention": config.snr_convention,
                "estimated_upper_input_samples": total * config.frame_symbols * 8,
                "output_dir": str(Path(config.output_dir) / config.experiment_id),
            },
            indent=2,
        )
    )
    if args.validate_only:
        return 0
    summary = run_paired_experiment(config)
    root = Path(config.output_dir) / config.experiment_id
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in root.glob("point_*/trial_*/trial.json")
    ]
    plot_paths = write_experiment_plots(summary, records, root / "plots")
    selected_plot_paths = []
    for record_path in root.glob("point_*/trial_*/trial.json"):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("diagnostics_sha256"):
            selected_plot_paths.extend(
                write_selected_trial_plots(
                    record_path.parent,
                    root / "plots" / record_path.parent.parent.name / record_path.parent.name,
                )
            )
    summary["plot_files"] = [
        path.relative_to(root).as_posix() for path in (*plot_paths, *selected_plot_paths)
    ]
    summary["output_payload_bytes_excluding_summary_and_manifest"] = sum(
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file()
        and path.name not in {"summary.json", "manifest.json"}
        and not path.name.endswith(".tmp")
    )
    summary_path = root / "summary.json"
    _atomic_write(
        summary_path,
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    manifest_files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json" and not path.name.endswith(".tmp")
    }
    _atomic_write(
        root / "manifest.json",
        (
            json.dumps(
                {"schema_version": "repro07-manifest-v1", "files": manifest_files},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )
    verify_experiment(root)
    if args.print_summary:
        print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"status={summary['status']} completed={summary['completed_trials']}/{summary['planned_trials']}"
    )
    return 0 if summary["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
