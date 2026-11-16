"""Strict configuration validation for the inactive reconstructed_offline profile.

Validation records explicit project inputs; it does not enable or run a receiver.
The profile is never evidence of a paper-exact implementation.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.posterior import (
    ALLOWED_HYPOTHESIS_TRANSITIONS,
    HYPOTHESIS_COUNT,
)

_ADR003_TRANSITION_MODEL = "adr003_uniform_allowed_edges"
_ADR005_LIKELIHOOD_KIND = "exp_negative_beta_project_reconstruction_metric"

_PROFILE = "reconstructed_offline"
_ESTIMATOR_TIME_RULE = "one_recursion_step_i_to_i_plus_1"
_PROVENANCE_FIELDS = {
    "candidate_index_space",
    "candidate_count",
    "labeling",
    "transition_model",
    "initial_state",
    "initial_prior",
    "likelihood_type",
    "beta",
    "alpha_prime",
    "k_tilde",
    "mu0",
    "initial_estimates",
    "estimator_time_index",
    "estimator_time_rule",
    "timebase",
    "samples_per_symbol",
    "sample_rate_hz",
    "symbol_rate_hz",
    "symbol_origin_sample",
    "path_delays_samples",
    "path_count",
    "aggregate_observation_model",
    "prediction_combination",
    "beam_width",
    "decision_lag_symbols",
}
_RECONSTRUCTION_ONLY_FIELDS = {
    "candidate_index_space",
    "candidate_count",
    "labeling",
    "transition_model",
    "initial",
    "likelihood",
    "estimator",
    "timebase",
    "observation_model",
    "search",
    "assumption_provenance",
}


class ReconstructionConfigError(ValueError):
    """Raised when an inactive reconstructed_offline config is incomplete/invalid."""


def _object(value: object, *, name: str, required: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReconstructionConfigError(f"{name} must be an object")
    keys = set(value)
    missing = required - keys
    unexpected = keys - required
    if missing:
        field = sorted(missing)[0]
        raise ReconstructionConfigError(f"missing required field {name}.{field}")
    if unexpected:
        field = sorted(unexpected)[0]
        raise ReconstructionConfigError(f"unexpected field {name}.{field}")
    return value


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReconstructionConfigError(f"{name} must be a non-empty string")
    return value.strip()


def _integer(value: object, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReconstructionConfigError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ReconstructionConfigError(f"{name} must be >= {minimum}")
    return value


def _finite_real(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReconstructionConfigError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReconstructionConfigError(f"{name} must be a finite real number") from exc
    if not math.isfinite(result):
        raise ReconstructionConfigError(f"{name} must be a finite real number")
    if minimum is not None and result < minimum:
        raise ReconstructionConfigError(f"{name} must be > {minimum}")
    return result


def _real_vector(
    value: object,
    *,
    name: str,
    length: int,
    nonnegative: bool = False,
    probability: bool = False,
) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReconstructionConfigError(f"{name} must be a numeric array with shape ({length},)")
    if len(value) != length:
        raise ReconstructionConfigError(f"{name} must have shape ({length},)")
    values = [_finite_real(item, name=f"{name}[{index}]") for index, item in enumerate(value)]
    if nonnegative and any(item < 0.0 for item in values):
        raise ReconstructionConfigError(f"{name} must be non-negative")
    if probability and any(item > 1.0 for item in values):
        raise ReconstructionConfigError(f"{name} probabilities must not exceed 1")
    return values


def _iq_matrix(value: object, *, name: str, rows: int) -> list[list[float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReconstructionConfigError(f"{name} must have shape ({rows}, 2)")
    if len(value) != rows:
        raise ReconstructionConfigError(f"{name} must have shape ({rows}, 2)")
    return [_real_vector(row, name=f"{name}[{index}]", length=2) for index, row in enumerate(value)]


def _validate_provenance(value: object) -> None:
    provenance = _object(
        value,
        name="assumption_provenance",
        required=_PROVENANCE_FIELDS,
    )
    for key in sorted(_PROVENANCE_FIELDS):
        entry = _object(
            provenance[key],
            name=f"assumption_provenance.{key}",
            required={"status", "source", "note"},
        )
        _text(entry["status"], name=f"assumption_provenance.{key}.status")
        _text(entry["source"], name=f"assumption_provenance.{key}.source")
        _text(entry["note"], name=f"assumption_provenance.{key}.note")


def _validate_labeling(value: object) -> None:
    labeling = _object(
        value,
        name="labeling",
        required={"name", "origin", "bit_order", "output_to_b", "phase_offset_rad"},
    )
    _text(labeling["name"], name="labeling.name")
    _text(labeling["origin"], name="labeling.origin")

    bit_order = labeling["bit_order"]
    if not isinstance(bit_order, Sequence) or isinstance(bit_order, (str, bytes)):
        raise ReconstructionConfigError(
            "labeling.bit_order must be a permutation of ['c2', 'c1', 'c0']"
        )
    if (
        len(bit_order) != 3
        or any(not isinstance(bit, str) for bit in bit_order)
        or set(bit_order) != {"c2", "c1", "c0"}
    ):
        raise ReconstructionConfigError(
            "labeling.bit_order must be a permutation of ['c2', 'c1', 'c0']"
        )

    mapping = labeling["output_to_b"]
    if not isinstance(mapping, Sequence) or isinstance(mapping, (str, bytes)):
        raise ReconstructionConfigError("labeling.output_to_b must contain 8 integer indices")
    if len(mapping) != 8 or any(
        isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 7
        for item in mapping
    ):
        raise ReconstructionConfigError("labeling.output_to_b must contain 8 indices in 0..7")
    if set(mapping) != set(range(8)):
        raise ReconstructionConfigError("labeling.output_to_b must be a permutation of 0..7")
    _finite_real(labeling["phase_offset_rad"], name="labeling.phase_offset_rad")


def _validate_transitions(value: object, *, candidate_count: int) -> None:
    transition = _object(
        value,
        name="transition_model",
        required={"name", "probabilities"},
    )
    name = _text(transition["name"], name="transition_model.name")
    if name != _ADR003_TRANSITION_MODEL:
        raise ReconstructionConfigError(
            f"transition_model.name must be {_ADR003_TRANSITION_MODEL!r} under ADR-003"
        )
    matrix = transition["probabilities"]
    if not isinstance(matrix, Sequence) or isinstance(matrix, (str, bytes)):
        raise ReconstructionConfigError(
            f"transition_model.probabilities must have shape ({candidate_count}, {candidate_count})"
        )
    if len(matrix) != candidate_count:
        raise ReconstructionConfigError(
            f"transition_model.probabilities must have shape ({candidate_count}, {candidate_count})"
        )

    for row_index, row in enumerate(matrix):
        values = _real_vector(
            row,
            name=f"transition_model.probabilities[{row_index}]",
            length=candidate_count,
            nonnegative=True,
            probability=True,
        )
        total = math.fsum(values)
        if not math.isclose(total, 1.0, rel_tol=1e-10, abs_tol=1e-10):
            raise ReconstructionConfigError(
                f"transition_model.probabilities[{row_index}] must sum to 1"
            )
        for column_index, probability in enumerate(values):
            if not ALLOWED_HYPOTHESIS_TRANSITIONS[row_index, column_index] and probability != 0.0:
                raise ReconstructionConfigError(
                    "transition_model.probabilities assigns mass to a structurally forbidden edge"
                )
        degrees = int(ALLOWED_HYPOTHESIS_TRANSITIONS[row_index].sum())
        expected = [
            1.0 / degrees if ALLOWED_HYPOTHESIS_TRANSITIONS[row_index, column_index] else 0.0
            for column_index in range(candidate_count)
        ]
        if any(
            not math.isclose(actual, target, rel_tol=1e-12, abs_tol=1e-12)
            for actual, target in zip(values, expected, strict=True)
        ):
            raise ReconstructionConfigError(
                f"transition_model.probabilities[{row_index}] must be uniform on allowed edges"
            )


def _validate_initial(value: object, *, candidate_count: int) -> None:
    initial = _object(value, name="initial", required={"state", "prior"})
    state = initial["state"]
    if (
        not isinstance(state, Sequence)
        or isinstance(state, (str, bytes))
        or len(state) != 2
        or any(type(bit) is not int or bit not in (0, 1) for bit in state)
    ):
        raise ReconstructionConfigError("initial.state must contain exactly two bits")
    if tuple(state) != (0, 0):
        raise ReconstructionConfigError("ADR-004 requires initial.state=(0, 0)")

    prior = _real_vector(
        initial["prior"],
        name="initial.prior",
        length=candidate_count,
        nonnegative=True,
        probability=True,
    )
    total = math.fsum(prior)
    if not math.isclose(total, 1.0, rel_tol=1e-10, abs_tol=1e-10):
        raise ReconstructionConfigError("initial.prior must sum to 1")
    expected_prior = [
        0.25 if hypothesis.current_state == (0, 0) else 0.0 for hypothesis in HYPOTHESES
    ]
    if any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
        for actual, expected in zip(prior, expected_prior, strict=True)
    ):
        raise ReconstructionConfigError(
            "initial.prior must be uniform on hypotheses with current_state=(0, 0)"
        )


def _validate_timebase(value: object) -> int:
    timebase = _object(
        value,
        name="timebase",
        required={
            "name",
            "samples_per_symbol",
            "sample_rate_hz",
            "symbol_rate_hz",
            "symbol_origin_sample",
            "path_count",
            "path_delays_samples",
        },
    )
    _text(timebase["name"], name="timebase.name")
    samples_per_symbol = _integer(
        timebase["samples_per_symbol"], name="timebase.samples_per_symbol", minimum=1
    )
    sample_rate = _finite_real(
        timebase["sample_rate_hz"], name="timebase.sample_rate_hz", minimum=0.0
    )
    symbol_rate = _finite_real(
        timebase["symbol_rate_hz"], name="timebase.symbol_rate_hz", minimum=0.0
    )
    if sample_rate <= 0.0 or symbol_rate <= 0.0:
        raise ReconstructionConfigError("timebase sample and symbol rates must be positive")
    if not math.isclose(
        sample_rate,
        samples_per_symbol * symbol_rate,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise ReconstructionConfigError(
            "timebase.sample_rate_hz must equal samples_per_symbol * symbol_rate_hz"
        )
    _integer(timebase["symbol_origin_sample"], name="timebase.symbol_origin_sample")

    path_count = _integer(timebase["path_count"], name="timebase.path_count", minimum=1)
    delays = timebase["path_delays_samples"]
    if not isinstance(delays, Sequence) or isinstance(delays, (str, bytes)) or not delays:
        raise ReconstructionConfigError(
            "timebase.path_delays_samples must be a non-empty integer array"
        )
    for index, delay in enumerate(delays):
        _integer(delay, name=f"timebase.path_delays_samples[{index}]", minimum=0)
    if len(delays) != path_count:
        raise ReconstructionConfigError(
            "timebase.path_count must equal the number of path_delays_samples"
        )
    return path_count


def _validate_likelihood(value: object) -> None:
    likelihood = _object(value, name="likelihood", required={"kind", "beta"})
    kind = _text(likelihood["kind"], name="likelihood.kind")
    if kind != _ADR005_LIKELIHOOD_KIND:
        raise ReconstructionConfigError(
            f"likelihood.kind must be {_ADR005_LIKELIHOOD_KIND!r} under ADR-005"
        )
    _finite_real(likelihood["beta"], name="likelihood.beta", minimum=0.0)
    if likelihood["beta"] == 0.0:
        raise ReconstructionConfigError("likelihood.beta must be > 0")


def _validate_estimator(value: object, *, path_count: int) -> None:
    estimator = _object(
        value,
        name="estimator",
        required={
            "alpha_prime",
            "k_tilde",
            "mu0",
            "initial_estimates",
            "initial_time_index",
            "time_rule",
        },
    )
    _finite_real(estimator["alpha_prime"], name="estimator.alpha_prime")
    _integer(estimator["initial_time_index"], name="estimator.initial_time_index")
    if _text(estimator["time_rule"], name="estimator.time_rule") != _ESTIMATOR_TIME_RULE:
        raise ReconstructionConfigError(f"estimator.time_rule must be {_ESTIMATOR_TIME_RULE!r}")
    _iq_matrix(estimator["k_tilde"], name="estimator.k_tilde", rows=path_count)
    _iq_matrix(estimator["mu0"], name="estimator.mu0", rows=path_count)
    initial_estimates = _object(
        estimator["initial_estimates"],
        name="estimator.initial_estimates",
        required={"fluctuating_iq", "full_iq"},
    )
    _iq_matrix(
        initial_estimates["fluctuating_iq"],
        name="estimator.initial_estimates.fluctuating_iq",
        rows=path_count,
    )
    _iq_matrix(
        initial_estimates["full_iq"],
        name="estimator.initial_estimates.full_iq",
        rows=path_count,
    )


def _validate_observation_model(value: object, *, timebase: object) -> None:
    if not isinstance(value, Mapping):
        raise ReconstructionConfigError("observation_model must be an object")
    kind = _text(value.get("kind"), name="observation_model.kind")
    required = {"kind", "prediction_combination"}
    if kind == "adr012_l1_real_mean8":
        required |= {"iq_rule", "sample_reduction", "waveform_rule"}
    elif kind != "aggregate_received_iq":
        raise ReconstructionConfigError(
            "observation_model.kind must be 'aggregate_received_iq' or 'adr012_l1_real_mean8'"
        )
    model = _object(value, name="observation_model", required=required)
    _text(
        model["prediction_combination"],
        name="observation_model.prediction_combination",
    )
    if kind == "adr012_l1_real_mean8":
        if not isinstance(timebase, Mapping):
            raise ReconstructionConfigError("timebase must be an object")
        delays = timebase.get("path_delays_samples")
        if (
            timebase.get("path_count") != 1
            or not isinstance(delays, Sequence)
            or isinstance(delays, (str, bytes))
            or tuple(delays) != (0,)
        ):
            raise ReconstructionConfigError("ADR-012 observation requires L=1 and zero delay")
        if timebase.get("samples_per_symbol") != 8:
            raise ReconstructionConfigError("ADR-012 observation requires 8 samples per symbol")
        fixed_values = {
            "iq_rule": "(-Im(received), Re(received))",
            "sample_reduction": "arithmetic_mean_exactly_8",
            "waveform_rule": "rectangular_zoh",
        }
        for field, expected in fixed_values.items():
            if model[field] != expected:
                raise ReconstructionConfigError(
                    f"observation_model.{field} must be {expected!r} for ADR-012"
                )


def _validate_search(value: object) -> None:
    search = _object(
        value,
        name="search",
        required={"beam_width", "decision_lag_symbols"},
    )
    _integer(search["beam_width"], name="search.beam_width", minimum=1)
    _integer(search["decision_lag_symbols"], name="search.decision_lag_symbols", minimum=0)


def validate_reconstructed_offline_config(data: object) -> dict[str, Any]:
    """Validate the complete, explicit, inactive reconstruction profile.

    No scientific field is defaulted. The returned copy remains configuration
    data only; this function does not construct or activate a receiver.
    """
    config = _object(
        data,
        name="configuration",
        required={
            "schema_version",
            "profile",
            "paper_exact",
            "receiver_enabled",
            "candidate_index_space",
            "candidate_count",
            "labeling",
            "transition_model",
            "initial",
            "likelihood",
            "estimator",
            "timebase",
            "observation_model",
            "search",
            "assumption_provenance",
        },
    )

    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ReconstructionConfigError("schema_version must be integer 1")
    if config["profile"] != _PROFILE:
        raise ReconstructionConfigError(f"profile must be {_PROFILE!r}")
    if config["paper_exact"] is not False:
        raise ReconstructionConfigError("paper_exact must be false for reconstructed_offline")
    if config["receiver_enabled"] is not False:
        raise ReconstructionConfigError(
            "receiver_enabled must be false; this schema does not activate a receiver"
        )
    if config["candidate_index_space"] != "m4_1_hypothesis_id":
        raise ReconstructionConfigError(
            "candidate_index_space must explicitly be 'm4_1_hypothesis_id'"
        )
    candidate_count = _integer(config["candidate_count"], name="candidate_count", minimum=1)
    if candidate_count != HYPOTHESIS_COUNT:
        raise ReconstructionConfigError(
            f"candidate_count must be {HYPOTHESIS_COUNT} for m4_1_hypothesis_id"
        )

    _validate_labeling(config["labeling"])
    _validate_transitions(config["transition_model"], candidate_count=candidate_count)
    _validate_initial(config["initial"], candidate_count=candidate_count)
    _validate_likelihood(config["likelihood"])
    path_count = _validate_timebase(config["timebase"])
    _validate_estimator(config["estimator"], path_count=path_count)
    _validate_observation_model(config["observation_model"], timebase=config["timebase"])
    _validate_search(config["search"])
    _validate_provenance(config["assumption_provenance"])
    return copy.deepcopy(dict(config))


def validate_receiver_profile_mode(data: object, *, requested_mode: str) -> None:
    """Reject reconstruction settings at a source-faithful mode boundary.

    This is a compatibility check only. No mode is started by this function.
    """
    if not isinstance(data, Mapping):
        raise ReconstructionConfigError("configuration must be an object")
    if requested_mode not in {"source_faithful", _PROFILE}:
        raise ReconstructionConfigError(f"unsupported receiver mode {requested_mode!r}")

    has_reconstruction_settings = data.get("profile") == _PROFILE or bool(
        _RECONSTRUCTION_ONLY_FIELDS.intersection(data)
    )
    if requested_mode == "source_faithful" and has_reconstruction_settings:
        raise ReconstructionConfigError(
            "source_faithful mode cannot consume reconstructed_offline reconstruction settings"
        )
    if requested_mode == _PROFILE and data.get("profile") != _PROFILE:
        raise ReconstructionConfigError(f"requested mode requires profile {_PROFILE!r}")


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is not allowed")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property {key!r}")
        result[key] = value
    return result


def load_reconstructed_offline_config(
    path: str | Path,
    *,
    requested_mode: str | None = None,
) -> dict[str, Any]:
    """Load and validate configuration only; no receiver entrypoint is called."""
    config_path = Path(path)
    try:
        with config_path.open(encoding="utf-8") as stream:
            data = json.load(
                stream,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonstandard_json_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ReconstructionConfigError(f"cannot read configuration {config_path}: {exc}") from exc

    if requested_mode is not None:
        validate_receiver_profile_mode(data, requested_mode=requested_mode)
    return validate_reconstructed_offline_config(data)
