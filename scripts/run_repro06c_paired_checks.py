"""Run a small, explicitly non-Monte-Carlo REPRO-06C paired integration set."""

from __future__ import annotations

import json
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
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_receiver_config import MultipathPathConfig, MultipathReceiverConfig
from hf_tcm.repro.receiver_config import SeparateReceiverConfig
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter

ROOT = Path("outputs/repro06c/paired_checks_f32")
N = 32


def _channel(
    name: str,
    paths: tuple[ChannelPathConfig, ...],
    fading: str,
    noise: float,
    rho: float = 0.0,
) -> ChannelConfig:
    return ChannelConfig(
        profile_id=f"repro06c_{name}_single_frame_control",
        paths=paths,
        fading_mode=fading,  # type: ignore[arg-type]
        noise_model="none" if noise == 0 else "complex_awgn_sample_domain",
        noise_complex_variance=noise,
        fading_seed=7001,
        noise_seed=8001,
        correlation=rho,
        reveal_noise_variance=True,
    )


def main() -> None:
    bits = ("00110110" * 8)[: 2 * N]
    tx = run_transmitter(TransmitterConfig(source_mode="manual", frame_symbols=N, manual_bits=bits))
    scenarios = {
        "identity": (
            _channel(
                "identity",
                (ChannelPathConfig(0, 1.0, 0, constant_coefficient=1 + 0j),),
                "constant",
                0,
            ),
            "unknown_static",
            1.0,
        ),
        "known_static_two_path": (
            _channel(
                "known_static_two_path",
                (
                    ChannelPathConfig(0, 1.0, 0, constant_coefficient=1 + 0j),
                    ChannelPathConfig(3, 0.1, 0, constant_coefficient=0.3 + 0.1j),
                ),
                "constant",
                0,
            ),
            "known_static_public",
            1.0,
        ),
        "unknown_static_two_path": (
            _channel(
                "unknown_static_two_path",
                (
                    ChannelPathConfig(0, 0.82, 0, constant_coefficient=0.9 + 0.1j),
                    ChannelPathConfig(3, 0.1325, 0, constant_coefficient=0.35 - 0.1j),
                ),
                "constant",
                0.005,
            ),
            "unknown_static",
            1.0,
        ),
        "slow_fading_two_path": (
            _channel(
                "slow_fading_two_path",
                (ChannelPathConfig(0, 1.0, 4, 0.1), ChannelPathConfig(3, 0.2, 2, -0.4)),
                "rician_ar1",
                0.01,
                0.995,
            ),
            "slow_fading_rician_ar1",
            0.995,
        ),
        "rician_ar1_two_path_awgn": (
            _channel(
                "rician_ar1_two_path_awgn",
                (ChannelPathConfig(0, 1.0, 4, 0.1), ChannelPathConfig(3, 0.2, 2, -0.4)),
                "rician_ar1",
                0.02,
                0.85,
            ),
            "rician_ar1",
            0.85,
        ),
    }
    records = {}
    for name, (channel_config, mode, rho) in scenarios.items():
        channel = run_channel(tx, channel_config)
        observation = channel.receiver_observation
        if mode == "known_static_public":
            paths = ()
        elif mode == "unknown_static":
            paths = tuple(
                AdaptivePathConfig(
                    p.delay_samples,
                    prior_mean=complex(1.0 if path_index == 0 else 0.5, 0.0),
                    prior_variance=0.5,
                )
                for path_index, p in enumerate(channel_config.paths)
            )
        elif mode != "known_static_public":
            paths = tuple(
                AdaptivePathConfig(
                    p.delay_samples,
                    average_power=p.average_power,
                    k_factor=p.k_factor,
                    los_phase_rad=p.los_phase_rad,
                )
                for p in channel_config.paths
            )
        if mode == "known_static_public":
            known_config = MultipathReceiverConfig(
                expected_symbol_count=N,
                paths=tuple(
                    MultipathPathConfig(p.delay_samples, p.constant_coefficient or 0j)
                    for p in channel_config.paths
                ),
                decoder_mode="finite_depth",
                traceback_depth=20,
                trace_output_mode="compact",
            )
            known_result = run_multipath_joint_receiver(observation, known_config)
            known_eval = evaluate_multipath_receiver(
                known_result, tx.information_bits, tx.phase_indices
            )
        else:
            adaptive_config = AdaptiveMultipathReceiverConfig(
                expected_symbol_count=N,
                paths=paths,
                channel_mode=mode,  # type: ignore[arg-type]
                observation_noise_variance=channel_config.noise_complex_variance,
                correlation=rho,
                decoder_mode="finite_depth",
                traceback_depth=20,
                profile_id=f"repro06c_{name}_eta20_v1",
            )
            adaptive = run_adaptive_multipath_receiver(observation, adaptive_config)
        separate = run_separate_receiver(
            observation,
            SeparateReceiverConfig(
                expected_symbol_count=N,
                decoder_mode="finite_depth",
                traceback_depth=20,
                trace_output_mode="compact",
            ),
        )
        eval_sep = evaluate_separate_receiver(separate, tx.information_bits, tx.phase_indices)
        if mode == "known_static_public":
            records[name] = {
                "observation_sha256": observation.sha256,
                "known_static_06b_bit_errors_evaluation_only": known_eval.bit_errors,
                "known_static_06b_ber_evaluation_only": known_eval.ber,
                "separate_observation_sha256": separate.observation_sha256,
                "separate_bit_errors_evaluation_only": eval_sep.bit_errors,
                "separate_ber_evaluation_only": eval_sep.ber,
                "separate_ser_evaluation_only": eval_sep.ser,
                "tail_samples": max(p.delay_samples for p in channel_config.paths),
                "profile_id": known_result.receiver_profile_id,
            }
            continue
        bit_errors = int(np.count_nonzero(adaptive.decoded_information_bits != tx.information_bits))
        phase_by_edge = {
            edge_id: 4 * coded[0] + 2 * coded[1] + coded[2]
            for edge_id, _state, _pair, coded, _target in transition_table()
        }
        decoded_phases = np.asarray(
            [phase_by_edge[int(edge)] for edge in adaptive.decoded_edge_ids], dtype=np.int8
        )
        symbol_errors = int(np.count_nonzero(decoded_phases != tx.phase_indices))
        result_dir = ROOT / name
        save_adaptive_result(adaptive, result_dir)
        plot_files = write_adaptive_receiver_plots(
            adaptive,
            observation.received_samples,
            result_dir / "plots",
            reference_bits=tx.information_bits,
            evaluation_coefficients=channel.evaluation_truth.coefficients,
            separate_decoded_bits=separate.decoded_information_bits,
        )
        records[name] = {
            "observation_sha256": observation.sha256,
            "adaptive_result_sha256": adaptive.result_sha256,
            "separate_observation_sha256": separate.observation_sha256,
            "adaptive_decoded_bits": int(adaptive.decoded_information_bits.size),
            "adaptive_bit_errors_evaluation_only": bit_errors,
            "adaptive_ber_evaluation_only": bit_errors / len(tx.information_bits),
            "adaptive_symbol_errors_evaluation_only": symbol_errors,
            "adaptive_ser_evaluation_only": symbol_errors / len(tx.phase_indices),
            "separate_bit_errors_evaluation_only": eval_sep.bit_errors,
            "separate_ber_evaluation_only": eval_sep.ber,
            "separate_ser_evaluation_only": eval_sep.ser,
            "tail_samples": max(
                channel_config_path.delay_samples for channel_config_path in channel_config.paths
            ),
            "trellis": [adaptive.trellis_state_count, adaptive.trellis_edge_count],
            "eta": adaptive.traceback_depth,
            "survivor_buffer_rows": adaptive.survivor_buffer_max_rows,
            "plot_files": [path.name for path in plot_files],
        }
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "paired_summary.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(records, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
