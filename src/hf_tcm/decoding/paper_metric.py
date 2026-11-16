"""Isolated scalar metric kernel for the squared-residual criterion [A](2)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _paper_integer(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _integer_vector(values: object, *, name: str) -> tuple[int, ...]:
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a 1-D integer sequence") from exc
    if (
        raw.ndim != 1
        or np.issubdtype(raw.dtype, np.bool_)
        or not np.issubdtype(raw.dtype, np.integer)
    ):
        raise ValueError(f"{name} must be a 1-D integer sequence")
    return tuple(int(value) for value in raw.tolist())


def _sequence(values: object, *, name: str, expected_length: int) -> list[object]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        result = list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence") from exc
    if len(result) != expected_length:
        raise ValueError(f"{name} must contain {expected_length} entries")
    return result


def _sample_bounds(values: object) -> tuple[tuple[int, int], ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("sample_bounds must contain inclusive (start, end) pairs")
    try:
        raw_bounds = list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError("sample_bounds must contain inclusive (start, end) pairs") from exc
    if not raw_bounds:
        raise ValueError("sample_bounds must contain at least one beam")

    bounds: list[tuple[int, int]] = []
    for beam, raw_pair in enumerate(raw_bounds, start=1):
        if isinstance(raw_pair, (str, bytes)):
            raise ValueError(f"sample_bounds for beam {beam} must be an integer pair")
        try:
            pair = list(raw_pair)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ValueError(f"sample_bounds for beam {beam} must be an integer pair") from exc
        if len(pair) != 2:
            raise ValueError(f"sample_bounds for beam {beam} must be an integer pair")
        start = _paper_integer(pair[0], name=f"sample_bounds[{beam}].start")
        end = _paper_integer(pair[1], name=f"sample_bounds[{beam}].end")
        if start > end:
            raise ValueError(f"sample_bounds for beam {beam} must be ordered start <= end")
        bounds.append((start, end))
    return tuple(bounds)


def _iq_segment(values: ArrayLike, *, name: str, sample_count: int) -> FloatArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw):
            raise ValueError
        result = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real I/Q array") from exc
    if result.shape != (sample_count, 2):
        raise ValueError(f"{name} must have shape ({sample_count}, 2)")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def compute_paper_metric(
    *,
    r: int,
    eta: int,
    f_indices: object,
    observed_iq: object,
    predicted_iq: object,
    sample_indices: object,
    sample_bounds: object,
) -> float:
    """Compute ``F(r)`` from [A](2) for one already specified trajectory.

    The outer sequence is ordered by explicit paper indices
    ``f = r - eta, ..., r``. Each ``observed_iq[f_offset]`` and
    ``predicted_iq[f_offset]`` contains one ``(N_l, 2)`` array per beam, in
    explicit beam order ``l = 1, ..., L``. Different beams may have different
    ``N_l``. The last axis is the source's ``j = 1, 2`` quadrature order.

    ``sample_bounds[l_offset] = (i_start, i_end)`` are inclusive paper sample
    labels. For every ``f`` and beam, ``sample_indices[f_offset][l_offset]``
    must explicitly enumerate every integer from ``i_start`` through
    ``i_end``. Python row offset is ``i - i_start``; quadrature ``j`` maps to
    last-axis offset ``j - 1``. The caller is responsible for mapping physical
    samples into these explicit ``(f, l, i)`` arrays; this function performs no
    physical-time, symbol-time, or per-path alignment.

    The scalar result is the sum of squared residuals for this one supplied
    trajectory. It does not minimize over trajectories or perform traceback.
    """
    r_index = _paper_integer(r, name="r")
    eta_value = _paper_integer(eta, name="eta")
    if eta_value < 0:
        raise ValueError("eta must be non-negative")

    expected_f = tuple(range(r_index - eta_value, r_index + 1))
    supplied_f = _integer_vector(f_indices, name="f_indices")
    if supplied_f != expected_f:
        raise ValueError("f_indices must equal the inclusive range r-eta through r")

    bounds = _sample_bounds(sample_bounds)
    beam_count = len(bounds)
    frame_count = len(expected_f)
    observed_frames = _sequence(observed_iq, name="observed_iq", expected_length=frame_count)
    predicted_frames = _sequence(predicted_iq, name="predicted_iq", expected_length=frame_count)
    index_frames = _sequence(sample_indices, name="sample_indices", expected_length=frame_count)

    validated: list[tuple[FloatArray, FloatArray]] = []
    for frame_offset, f_index in enumerate(expected_f):
        observations = _sequence(
            observed_frames[frame_offset],
            name=f"observed_iq at f={f_index}",
            expected_length=beam_count,
        )
        predictions = _sequence(
            predicted_frames[frame_offset],
            name=f"predicted_iq at f={f_index}",
            expected_length=beam_count,
        )
        indices_by_beam = _sequence(
            index_frames[frame_offset],
            name=f"sample_indices at f={f_index}",
            expected_length=beam_count,
        )

        for beam_offset, (start, end) in enumerate(bounds):
            beam = beam_offset + 1
            expected_indices = tuple(range(start, end + 1))
            actual_indices = _integer_vector(
                indices_by_beam[beam_offset],
                name=f"sample_indices at f={f_index}, beam={beam}",
            )
            if actual_indices != expected_indices:
                raise ValueError(
                    f"sample_indices at f={f_index}, beam={beam} must enumerate "
                    "the inclusive sample_bounds"
                )
            sample_count = end - start + 1
            observed_segment = _iq_segment(
                observations[beam_offset],
                name=f"observed_iq at f={f_index}, beam={beam}",
                sample_count=sample_count,
            )
            predicted_segment = _iq_segment(
                predictions[beam_offset],
                name=f"predicted_iq at f={f_index}, beam={beam}",
                sample_count=sample_count,
            )
            validated.append((observed_segment, predicted_segment))

    def squared_residuals() -> Iterator[float]:
        for observed_segment, predicted_segment in validated:
            with np.errstate(over="ignore", invalid="ignore"):
                residuals = observed_segment - predicted_segment
            if not np.all(np.isfinite(residuals)):
                raise ValueError("residuals must be finite")
            for residual in residuals.flat:
                value = float(residual)
                squared = value * value
                if not math.isfinite(squared):
                    raise ValueError("squared residual is outside the supported numeric range")
                yield squared

    try:
        metric = math.fsum(squared_residuals())
    except OverflowError as exc:
        raise ValueError("metric is outside the supported numeric range") from exc
    if not math.isfinite(metric):
        raise ValueError("metric is outside the supported numeric range")
    return metric
