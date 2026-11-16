"""M4.1: exhaustive discrete hypothesis space based on the M1 trellis."""

from hf_tcm.coding.encoder import encode_step
from hf_tcm.coding.hypotheses import (
    HYPOTHESES,
    Hypothesis,
    build_hypotheses,
    is_allowed_transition,
)
from hf_tcm.coding.trellis import INPUT_PAIRS, STATES, build_trellis


def test_hypothesis_table_has_all_sixteen_state_input_combinations() -> None:
    hypotheses = build_hypotheses()

    assert len(hypotheses) == 16
    assert len({hypothesis.hypothesis_id for hypothesis in hypotheses}) == 16
    assert [hypothesis.hypothesis_id for hypothesis in hypotheses] == list(range(16))
    assert {(hypothesis.current_state, hypothesis.input_bits) for hypothesis in hypotheses} == {
        (state, bits) for state in STATES for bits in INPUT_PAIRS
    }
    assert HYPOTHESES == hypotheses


def test_hypotheses_follow_generator_matrix_gx() -> None:
    # G(x) = [[1, 0, 0], [0, 1 + x^2, x]], with state
    # (u1[k-1], u1[k-2]) and output order (c2, c1, c0).
    for hypothesis in HYPOTHESES:
        (u0, u1), (u1_k_minus_1, u1_k_minus_2) = (
            hypothesis.input_bits,
            hypothesis.current_state,
        )
        assert hypothesis.output_bits == (
            u0,
            u1 ^ u1_k_minus_2,
            u1_k_minus_1,
        )
        assert hypothesis.next_state == (u1, u1_k_minus_1)


def test_hypotheses_match_trellis_and_encoder_for_every_branch() -> None:
    branches = build_trellis()
    assert len(branches) == len(HYPOTHESES)

    for hypothesis, branch in zip(HYPOTHESES, branches, strict=True):
        assert isinstance(hypothesis, Hypothesis)
        assert hypothesis.current_state == branch.state
        assert hypothesis.input_bits == branch.input_pair
        assert hypothesis.output_bits == branch.output
        assert hypothesis.next_state == branch.next_state
        assert encode_step(hypothesis.input_bits, hypothesis.current_state) == (
            hypothesis.output_bits,
            hypothesis.next_state,
        )


def test_transition_validator_accepts_only_encoder_allowed_transitions() -> None:
    for hypothesis in HYPOTHESES:
        assert is_allowed_transition(
            hypothesis.current_state,
            hypothesis.input_bits,
            hypothesis.next_state,
        )
        other_states = [state for state in STATES if state != hypothesis.next_state]
        assert all(
            not is_allowed_transition(
                hypothesis.current_state,
                hypothesis.input_bits,
                state,
            )
            for state in other_states
        )


def test_hypothesis_order_is_deterministic() -> None:
    assert build_hypotheses() == build_hypotheses()
