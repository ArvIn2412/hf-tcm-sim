"""Single-frame REPRO-06C size check; no statistical study is performed."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from hf_tcm.repro.adaptive_multipath_config import (
    AdaptiveMultipathReceiverConfig,
    AdaptivePathConfig,
)
from hf_tcm.repro.adaptive_multipath_io import save_adaptive_result
from hf_tcm.repro.adaptive_multipath_plots import write_adaptive_receiver_plots
from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import transition_table
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=int, default=256)
    args = parser.parse_args()
    count = args.symbols
    tx_started = time.perf_counter()
    tx = run_transmitter(
        TransmitterConfig(source_mode="seeded_random", frame_symbols=count, seed=20261109)
    )
    channel_config = ChannelConfig(
        profile_id=f"repro06c_sizecheck_f{count}_rician_v1",
        paths=(
            ChannelPathConfig(0, 1.0, 4.0, 0.0),
            ChannelPathConfig(3, 0.25, 1.0, 0.7),
        ),
        fading_mode="rician_ar1",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=0.02,
        fading_seed=3002,
        noise_seed=4002,
        correlation=0.98,
        reveal_noise_variance=True,
    )
    channel = run_channel(tx, channel_config)
    observation = channel.receiver_observation
    receiver_config = AdaptiveMultipathReceiverConfig(
        expected_symbol_count=count,
        paths=(
            AdaptivePathConfig(0, average_power=1.0, k_factor=4.0, los_phase_rad=0.0),
            AdaptivePathConfig(3, average_power=0.25, k_factor=1.0, los_phase_rad=0.7),
        ),
        channel_mode="rician_ar1",
        observation_noise_variance=0.02,
        correlation=0.98,
        decoder_mode="finite_depth",
        traceback_depth=20,
        profile_id=f"repro06c_sizecheck_f{count}_eta20_v1",
    )
    result = run_adaptive_multipath_receiver(observation, receiver_config)
    separate = run_separate_receiver(
        observation,
        SeparateReceiverConfig(
            expected_symbol_count=count,
            decoder_mode="finite_depth",
            traceback_depth=20,
            trace_output_mode="compact",
        ),
    )
    evaluation = evaluate_separate_receiver(separate, tx.information_bits, tx.phase_indices)
    phase_by_edge = {
        edge_id: 4 * coded[0] + 2 * coded[1] + coded[2]
        for edge_id, _state, _pair, coded, _target in transition_table()
    }
    decoded_phases = np.asarray(
        [phase_by_edge[int(edge)] for edge in result.decoded_edge_ids], dtype=np.int8
    )
    adaptive_symbol_errors = int(np.count_nonzero(decoded_phases != tx.phase_indices))
    output = Path(f"outputs/repro06c/reference_f{count}")
    files = save_adaptive_result(result, output)
    plots = write_adaptive_receiver_plots(result, observation.received_samples, output / "plots")
    numeric_bytes = sum(
        array.nbytes
        for array in (
            result.branch_metric_rows,
            result.estimator_mean_by_symbol_node,
            result.estimator_covariance_diag_by_symbol_node,
            result.decoded_information_bits,
        )
    )
    summary = {
        "symbols": count,
        "transmit_samples": int(tx.tx_samples.size),
        "receive_samples": int(observation.received_samples.size),
        "tail_samples": int(len(observation.received_samples) - len(tx.tx_samples)),
        "observation_sha256": observation.sha256,
        "separate_observation_sha256": separate.observation_sha256,
        "adaptive_result_sha256": result.result_sha256,
        "adaptive_elapsed_seconds": result.diagnostics["elapsed_seconds"],
        "adaptive_bit_errors_evaluation_only": int(
            np.count_nonzero(result.decoded_information_bits != tx.information_bits)
        ),
        "adaptive_ser_errors_evaluation_only": adaptive_symbol_errors,
        "adaptive_ser_evaluation_only": adaptive_symbol_errors / len(tx.phase_indices),
        "separate_ber_evaluation_only": evaluation.ber,
        "separate_ser_evaluation_only": evaluation.ser,
        "eta": result.traceback_depth,
        "survivor_buffer_rows": result.survivor_buffer_max_rows,
        "array_nbytes_subset": numeric_bytes,
        "run_seconds_including_transmitter_channel": time.perf_counter() - tx_started,
        "result_files": {name: digest for name, digest in files.items() if name != "manifest.json"},
        "plots": [path.name for path in plots],
        "paper_exact": False,
        "receiver_enabled": False,
    }
    size_summary_path = output / "paired_size_summary.json"
    size_summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][size_summary_path.name] = hashlib.sha256(
        size_summary_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
