import math
from dataclasses import replace

import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.modulation.labeling import BASELINE_ASSUMPTION, label_to_index
from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
    output_bits_to_phase_index,
)

GOLDEN_LABELS = (
    ((0, 0, 0), 0),
    ((0, 0, 1), 1),
    ((0, 1, 0), 2),
    ((0, 1, 1), 3),
    ((1, 0, 0), 4),
    ((1, 0, 1), 5),
    ((1, 1, 0), 6),
    ((1, 1, 1), 7),
)


def map_output(bits: tuple[int, int, int]) -> int:
    return output_bits_to_phase_index(
        bits,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )


def test_all_output_triples_match_natural_binary_golden_table() -> None:
    for bits, expected_b in GOLDEN_LABELS:
        assert map_output(bits) == expected_b


def test_mapping_is_consistent_with_explicit_m1_baseline() -> None:
    for bits, _ in GOLDEN_LABELS:
        assert map_output(bits) == label_to_index(bits, profile=BASELINE_ASSUMPTION)


def test_all_sixteen_hypotheses_map_via_output_bits_only() -> None:
    assert len(HYPOTHESES) == 16
    for hypothesis in HYPOTHESES:
        expected_b = (
            4 * hypothesis.output_bits[0]
            + 2 * hypothesis.output_bits[1]
            + hypothesis.output_bits[2]
        )
        assert (
            hypothesis_to_phase_index(
                hypothesis,
                profile=ASSUMED_NATURAL_BINARY,
                bit_order=OUTPUT_BIT_ORDER,
            )
            == expected_b
        )


def test_hypothesis_order_does_not_change_mapping_for_same_output_bits() -> None:
    forward = {
        hypothesis.output_bits: hypothesis_to_phase_index(
            hypothesis,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for hypothesis in HYPOTHESES
    }
    backward = {
        hypothesis.output_bits: hypothesis_to_phase_index(
            hypothesis,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        for hypothesis in reversed(HYPOTHESES)
    }
    assert backward == forward


def test_hypothesis_id_does_not_participate_in_phase_mapping() -> None:
    hypothesis = HYPOTHESES[0]
    changed_id = replace(hypothesis, hypothesis_id=987654)
    assert hypothesis_to_phase_index(
        hypothesis,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    ) == hypothesis_to_phase_index(
        changed_id,
        profile=ASSUMED_NATURAL_BINARY,
        bit_order=OUTPUT_BIT_ORDER,
    )


def test_each_phase_index_is_accepted_by_iq_prediction() -> None:
    expected = (
        (0.0, 1.0),
        (-math.sqrt(2.0) / 2.0, math.sqrt(2.0) / 2.0),
        (-1.0, 0.0),
        (-math.sqrt(2.0) / 2.0, -math.sqrt(2.0) / 2.0),
        (0.0, -1.0),
        (math.sqrt(2.0) / 2.0, -math.sqrt(2.0) / 2.0),
        (1.0, 0.0),
        (math.sqrt(2.0) / 2.0, math.sqrt(2.0) / 2.0),
    )
    for bits, b in GOLDEN_LABELS:
        result = iq_quadratures_from_index(map_output(bits), 1.0, 1.0)
        assert result == pytest.approx(expected[b], abs=1e-15)


@pytest.mark.parametrize("bits", [(0, 1), (0, 1, 1, 0), (0, 1, 2), (0, True, 1), (0.0, 0, 1)])
def test_invalid_output_bits_are_rejected(bits: object) -> None:
    with pytest.raises(ValueError, match="exactly three integer bits"):
        output_bits_to_phase_index(
            bits,  # type: ignore[arg-type]
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )


def test_profile_and_bit_order_must_be_explicitly_supported() -> None:
    with pytest.raises(ValueError, match="profile"):
        output_bits_to_phase_index(
            (0, 0, 0), profile="baseline_assumption", bit_order=OUTPUT_BIT_ORDER
        )
    with pytest.raises(ValueError, match="bit_order"):
        output_bits_to_phase_index(
            (0, 0, 1), profile=ASSUMED_NATURAL_BINARY, bit_order=("c0", "c1", "c2")
        )


def test_hypothesis_adapter_rejects_non_hypothesis_values() -> None:
    with pytest.raises(TypeError, match="Hypothesis"):
        hypothesis_to_phase_index(
            object(),  # type: ignore[arg-type]
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
