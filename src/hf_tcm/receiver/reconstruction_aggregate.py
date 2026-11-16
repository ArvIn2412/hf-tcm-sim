"""Isolated aggregate-I/Q arithmetic for an explicitly supplied reconstruction.

This module combines already aligned receiver-side estimated path predictions.
It does not implement a channel forward model, time alignment, or a paper-exact
metric.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _finite_real_array(values: ArrayLike, *, name: str) -> FloatArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) or not (
            np.issubdtype(raw.dtype, np.integer) or np.issubdtype(raw.dtype, np.floating)
        ):
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real numeric array") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def sum_estimated_path_predictions(path_predictions: ArrayLike) -> FloatArray:
    """Sum explicit aligned estimated path predictions over the beam axis.

    Input must have shape ``(L, N, 2)`` with positive beam count ``L`` and
    sample count ``N``. The final axis is ``(I, Q)``. Output has shape
    ``(N, 2)``. Every beam is assumed to already refer to the same sample
    positions; this function performs no broadcasting, delay handling, or
    alignment. Inputs are read only and are never modified.
    """
    predictions = _finite_real_array(path_predictions, name="path_predictions")
    if predictions.ndim != 3 or predictions.shape[2] != 2:
        raise ValueError("path_predictions must have exact shape (L, N, 2)")
    beam_count, sample_count, _ = predictions.shape
    if beam_count == 0 or sample_count == 0:
        raise ValueError("path_predictions must contain at least one beam and one sample")

    aggregate = np.empty((sample_count, 2), dtype=np.float64)
    try:
        for sample in range(sample_count):
            for quadrature in range(2):
                aggregate[sample, quadrature] = math.fsum(
                    float(predictions[beam, sample, quadrature]) for beam in range(beam_count)
                )
    except OverflowError as exc:
        raise ValueError("aggregate prediction is outside the supported numeric range") from exc
    if not np.all(np.isfinite(aggregate)):
        raise ValueError("aggregate prediction is outside the supported numeric range")
    return aggregate


def compute_project_reconstruction_metric(
    received_iq: ArrayLike,
    predicted_iq: ArrayLike,
) -> float:
    """Return the project reconstruction squared-residual metric.

    Both arguments must be explicitly supplied aggregate I/Q arrays with the
    same non-empty shape ``(N, 2)`` and quadrature order ``(I, Q)``. The result
    is ``sum((received_iq - predicted_iq) ** 2)`` over both axes, accumulated
    with ``math.fsum``. It is not the path-indexed [A](2) metric implemented by
    ``decoding/paper_metric.py``.
    """
    received = _finite_real_array(received_iq, name="received_iq")
    predicted = _finite_real_array(predicted_iq, name="predicted_iq")
    if received.ndim != 2 or received.shape[1] != 2 or received.shape[0] == 0:
        raise ValueError("received_iq must have non-empty shape (N, 2)")
    if predicted.shape != received.shape:
        raise ValueError("predicted_iq must have the same shape as received_iq")

    with np.errstate(over="ignore", invalid="ignore"):
        residuals = received - predicted
    if not np.all(np.isfinite(residuals)):
        raise ValueError("residuals must be finite")

    def squared_residuals() -> Iterator[float]:
        for residual in residuals.flat:
            value = float(residual)
            square = value * value
            if not math.isfinite(square):
                raise ValueError("squared residual is outside the supported numeric range")
            yield square

    try:
        metric = math.fsum(squared_residuals())
    except OverflowError as exc:
        raise ValueError("metric is outside the supported numeric range") from exc
    if not math.isfinite(metric):
        raise ValueError("metric is outside the supported numeric range")
    return metric
