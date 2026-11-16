"""Run one deterministic REPRO-06B static two-path integration validation."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

from hf_tcm.repro.channel_config import ChannelConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.channel_serialization import save_channel_result
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_plot_adapter import write_multipath_receiver_plots
from hf_tcm.repro.multipath_receiver_config import MultipathReceiverConfig
from hf_tcm.repro.multipath_receiver_io import save_multipath_receiver_result
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.receiver_io import save_separate_receiver_result
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "repro06b" / "reference_static_2path"
SIZES = (32, 256, 20_000)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _transmitter_config(frame_symbols: int) -> TransmitterConfig:
    return TransmitterConfig(
        source_mode="seeded_random",
        frame_symbols=frame_symbols,
        seed=60601,
        rng_algorithm="PCG64",
        initial_state=(0, 0),
        termination_policy="none",
        amplitude=1.0,
        phase_offset_rad=0.0,
        samples_per_symbol=8,
    )


def _channel_config() -> ChannelConfig:
    return ChannelConfig.from_json(
        (ROOT / "configs/repro06b/channel_static_2path.json").read_text(encoding="utf-8")
    )


def _receiver_config(frame_symbols: int, diagnostic_symbol: int) -> MultipathReceiverConfig:
    data = json.loads(
        (ROOT / "configs/repro06b/receiver_static_2path_eta20.json").read_text(encoding="utf-8")
    )
    data["expected_symbol_count"] = frame_symbols
    data["diagnostic_symbol_index"] = min(diagnostic_symbol, frame_symbols - 1)
    return MultipathReceiverConfig.from_dict(data)


def _separate_config(frame_symbols: int) -> SeparateReceiverConfig:
    data = json.loads(
        (ROOT / "configs/repro06b/separate_hamming_eta20.json").read_text(encoding="utf-8")
    )
    data["expected_symbol_count"] = frame_symbols
    return SeparateReceiverConfig.from_dict(data)


def _run_one(frame_symbols: int) -> dict[str, object]:
    run_root = OUTPUT / f"F{frame_symbols}"
    run_root.mkdir(parents=True, exist_ok=True)
    tx_config = _transmitter_config(frame_symbols)
    tx_started = time.perf_counter()
    transmitter = run_transmitter(tx_config)
    tx_seconds = time.perf_counter() - tx_started
    channel_started = time.perf_counter()
    channel = run_channel(transmitter, _channel_config())
    channel_seconds = time.perf_counter() - channel_started
    channel_dir = run_root / "channel"
    save_channel_result(channel, channel_dir)

    observation = channel.receiver_observation
    joint_config = _receiver_config(frame_symbols, frame_symbols // 2)
    joint_started = time.perf_counter()
    joint = run_multipath_joint_receiver(observation, joint_config)
    joint_seconds = time.perf_counter() - joint_started
    joint_evaluation = evaluate_multipath_receiver(
        joint,
        transmitter.information_bits,
        transmitter.phase_indices,
    )
    joint_dir = run_root / "joint_euclidean"
    save_multipath_receiver_result(joint, observation, joint_dir, evaluation=joint_evaluation)

    separate_config = _separate_config(frame_symbols)
    separate_started = time.perf_counter()
    separate = run_separate_receiver(observation, separate_config)
    separate_seconds = time.perf_counter() - separate_started
    if separate.observation_sha256 != joint.observation_sha256:
        raise RuntimeError("receiver arms were not given the same observation")
    separate_evaluation = evaluate_separate_receiver(
        separate,
        transmitter.information_bits,
        transmitter.phase_indices,
    )
    # Persist evaluation truth only after both receiver calls have completed.
    reference = {
        "information_bits": transmitter.information_bits.astype(int).tolist(),
        "phase_indices": transmitter.phase_indices.astype(int).tolist(),
        "scope": "evaluation-only; created from transmitter result after decoding",
    }
    _save_json(run_root / "evaluation_reference.json", reference)
    separate_dir = run_root / "paired_separate_hamming"
    save_separate_receiver_result(separate, separate_dir, evaluation=separate_evaluation)

    plot_started = time.perf_counter()
    plots = write_multipath_receiver_plots(
        observation,
        joint,
        joint_dir / "plots",
        evaluation=joint_evaluation,
        separate_result=separate,
        evaluation_truth=channel.evaluation_truth,
    )
    plot_seconds = time.perf_counter() - plot_started

    result = {
        "frame_symbols": frame_symbols,
        "information_bit_count": len(transmitter.information_bits),
        "transmitter_sample_count": len(transmitter.tx_samples),
        "received_sample_count": len(observation.received_samples),
        "tail_sample_indices": joint.diagnostics["tail_sample_indices"],
        "tail_samples_assigned_to_symbol": joint.diagnostics["tail_samples_assigned_to_symbol"],
        "observation_sha256": observation.sha256,
        "same_observation_for_both_receivers": (
            separate.observation_sha256 == joint.observation_sha256
        ),
        "expanded_state_count": joint.trellis_state_count,
        "expanded_edge_count": joint.trellis_edge_count,
        "joint_decoder_mode": joint.decoder_mode,
        "joint_traceback_depth": joint.traceback_depth,
        "joint_survivor_buffer_max_rows": joint.survivor_buffer_max_rows,
        "joint_evaluation_only": {
            "bit_errors": joint_evaluation.bit_errors,
            "ber": joint_evaluation.ber,
            "symbol_errors": joint_evaluation.symbol_errors,
            "ser": joint_evaluation.ser,
            "scope": joint_evaluation.evidence_scope,
        },
        "separate_evaluation_only": {
            "bit_errors": separate_evaluation.bit_errors,
            "ber": separate_evaluation.ber,
            "symbol_errors": separate_evaluation.symbol_errors,
            "ser": separate_evaluation.ser,
            "scope": separate_evaluation.evidence_scope,
        },
        "timings_seconds_single_run_not_benchmark": {
            "transmitter": tx_seconds,
            "channel": channel_seconds,
            "joint_receiver_total": joint_seconds,
            "joint_candidate_and_metric_matrix": joint.reproducibility_metadata[
                "branch_metric_seconds"
            ],
            "joint_diagnostic_prediction": joint.reproducibility_metadata[
                "diagnostic_prediction_seconds"
            ],
            "joint_viterbi": joint.reproducibility_metadata["expanded_viterbi_seconds"],
            "separate_receiver_total": separate_seconds,
            "plot_generation": plot_seconds,
        },
        "persistent_sizes_bytes": {
            "observation_npz": (channel_dir / "receiver_observation.npz").stat().st_size,
            "joint_npz": (joint_dir / "multipath_receiver_result.npz").stat().st_size,
            "separate_npz": (separate_dir / "receiver_result.npz").stat().st_size,
            "plots_total": sum(path.stat().st_size for path in plots),
        },
        "plot_sha256": {path.name: _sha(path) for path in plots},
        "channel_model": "project-defined known static two-path; delays [0,3], gains [(1,0),(0.35,0.15)], no noise",
        "scientific_scope": "single deterministic integration validation; not Monte Carlo or performance evidence",
    }
    _save_json(run_root / "run_summary.json", result)
    return result


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summaries = [_run_one(size) for size in SIZES]
    _save_json(
        OUTPUT / "summary.json",
        {
            "schema_version": "repro06b-reference-run-v1",
            "python": platform.python_version(),
            "numpy": np.__version__,
            "measurements": "single controlled run per frame size; not benchmarks",
            "source_alignment": "project-defined static known CSI; no article attribution",
            "runs": summaries,
            "paper_exact": False,
            "receiver_enabled": False,
            "adaptive_rician_multipath": "unavailable; survivor-specific estimator not verified",
        },
    )
    files = {
        path.relative_to(OUTPUT).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in OUTPUT.rglob("*")
        if path.is_file() and path != OUTPUT / "manifest.json"
    }
    _save_json(
        OUTPUT / "manifest.json",
        {
            "schema_version": "repro06b-reference-run-v1",
            "files": files,
            "file_count": len(files),
            "paper_exact": False,
            "receiver_enabled": False,
        },
    )
    for relative, entry in files.items():
        path = OUTPUT / relative
        if path.stat().st_size != entry["size_bytes"] or _sha(path) != entry["sha256"]:
            raise RuntimeError(f"run manifest verification failed: {relative}")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
