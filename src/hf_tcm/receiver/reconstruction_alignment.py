"""Explicit sample-index alignment for estimated path predictions.

The operator is a project reconstruction utility. It applies caller-provided
integer sample shifts and zero padding; it is not a time model established by
article [A].
"""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
ZERO_PADDING = "zero_padding"


def _integer(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _sequence(values: object, *, name: str) -> list[object]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        return list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence") from exc


def _path_segment(values: ArrayLike, *, path: int) -> FloatArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) or not (
            np.issubdtype(raw.dtype, np.integer) or np.issubdtype(raw.dtype, np.floating)
        ):
            raise ValueError
        segment = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"path segment {path} must be a finite real I/Q array") from exc
    if segment.ndim != 2 or segment.shape[1] != 2 or segment.shape[0] == 0:
        raise ValueError(f"path segment {path} must have non-empty shape (N_l, 2)")
    if not np.all(np.isfinite(segment)):
        raise ValueError(f"path segment {path} must contain only finite values")
    return segment


def align_estimated_path_predictions(
    *,
    path_segments: Sequence[ArrayLike],
    segment_start_indices: Sequence[int],
    delays_samples: Sequence[int],
    frame_start_sample: int,
    frame_sample_count: int,
    edge_policy: str,
) -> FloatArray:
    """Place delayed estimated I/Q segments on one explicit output frame.

    Each ``path_segments[l]`` has shape ``(N_l, 2)`` and contains real
    ``(I, Q)`` values. Its row ``k`` is labeled by the nonnegative absolute
    sample index ``segment_start_indices[l] + k``. The explicitly supplied nonnegative
    integer ``delays_samples[l]`` shifts that label to
    ``segment_start_indices[l] + k + delays_samples[l]``. Output row ``n`` is
    labeled ``frame_start_sample + n`` for ``n=0,...,frame_sample_count-1``;
    ``frame_start_sample`` must also be nonnegative and the count positive.

    ``edge_policy`` is required and currently accepts only ``"zero_padding"``:
    uncovered output positions are zero; input samples shifted outside the
    output frame are cropped. The returned array is ``(L, N, 2)`` and can be
    passed directly to the B2a aggregate sum. No samples-per-symbol, physical
    delay conversion, phase/bit convention, or inferred alignment is applied.
    Input segments are read-only and may have different lengths.
    """
    if type(edge_policy) is not str or edge_policy != ZERO_PADDING:
        raise ValueError(f"edge_policy must be explicitly set to {ZERO_PADDING!r}")

    segments_raw = _sequence(path_segments, name="path_segments")
    starts_raw = _sequence(segment_start_indices, name="segment_start_indices")
    delays_raw = _sequence(delays_samples, name="delays_samples")
    path_count = len(segments_raw)
    if path_count == 0:
        raise ValueError("path_segments must contain at least one path")
    if len(starts_raw) != path_count or len(delays_raw) != path_count:
        raise ValueError(
            "path_segments, segment_start_indices, and delays_samples must have equal lengths"
        )

    frame_start = _integer(frame_start_sample, name="frame_start_sample")
    frame_count = _integer(frame_sample_count, name="frame_sample_count")
    if frame_count <= 0:
        raise ValueError("frame_sample_count must be positive")

    starts = tuple(
        _integer(value, name=f"segment_start_indices[{path}]")
        for path, value in enumerate(starts_raw)
    )
    delays = tuple(
        _integer(value, name=f"delays_samples[{path}]") for path, value in enumerate(delays_raw)
    )
    if frame_start < 0 or any(start < 0 for start in starts):
        raise ValueError("frame_start_sample and segment_start_indices must be non-negative")
    if any(delay < 0 for delay in delays):
        raise ValueError("delays_samples must contain non-negative integers")
    segments = tuple(_path_segment(segment, path=path) for path, segment in enumerate(segments_raw))

    aligned = np.zeros((path_count, frame_count, 2), dtype=np.float64)
    frame_end_exclusive = frame_start + frame_count
    for path, (segment, start, delay) in enumerate(zip(segments, starts, delays, strict=True)):
        delayed_start = start + delay
        delayed_end_exclusive = delayed_start + segment.shape[0]
        overlap_start = max(delayed_start, frame_start)
        overlap_end = min(delayed_end_exclusive, frame_end_exclusive)
        if overlap_start >= overlap_end:
            continue
        output_start = overlap_start - frame_start
        output_end = overlap_end - frame_start
        segment_start = overlap_start - delayed_start
        segment_end = segment_start + (output_end - output_start)
        aligned[path, output_start:output_end] = segment[segment_start:segment_end]
    return aligned
