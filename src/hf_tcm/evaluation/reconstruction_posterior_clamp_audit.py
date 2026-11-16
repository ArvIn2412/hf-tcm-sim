"""Evaluation-only same-state posterior swap and multistep posterior clamp."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.evaluation.reconstruction_factorial_ablation import FACTORIAL_ARMS
from hf_tcm.evaluation.reconstruction_multistep_feedback_audit import (
    deterministic_feedback_fixture,
)
from hf_tcm.receiver.paper_recursion import update_quadrature_estimates
from hf_tcm.receiver.reconstruction_alignment import ZERO_PADDING
from hf_tcm.receiver.reconstruction_candidate_metrics import (
    generate_reconstruction_candidate_metrics,
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
    extract_adr012_observed_iq,
)
from hf_tcm.receiver.reconstruction_posterior import (
    build_initial_reconstruction_prior,
    build_reconstruction_transition_matrix,
    initial_reconstruction_observation_update,
    transition_reconstruction_posterior,
)

M6G_FIXTURE_SHA256 = "99df8784d417cd9d615c389d088f717f0735f4af6accb282fcff82a547629969"
_EXPECTED_M6G_TRACE_SHA256 = "67a48243f4fd43a104584004ec98f5aa7c2a08c6b3b14aed20372fc8e3426a75"
_EXPECTED_M6G_SCHEMA = "m6g.feedback-trace.v1"
_ARMS = ("B", "A", "K", "C")
_BETA = 0.7
_MU0 = np.zeros(2, dtype=np.float64)
_INITIAL = np.asarray([0.42, 0.91], dtype=np.float64)
_ATOL = 1e-10


def _weighted_innovation(
    posterior: NDArray[np.float64], observed: NDArray[np.float64], predicted: NDArray[np.float64]
) -> NDArray[np.float64]:
    return np.asarray(
        [
            math.fsum(
                float(posterior[h]) * (float(observed[j]) - float(predicted[h, j]))
                for h in range(16)
            )
            for j in range(2)
        ],
        dtype=np.float64,
    )


def _sum(values: NDArray[np.float64]) -> float:
    return math.fsum(float(value) for value in values)


def _validate_vector(value: object, shape: tuple[int, ...], name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return array


def _read_m6g_trace(path: str | Path) -> tuple[dict[str, object], str]:
    target = Path(path)
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != _EXPECTED_M6G_TRACE_SHA256:
        raise ValueError("M6g source trace SHA-256 differs from its recorded baseline")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("M6g source trace is not valid UTF-8 JSON") from exc
    if payload.get("schema_version") != _EXPECTED_M6G_SCHEMA:
        raise ValueError("unsupported M6g source trace schema")
    if payload.get("fixture_sha256") != M6G_FIXTURE_SHA256:
        raise ValueError("M6g fixture provenance does not match the recorded M6g fixture")
    if payload.get("received_sample_count") != 64 or tuple(payload["closed_loop"]["arms"]) != _ARMS:
        raise ValueError("M6g source trace has an unexpected sample count or arm order")
    if tuple(payload["common_operand"]["arms"]) != _ARMS:
        raise ValueError("M6g common-operand arm order is not canonical")
    expected_parameters = {
        "B": (1.0, (0.0, 0.0)),
        "A": (0.85, (0.0, 0.0)),
        "K": (1.0, (0.35, -0.2)),
        "C": (0.85, (0.35, -0.2)),
    }
    for arm in _ARMS:
        for regime in ("closed_loop", "common_operand"):
            record = payload[regime]["arms"][arm]
            if (record["alpha_prime"], tuple(record["k_tilde"])) != expected_parameters[arm]:
                raise ValueError("M6g arm policy differs from the fixed M6f/M6g policy")
            rows = record.get("rows")
            if len(rows) != 8 or len(record.get("frozen_metric_matrix", [])) != 8:
                raise ValueError("M6g trace must contain eight symbol rows per arm")
            for f, row in enumerate(rows):
                if (
                    row["symbol_position"] != f
                    or row["symbol_index"] != f
                    or row["estimator_time_index"] != f
                    or row["sample_window"] != list(range(8 * f, 8 * f + 8))
                    or row["prediction_cutoff_sample"] != 8 * f - 1
                    or row["observation_cutoff_sample"] != 8 * f + 7
                    or row["hypothesis_ids"] != list(range(16))
                ):
                    raise ValueError("M6g row clocks or canonical hypothesis order are invalid")
                posterior = np.asarray(row["posterior"], dtype=np.float64)
                if (
                    posterior.shape != (16,)
                    or not np.all(np.isfinite(posterior))
                    or np.any(posterior < 0)
                ):
                    raise ValueError("M6g posterior must be finite and shape (16,)")
                if not math.isclose(_sum(posterior), 1.0, rel_tol=0.0, abs_tol=1e-12):
                    raise ValueError("M6g posterior is not normalized")
                _validate_vector(row["metrics"], (16,), "M6g metrics")
                _validate_vector(row["predictions"], (16, 2), "M6g predictions")
        if payload["closed_loop"]["arms"][arm]["rows"][0]["edge_mode"] != "first_edge":
            raise ValueError("M6g first symbol must use ADR-004 first-edge policy")
        if any(
            row["edge_mode"] != "later_edge"
            for row in payload["closed_loop"]["arms"][arm]["rows"][1:]
        ):
            raise ValueError("M6g continuation rows must use the transition policy")
    return payload, digest


def _observations(received: NDArray[np.complex128]) -> tuple[NDArray[np.float64], ...]:
    labels = np.arange(64, dtype=np.int64)
    return tuple(
        np.asarray(
            extract_adr012_observed_iq(
                received,
                absolute_sample_indices=labels,
                received_start_sample=0,
                symbol_origin_sample=0,
                target_symbol_index=f,
                profile=ADR012_PROFILE,
                adr_profile=ADR012_PROFILE_ID,
                path_count=1,
                path_delays_samples=(0,),
                samples_per_symbol=8,
                iq_rule=ADR012_IQ_RULE,
                waveform_rule=ADR012_WAVEFORM_RULE,
            ),
            dtype=np.float64,
        )
        for f in range(8)
    )


def run_posterior_clamp_audit(
    *,
    received: ArrayLike | None = None,
    m6g_trace_path: str | Path = "outputs/m6g_multistep_feedback_audit/deterministic_trace.json",
) -> dict[str, object]:
    """Audit same-state weight swaps and replay a per-symbol B-posterior clamp.

    The M6g closed-loop and common-operand rows are loaded read-only. The
    clamp replay computes each arm's own candidates/posterior history, then
    passes the same-symbol B posterior to the existing [A](1) update API.
    """
    samples = deterministic_feedback_fixture() if received is None else np.asarray(received)
    if samples.shape != (64,) or not np.iscomplexobj(samples):
        raise ValueError("received must be a complex vector with shape (64,)")
    samples = np.asarray(samples, dtype=np.complex128)
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("received must contain only finite complex values")
    fixture_hash = hashlib.sha256(samples.tobytes()).hexdigest()
    if fixture_hash != M6G_FIXTURE_SHA256:
        raise ValueError("received fixture SHA-256 differs from the fixed M6g fixture SHA-256")
    source, source_hash = _read_m6g_trace(m6g_trace_path)
    labels = np.arange(64, dtype=np.int64)
    observations = _observations(samples)
    b_rows = source["closed_loop"]["arms"]["B"]["rows"]
    b_posteriors = [np.asarray(row["posterior"], dtype=np.float64) for row in b_rows]
    b_innovations = [
        np.asarray(row["own_posterior_innovation"], dtype=np.float64) for row in b_rows
    ]
    transition = build_reconstruction_transition_matrix()
    initial_prior = build_initial_reconstruction_prior(initial_state=(0, 0))
    same_state: dict[str, list[dict[str, object]]] = {arm: [] for arm in _ARMS}
    posterior_clamp: dict[str, dict[str, object]] = {}
    for arm in _ARMS:
        m6g_rows = source["closed_loop"]["arms"][arm]["rows"]
        for f, own_row in enumerate(m6g_rows):
            p_own = np.asarray(own_row["posterior"], dtype=np.float64)
            p_b = b_posteriors[f]
            y = observations[f]
            u_own = np.asarray(own_row["predictions"], dtype=np.float64)
            u_b = np.asarray(b_rows[f]["predictions"], dtype=np.float64)
            eps_own = _weighted_innovation(p_own, y, u_own)
            eps_clamp = _weighted_innovation(p_b, y, u_own)
            eps_b = _weighted_innovation(p_b, y, u_b)
            if not np.allclose(
                eps_b,
                np.asarray(b_innovations[f], dtype=np.float64),
                rtol=0.0,
                atol=_ATOL,
            ):
                raise RuntimeError(
                    "INVARIANT FAILURE: re-derived B innovation differs from M6g trace"
                )
            delta_weights = eps_own - eps_clamp
            delta_weight_oracle = _weighted_innovation(p_own - p_b, np.zeros(2), u_own)
            # For normalized weights, the observation terms cancel.
            delta_weight_norm_identity = -np.asarray(
                [
                    math.fsum(float(p_own[h] - p_b[h]) * float(u_own[h, j]) for h in range(16))
                    for j in range(2)
                ]
            )
            delta_prediction = eps_clamp - eps_b
            delta_prediction_oracle = np.asarray(
                [
                    math.fsum(
                        float(p_b[h]) * (float(u_b[h, j]) - float(u_own[h, j])) for h in range(16)
                    )
                    for j in range(2)
                ]
            )
            if not (
                np.allclose(delta_weights, delta_weight_oracle, rtol=0.0, atol=_ATOL)
                and np.allclose(delta_weights, delta_weight_norm_identity, rtol=0.0, atol=_ATOL)
                and np.allclose(delta_prediction, delta_prediction_oracle, rtol=0.0, atol=_ATOL)
                and np.allclose(
                    eps_own - eps_b, delta_weights + delta_prediction, rtol=0.0, atol=_ATOL
                )
            ):
                raise RuntimeError("INVARIANT FAILURE: same-state innovation decomposition failed")
            state = np.asarray(own_row["pre_fluctuating"], dtype=np.float64)
            policy = FACTORIAL_ARMS[arm]
            own_next, own_full = update_quadrature_estimates(
                previous_fluctuating=state,
                alpha_prime=policy.alpha_prime,
                k_tilde=np.asarray(policy.k_tilde),
                posterior=p_own,
                observed_iq=y,
                predicted_iq=u_own,
                mu0=_MU0,
            )
            clamp_next, clamp_full = update_quadrature_estimates(
                previous_fluctuating=state,
                alpha_prime=policy.alpha_prime,
                k_tilde=np.asarray(policy.k_tilde),
                posterior=p_b,
                observed_iq=y,
                predicted_iq=u_own,
                mu0=_MU0,
            )
            if not np.allclose(
                own_next,
                np.asarray(own_row["post_fluctuating"], dtype=np.float64),
                rtol=0.0,
                atol=_ATOL,
            ):
                raise RuntimeError(
                    "INVARIANT FAILURE: own same-state update disagrees with M6g row"
                )
            same_state[arm].append(
                {
                    "symbol_position": f,
                    "symbol_index": f,
                    "sample_window": list(range(8 * f, 8 * f + 8)),
                    "prediction_cutoff_sample": 8 * f - 1,
                    "observation_cutoff_sample": 8 * f + 7,
                    "hypothesis_ids": list(range(16)),
                    "observed_iq": y.tolist(),
                    "own_predictions": u_own.tolist(),
                    "b_predictions_same_symbol": u_b.tolist(),
                    "own_posterior": p_own.tolist(),
                    "b_posterior": p_b.tolist(),
                    "own_posterior_normalization_error": _sum(p_own) - 1.0,
                    "b_posterior_normalization_error": _sum(p_b) - 1.0,
                    "epsilon_own": eps_own.tolist(),
                    "epsilon_clamp": eps_clamp.tolist(),
                    "epsilon_b": eps_b.tolist(),
                    "pre_fluctuating": state.tolist(),
                    "delta_epsilon_weights": delta_weights.tolist(),
                    "delta_epsilon_weights_oracle": delta_weight_oracle.tolist(),
                    "delta_epsilon_weights_normalized_identity": delta_weight_norm_identity.tolist(),
                    "delta_epsilon_prediction": delta_prediction.tolist(),
                    "delta_epsilon_prediction_oracle": delta_prediction_oracle.tolist(),
                    "innovation_decomposition_residual": (
                        eps_own - eps_b - delta_weights - delta_prediction
                    ).tolist(),
                    "one_step_own_post_fluctuating": own_next.tolist(),
                    "one_step_own_post_full": own_full.tolist(),
                    "one_step_clamp_post_fluctuating": clamp_next.tolist(),
                    "one_step_clamp_post_full": clamp_full.tolist(),
                    "one_step_state_difference": (own_next - clamp_next).tolist(),
                    "weights_changed_only": True,
                    "finite": bool(
                        all(
                            np.all(np.isfinite(value))
                            for value in (
                                y,
                                u_own,
                                u_b,
                                p_own,
                                p_b,
                                eps_own,
                                eps_clamp,
                                eps_b,
                                own_next,
                                own_full,
                                clamp_next,
                                clamp_full,
                            )
                        )
                    ),
                    "input_provenance": "M6g CLOSED_LOOP state/prediction/posterior; ADR-012 mean re-derived from identical fixed fixture",
                }
            )

        # Multistep posterior-clamp replay: own posterior history, B[f] weights
        # only at the correction operand. No frozen B innovation is injected.
        rows: list[dict[str, object]] = []
        pre_fluct = _INITIAL.copy()
        pre_full = _INITIAL.copy()
        previous_posterior = None
        start = 0
        for f in range(8):
            state = ReconstructionEstimatorState(pre_fluct.reshape(1, 2), pre_full.reshape(1, 2), f)
            candidate = generate_reconstruction_candidate_metrics(
                received=samples,
                absolute_sample_indices=labels,
                received_start_sample=start,
                symbol_origin_sample=0,
                target_symbol_index=f,
                state=state,
                time_index=f,
                profile=ADR012_PROFILE,
                adr_profile=ADR012_PROFILE_ID,
                path_count=1,
                path_delays_samples=(0,),
                samples_per_symbol=8,
                iq_rule=ADR012_IQ_RULE,
                waveform_rule=ADR012_WAVEFORM_RULE,
                labeling_profile=ASSUMED_NATURAL_BINARY,
                bit_order=OUTPUT_BIT_ORDER,
                timebase_profile=APPROXIMATE_RECTANGULAR_8SPS,
                symbol_to_sample_rule=RECTANGULAR_ZOH_RULE,
                edge_policy=ZERO_PADDING,
            )
            if candidate.hypothesis_ids != tuple(range(16)):
                raise RuntimeError("candidate API changed canonical 16-edge ordering")
            predictions = np.asarray(candidate.sample_predictions_iq[:, 0, :], dtype=np.float64)
            observed = observations[f]
            posterior = (
                initial_reconstruction_observation_update(
                    prior=initial_prior, candidate_metrics=candidate.metrics, beta=_BETA
                )
                if f == 0
                else transition_reconstruction_posterior(
                    previous_posterior, candidate.metrics, beta=_BETA
                )
            )
            if f == 0:
                q = initial_prior
                prior_provenance = "ADR-004 initial prior"
                q_provenance = "none_first_edge"
            else:
                q = np.asarray(
                    [
                        math.fsum(
                            float(previous_posterior[i]) * float(transition[i, j])
                            for i in range(16)
                        )
                        for j in range(16)
                    ]
                )
                prior_provenance = "own previous posterior transitioned by ADR-003"
                q_provenance = "derived_from_own_previous_posterior @ ADR-003 transition"
            p_b = b_posteriors[f]
            eps_own = _weighted_innovation(posterior, observed, predictions)
            eps_supplied = _weighted_innovation(p_b, observed, predictions)
            policy = FACTORIAL_ARMS[arm]
            next_fluct, next_full = update_quadrature_estimates(
                previous_fluctuating=pre_fluct,
                alpha_prime=policy.alpha_prime,
                k_tilde=np.asarray(policy.k_tilde),
                posterior=p_b,
                observed_iq=observed,
                predicted_iq=predictions,
                mu0=_MU0,
            )
            posterior_sum = _sum(posterior)
            finite = all(
                np.all(np.isfinite(value))
                for value in (
                    pre_fluct,
                    pre_full,
                    predictions,
                    candidate.metrics,
                    posterior,
                    eps_own,
                    eps_supplied,
                    next_fluct,
                    next_full,
                )
            )
            row = {
                "symbol_position": f,
                "symbol_index": f,
                "estimator_time_index": f,
                "sample_window": list(candidate.sample_indices),
                "prediction_cutoff_sample": candidate.prediction_cutoff_sample_index,
                "observation_cutoff_sample": candidate.metric_available_after_sample_index,
                "edge_mode": "first_edge" if f == 0 else "later_edge",
                "hypothesis_ids": list(candidate.hypothesis_ids),
                "pre_fluctuating": pre_fluct.tolist(),
                "pre_full": pre_full.tolist(),
                "predictions": predictions.tolist(),
                "metrics": candidate.metrics.tolist(),
                "posterior_prior": q.tolist(),
                "posterior_prior_provenance": prior_provenance,
                "posterior": posterior.tolist(),
                "own_posterior": posterior.tolist(),
                "posterior_sum": posterior_sum,
                "own_posterior_innovation": eps_own.tolist(),
                "supplied_innovation": eps_supplied.tolist(),
                "supplied_weights": p_b.tolist(),
                "supplied_weight_origin": "same_symbol_frozen_B_posterior",
                "posterior_origin": "ADR-004 first-edge update"
                if f == 0
                else "own previous posterior via transition",
                "innovation_difference_own_minus_supplied": (eps_own - eps_supplied).tolist(),
                "alpha_prime": policy.alpha_prime,
                "k_tilde": list(policy.k_tilde),
                "coefficient_delta": (next_fluct - pre_fluct).tolist(),
                "post_fluctuating": next_fluct.tolist(),
                "post_full": next_full.tolist(),
                "raw_q": "unavailable",
                "q_provenance": q_provenance,
                "normalization_error": posterior_sum - 1.0,
                "finite": bool(finite),
            }
            if not finite or not math.isclose(posterior_sum, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(
                    "INVARIANT FAILURE: clamp replay produced invalid state/posterior"
                )
            rows.append(row)
            pre_fluct, pre_full, previous_posterior = next_fluct, next_full, posterior
        posterior_clamp[arm] = {
            "rows": rows,
            "frozen_metric_matrix": [row["metrics"] for row in rows],
        }

    first_cl = [source["closed_loop"]["arms"][arm]["rows"][0] for arm in _ARMS]
    first_clamp = [posterior_clamp[arm]["rows"][0] for arm in _ARMS]
    for collection in (first_cl, first_clamp):
        for key in ("metrics", "posterior"):
            reference = np.asarray(collection[0][key], dtype=np.float64)
            if any(
                not np.array_equal(np.asarray(row[key], dtype=np.float64), reference)
                for row in collection[1:]
            ):
                raise RuntimeError(f"INVARIANT FAILURE: first-symbol {key} differs across arms")
    if any(
        not np.allclose(
            np.asarray(row["own_posterior_innovation"]),
            np.asarray(row["supplied_innovation"]),
            rtol=0.0,
            atol=_ATOL,
        )
        for row in first_clamp
    ):
        raise RuntimeError("INVARIANT FAILURE: first-symbol clamp weights differ from own weights")

    m6g_closed = {arm: source["closed_loop"]["arms"][arm] for arm in _ARMS}
    m6g_common = {arm: source["common_operand"]["arms"][arm] for arm in _ARMS}
    comparisons: dict[str, list[dict[str, object]]] = {arm: [] for arm in _ARMS}
    for arm in _ARMS:
        for f in range(8):
            cl = m6g_closed[arm]["rows"][f]
            cp = posterior_clamp[arm]["rows"][f]
            co = m6g_common[arm]["rows"][f]
            comparisons[arm].append(
                {
                    "symbol_position": f,
                    "D_closed_minus_clamp": {
                        "pre_state": (
                            np.asarray(cl["pre_fluctuating"]) - np.asarray(cp["pre_fluctuating"])
                        ).tolist(),
                        "post_state": (
                            np.asarray(cl["post_fluctuating"]) - np.asarray(cp["post_fluctuating"])
                        ).tolist(),
                        "metrics": (np.asarray(cl["metrics"]) - np.asarray(cp["metrics"])).tolist(),
                        "posterior": (
                            np.asarray(cl["posterior"]) - np.asarray(cp["posterior"])
                        ).tolist(),
                    },
                    "D_clamp_minus_common": {
                        "pre_state": (
                            np.asarray(cp["pre_fluctuating"]) - np.asarray(co["pre_fluctuating"])
                        ).tolist(),
                        "post_state": (
                            np.asarray(cp["post_fluctuating"]) - np.asarray(co["post_fluctuating"])
                        ).tolist(),
                        "metrics": (np.asarray(cp["metrics"]) - np.asarray(co["metrics"])).tolist(),
                        "posterior": (
                            np.asarray(cp["posterior"]) - np.asarray(co["posterior"])
                        ).tolist(),
                    },
                }
            )

    return {
        "schema_version": "m6h.posterior-clamp.v1",
        "classification": "deterministic posterior-weight intervention and feedback audit; not M5j root-cause proof; not optimized; not paper-exact",
        "fixture_sha256": fixture_hash,
        "m6g_source_path": str(m6g_trace_path),
        "m6g_source_sha256": source_hash,
        "m6g_source_schema": _EXPECTED_M6G_SCHEMA,
        "beta": _BETA,
        "initial_full_iq": _INITIAL.tolist(),
        "mu0": _MU0.tolist(),
        "origins": {"absolute_sample": 0, "absolute_symbol": 0, "estimator_tick": 0},
        "array_shapes": {
            "posterior": [16],
            "prediction_row": [16, 2],
            "metric_row": [16],
            "coefficient_or_innovation": [2],
            "frozen_metric_history": [8, 16],
            "posterior_history": [8, 16],
        },
        "arms": {
            arm: {
                "alpha_prime": FACTORIAL_ARMS[arm].alpha_prime,
                "k_tilde": list(FACTORIAL_ARMS[arm].k_tilde),
            }
            for arm in _ARMS
        },
        "numeric_tolerances": {
            "identity_atol": _ATOL,
            "posterior_normalization_atol": 1e-12,
            "read_only_hash": "exact SHA-256",
        },
        "b_reference_posterior_source": "M6g CLOSED_LOOP arm B posterior rows, same absolute symbol f",
        "b_reference_posteriors": [row.tolist() for row in b_posteriors],
        "b_reference_innovations": [row.tolist() for row in b_innovations],
        "same_state": same_state,
        "m6g_closed_loop": m6g_closed,
        "posterior_clamp": posterior_clamp,
        "m6g_common_operand": m6g_common,
        "three_way_comparison": comparisons,
        "decoder_invoked": False,
        "random_generation_invoked": False,
        "transmitted_data_or_channel_truth_used": False,
        "invariant_status": "fixture_source_first_symbol_and_identity_controls_passed",
    }


def posterior_clamp_to_json(result: Mapping[str, object]) -> str:
    """Stable compact JSON; reject non-finite numeric values."""
    return json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n"


def write_posterior_clamp_json(result: Mapping[str, object], path: str | Path) -> Path:
    """Atomically write a new M6h artifact without touching M6g."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(posterior_clamp_to_json(result), encoding="utf-8", newline="\n")
    temporary.replace(target)
    return target
