from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest

from hf_tcm.coding.encoder import INITIAL_STATE, encode_step
from hf_tcm.receiver import reconstruction_segmented_decode as segmented
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_conditional_decode import (
    decode_reconstruction_conditional_sequence,
)
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


def _input_pairs(length: int) -> tuple[tuple[int, int], ...]:
    pattern = ((1, 1), (0, 1), (1, 0), (0, 0), (1, 0), (0, 1))
    return tuple(pattern[index % len(pattern)] for index in range(length))


def _noiseless_received(pairs: tuple[tuple[int, int], ...], coefficient: float) -> np.ndarray:
    state = INITIAL_STATE
    samples: list[complex] = []
    for pair in pairs:
        output_bits, state = encode_step(pair, state)
        phase_index = 4 * output_bits[0] + 2 * output_bits[1] + output_bits[2]
        quadratures = iq_quadratures_from_index(phase_index, coefficient, coefficient)
        received_sample = quadratures[1] - 1j * quadratures[0]
        samples.extend([received_sample] * 8)
    return np.asarray(samples, dtype=np.complex128)


def _base_operands(
    *,
    received: np.ndarray,
    coefficient: float,
    first_symbol: int,
    symbol_origin: int,
    initial_time: int,
    alpha_prime: object = 1.0,
    k_tilde: object | None = None,
    mu0: object | None = None,
) -> dict[str, object]:
    count = received.size // 8
    received_start = symbol_origin + 8 * first_symbol
    return {
        "received": received,
        "absolute_sample_indices": np.arange(received_start, received_start + received.size),
        "received_start_sample": received_start,
        "symbol_origin_sample": symbol_origin,
        "sequence_origin_symbol_index": first_symbol,
        "initial_estimator_state": ReconstructionEstimatorState(
            [[coefficient, coefficient]], [[coefficient, coefficient]], initial_time
        ),
        "initial_estimator_time_index": initial_time,
        "beta": 0.7,
        "alpha_prime": alpha_prime,
        "k_tilde": np.zeros((1, 2)) if k_tilde is None else k_tilde,
        "mu0": np.zeros((1, 2)) if mu0 is None else mu0,
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
        "_symbol_count": count,
    }


def _partition(counts: tuple[int, ...], first_symbol: int) -> tuple[object, ...]:
    descriptors = []
    symbol = first_symbol
    sample_offset = 0
    for size in counts:
        descriptors.append(
            segmented.ReconstructionSequenceSegment(
                first_symbol_index=symbol,
                received_start_offset=sample_offset,
                symbol_count=size,
            )
        )
        symbol += size
        sample_offset += size * 8
    return tuple(descriptors)


def _run_monolithic(operands: dict[str, object]):
    count = operands["_symbol_count"]
    first_symbol = operands["sequence_origin_symbol_index"]
    public = {key: value for key, value in operands.items() if not key.startswith("_")}
    return decode_reconstruction_conditional_sequence(
        **public,
        initial_encoder_state=INITIAL_STATE,
        first_symbol_index=first_symbol,
        symbol_count=count,
        symbol_indices=tuple(range(first_symbol, first_symbol + count)),
        sequence_mode="new_independent_sequence",
    )


def _run_segmented(operands: dict[str, object], counts: tuple[int, ...]):
    public = {key: value for key, value in operands.items() if not key.startswith("_")}
    return segmented.decode_reconstruction_segmented_sequence(
        **public,
        initial_encoder_state=INITIAL_STATE,
        segments=_partition(counts, int(operands["sequence_origin_symbol_index"])),
    )


@pytest.mark.parametrize(
    ("length", "partitions"),
    [
        (1, ((1,),)),
        (2, ((2,), (1, 1))),
        (4, ((4,), (1, 3), (2, 2), (3, 1), (1, 1, 1, 1))),
        (6, ((2, 4), (1, 2, 3))),
    ],
)
@pytest.mark.parametrize("coefficient", [0.75, 2.0])
def test_segment_partitions_equal_monolithic_decode(
    length: int, partitions: tuple[tuple[int, ...], ...], coefficient: float
) -> None:
    pairs = _input_pairs(length)
    received = _noiseless_received(pairs, coefficient)
    operands = _base_operands(
        received=received,
        coefficient=coefficient,
        first_symbol=5,
        symbol_origin=19,
        initial_time=37,
    )
    monolithic = _run_monolithic(operands)
    one_segment = _run_segmented(operands, (length,))

    for partition in partitions:
        result = _run_segmented(operands, partition)
        np.testing.assert_array_equal(result.candidate_metrics, monolithic.candidate_metrics)
        np.testing.assert_array_equal(result.posterior_history, one_segment.posterior_history)
        np.testing.assert_array_equal(result.posterior_history[-1], monolithic.final_posterior)
        np.testing.assert_array_equal(result.final_posterior, monolithic.final_posterior)
        np.testing.assert_array_equal(
            result.final_estimator_state.fluctuating_iq,
            monolithic.final_estimator_state.fluctuating_iq,
        )
        np.testing.assert_array_equal(
            result.final_estimator_state.full_iq, monolithic.final_estimator_state.full_iq
        )
        assert (
            result.final_estimator_state.time_index == monolithic.final_estimator_state.time_index
        )
        assert result.decoded_hypothesis_path == monolithic.decoded_hypothesis_path
        np.testing.assert_array_equal(
            result.decoded_information_bits, monolithic.decoded_information_bits
        )
        np.testing.assert_array_equal(result.decoded_input_pairs, np.asarray(pairs, dtype=np.int8))
        assert result.best_conditional_path_cost == monolithic.best_conditional_path_cost
        assert result.symbol_indices == tuple(range(5, 5 + length))
        assert result.estimator_time_indices == tuple(range(37, 37 + length))
        assert result.symbol_indices != result.estimator_time_indices
        assert tuple(row.sequence_position for row in result.symbol_schedule) == tuple(
            range(length)
        )
        assert tuple(row.segment_local_position for row in result.symbol_schedule) == tuple(
            position for segment_size in partition for position in range(segment_size)
        )
        assert tuple(row.edge_mode for row in result.symbol_schedule) == (
            "first_edge",
            *("later_edge" for _ in range(length - 1)),
        )
        assert result.hypothesis_order == tuple(range(16))
        assert result.prediction_cutoff_sample_indices == tuple(
            19 + 8 * symbol - 1 for symbol in range(5, 5 + length)
        )
        assert result.observation_cutoff_sample_indices == tuple(
            19 + 8 * symbol + 7 for symbol in range(5, 5 + length)
        )
        assert [
            (boundary.sequence_start_position, boundary.sequence_stop_position)
            for boundary in result.segment_boundaries
        ] == [
            (sum(partition[:index]), sum(partition[: index + 1])) for index in range(len(partition))
        ]


def test_variable_explicit_recursion_schedules_match_monolithic() -> None:
    length = 6
    received = _noiseless_received(_input_pairs(length), 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=2,
        symbol_origin=23,
        initial_time=101,
        alpha_prime=np.asarray([0.7, 0.8, 0.9, 1.0, 0.6, 0.5]),
        k_tilde=np.arange(length * 2, dtype=np.float64).reshape(length, 1, 2) / 100.0,
        mu0=np.arange(length * 2, dtype=np.float64).reshape(length, 1, 2) / 50.0,
    )
    monolithic = _run_monolithic(operands)
    result = _run_segmented(operands, (2, 1, 3))

    np.testing.assert_array_equal(result.candidate_metrics, monolithic.candidate_metrics)
    np.testing.assert_array_equal(result.posterior_history[-1], monolithic.final_posterior)
    np.testing.assert_array_equal(result.final_posterior, monolithic.final_posterior)
    np.testing.assert_array_equal(
        result.final_estimator_state.full_iq, monolithic.final_estimator_state.full_iq
    )
    assert result.decoded_hypothesis_path == monolithic.decoded_hypothesis_path


def test_full_per_symbol_posterior_history_equals_monolithic_b4d() -> None:
    pairs = _input_pairs(4)
    received = _noiseless_received(pairs, 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=3,
        symbol_origin=7,
        initial_time=52,
    )
    result = _run_segmented(operands, (1, 2, 1))
    start = operands["received_start_sample"]
    whole = run_reconstruction_posterior_estimator_sequence(
        received=received,
        absolute_sample_indices=np.arange(start, start + received.size),
        received_start_sample=start,
        symbol_origin_sample=7,
        first_symbol_index=3,
        sequence_origin_symbol_index=3,
        symbol_count=4,
        symbol_indices=(3, 4, 5, 6),
        initial_state=operands["initial_estimator_state"],
        initial_estimator_time_index=52,
        run_mode="new_independent_sequence",
        initial_prior=build_initial_reconstruction_prior(initial_state=(0, 0)),
        previous_posterior=None,
        continuation_from_symbol_index=None,
        continuation_from_estimator_time_index=None,
        beta=operands["beta"],
        alpha_prime=operands["alpha_prime"],
        k_tilde=operands["k_tilde"],
        mu0=operands["mu0"],
        include_history=True,
        profile=operands["profile"],
        adr_profile=operands["adr_profile"],
        path_count=operands["path_count"],
        path_delays_samples=operands["path_delays_samples"],
        samples_per_symbol=operands["samples_per_symbol"],
        iq_rule=operands["iq_rule"],
        waveform_rule=operands["waveform_rule"],
        labeling_profile=operands["labeling_profile"],
        bit_order=operands["bit_order"],
        timebase_profile=operands["timebase_profile"],
        symbol_to_sample_rule=operands["symbol_to_sample_rule"],
        edge_policy=operands["edge_policy"],
    )
    assert whole.history is not None
    manual_posterior_history = np.stack([item.b4c_result.posterior for item in whole.history])
    manual_metrics = np.stack([item.b4c_result.candidate_result.metrics for item in whole.history])

    np.testing.assert_array_equal(result.posterior_history, manual_posterior_history)
    np.testing.assert_array_equal(result.candidate_metrics, manual_metrics)


def test_segmented_runner_calls_b5b_once_and_passes_exact_continuation_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pairs = _input_pairs(4)
    received = _noiseless_received(pairs, 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=4,
        symbol_origin=9,
        initial_time=28,
    )
    original_b4d = segmented.run_reconstruction_posterior_estimator_sequence
    calls: list[dict[str, object]] = []
    b4d_results = []

    def b4d_spy(**kwargs: object):
        calls.append(kwargs)
        result = original_b4d(**kwargs)
        b4d_results.append(result)
        return result

    viterbi_calls: list[object] = []
    original_b5b = segmented.decode_reconstruction_viterbi

    def b5b_spy(*args: object, **kwargs: object):
        viterbi_calls.append(args[0])
        return original_b5b(*args, **kwargs)

    monkeypatch.setattr(segmented, "run_reconstruction_posterior_estimator_sequence", b4d_spy)
    monkeypatch.setattr(segmented, "decode_reconstruction_viterbi", b5b_spy)
    result = _run_segmented(operands, (2, 1, 1))

    assert len(calls) == 3
    assert [call["run_mode"] for call in calls] == [
        "new_independent_sequence",
        "continuation",
        "continuation",
    ]
    assert calls[0]["initial_prior"] is not None
    assert calls[1]["initial_prior"] is None
    assert calls[1]["previous_posterior"] is b4d_results[0].final_posterior
    assert calls[1]["initial_state"] is b4d_results[0].final_state
    assert calls[1]["continuation_from_symbol_index"] == 5
    assert calls[1]["continuation_from_estimator_time_index"] == 29
    assert calls[1]["initial_state"].time_index == 30
    assert calls[2]["continuation_from_symbol_index"] == 6
    assert len(viterbi_calls) == 1
    np.testing.assert_array_equal(viterbi_calls[0], result.candidate_metrics)


@pytest.mark.parametrize("corrupt", ["state", "time"])
def test_invalid_continuation_state_or_clock_is_rejected(
    monkeypatch: pytest.MonkeyPatch, corrupt: str
) -> None:
    received = _noiseless_received(_input_pairs(3), 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=2,
        symbol_origin=13,
        initial_time=40,
    )
    original = segmented.run_reconstruction_posterior_estimator_sequence

    def corrupt_continuation(**kwargs: object):
        if kwargs["run_mode"] == "continuation":
            if corrupt == "time":
                kwargs["continuation_from_estimator_time_index"] += 1
            else:
                state = kwargs["initial_state"]
                kwargs["initial_state"] = ReconstructionEstimatorState(
                    state.fluctuating_iq,
                    state.full_iq,
                    state.time_index + 1,
                )
        return original(**kwargs)

    monkeypatch.setattr(
        segmented, "run_reconstruction_posterior_estimator_sequence", corrupt_continuation
    )
    with pytest.raises(ValueError, match="time_index|preceding estimator time"):
        _run_segmented(operands, (1, 2))


@pytest.mark.parametrize(
    "segments",
    [
        (),
        ("empty",),
    ],
)
def test_invalid_segment_collection_rejected(segments: tuple[object, ...]) -> None:
    received = _noiseless_received(_input_pairs(1), 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=0,
        symbol_origin=0,
        initial_time=0,
    )
    public = {key: value for key, value in operands.items() if not key.startswith("_")}
    with pytest.raises(ValueError):
        segmented.decode_reconstruction_segmented_sequence(
            **public,
            initial_encoder_state=INITIAL_STATE,
            segments=segments,
        )


def test_zero_length_segment_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="symbol_count"):
        segmented.ReconstructionSequenceSegment(
            first_symbol_index=0,
            received_start_offset=0,
            symbol_count=0,
        )


def test_gapped_overlapping_duplicate_and_wrong_origin_segments_rejected() -> None:
    received = _noiseless_received(_input_pairs(4), 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=2,
        symbol_origin=17,
        initial_time=80,
    )
    public = {key: value for key, value in operands.items() if not key.startswith("_")}
    bad_layouts = (
        (
            segmented.ReconstructionSequenceSegment(2, 0, 1),
            segmented.ReconstructionSequenceSegment(4, 8, 3),
        ),
        (
            segmented.ReconstructionSequenceSegment(2, 0, 2),
            segmented.ReconstructionSequenceSegment(4, 8, 2),
        ),
        (
            segmented.ReconstructionSequenceSegment(2, 0, 2),
            segmented.ReconstructionSequenceSegment(3, 16, 2),
        ),
        (segmented.ReconstructionSequenceSegment(3, 0, 4),),
    )
    for layout in bad_layouts:
        with pytest.raises(ValueError):
            segmented.decode_reconstruction_segmented_sequence(
                **public,
                initial_encoder_state=INITIAL_STATE,
                segments=layout,
            )


def test_incomplete_received_buffer_and_noncontiguous_absolute_labels_rejected() -> None:
    received = _noiseless_received(_input_pairs(2), 0.75)
    operands = _base_operands(
        received=received,
        coefficient=0.75,
        first_symbol=1,
        symbol_origin=5,
        initial_time=9,
    )
    public = {key: value for key, value in operands.items() if not key.startswith("_")}
    segments = _partition((2,), 1)
    with pytest.raises(ValueError, match="8 samples"):
        segmented.decode_reconstruction_segmented_sequence(
            **dict(public, received=received[:-1], absolute_sample_indices=np.arange(15)),
            initial_encoder_state=INITIAL_STATE,
            segments=segments,
        )
    broken_labels = np.asarray(public["absolute_sample_indices"]).copy()
    broken_labels[8] += 1
    with pytest.raises(ValueError, match="contiguous"):
        segmented.decode_reconstruction_segmented_sequence(
            **dict(public, absolute_sample_indices=broken_labels),
            initial_encoder_state=INITIAL_STATE,
            segments=segments,
        )


def test_result_and_inputs_are_immutable_and_calls_are_deterministic() -> None:
    received = _noiseless_received(_input_pairs(4), 2.0)
    original_received = received.copy()
    operands = _base_operands(
        received=received,
        coefficient=2.0,
        first_symbol=7,
        symbol_origin=31,
        initial_time=103,
    )
    original_state = operands["initial_estimator_state"]
    original_full = original_state.full_iq.copy()
    first = _run_segmented(operands, (1, 3))
    second = _run_segmented(operands, (1, 3))

    np.testing.assert_array_equal(received, original_received)
    np.testing.assert_array_equal(original_state.full_iq, original_full)
    assert first.decoded_hypothesis_path == second.decoded_hypothesis_path
    np.testing.assert_array_equal(first.candidate_metrics, second.candidate_metrics)
    np.testing.assert_array_equal(first.posterior_history, second.posterior_history)
    with pytest.raises(ValueError):
        first.candidate_metrics[0, 0] = 1.0
    with pytest.raises(ValueError):
        first.posterior_history[0, 0] = 0.0


def test_no_truth_runtime_parameter_and_ast_boundary() -> None:
    signature = inspect.signature(segmented.decode_reconstruction_segmented_sequence)
    assert not any("truth" in name.lower() for name in signature.parameters)
    tree = ast.parse(inspect.getsource(segmented))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "ChannelTruth" not in names | attrs
    assert "ChannelOutput" not in names | attrs
    assert not any("hf_tcm.channel" in module for module in imports)
