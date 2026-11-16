from __future__ import annotations

from dataclasses import fields

import numpy as np
import pytest

from hf_tcm.repro.channel_config import (
    identity_profile,
    multipath_rician_awgn_profile,
    single_path_rician_awgn_profile,
)
from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.receiver_config import (
    ReceiverFrontEndConfig,
    SeparateReceiverConfig,
)
from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.separate_receiver import run_separate_receiver
from hf_tcm.repro.transmitter import run_transmitter


def _observation(samples: np.ndarray, *, sps: int = 8) -> ReceiverObservation:
    indices = np.arange(len(samples), dtype=np.int64)
    return ReceiverObservation(
        received_samples=np.asarray(samples, dtype=np.complex128),
        absolute_sample_index=indices,
        sample_symbol_index=indices // sps,
        sample_local_index=indices % sps,
        samples_per_symbol=sps,
        profile_id="receiver-test",
        model_id="receiver-test-model",
        sampling_convention="discrete_complex_baseband_absolute_sample_index",
        boundary_policy="zero_extension",
        output_length_policy="tx_plus_max_delay",
        noise_model="none",
        noise_complex_variance=0.0,
    )


def _tx(bits: str, *, tail: str = "zero_tail_2", initial=(0, 0)):
    return run_transmitter(
        TransmitterConfig(
            source_mode="manual",
            frame_symbols=len(bits) // 2,
            manual_bits=bits,
            termination_policy=tail,
            initial_state=initial,
        )
    )


def _cfg(count: int, *, initial=(0, 0), tail="zero_tail_2", offset=0, frontend=None):
    return SeparateReceiverConfig(
        expected_symbol_count=count,
        initial_state=initial,
        termination_policy=tail,
        timing_offset_samples=offset,
        front_end=frontend or ReceiverFrontEndConfig(),
    )


def test_all_eight_hypotheses_and_bijective_inverse_labeling() -> None:
    phases = np.arange(8, dtype=np.float64) * (np.pi / 4)
    samples = np.repeat(np.exp(1j * phases), 8)
    rx = run_separate_receiver(_observation(samples), _cfg(8, tail="none"))
    assert rx.hard_phase_indices.tolist() == list(range(8))
    assert rx.hard_coded_triples.shape == (8, 3)
    assert len(set(map(tuple, rx.hard_coded_triples.tolist()))) == 8


def test_identity_noiseless_end_to_end_decodes_payload_with_explicit_zero_tail() -> None:
    tx = _tx("001101011110")
    channel = run_channel(tx, identity_profile())
    rx = run_separate_receiver(channel.receiver_observation, _cfg(len(tx.phase_indices)))
    evaluation = evaluate_separate_receiver(rx, tx.information_bits, tx.phase_indices[:-2])
    np.testing.assert_array_equal(rx.decoded_information_bits, tx.information_bits)
    assert evaluation.bit_errors == 0
    assert evaluation.symbol_errors == 0
    assert rx.final_state == (0, 0)
    assert rx.traceback_mode == "full_frame"
    assert rx.decoder_depth is None


def test_known_static_complex_gain_is_receiver_public_and_compensated() -> None:
    tx = _tx("001101")
    gain = 0.3 - 0.7j
    channel_cfg = identity_profile()
    from dataclasses import replace

    channel_cfg = replace(
        channel_cfg,
        paths=(
            replace(channel_cfg.paths[0], constant_coefficient=gain, average_power=abs(gain) ** 2),
        ),
    )
    channel = run_channel(tx, channel_cfg)
    config = _cfg(
        len(tx.phase_indices),
        frontend=ReceiverFrontEndConfig(mode="known_static_complex_gain", known_static_gain=gain),
    )
    rx = run_separate_receiver(channel.receiver_observation, config)
    np.testing.assert_array_equal(rx.decoded_information_bits, tx.information_bits)


def test_hamming_costs_are_integer_and_one_bit_error_has_exact_distances() -> None:
    from hf_tcm.repro.encoder import transition_table
    from hf_tcm.repro.hamming_metric import hamming_edge_costs

    table = transition_table()
    for _, _, _, triple, _ in table:
        costs = hamming_edge_costs(np.asarray(triple, dtype=np.int8))
        assert costs.dtype == np.int8
        assert set(np.unique(costs)).issubset({0, 1, 2, 3})
        assert costs.min() == 0
    received = np.asarray((1, 0, 0), dtype=np.int8)
    costs = hamming_edge_costs(received)
    independent = np.asarray(
        [sum(a != b for a, b in zip(received, row[3], strict=True)) for row in table],
        dtype=np.int8,
    )
    np.testing.assert_array_equal(costs, independent)


def test_viterbi_equal_costs_use_canonical_edge_order() -> None:
    from hf_tcm.repro.hamming_viterbi import decode_hamming_viterbi

    result = decode_hamming_viterbi(
        np.zeros((6, 16), dtype=np.int8), initial_state=(0, 0), termination_policy="none"
    )
    assert result.decoded_edge_ids.tolist() == [0] * 6
    assert result.final_state == (0, 0)


def test_all_sixteen_canonical_edges_are_present_in_metric_matrix() -> None:
    tx = _tx("0011", tail="none")
    obs = _observation(tx.tx_samples)
    rx = run_separate_receiver(obs, _cfg(2, tail="none"))
    assert rx.hamming_branch_metrics.shape == (2, 16)
    assert rx.hamming_branch_metrics.dtype == np.int8
    assert rx.edge_order_id == "state_order_00_10_01_11_input_binary_00_01_10_11_v1"


def test_separate_receiver_config_round_trips_explicit_finite_depth_settings() -> None:
    config = SeparateReceiverConfig(
        expected_symbol_count=32,
        decoder_mode="finite_depth",
        traceback_depth=20,
        final_state_policy="free",
        trace_output_mode="compact",
    )
    restored = SeparateReceiverConfig.from_dict(config.to_dict())
    assert restored.decoder_mode == "finite_depth"
    assert restored.traceback_depth == 20
    assert restored.final_state_policy == "free"
    assert restored.trace_output_mode == "compact"


def test_article_oriented_separate_config_selects_eta_twenty() -> None:
    config = SeparateReceiverConfig.article_oriented(expected_symbol_count=32)
    assert config.decoder_mode == "finite_depth"
    assert config.traceback_depth == 20
    assert config.trace_output_mode == "compact"


def test_finite_depth_hamming_identity_decodes_and_records_latency() -> None:
    tx = _tx("001101" * 12, tail="none")
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = SeparateReceiverConfig.article_oriented(
        expected_symbol_count=len(tx.phase_indices), termination_policy="none"
    )
    result = run_separate_receiver(observation, config)
    full = run_separate_receiver(
        observation,
        SeparateReceiverConfig(
            expected_symbol_count=len(tx.phase_indices), termination_policy="none"
        ),
    )
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    np.testing.assert_array_equal(result.hamming_branch_metrics, full.hamming_branch_metrics)
    assert result.hamming_branch_metrics.shape == (36, 16)
    assert result.traceback_mode == "finite_depth"
    assert result.decoder_depth == 20
    records = result.diagnostics["decision_records"]
    assert records[0]["symbol_index"] == 0
    assert records[0]["decision_available_at"] == 19
    assert records[0]["traceback_depth_used"] == 20
    assert result.diagnostics["survivor_buffer_max_rows"] <= 20


def test_compact_finite_hamming_trace_keeps_plots_explicitly_unavailable(tmp_path) -> None:
    from hf_tcm.repro.receiver_plot_adapter import write_receiver_plots

    tx = _tx("001101" * 4, tail="none")
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = SeparateReceiverConfig(
        expected_symbol_count=len(tx.phase_indices),
        termination_policy="none",
        decoder_mode="finite_depth",
        traceback_depth=3,
        trace_output_mode="compact",
    )
    result = run_separate_receiver(observation, config)
    assert result.accumulated_state_metrics.shape == (0, 4)
    paths = write_receiver_plots(observation, result, tmp_path)
    metric_plot = next(path for path in paths if path.name == "viterbi_path_metric.svg")
    assert "trace_output_mode=compact" in metric_plot.read_text(encoding="utf-8")


def test_finite_hamming_runs_known_static_gain_and_noisy_single_path() -> None:
    from dataclasses import replace

    tx = _tx("001101" * 8, tail="none")
    gain = 0.6 - 0.8j
    identity = identity_profile()
    static_config = replace(
        identity,
        paths=(replace(identity.paths[0], constant_coefficient=gain),),
    )
    static_observation = run_channel(tx, static_config).receiver_observation
    static_receiver = SeparateReceiverConfig(
        expected_symbol_count=len(tx.phase_indices),
        termination_policy="none",
        decoder_mode="finite_depth",
        traceback_depth=5,
        front_end=ReceiverFrontEndConfig(mode="known_static_complex_gain", known_static_gain=gain),
    )
    static_result = run_separate_receiver(static_observation, static_receiver)
    assert np.all(np.isfinite(static_result.hard_symbol_squared_distances))

    noisy_observation = run_channel(tx, single_path_rician_awgn_profile()).receiver_observation
    noisy_result = run_separate_receiver(
        noisy_observation,
        SeparateReceiverConfig(
            expected_symbol_count=len(tx.phase_indices),
            termination_policy="none",
            decoder_mode="finite_depth",
            traceback_depth=5,
        ),
    )
    assert np.all(np.isfinite(noisy_result.accumulated_state_metrics))
    assert noisy_result.diagnostics["survivor_buffer_max_rows"] <= 5


def test_finite_hamming_flush_honors_public_zero_tail_and_payload_contract() -> None:
    tx = _tx("001101" * 12, tail="zero_tail_2")
    observation = run_channel(tx, identity_profile()).receiver_observation
    config = SeparateReceiverConfig.article_oriented(
        expected_symbol_count=len(tx.phase_indices), termination_policy="zero_tail_2"
    )
    result = run_separate_receiver(observation, config)
    np.testing.assert_array_equal(result.decoded_information_bits, tx.information_bits)
    assert result.decoded_frame_information_bits[-4:].tolist() == [0, 0, 0, 0]
    assert result.final_state == (0, 0)


def test_nonzero_initial_state_is_enforced() -> None:
    tx = _tx("0110", initial=(1, 1), tail="zero_tail_2")
    rx = run_separate_receiver(
        run_channel(tx, identity_profile()).receiver_observation,
        _cfg(len(tx.phase_indices), initial=(1, 1)),
    )
    np.testing.assert_array_equal(rx.decoded_information_bits, tx.information_bits)
    assert tuple(rx.decoded_state_path[0]) == (1, 1)


def test_rician_multipath_tail_is_unprocessed_not_a_new_symbol() -> None:
    tx = _tx("001101" * 4)
    observation = run_channel(tx, multipath_rician_awgn_profile()).receiver_observation
    assert len(observation.received_samples) == len(tx.tx_samples) + 3
    rx = run_separate_receiver(observation, _cfg(len(tx.phase_indices)))
    assert rx.hard_phase_indices.shape == (len(tx.phase_indices),)
    assert rx.unprocessed_sample_indices.tolist() == [
        len(tx.tx_samples),
        len(tx.tx_samples) + 1,
        len(tx.tx_samples) + 2,
    ]
    assert rx.processed_sample_ranges[-1, 1] == len(tx.tx_samples) - 1


def test_noisy_single_path_receiver_output_is_finite_deterministic_and_aligned() -> None:
    tx = _tx("001101" * 8)
    observation = run_channel(tx, single_path_rician_awgn_profile()).receiver_observation
    config = _cfg(len(tx.phase_indices))
    first = run_separate_receiver(observation, config)
    second = run_separate_receiver(observation, config)
    np.testing.assert_array_equal(first.hard_phase_indices, second.hard_phase_indices)
    np.testing.assert_array_equal(first.hamming_branch_metrics, second.hamming_branch_metrics)
    np.testing.assert_array_equal(first.decoded_information_bits, second.decoded_information_bits)
    assert first.hard_symbol_squared_distances.shape == (len(tx.phase_indices), 8)
    assert np.all(np.isfinite(first.hard_symbol_squared_distances))


def test_timing_offset_records_exact_sample_ranges() -> None:
    tx = _tx("001101", tail="none")
    rx = run_separate_receiver(_observation(tx.tx_samples), _cfg(3, tail="none", offset=2))
    assert rx.processed_sample_ranges.tolist() == [[2, 7], [10, 15], [18, 23]]
    assert rx.unprocessed_sample_indices.tolist() == [0, 1, 8, 9, 16, 17]


def test_receiver_rejects_truth_and_channel_result_objects() -> None:
    tx = _tx("001101")
    channel = run_channel(tx, identity_profile())
    with pytest.raises(TypeError, match="ReceiverObservation"):
        run_separate_receiver(channel, _cfg(len(tx.phase_indices)))  # type: ignore[arg-type]
    truth_fields = {field.name for field in fields(channel.evaluation_truth)}
    observation_fields = {field.name for field in fields(channel.receiver_observation)}
    assert not truth_fields.intersection(observation_fields)


def test_sample_count_and_timing_arrays_are_strictly_validated() -> None:
    tx = _tx("001101", tail="none")
    obs = _observation(tx.tx_samples)
    with pytest.raises(ValueError, match="expected_symbol_count"):
        run_separate_receiver(obs, _cfg(4, tail="none"))
    broken = ReceiverObservation(
        **{
            **{field.name: getattr(obs, field.name) for field in fields(obs)},
            "samples_per_symbol": 4,
        }
    )
    with pytest.raises(ValueError, match="8 samples per symbol"):
        run_separate_receiver(broken, _cfg(3, tail="none"))


def test_static_gain_requires_finite_explicit_complex_value() -> None:
    with pytest.raises(ValueError, match="known_static_gain"):
        ReceiverFrontEndConfig(
            mode="known_static_complex_gain", known_static_gain=complex(float("nan"), 0)
        )


def test_result_serialization_is_receiver_only_and_hash_verified(tmp_path) -> None:
    import json

    from hf_tcm.repro.receiver_evaluation_cli import main as evaluation_main
    from hf_tcm.repro.receiver_io import (
        load_separate_receiver_result,
        save_separate_receiver_result,
    )

    tx = _tx("001101")
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_separate_receiver(observation, _cfg(len(tx.phase_indices)))
    manifest = save_separate_receiver_result(result, tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert manifest["observation_sha256"] == observation.sha256
    assert summary["output_npz_sha256"] == manifest["files"]["receiver_result.npz"]
    assert "evaluation_truth" not in summary
    restored = load_separate_receiver_result(tmp_path)
    assert (
        restored.reproducibility_metadata["output_arrays_sha256"]
        == result.reproducibility_metadata["output_arrays_sha256"]
    )
    np.testing.assert_array_equal(restored.decoded_edge_ids, result.decoded_edge_ids)
    with np.load(tmp_path / "receiver_result.npz", allow_pickle=False) as arrays:
        assert arrays["decoded_information_bits"].tolist() == tx.information_bits.tolist()
        assert arrays["decision_symbol_index"].tolist() == list(range(len(tx.phase_indices)))
        assert arrays["decision_traceback_depth_used"].shape == (len(tx.phase_indices),)
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            {
                "information_bits": tx.information_bits.tolist(),
                "phase_indices": tx.phase_indices[:-2].tolist(),
            }
        ),
        encoding="utf-8",
    )
    evaluation_dir = tmp_path / "evaluation"
    assert (
        evaluation_main(
            [
                "--receiver-output",
                str(tmp_path),
                "--reference",
                str(reference_path),
                "--output",
                str(evaluation_dir),
                "--print-summary",
            ]
        )
        == 0
    )
    evaluation = json.loads((evaluation_dir / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["bit_errors"] == 0
    assert evaluation["symbol_errors"] == 0
    assert evaluation["receiver_decision_uses_reference"] is False


def test_plots_are_generated_from_actual_receiver_arrays(tmp_path) -> None:
    from hf_tcm.repro.receiver_plot_adapter import write_receiver_plots

    tx = _tx("001101")
    observation = run_channel(tx, identity_profile()).receiver_observation
    result = run_separate_receiver(observation, _cfg(len(tx.phase_indices)))
    paths = write_receiver_plots(observation, result, tmp_path, selected_symbol=1)
    assert len(paths) >= 9
    assert all(
        path.is_file() and path.read_text(encoding="utf-8").startswith("<svg") for path in paths
    )


def test_public_observation_loader_round_trip_keeps_truth_out_of_receiver(tmp_path) -> None:
    from hf_tcm.repro.channel_serialization import save_channel_result
    from hf_tcm.repro.receiver_io import load_receiver_observation

    tx = _tx("001101")
    channel = run_channel(tx, identity_profile())
    save_channel_result(channel, tmp_path)
    loaded = load_receiver_observation(tmp_path)
    assert loaded.sha256 == channel.receiver_observation.sha256
    rx = run_separate_receiver(loaded, _cfg(len(tx.phase_indices)))
    np.testing.assert_array_equal(rx.decoded_information_bits, tx.information_bits)
