"""I/Q utilities and explicitly approximate rectangular 8-sample waveforms."""

import numpy as np
from numpy.typing import NDArray

IQ_WAVEFORM_PROFILE = "approximate_rectangular"


def _complex_vector(samples: object) -> NDArray[np.complex128]:
    try:
        values = np.asarray(samples, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("samples must be a finite 1-D numeric array") from exc
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("samples must be a finite 1-D numeric array")
    return values


def split_iq(samples: object) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return aligned real I and Q arrays from finite complex samples."""
    values = _complex_vector(samples)
    return np.asarray(values.real, dtype=np.float64), np.asarray(values.imag, dtype=np.float64)


def combine_iq(in_phase: object, quadrature: object) -> NDArray[np.complex128]:
    """Reconstruct complex samples from equal-shaped real I/Q vectors."""
    try:
        i_values = np.asarray(in_phase, dtype=np.float64)
        q_values = np.asarray(quadrature, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("I and Q must be finite real 1-D arrays") from exc
    if (
        i_values.ndim != 1
        or q_values.ndim != 1
        or i_values.shape != q_values.shape
        or not np.all(np.isfinite(i_values))
        or not np.all(np.isfinite(q_values))
    ):
        raise ValueError("I and Q must be finite 1-D arrays with the same shape")
    return np.asarray(i_values + 1j * q_values, dtype=np.complex128)


def symbols_to_iq_waveform(
    symbols: object, *, samples_per_symbol: int = 8
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Expand symbols with a zero-order hold, then return I/Q sample arrays.

    The rectangular pulse is a project approximation for exercising sample-
    domain processing; it is not a reconstruction of the paper's pulse shape.
    """
    if type(samples_per_symbol) is not int or samples_per_symbol < 1:
        raise ValueError("samples_per_symbol must be a positive integer")
    return split_iq(np.repeat(_complex_vector(symbols), samples_per_symbol))
