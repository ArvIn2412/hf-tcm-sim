from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest

from hf_tcm.coding.encoder import encode
from hf_tcm.evaluation.error_metrics import (
    ErrorAggregate,
    ErrorCounts,
    aggregate_error_counts,
    calculate_ber_ser,
    count_bit_errors,
    count_symbol_errors,
    decoded_path_symbol_indices,
    encode_reference_symbol_indices,
    evaluate_run,
)
from hf_tcm.modulation.labeling import index_to_label
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    output_bits_to_phase_index,
)


@pytest.mark.parametrize("symbols", [1, 2, 4, 6])
def test_zero_errors_for_valid_rate_two_thirds_run(symbols: int) -> None:
    bits = np.asarray(([0, 1, 1, 0] * symbols)[: 2 * symbols], dtype=np.int8)
    pairs = bits.reshape(symbols, 2)
    output_bits = encode(pairs.tolist())
    symbol_indices = np.asarray(
        [
            output_bits_to_phase_index(
                output,
                profile=ASSUMED_NATURAL_BINARY,
                bit_order=OUTPUT_BIT_ORDER,
            )
            for output in output_bits
        ],
        dtype=np.int64,
    )

    evaluation = evaluate_run(bits, bits.copy(), symbol_indices, symbol_indices.copy())

    assert evaluation.counts == ErrorCounts(0, 2 * symbols, 0, symbols)
    assert evaluation.ber == 0.0
    assert evaluation.ser == 0.0


def test_bit_and_coded_symbol_errors_are_independent_counts() -> None:
    assert count_bit_errors([0, 0, 1, 1], [1, 1, 1, 1]) == 2
    assert count_symbol_errors([0, 1], [0, 7]) == 1
    result = evaluate_run([0, 0, 1, 1], [1, 1, 1, 1], [0, 1], [0, 7])
    assert (result.counts.bit_errors, result.counts.symbol_errors) == (2, 1)
    assert (result.ber, result.ser) == (0.5, 0.5)


def test_all_wrong_counts_and_rate_denominators() -> None:
    result = evaluate_run([0, 0], [1, 1], [0], [1])
    assert result.counts == ErrorCounts(2, 2, 1, 1)
    assert (result.ber, result.ser) == (1.0, 1.0)


def test_pooled_aggregation_uses_counts_not_mean_run_rates() -> None:
    short = ErrorCounts(bit_errors=1, total_bits=2, symbol_errors=1, total_symbols=1)
    long = ErrorCounts(bit_errors=0, total_bits=6, symbol_errors=0, total_symbols=3)

    pooled = aggregate_error_counts([short, long])
    rates = calculate_ber_ser(pooled)

    assert pooled.counts == ErrorCounts(1, 8, 1, 4)
    assert pooled.run_counts == (short, long)
    assert rates.ber == pytest.approx(1 / 8)
    assert rates.ser == pytest.approx(1 / 4)
    assert rates.ber != pytest.approx((0.5 + 0.0) / 2)


def test_reference_and_decoded_symbol_mapping_use_output_bits() -> None:
    labels = [index_to_label(index) for index in range(8)]
    # For each output triple, find an M1 edge that emits it, then verify the
    # reconstruction mapping covers all eight labels in the expected order.
    from hf_tcm.coding.hypotheses import HYPOTHESES

    mapped = {
        output_bits_to_phase_index(
            hypothesis.output_bits,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for hypothesis in HYPOTHESES
    }
    assert mapped == set(range(8))
    assert [label for label in labels] == [tuple(map(int, f"{i:03b}")) for i in range(8)]
    for index, label in enumerate(labels):
        assert (
            output_bits_to_phase_index(
                label,
                profile=ASSUMED_NATURAL_BINARY,
                bit_order=OUTPUT_BIT_ORDER,
            )
            == index
        )

    information_bits = [0, 0, 0, 1, 1, 0]
    expected = [
        output_bits_to_phase_index(
            output,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for output in encode(np.asarray(information_bits).reshape(-1, 2).tolist())
    ]
    assert (
        encode_reference_symbol_indices(
            information_bits,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        ).tolist()
        == expected
    )

    path_ids = [
        hypothesis.hypothesis_id for hypothesis in HYPOTHESES if hypothesis.current_state == (0, 0)
    ][:1]
    edge = HYPOTHESES[path_ids[0]]
    assert decoded_path_symbol_indices(
        path_ids,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    ).tolist() == [
        output_bits_to_phase_index(
            edge.output_bits,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
    ]


@pytest.mark.parametrize(
    ("reference", "decoded"),
    [([0], [0, 1]), ([0, 1], [0]), ([], [])],
)
def test_bit_count_rejects_length_mismatch_or_empty(reference, decoded) -> None:
    with pytest.raises(ValueError):
        count_bit_errors(reference, decoded)


@pytest.mark.parametrize("values", [[0, 2], [0, -1], [0.0, 1.0], [[0, 1]]])
def test_bit_count_rejects_invalid_values_and_shapes(values) -> None:
    with pytest.raises(ValueError):
        count_bit_errors(values, values)


@pytest.mark.parametrize("values", [[0, 8], [-1], [1.0], [[1]]])
def test_symbol_count_rejects_invalid_values_and_shapes(values) -> None:
    with pytest.raises(ValueError):
        count_symbol_errors(values, values)


def test_evaluation_rejects_unequal_or_rate_inconsistent_lengths() -> None:
    with pytest.raises(ValueError):
        evaluate_run([0, 1], [0, 1], [0, 1], [0])
    with pytest.raises(ValueError):
        evaluate_run([0, 1, 1], [0, 1, 1], [0], [0])


def test_aggregation_rejects_empty_and_inconsistent_run_counts() -> None:
    with pytest.raises(ValueError):
        aggregate_error_counts([])
    with pytest.raises(ValueError):
        ErrorCounts(bit_errors=0, total_bits=3, symbol_errors=0, total_symbols=1)
    with pytest.raises(ValueError):
        ErrorAggregate(run_counts=(ErrorCounts(0, 2, 0, 1),), counts=ErrorCounts(1, 2, 1, 1))


def test_inputs_are_unchanged_and_results_are_deterministic() -> None:
    reference = np.asarray([0, 1, 1, 0], dtype=np.int8)
    decoded = np.asarray([0, 0, 1, 0], dtype=np.int8)
    symbols = np.asarray([1, 2], dtype=np.int64)
    originals = (reference.copy(), decoded.copy(), symbols.copy())

    first = evaluate_run(reference, decoded, symbols, symbols)
    second = evaluate_run(reference, decoded, symbols, symbols)

    assert first == second
    for actual, original in zip((reference, decoded, symbols), originals, strict=True):
        np.testing.assert_array_equal(actual, original)


def test_evaluation_module_has_no_channel_truth_dependency() -> None:
    source = inspect.getsource(__import__("hf_tcm.evaluation.error_metrics", fromlist=["*"]))
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "ChannelTruth" not in names | attributes
    assert "truth" not in {name.lower() for name in names | attributes}
