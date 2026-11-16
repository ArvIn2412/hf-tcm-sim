"""Project reconstruction forward prediction for explicit 8PSK candidates.

This composes already approved project adapters and arithmetic kernels. It is
not an author receiver or a passband waveform model from article [A].
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from hf_tcm.receiver.iq_prediction import iq_quadratures_from_index
from hf_tcm.receiver.reconstruction_aggregate import sum_estimated_path_predictions
from hf_tcm.receiver.reconstruction_alignment import align_estimated_path_predictions
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    output_bits_to_phase_index,
)

APPROXIMATE_RECTANGULAR_8SPS = "approximate_rectangular_8sps"
RECTANGULAR_ZOH_RULE = "rectangular_zero_order_hold_8_samples_per_symbol"
SAMPLES_PER_SYMBOL = 8
FloatArray = NDArray[np.float64]


def _sequence(values: object, *, name: str) -> list[object]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        return list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence") from exc


def _estimated_coefficients(values: ArrayLike) -> FloatArray:
    try:
        raw = np.asarray(values)
        if np.iscomplexobj(raw) or not (
            np.issubdtype(raw.dtype, np.integer) or np.issubdtype(raw.dtype, np.floating)
        ):
            raise ValueError
        coefficients = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "estimated_path_coefficients must be a finite real array of shape (L, 2)"
        ) from exc
    if coefficients.ndim != 2 or coefficients.shape[1] != 2 or coefficients.shape[0] == 0:
        raise ValueError("estimated_path_coefficients must have non-empty shape (L, 2)")
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("estimated_path_coefficients must contain only finite values")
    return coefficients


def predict_reconstructed_aggregate_iq(
    *,
    candidate_output_bits: Sequence[Sequence[int]],
    estimated_path_coefficients: ArrayLike,
    path_delays_samples: Sequence[int],
    symbol_origin_sample: int,
    frame_start_sample: int,
    frame_sample_count: int,
    labeling_profile: str,
    bit_order: Sequence[str],
    timebase_profile: str,
    symbol_to_sample_rule: str,
    edge_policy: str,
) -> FloatArray:
    """Predict aggregate baseband I/Q for an explicit candidate symbol sequence.

    ``candidate_output_bits`` contains one `(c2,c1,c0)` triple per symbol.
    The explicit labeling adapter obtains ``b`` from each triple. For every
    path, ``estimated_path_coefficients[l] = (mu1, mu2)`` is a finite
    receiver-side estimate held constant for the entire supplied frame; this
    API does not accept sample-indexed or per-symbol coefficients.

    Only the explicit ``approximate_rectangular_8sps`` profile and
    ``rectangular_zero_order_hold_8_samples_per_symbol`` rule are supported.
    Symbol ``s`` maps to the eight consecutive sample labels
    ``symbol_origin_sample + 8*s`` through ``symbol_origin_sample + 8*s + 7``.
    The local I/Q pair at each symbol is computed by the existing [A](5)
    algebra kernel; each pair is repeated across those eight samples. The
    existing alignment kernel then applies the explicit integer sample delays,
    frame bounds and zero-padding policy; the existing aggregate kernel sums
    paths and returns shape ``(frame_sample_count, 2)`` in (I,Q) order.

    This is a project reconstruction baseband model, not the complete passband
    waveform in [A](3)-(6), not a claim that `U0 == U**`, and not a paper-exact
    receiver. It reads no channel truth and performs no coefficient estimation.
    All profile, bit-order, symbol/sample and frame conventions are required
    arguments; no phase offset is added (the `π/4` in [A](5) is its phase step).
    """
    if type(labeling_profile) is not str or labeling_profile != ASSUMED_NATURAL_BINARY:
        raise ValueError(f"labeling_profile must be {ASSUMED_NATURAL_BINARY!r}")
    if (
        not isinstance(bit_order, Sequence)
        or isinstance(bit_order, (str, bytes))
        or tuple(bit_order) != OUTPUT_BIT_ORDER
    ):
        raise ValueError(f"bit_order must be {OUTPUT_BIT_ORDER!r}")
    if type(timebase_profile) is not str or timebase_profile != APPROXIMATE_RECTANGULAR_8SPS:
        raise ValueError(f"timebase_profile must be {APPROXIMATE_RECTANGULAR_8SPS!r}")
    if type(symbol_to_sample_rule) is not str or symbol_to_sample_rule != RECTANGULAR_ZOH_RULE:
        raise ValueError(f"symbol_to_sample_rule must be {RECTANGULAR_ZOH_RULE!r}")

    symbols = _sequence(candidate_output_bits, name="candidate_output_bits")
    if not symbols:
        raise ValueError("candidate_output_bits must contain at least one symbol")
    phase_indices = np.asarray(
        [
            output_bits_to_phase_index(
                symbol,  # type: ignore[arg-type]
                profile=labeling_profile,
                bit_order=bit_order,
            )
            for symbol in symbols
        ],
        dtype=np.int64,
    )
    coefficients = _estimated_coefficients(estimated_path_coefficients)
    path_count = coefficients.shape[0]

    segments: list[FloatArray] = []
    for path in range(path_count):
        local_symbol_iq = iq_quadratures_from_index(
            phase_indices,
            np.full(len(symbols), coefficients[path, 0], dtype=np.float64),
            np.full(len(symbols), coefficients[path, 1], dtype=np.float64),
        )
        segments.append(np.repeat(local_symbol_iq, SAMPLES_PER_SYMBOL, axis=0))

    aligned = align_estimated_path_predictions(
        path_segments=tuple(segments),
        segment_start_indices=(symbol_origin_sample,) * path_count,
        delays_samples=path_delays_samples,
        frame_start_sample=frame_start_sample,
        frame_sample_count=frame_sample_count,
        edge_policy=edge_policy,
    )
    return sum_estimated_path_predictions(aligned)
