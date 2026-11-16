import inspect

import numpy as np
import pytest

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
from hf_tcm.receiver.reconstruction_posterior_estimator_step import (
    process_reconstruction_posterior_estimator_step,
)


def _operands(
    received: np.ndarray,
    *,
    state: ReconstructionEstimatorState,
    origin: int,
    first_symbol: int,
    symbol_indices: tuple[int, ...],
    sequence_origin_symbol: int | None = None,
    estimator_time: int | None = None,
    mode: str = "new_independent_sequence",
    prior: np.ndarray | None = None,
    previous: np.ndarray | None = None,
    previous_symbol: int | None = None,
    previous_time: int | None = None,
    alpha: float | tuple[float, ...] = 0.35,
    k_tilde: object = ((0.25, 0.4),),
    mu0: object = ((0.1, -0.2),),
    beta: float = 0.8,
) -> dict[str, object]:
    first_sample = origin + 8 * first_symbol
    return {
        "received": received,
        "absolute_sample_indices": np.arange(first_sample, first_sample + received.size),
        "received_start_sample": first_sample,
        "symbol_origin_sample": origin,
        "first_symbol_index": first_symbol,
        "sequence_origin_symbol_index": (
            first_symbol if sequence_origin_symbol is None else sequence_origin_symbol
        ),
        "symbol_count": len(symbol_indices),
        "symbol_indices": symbol_indices,
        "initial_state": state,
        "initial_estimator_time_index": (
            state.time_index if estimator_time is None else estimator_time
        ),
        "run_mode": mode,
        "initial_prior": (
            build_initial_reconstruction_prior(initial_state=(0, 0))
            if mode == "new_independent_sequence" and prior is None
            else prior
        ),
        "previous_posterior": previous,
        "continuation_from_symbol_index": previous_symbol,
        "continuation_from_estimator_time_index": previous_time,
        "beta": beta,
        "alpha_prime": alpha,
        "k_tilde": k_tilde,
        "mu0": mu0,
        "include_history": True,
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
    }


def _received_sequence(count: int, *, origin: int = 0, first_symbol: int = 0) -> np.ndarray:
    _ = origin, first_symbol
    samples = []
    for symbol in range(count):
        phase = (symbol * 3 + 1) % 8
        angle = phase * np.pi / 4.0
        z = 0.8 * np.cos(angle) + 1j * 0.8 * np.sin(angle)
        samples.extend(z + complex(0.007 * k, -0.013 * k) for k in range(8))
    return np.asarray(samples, dtype=np.complex128)


def _manual_chain(args: dict[str, object]):
    state = args["initial_state"]
    posterior = args["initial_prior"]
    results = []
    received = args["received"]
    origin = args["symbol_origin_sample"]
    initial_time = args["initial_estimator_time_index"]
    for offset, symbol in enumerate(args["symbol_indices"]):
        start = origin + symbol * 8
        prefix_count = (offset + 1) * 8
        prefix = received[:prefix_count]
        result = process_reconstruction_posterior_estimator_step(
            received=prefix,
            absolute_sample_indices=np.arange(args["received_start_sample"], start + 8),
            received_start_sample=args["received_start_sample"],
            symbol_origin_sample=origin,
            target_symbol_index=symbol,
            state=state,
            time_index=initial_time + offset,
            edge_mode="first_edge" if offset == 0 else "later_edge",
            initial_prior=args["initial_prior"] if offset == 0 else None,
            previous_posterior=None if offset == 0 else posterior,
            beta=args["beta"],
            alpha_prime=(
                args["alpha_prime"]
                if isinstance(args["alpha_prime"], float)
                else args["alpha_prime"][offset]
            ),
            k_tilde=(
                args["k_tilde"]
                if np.asarray(args["k_tilde"]).shape == (1, 2)
                else np.asarray(args["k_tilde"])[offset]
            ),
            mu0=(
                args["mu0"]
                if np.asarray(args["mu0"]).shape == (1, 2)
                else np.asarray(args["mu0"])[offset]
            ),
            prediction_data_cutoff_sample=start - 1,
            posterior_data_cutoff_sample=start + 7,
            profile=args["profile"],
            adr_profile=args["adr_profile"],
            path_count=args["path_count"],
            path_delays_samples=args["path_delays_samples"],
            samples_per_symbol=args["samples_per_symbol"],
            iq_rule=args["iq_rule"],
            waveform_rule=args["waveform_rule"],
            labeling_profile=args["labeling_profile"],
            bit_order=args["bit_order"],
            timebase_profile=args["timebase_profile"],
            symbol_to_sample_rule=args["symbol_to_sample_rule"],
            edge_policy=args["edge_policy"],
        )
        results.append(result)
        state = result.next_state
        posterior = result.posterior
    return tuple(results)


@pytest.mark.parametrize("count", [2, 3])
def test_runner_matches_manual_b4c_chain_for_two_and_three_symbols(count: int) -> None:
    origin = 19
    first_symbol = 3
    state = ReconstructionEstimatorState([[0.15, -0.2]], [[0.6, 0.75]], 72)
    received = _received_sequence(count, origin=origin, first_symbol=first_symbol)
    symbols = tuple(range(first_symbol, first_symbol + count))
    args = _operands(
        received,
        state=state,
        origin=origin,
        first_symbol=first_symbol,
        symbol_indices=symbols,
    )
    expected_steps = _manual_chain(args)
    result = run_reconstruction_posterior_estimator_sequence(**args)
    np.testing.assert_array_equal(
        result.final_state.fluctuating_iq, expected_steps[-1].next_state.fluctuating_iq
    )
    np.testing.assert_array_equal(result.final_state.full_iq, expected_steps[-1].next_state.full_iq)
    assert result.final_state.time_index == expected_steps[-1].next_state.time_index
    np.testing.assert_allclose(result.final_posterior, expected_steps[-1].posterior)
    assert result.history is not None
    for index, (entry, expected) in enumerate(zip(result.history, expected_steps, strict=True)):
        assert entry.symbol_index == symbols[index]
        assert entry.estimator_time_index == state.time_index + index
        assert entry.first_sample_index == origin + 8 * symbols[index]
        assert entry.last_sample_index == origin + 8 * symbols[index] + 7
        assert expected.prediction_data_cutoff_sample == entry.first_sample_index - 1
        assert expected.posterior_data_cutoff_sample == entry.last_sample_index
        assert entry.b4c_result.edge_mode == ("first_edge" if index == 0 else "later_edge")
        np.testing.assert_allclose(entry.b4c_result.posterior, expected.posterior)
        assert np.isclose(entry.b4c_result.posterior.sum(), 1.0)
        assert entry.b4c_result.hypothesis_ids == tuple(range(16))
    assert result.final_symbol_index == symbols[-1]
    assert result.final_estimator_time_index == state.time_index + count
    assert result.next_symbol_index == symbols[-1] + 1


def test_mu0_schedule_beta_sensitivity_and_state_handoff() -> None:
    count = 3
    state = ReconstructionEstimatorState([[0.2, -0.1]], [[0.4, 0.3]], 8)
    received = _received_sequence(count)
    params = _operands(
        received,
        state=state,
        origin=0,
        first_symbol=0,
        symbol_indices=(0, 1, 2),
        alpha=(0.2, 0.5, 1.0),
        k_tilde=np.array([[[0.1, 0.2]], [[0.3, -0.1]], [[0.25, 0.4]]]),
        mu0=np.array([[[0.0, 0.0]], [[0.1, -0.2]], [[0.5, 0.25]]]),
    )
    result = run_reconstruction_posterior_estimator_sequence(**params)
    assert result.history is not None
    assert not np.array_equal(
        result.history[0].b4c_result.next_state.full_iq,
        result.history[1].b4c_result.next_state.full_iq,
    )
    assert (
        result.history[1].b4c_result.next_state.time_index
        == result.history[0].b4c_result.next_state.time_index + 1
    )
    params["beta"] = 0.15
    different_beta = run_reconstruction_posterior_estimator_sequence(**params)
    assert not np.allclose(result.final_posterior, different_beta.final_posterior)


def test_split_continuation_matches_one_uninterrupted_run() -> None:
    origin = 13
    state0 = ReconstructionEstimatorState([[0.0, 0.0]], [[0.8, 0.7]], 50)
    received = _received_sequence(3, origin=origin)
    full_args = _operands(
        received,
        state=state0,
        origin=origin,
        first_symbol=0,
        symbol_indices=(0, 1, 2),
    )
    full = run_reconstruction_posterior_estimator_sequence(**full_args)

    first_args = _operands(
        received[:8],
        state=state0,
        origin=origin,
        first_symbol=0,
        symbol_indices=(0,),
    )
    first = run_reconstruction_posterior_estimator_sequence(**first_args)
    continuation_args = _operands(
        received[8:],
        state=first.final_state,
        origin=origin,
        first_symbol=1,
        symbol_indices=(1, 2),
        sequence_origin_symbol=0,
        mode="continuation",
        prior=None,
        previous=first.final_posterior,
        previous_symbol=0,
        previous_time=50,
    )
    continuation = run_reconstruction_posterior_estimator_sequence(**continuation_args)
    np.testing.assert_array_equal(
        full.final_state.fluctuating_iq, continuation.final_state.fluctuating_iq
    )
    np.testing.assert_array_equal(full.final_state.full_iq, continuation.final_state.full_iq)
    np.testing.assert_allclose(full.final_posterior, continuation.final_posterior)
    assert continuation.history is not None
    assert all(item.b4c_result.edge_mode == "later_edge" for item in continuation.history)


def test_future_symbols_do_not_change_earlier_history_and_restarts_are_deterministic() -> None:
    state = ReconstructionEstimatorState([[0.1, -0.1]], [[0.5, 0.4]], 3)
    received = _received_sequence(2)
    args = _operands(
        received,
        state=state,
        origin=0,
        first_symbol=0,
        symbol_indices=(0, 1),
    )
    baseline = run_reconstruction_posterior_estimator_sequence(**args)
    changed = received.copy()
    changed[8:] += 0.75 - 1.25j
    args_changed = _operands(
        changed,
        state=state,
        origin=0,
        first_symbol=0,
        symbol_indices=(0, 1),
    )
    changed_result = run_reconstruction_posterior_estimator_sequence(**args_changed)
    assert baseline.history is not None and changed_result.history is not None
    np.testing.assert_array_equal(
        baseline.history[0].b4c_result.posterior,
        changed_result.history[0].b4c_result.posterior,
    )
    invalid = changed.copy()
    invalid[-1] = np.inf + 0j
    invalid_args = _operands(
        invalid,
        state=state,
        origin=0,
        first_symbol=0,
        symbol_indices=(0, 1),
    )
    with pytest.raises(ValueError, match="finite"):
        run_reconstruction_posterior_estimator_sequence(**invalid_args)

    again = run_reconstruction_posterior_estimator_sequence(**args)
    assert baseline.history is not None and again.history is not None
    np.testing.assert_array_equal(
        baseline.history[0].b4c_result.posterior, again.history[0].b4c_result.posterior
    )
    np.testing.assert_array_equal(baseline.final_state.full_iq, again.final_state.full_iq)
    np.testing.assert_array_equal(received, _received_sequence(2))
    np.testing.assert_array_equal(state.full_iq, [[0.5, 0.4]])


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"symbol_indices": (0, 2)}, "contiguous"),
        ({"symbol_indices": (0, 0)}, "contiguous"),
        ({"sequence_origin_symbol_index": 1}, "sequence_origin_symbol_index"),
        ({"received": np.zeros(15, dtype=np.complex128)}, "exactly 8 samples per requested symbol"),
        ({"received_start_sample": 1}, "start at sample"),
        ({"initial_estimator_time_index": 1}, "initial state time_index"),
        ({"initial_prior": None}, "initial_prior"),
        ({"initial_prior": np.full(16, 1 / 16)}, "ADR-004"),
        ({"alpha_prime": (0.1,)}, "one value per symbol"),
        ({"mu0": np.zeros((2, 2, 2))}, "shape"),
    ],
)
def test_new_independent_sequence_rejects_bad_schedule_or_operands(override, message) -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 6)
    received = _received_sequence(2)
    args = _operands(
        received,
        state=state,
        origin=0,
        first_symbol=0,
        symbol_indices=(0, 1),
    )
    args.update(override)
    with pytest.raises(ValueError, match=message):
        run_reconstruction_posterior_estimator_sequence(**args)


def test_continuation_requires_adjacent_prior_edge_and_state_clocks() -> None:
    state = ReconstructionEstimatorState([[0.0, 0.0]], [[1.0, 1.0]], 20)
    received = _received_sequence(1, first_symbol=1)
    args = _operands(
        received,
        state=state,
        origin=0,
        first_symbol=1,
        symbol_indices=(1,),
        sequence_origin_symbol=0,
        mode="continuation",
        prior=None,
        previous=np.full(16, 1 / 16),
        previous_symbol=0,
        previous_time=18,
    )
    with pytest.raises(
        ValueError, match=r"state time_index must equal preceding estimator time \+ 1"
    ):
        run_reconstruction_posterior_estimator_sequence(**args)
    args["continuation_from_estimator_time_index"] = 19
    args["continuation_from_symbol_index"] = 3
    with pytest.raises(ValueError, match="immediately follow"):
        run_reconstruction_posterior_estimator_sequence(**args)


def test_truth_operands_are_not_part_of_runner_api() -> None:
    parameters = inspect.signature(run_reconstruction_posterior_estimator_sequence).parameters
    assert not {
        "truth",
        "channel_truth",
        "transmitted_bits",
        "true_b",
        "true_channel_coefficient",
        "posterior_sequence",
    }.intersection(parameters)
