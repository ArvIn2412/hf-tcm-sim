"""T-02: exhaustive encoder/trellis transition consistency."""

from hf_tcm.coding.encoder import encode_step
from hf_tcm.coding.trellis import INPUT_PAIRS, STATES, build_trellis


def test_trellis_has_one_transition_for_every_state_and_input() -> None:
    transitions = build_trellis()

    assert len(transitions) == 4 * 4
    assert {(branch.state, branch.input_pair) for branch in transitions} == {
        (state, input_pair) for state in STATES for input_pair in INPUT_PAIRS
    }


def test_trellis_transitions_match_encoder() -> None:
    for branch in build_trellis():
        expected_output, expected_state = encode_step(branch.input_pair, branch.state)
        assert branch.output == expected_output
        assert branch.next_state == expected_state


def test_u0_changes_only_c2_and_does_not_change_next_state() -> None:
    for state in STATES:
        for u1 in (0, 1):
            first, second = (
                next(
                    branch
                    for branch in build_trellis()
                    if branch.state == state and branch.input_pair == (u0, u1)
                )
                for u0 in (0, 1)
            )
            assert first.output[0] != second.output[0]
            assert first.output[1:] == second.output[1:]
            assert first.next_state == second.next_state
