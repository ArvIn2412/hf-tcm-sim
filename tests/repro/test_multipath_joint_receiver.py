from __future__ import annotations

import json
from itertools import product

import numpy as np
import pytest

from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.channel_serialization import save_channel_result
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.multipath_evaluation import evaluate_multipath_receiver
from hf_tcm.repro.multipath_joint_receiver import run_multipath_joint_receiver
from hf_tcm.repro.multipath_plot_adapter import write_multipath_receiver_plots
from hf_tcm.repro.multipath_receiver_cli import main as multipath_cli_main
from hf_tcm.repro.multipath_receiver_config import (
    MultipathPathConfig,
    MultipathReceiverConfig,
)
from hf_tcm.repro.multipath_receiver_io import (
    save_multipath_receiver_result,
    verify_multipath_receiver_manifest,
)
from hf_tcm.repro.receiver_config import ReceiverFrontEndConfig, SeparateReceiverConfig
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def _constant_channel(*gains: complex, delays: tuple[int, ...]) -> ChannelConfig:
    paths = tuple(
        ChannelPathConfig(
            delay_samples=delay,
            average_power=float(abs(gain) ** 2),
            k_factor=0.0,
            constant_coefficient=gain,
        )
        for delay, gain in zip(delays, gains, strict=True)
    )
    return ChannelConfig(
        profile_id="repro06b_static_test",
        paths=paths,
        fading_mode="constant",
        noise_model="none",
        noise_complex_variance=0.0,
        fading_seed=91,
        noise_seed=92,
    )


def _transmitter(bits: str, initial_state: tuple[int, int] = (0, 0)):
    return run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=len(bits) // 2,
            manual_bits=bits,
            initial_state=initial_state,
        )
    )


def _receiver_config(frame_symbols: int, gains: tuple[complex, ...], delays: tuple[int, ...], **kw):
    return MultipathReceiverConfig(
        expected_symbol_count=frame_symbols,
        paths=tuple(
            MultipathPathConfig(delay, gain) for delay, gain in zip(delays, gains, strict=True)
        ),
        **kw,
    )


def _reference_transmit(pairs: tuple[tuple[int, int], ...]) -> np.ndarray:
    """Small independent recurrence oracle: no REPRO production encoder calls."""
    state = (0, 0)
    symbols = []
    for u0, u1 in pairs:
        coded = (u0, u1 ^ state[1], state[0])
        phase = 4 * coded[0] + 2 * coded[1] + coded[2]
        symbols.append(np.exp(1j * phase * np.pi / 4.0))
        state = (u1, state[0])
    return np.repeat(np.asarray(symbols, dtype=np.complex128), 8)


def _reference_channel(tx: np.ndarray, gains: tuple[complex, ...], delays: tuple[int, ...]):
    received = np.zeros(len(tx) + max(delays), dtype=np.complex128)
    for n in range(len(received)):
        for gain, delay in zip(gains, delays, strict=True):
            source = n - delay
            if 0 <= source < len(tx):
                received[n] += gain * tx[source]
    return received


def _exhaustive_pairs(observed: np.ndarray, symbols: int, gains, delays):
    best = (float("inf"), None)
    pair_values = ((0, 0), (0, 1), (1, 0), (1, 1))
    for candidate in product(pair_values, repeat=symbols):
        tx = _reference_transmit(candidate)
        predicted = _reference_channel(tx, gains, delays)
        cost = float(np.vdot(observed - predicted, observed - predicted).real)
        if cost < best[0]:
            best = cost, candidate
    assert best[1] is not None
    return best


def test_identity_channel_recovers_payload_with_full_and_eta20_modes() -> None:
    tx = _transmitter("001101100011")
    channel = run_channel(tx, _constant_channel(1 + 0j, delays=(0,)))
    common = dict(expected_symbol_count=6, paths=(MultipathPathConfig(0, 1 + 0j),))
    full = run_multipath_joint_receiver(
        channel.receiver_observation, MultipathReceiverConfig(**common)
    )
    finite = run_multipath_joint_receiver(
        channel.receiver_observation,
        MultipathReceiverConfig(
            **common,
            decoder_mode="finite_depth",
            traceback_depth=20,
        ),
    )

    np.testing.assert_array_equal(full.decoded_information_bits, tx.information_bits)
    np.testing.assert_array_equal(finite.decoded_information_bits, tx.information_bits)
    assert full.trellis_state_count == 4
    assert full.trellis_edge_count == 16
    assert full.observation_sha256 == finite.observation_sha256
    np.testing.assert_array_equal(full.branch_metric_rows, finite.branch_metric_rows)


def test_static_d3_full_frame_matches_independent_exhaustive_waveform_search() -> None:
    bits = "00110110"
    gains = (1 + 0.2j, 0.4 - 0.15j)
    delays = (0, 3)
    transmitter = _transmitter(bits)
    channel = run_channel(transmitter, _constant_channel(*gains, delays=delays))
    config = _receiver_config(4, gains, delays)

    expected_cost, expected_pairs = _exhaustive_pairs(
        channel.receiver_observation.received_samples, 4, gains, delays
    )
    result = run_multipath_joint_receiver(channel.receiver_observation, config)

    assert result.trellis_state_count == 17
    assert result.trellis_edge_count == 68
    assert tuple(map(tuple, result.decoded_information_pairs.tolist())) == expected_pairs
    assert np.isclose(result.final_path_metric, expected_cost, atol=1e-12)
    assert result.sample_indices[-3:].tolist() == [32, 33, 34]
    assert len(result.sample_indices) == 35


def test_nonzero_initial_state_and_known_static_seeded_noise_are_deterministic() -> None:
    transmitter = _transmitter("011010011101", (1, 0))
    channel_config = ChannelConfig(
        profile_id="repro06b_static_awgn_test",
        paths=(
            ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),
            ChannelPathConfig(3, 0.05, 0.0, constant_coefficient=0.2 + 0.1j),
        ),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=1e-5,
        fading_seed=101,
        noise_seed=202,
    )
    first = run_channel(transmitter, channel_config)
    repeated = run_channel(transmitter, channel_config)
    config = _receiver_config(
        6,
        (1 + 0j, 0.2 + 0.1j),
        (0, 3),
        initial_state=(1, 0),
        decoder_mode="finite_depth",
        traceback_depth=20,
    )
    decoded_a = run_multipath_joint_receiver(first.receiver_observation, config)
    decoded_b = run_multipath_joint_receiver(repeated.receiver_observation, config)

    assert first.receiver_observation.sha256 == repeated.receiver_observation.sha256
    np.testing.assert_array_equal(decoded_a.branch_metric_rows, decoded_b.branch_metric_rows)
    np.testing.assert_array_equal(
        decoded_a.decoded_information_bits, decoded_b.decoded_information_bits
    )
    assert decoded_a.decisions[0].decision_available_at == 5
    assert decoded_a.decisions[-1].traceback_depth_used == 1


def test_eta20_latency_flush_and_output_has_one_decision_per_symbol() -> None:
    transmitter = _transmitter("01" * 24)
    channel = run_channel(transmitter, _constant_channel(1 + 0j, delays=(0,)))
    result = run_multipath_joint_receiver(
        channel.receiver_observation,
        MultipathReceiverConfig(
            expected_symbol_count=24,
            paths=(MultipathPathConfig(0, 1 + 0j),),
            decoder_mode="finite_depth",
            traceback_depth=20,
        ),
    )

    assert result.decisions[0].symbol_index == 0
    assert result.decisions[0].decision_available_at == 19
    assert result.decisions[0].traceback_depth_used == 20
    assert len(result.decisions) == 24
    assert [row.symbol_index for row in result.decisions] == list(range(24))
    assert result.survivor_buffer_max_rows == 20


def test_separate_hamming_can_consume_same_observation_without_truth() -> None:
    transmitter = _transmitter("00110110")
    gains = (1 + 0j, 0.3 + 0j)
    channel = run_channel(transmitter, _constant_channel(*gains, delays=(0, 3)))
    observation = channel.receiver_observation
    config = _receiver_config(4, gains, (0, 3))
    joint = run_multipath_joint_receiver(observation, config)
    separate = run_separate_receiver(
        observation,
        SeparateReceiverConfig(
            expected_symbol_count=4,
            front_end=ReceiverFrontEndConfig(mode="known_static_complex_gain"),
            decoder_mode="finite_depth",
            traceback_depth=20,
            trace_output_mode="compact",
        ),
    )

    assert joint.observation_sha256 == separate.observation_sha256 == observation.sha256
    assert "evaluation_truth" not in joint.__dataclass_fields__
    assert "transmitter_information_bits" not in joint.__dataclass_fields__
    assert len(separate.unprocessed_sample_indices) == 3


def test_channel_result_truth_object_is_rejected_by_receiver_api() -> None:
    transmitter = _transmitter("00110110")
    channel = run_channel(transmitter, _constant_channel(1 + 0j, delays=(0,)))
    config = _receiver_config(4, (1 + 0j,), (0,))

    with pytest.raises(TypeError, match="ReceiverObservation"):
        run_multipath_joint_receiver(channel, config)


def test_receiver_rejects_observation_with_missing_multipath_tail() -> None:
    transmitter = _transmitter("00110110")
    channel = run_channel(transmitter, _constant_channel(1 + 0j, 0.3 + 0j, delays=(0, 3)))
    truncated = channel.receiver_observation
    from dataclasses import replace

    short = replace(
        truncated,
        received_samples=truncated.received_samples[:-1],
        absolute_sample_index=truncated.absolute_sample_index[:-1],
        sample_symbol_index=truncated.sample_symbol_index[:-1],
        sample_local_index=truncated.sample_local_index[:-1],
    )
    with pytest.raises(ValueError, match="exactly 35"):
        run_multipath_joint_receiver(short, _receiver_config(4, (1 + 0j, 0.3 + 0j), (0, 3)))


def test_receiver_npz_json_manifest_round_trip_has_no_truth_arrays(tmp_path) -> None:
    tx = _transmitter("00110110")
    channel = run_channel(tx, _constant_channel(1 + 0j, 0.25 + 0.1j, delays=(0, 3)))
    result = run_multipath_joint_receiver(
        channel.receiver_observation,
        _receiver_config(4, (1 + 0j, 0.25 + 0.1j), (0, 3)),
    )
    manifest = save_multipath_receiver_result(result, channel.receiver_observation, tmp_path)
    integrity = verify_multipath_receiver_manifest(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert len(manifest["files"]) == 4
    assert integrity == {"verified": 4, "failed": 0}
    assert summary["diagnostics"]["decision_record_count"] == 4
    assert "decision_records" not in summary["diagnostics"]
    with np.load(tmp_path / "multipath_receiver_result.npz", allow_pickle=False) as arrays:
        assert "branch_metric_rows" in arrays.files
        assert "decision_available_at" in arrays.files
        assert "evaluation_truth" not in arrays.files
        assert "transmitter_information_bits" not in arrays.files


def test_actual_data_plot_adapter_writes_trellis_tail_and_truth_separated_charts(tmp_path) -> None:
    tx = _transmitter("00110110")
    gains = (1 + 0j, 0.25 + 0.1j)
    channel = run_channel(tx, _constant_channel(*gains, delays=(0, 3)))
    observation = channel.receiver_observation
    config = _receiver_config(4, gains, (0, 3), diagnostic_symbol_index=3)
    joint = run_multipath_joint_receiver(observation, config)
    separate = run_separate_receiver(
        observation,
        SeparateReceiverConfig(
            expected_symbol_count=4,
            decoder_mode="finite_depth",
            traceback_depth=20,
            trace_output_mode="compact",
        ),
    )
    evaluation = evaluate_multipath_receiver(joint, tx.information_bits, tx.phase_indices)
    paths = write_multipath_receiver_plots(
        observation,
        joint,
        tmp_path,
        evaluation=evaluation,
        separate_result=separate,
        evaluation_truth=channel.evaluation_truth,
    )

    assert len(paths) == 9
    assert all(path.is_file() and "<svg" in path.read_text(encoding="utf-8") for path in paths)
    assert (tmp_path / "07_path_contributions_evaluation_only.svg").is_file()
    assert (tmp_path / "08_bit_error_positions_evaluation_only.svg").is_file()


def test_cli_validate_only_checks_public_observation_without_running_receiver(tmp_path) -> None:
    tx = _transmitter("00110110")
    channel = run_channel(tx, _constant_channel(1 + 0j, delays=(0,)))
    input_dir = tmp_path / "channel"
    save_channel_result(channel, input_dir)
    config = _receiver_config(4, (1 + 0j,), (0,))
    config_path = tmp_path / "receiver.json"
    config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    output_dir = tmp_path / "must-not-be-created"

    assert (
        multipath_cli_main(
            [
                "--config",
                str(config_path),
                "--input",
                str(input_dir),
                "--output",
                str(output_dir),
                "--validate-only",
            ]
        )
        == 0
    )
    assert not output_dir.exists()
