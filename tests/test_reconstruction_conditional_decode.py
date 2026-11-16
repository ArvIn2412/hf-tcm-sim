from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest

from hf_tcm.coding.encoder import INITIAL_STATE, encode_step
from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.hypothesis_path import validate_hypothesis_edge_path
from hf_tcm.decoding.reconstruction_viterbi import decode_reconstruction_viterbi
from hf_tcm.receiver import reconstruction_conditional_decode as conditional_decode
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_estimator_state import ReconstructionEstimatorState
from hf_tcm.receiver.reconstruction_forward import (
    APPROXIMATE_RECTANGULAR_8SPS,
    RECTANGULAR_ZOH_RULE,
)
from hf_tcm.receiver.reconstruction_labeling import ASSUMED_NATURAL_BINARY, OUTPUT_BIT_ORDER
from hf_tcm.receiver.reconstruction_observation import (
    ADR012_IQ_RULE,
    ADR012_PROFILE,
    ADR012_PROFILE_ID,
    ADR012_WAVEFORM_RULE,
)
from hf_tcm.receiver.reconstruction_posterior import build_initial_reconstruction_prior
from hf_tcm.receiver.reconstruction_posterior_estimator_sequence import (
    run_reconstruction_posterior_estimator_sequence,
)


def _input_bits_for_length(length: int) -> tuple[tuple[int, int], ...]:
    choices = {
        1: ((1, 0),),
        2: ((1, 0), (1, 1)),
        4: ((1, 1), (0, 1), (1, 0), (0, 0)),
    }
    return choices[length]


def _noiseless_received(input_pairs: tuple[tuple[int, int], ...], coefficient: float) -> np.ndarray:
    state = INITIAL_STATE
    samples: list[complex] = []
    for pair in input_pairs:
        output_bits, state = encode_step(pair, state)
        b = 4 * output_bits[0] + 2 * output_bits[1] + output_bits[2]
        quadratures = iq_quadratures_from_index(b, coefficient, coefficient)
        complex_sample = quadratures[1] - 1j * quadratures[0]
        samples.extend([complex_sample] * 8)
    return np.asarray(samples, dtype=np.complex128)


def _operands(
    *,
    received: np.ndarray,
    initial_state: ReconstructionEstimatorState,
    coefficient: float,
    beta: float = 1.0,
    origin: int = 11,
    first_symbol: int = 3,
    initial_time: int = 13,
) -> dict[str, object]:
    count = received.size // 8
    first_sample = origin + 8 * first_symbol
    return {
        "received": received,
        "absolute_sample_indices": np.arange(first_sample, first_sample + received.size),
        "received_start_sample": first_sample,
        "symbol_origin_sample": origin,
        "first_symbol_index": first_symbol,
        "sequence_origin_symbol_index": first_symbol,
        "symbol_count": count,
        "symbol_indices": tuple(range(first_symbol, first_symbol + count)),
        "initial_estimator_state": initial_state,
        "initial_estimator_time_index": initial_time,
        "initial_encoder_state": INITIAL_STATE,
        "sequence_mode": "new_independent_sequence",
        "beta": beta,
        "alpha_prime": 1.0,
        "k_tilde": np.zeros((1, 2)),
        "mu0": np.zeros((1, 2)),
        "profile": ADR012_PROFILE,
        "adr_profile": ADR012_PROFILE_ID,
        "path_count": 1,
        "path_delays_samples": (0,),
        "samples_per_symbol": 8,
        "iq_rule": ADR012_IQ_RULE,
        "waveform_rule": ADR012_WAVEFORM_RULE,
        "labeling_profile": ASSUMED_NATURAL_BINARY,
        "bit_order": OUTPUT_BIT_ORDER,
        "timebase_profile": APPROXIMATE_RECTANGULAR_8SPS,
        "symbol_to_sample_rule": RECTANGULAR_ZOH_RULE,
        "edge_policy": ZERO_PADDING,
        "_oracle_coefficient": coefficient,
    }


def _public_operands(args: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in args.items() if not key.startswith("_")}


def _manual_b4d(args: dict[str, object]):
    values = _public_operands(args)
    return run_reconstruction_posterior_estimator_sequence(
        received=values["received"],
        absolute_sample_indices=values["absolute_sample_indices"],
        received_start_sample=values["received_start_sample"],
        symbol_origin_sample=values["symbol_origin_sample"],
        first_symbol_index=values["first_symbol_index"],
        sequence_origin_symbol_index=values["sequence_origin_symbol_index"],
        symbol_count=values["symbol_count"],
        symbol_indices=values["symbol_indices"],
        initial_state=values["initial_estimator_state"],
        initial_estimator_time_index=values["initial_estimator_time_index"],
        run_mode="new_independent_sequence",
        initial_prior=build_initial_reconstruction_prior(initial_state=(0, 0)),
        previous_posterior=None,
        continuation_from_symbol_index=None,
        continuation_from_estimator_time_index=None,
        beta=values["beta"],
        alpha_prime=values["alpha_prime"],
        k_tilde=values["k_tilde"],
        mu0=values["mu0"],
        include_history=True,
        profile=values["profile"],
        adr_profile=values["adr_profile"],
        path_count=values["path_count"],
        path_delays_samples=values["path_delays_samples"],
        samples_per_symbol=values["samples_per_symbol"],
        iq_rule=values["iq_rule"],
        waveform_rule=values["waveform_rule"],
        labeling_profile=values["labeling_profile"],
        bit_order=values["bit_order"],
        timebase_profile=values["timebase_profile"],
        symbol_to_sample_rule=values["symbol_to_sample_rule"],
        edge_policy=values["edge_policy"],
    )


def test_adapter_equals_manual_b4d_metric_extraction_and_one_b5b_call() -> None:
    pairs = _input_bits_for_length(4)
    received = _noiseless_received(pairs, 0.75)
    state = ReconstructionEstimatorState([[0.75, 0.75]], [[0.75, 0.75]], 13)
    args = _operands(received=received, initial_state=state, coefficient=0.75)
    expected_sequence = _manual_b4d(args)
    assert expected_sequence.history is not None
    expected_metrics = np.stack(
        [row.b4c_result.candidate_result.metrics for row in expected_sequence.history]
    )
    expected_provenance = tuple(
        conditional_decode.ReconstructionMetricRowProvenance(
            absolute_symbol_index=row.symbol_index,
            estimator_time_index=row.estimator_time_index,
            sample_indices=row.b4c_result.candidate_result.sample_indices,
            prediction_cutoff_sample_index=(
                row.b4c_result.candidate_result.prediction_cutoff_sample_index
            ),
            observation_cutoff_sample_index=(
                row.b4c_result.candidate_result.metric_available_after_sample_index
            ),
            hypothesis_ids=row.b4c_result.candidate_result.hypothesis_ids,
            profile=row.b4c_result.candidate_result.profile,
            profile_id=row.b4c_result.candidate_result.profile_id,
        )
        for row in expected_sequence.history
    )
    expected_viterbi = decode_reconstruction_viterbi(
        expected_metrics,
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile=ADR012_PROFILE,
        edge_indices=tuple(range(len(pairs))),
        symbol_indices=tuple(range(3, 3 + len(pairs))),
        estimator_time_indices=tuple(range(13, 13 + len(pairs))),
    )

    result = conditional_decode.decode_reconstruction_conditional_sequence(**_public_operands(args))

    np.testing.assert_array_equal(result.candidate_metrics, expected_metrics)
    assert result.candidate_metrics.tobytes() == expected_metrics.tobytes()
    assert result.decoder_result.hypothesis_ids == expected_viterbi.hypothesis_ids
    np.testing.assert_array_equal(result.decoded_information_bits, expected_viterbi.decoded_bits)
    np.testing.assert_array_equal(
        result.final_estimator_state.fluctuating_iq,
        expected_sequence.final_state.fluctuating_iq,
    )
    np.testing.assert_array_equal(
        result.final_estimator_state.full_iq, expected_sequence.final_state.full_iq
    )
    assert result.final_estimator_state.time_index == expected_sequence.final_state.time_index
    np.testing.assert_array_equal(result.final_posterior, expected_sequence.final_posterior)
    assert result.metric_provenance == expected_provenance
    assert result.hypothesis_order == tuple(range(16))


@pytest.mark.parametrize("coefficient", [0.75, 2.0])
@pytest.mark.parametrize("length", [1, 2, 4])
def test_noiseless_real_channel_oracle_decodes_m1_input_pairs(
    coefficient: float, length: int
) -> None:
    input_pairs = _input_bits_for_length(length)
    received = _noiseless_received(input_pairs, coefficient)
    state = ReconstructionEstimatorState(
        [[coefficient, coefficient]], [[coefficient, coefficient]], 31
    )
    args = _operands(
        received=received,
        initial_state=state,
        coefficient=coefficient,
        origin=17,
        first_symbol=4,
        initial_time=31,
    )

    result = conditional_decode.decode_reconstruction_conditional_sequence(**_public_operands(args))

    assert result.profile == "reconstructed_offline"
    assert result.candidate_metrics.shape == (length, 16)
    assert np.all(np.isfinite(result.candidate_metrics))
    assert np.all(result.candidate_metrics >= 0.0)
    np.testing.assert_array_equal(
        result.decoded_input_pairs, np.asarray(input_pairs, dtype=np.int8)
    )
    np.testing.assert_array_equal(
        result.decoded_information_bits,
        np.asarray(input_pairs, dtype=np.int8).reshape(-1),
    )
    assert result.decoder_result.final_state == result.final_encoder_state
    assert result.final_encoder_state == result.decoder_result.state_path[-1]
    assert result.best_conditional_path_cost == 0.0
    assert result.symbol_indices == tuple(range(4, 4 + length))
    assert result.estimator_time_indices == tuple(range(31, 31 + length))
    assert result.symbol_indices != result.estimator_time_indices
    assert result.prediction_cutoff_sample_indices == tuple(
        17 + 8 * symbol - 1 for symbol in result.symbol_indices
    )
    assert result.observation_cutoff_sample_indices == tuple(
        17 + 8 * symbol + 7 for symbol in result.symbol_indices
    )
    assert validate_hypothesis_edge_path(
        result.decoded_hypothesis_path, initial_state=INITIAL_STATE
    )


def test_beta_changes_posterior_without_recomputing_historical_metrics() -> None:
    pairs = _input_bits_for_length(4)
    received = _noiseless_received(pairs, 0.75)
    state = ReconstructionEstimatorState([[0.2, 0.35]], [[0.75, 0.75]], 13)
    low = _operands(received=received, initial_state=state, coefficient=0.75, beta=0.15)
    low["k_tilde"] = np.asarray([[0.7, 0.7]])
    high = dict(low, beta=3.0)

    low_result = conditional_decode.decode_reconstruction_conditional_sequence(
        **_public_operands(low)
    )
    high_result = conditional_decode.decode_reconstruction_conditional_sequence(
        **_public_operands(high)
    )

    assert not np.array_equal(low_result.final_posterior, high_result.final_posterior)
    # The first cost row shares the same pre-state; later rows can differ
    # because beta changed the intervening causal estimator state.
    np.testing.assert_array_equal(low_result.candidate_metrics[0], high_result.candidate_metrics[0])
    assert not np.array_equal(
        low_result.final_estimator_state.full_iq, high_result.final_estimator_state.full_iq
    )


def test_received_and_final_result_arrays_are_immutable_and_repeatable() -> None:
    received = _noiseless_received(_input_bits_for_length(4), 2.0)
    original_received = received.copy()
    state = ReconstructionEstimatorState([[2.0, 2.0]], [[2.0, 2.0]], 13)
    original_fluctuating = state.fluctuating_iq.copy()
    original_full = state.full_iq.copy()
    args = _operands(received=received, initial_state=state, coefficient=2.0)

    first = conditional_decode.decode_reconstruction_conditional_sequence(**_public_operands(args))
    second = conditional_decode.decode_reconstruction_conditional_sequence(**_public_operands(args))

    np.testing.assert_array_equal(received, original_received)
    np.testing.assert_array_equal(state.fluctuating_iq, original_fluctuating)
    np.testing.assert_array_equal(state.full_iq, original_full)
    assert first.decoded_hypothesis_path == second.decoded_hypothesis_path
    np.testing.assert_array_equal(first.candidate_metrics, second.candidate_metrics)
    np.testing.assert_array_equal(first.decoded_information_bits, second.decoded_information_bits)
    assert first.final_estimator_time_index == first.final_estimator_state.time_index
    assert first.final_completed_symbol_index == first.symbol_indices[-1]
    with pytest.raises(ValueError):
        first.candidate_metrics[0, 0] = 2.0
    with pytest.raises(ValueError):
        first.decoded_information_bits[0] = 1


def test_incomplete_and_nonfinite_received_inputs_are_rejected() -> None:
    received = _noiseless_received(_input_bits_for_length(2), 0.75)
    state = ReconstructionEstimatorState([[0.75, 0.75]], [[0.75, 0.75]], 13)
    args = _operands(received=received, initial_state=state, coefficient=0.75)
    with pytest.raises(ValueError, match="8 samples"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(
                _public_operands(args),
                received=received[:-1],
                absolute_sample_indices=np.arange(15),
            )
        )
    broken = received.copy()
    broken[-1] = complex(np.inf, 0.0)
    with pytest.raises(ValueError, match="finite"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(_public_operands(args), received=broken)
        )


def test_time_gaps_repeats_and_wrong_independent_start_are_rejected() -> None:
    received = _noiseless_received(_input_bits_for_length(2), 0.75)
    state = ReconstructionEstimatorState([[0.75, 0.75]], [[0.75, 0.75]], 13)
    args = _operands(received=received, initial_state=state, coefficient=0.75)
    base = _public_operands(args)
    with pytest.raises(ValueError, match="contiguous"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(base, symbol_indices=(3, 5))
        )
    with pytest.raises(ValueError, match="contiguous"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(base, absolute_sample_indices=np.arange(24, 40).tolist())
        )
    with pytest.raises(ValueError, match="sequence origin"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(base, first_symbol_index=4, symbol_indices=(4, 5))
        )
    with pytest.raises(ValueError, match="initial_encoder_state"):
        conditional_decode.decode_reconstruction_conditional_sequence(
            **dict(base, initial_encoder_state=(1, 0))
        )


def test_split_b4d_continuation_rows_join_for_one_final_b5b_call() -> None:
    pairs = _input_bits_for_length(4)
    received = _noiseless_received(pairs, 0.75)
    state = ReconstructionEstimatorState([[0.75, 0.75]], [[0.75, 0.75]], 13)
    args = _operands(received=received, initial_state=state, coefficient=0.75)
    whole = _manual_b4d(args)
    assert whole.history is not None

    first_symbols = (3, 4)
    values = _public_operands(args)
    first_args = dict(
        received=received[:16],
        absolute_sample_indices=np.arange(35, 51),
        received_start_sample=35,
        symbol_origin_sample=values["symbol_origin_sample"],
        first_symbol_index=3,
        sequence_origin_symbol_index=3,
        symbol_count=2,
        symbol_indices=first_symbols,
        initial_state=state,
        initial_estimator_time_index=13,
        run_mode="new_independent_sequence",
        initial_prior=build_initial_reconstruction_prior(initial_state=(0, 0)),
        previous_posterior=None,
        continuation_from_symbol_index=None,
        continuation_from_estimator_time_index=None,
        beta=values["beta"],
        alpha_prime=values["alpha_prime"],
        k_tilde=values["k_tilde"],
        mu0=values["mu0"],
        include_history=True,
        profile=values["profile"],
        adr_profile=values["adr_profile"],
        path_count=values["path_count"],
        path_delays_samples=values["path_delays_samples"],
        samples_per_symbol=values["samples_per_symbol"],
        iq_rule=values["iq_rule"],
        waveform_rule=values["waveform_rule"],
        labeling_profile=values["labeling_profile"],
        bit_order=values["bit_order"],
        timebase_profile=values["timebase_profile"],
        symbol_to_sample_rule=values["symbol_to_sample_rule"],
        edge_policy=values["edge_policy"],
    )
    first = run_reconstruction_posterior_estimator_sequence(**first_args)

    second_args = dict(
        received=received[16:],
        absolute_sample_indices=np.arange(51, 67),
        received_start_sample=51,
        first_symbol_index=5,
        sequence_origin_symbol_index=3,
        symbol_count=2,
        symbol_indices=(5, 6),
        initial_state=first.final_state,
        initial_estimator_time_index=first.final_estimator_time_index,
        run_mode="continuation",
        initial_prior=None,
        previous_posterior=first.final_posterior,
        continuation_from_symbol_index=first.final_symbol_index,
        continuation_from_estimator_time_index=first.final_estimator_time_index - 1,
        include_history=True,
    )
    for key in (
        "symbol_origin_sample",
        "beta",
        "alpha_prime",
        "k_tilde",
        "mu0",
        "profile",
        "adr_profile",
        "path_count",
        "path_delays_samples",
        "samples_per_symbol",
        "iq_rule",
        "waveform_rule",
        "labeling_profile",
        "bit_order",
        "timebase_profile",
        "symbol_to_sample_rule",
        "edge_policy",
    ):
        second_args[key] = values[key]
    second = run_reconstruction_posterior_estimator_sequence(**second_args)

    assert first.history is not None and second.history is not None
    split_metrics = np.stack(
        [row.b4c_result.candidate_result.metrics for row in (*first.history, *second.history)]
    )
    whole_metrics = np.stack([row.b4c_result.candidate_result.metrics for row in whole.history])
    np.testing.assert_array_equal(split_metrics, whole_metrics)
    np.testing.assert_array_equal(second.final_state.full_iq, whole.final_state.full_iq)
    np.testing.assert_array_equal(second.final_posterior, whole.final_posterior)

    decoded = decode_reconstruction_viterbi(
        split_metrics,
        hypotheses=HYPOTHESES,
        initial_state=INITIAL_STATE,
        sequence_mode="new_independent_sequence",
        profile=ADR012_PROFILE,
        edge_indices=(0, 1, 2, 3),
        symbol_indices=(3, 4, 5, 6),
        estimator_time_indices=(13, 14, 15, 16),
    )
    assert tuple(decoded.input_pairs.reshape(-1)) == tuple(bit for pair in pairs for bit in pair)


def test_truth_is_not_a_runtime_operand_or_imported_dependency() -> None:
    signature = inspect.signature(conditional_decode.decode_reconstruction_conditional_sequence)
    assert not any("truth" in name.lower() for name in signature.parameters)
    tree = ast.parse(inspect.getsource(conditional_decode))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "ChannelTruth" not in names | attrs
    assert "ChannelOutput" not in names | attrs
    assert not any("hf_tcm.channel" in module for module in modules)


def test_different_oracle_truth_labels_cannot_change_receiver_result() -> None:
    received = _noiseless_received(_input_bits_for_length(2), 0.75)
    state = ReconstructionEstimatorState([[0.75, 0.75]], [[0.75, 0.75]], 13)
    operands = _public_operands(_operands(received=received, initial_state=state, coefficient=0.75))
    # These simulation-fixture labels intentionally remain outside the receiver API.
    oracle_truth_a = {"coefficient": 0.75, "path": "fixture-a"}
    oracle_truth_b = {"coefficient": 2.0, "path": "fixture-b"}
    first = conditional_decode.decode_reconstruction_conditional_sequence(**operands)
    second = conditional_decode.decode_reconstruction_conditional_sequence(**operands)

    assert oracle_truth_a != oracle_truth_b
    assert first.decoded_hypothesis_path == second.decoded_hypothesis_path
    np.testing.assert_array_equal(first.candidate_metrics, second.candidate_metrics)
    np.testing.assert_array_equal(first.decoded_information_bits, second.decoded_information_bits)
