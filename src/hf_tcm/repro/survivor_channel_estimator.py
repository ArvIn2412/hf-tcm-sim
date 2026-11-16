"""Sample-causal complex Kalman/RLS primitives for survivor-specific paths."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.adaptive_multipath_config import AdaptiveMultipathReceiverConfig
from hf_tcm.repro.augmented_trellis import AugmentedTransition, AugmentedTrellis


@dataclass(frozen=True, slots=True)
class EstimatorState:
    mean: NDArray[np.complex128]
    covariance: NDArray[np.complex128]
    last_sample_index: int = -1
    hypothesis_node_id: int = -1

    def __post_init__(self) -> None:
        mean = np.array(self.mean, dtype=np.complex128, copy=True)
        covariance = np.array(self.covariance, dtype=np.complex128, copy=True)
        if mean.ndim != 1 or covariance.shape != (mean.size, mean.size):
            raise ValueError("estimator mean/covariance shapes are inconsistent")
        if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(covariance)):
            raise ValueError("estimator state must be finite")
        if type(self.last_sample_index) is not int or type(self.hypothesis_node_id) is not int:
            raise ValueError("estimator sample/hypothesis identifiers must be integers")
        mean.setflags(write=False)
        covariance.setflags(write=False)
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "covariance", covariance)


def initial_estimator_state(
    config: AdaptiveMultipathReceiverConfig, *, hypothesis_node_id: int = 0
) -> EstimatorState:
    mean = np.asarray([path.public_mean for path in config.paths], dtype=np.complex128)
    variances = np.asarray([path.diffuse_variance for path in config.paths], dtype=np.float64)
    if config.channel_mode == "unknown_static":
        variances = np.asarray([path.prior_variance for path in config.paths], dtype=np.float64)
    covariance = np.diag(variances).astype(np.complex128)
    covariance += np.eye(len(mean), dtype=np.complex128) * config.covariance_floor
    return EstimatorState(mean, covariance, -1, hypothesis_node_id)


def predict_estimator_sample(
    state: EstimatorState,
    config: AdaptiveMultipathReceiverConfig,
    *,
    sample_index: int,
) -> tuple[EstimatorState, NDArray[np.complex128]]:
    if type(sample_index) is not int or sample_index < 0:
        raise ValueError("sample_index must be a non-negative integer")
    if state.mean.size != len(config.paths):
        raise ValueError("estimator dimension does not match configured paths")
    if state.last_sample_index >= 0 and sample_index != state.last_sample_index + 1:
        raise ValueError("estimator samples must be consumed consecutively")
    mean = np.array(state.mean, copy=True)
    covariance = np.array(state.covariance, copy=True)
    if state.last_sample_index >= 0:
        if config.channel_mode == "unknown_static":
            covariance /= config.forgetting_factor
        else:
            rho = config.correlation
            public_mean = np.asarray([path.public_mean for path in config.paths])
            q = np.asarray([(1.0 - rho * rho) * path.diffuse_variance for path in config.paths])
            mean = public_mean + rho * (mean - public_mean)
            covariance = rho * rho * covariance + np.diag(q)
    covariance = (covariance + covariance.conj().T) * 0.5
    predicted = EstimatorState(mean, covariance, sample_index, state.hypothesis_node_id)
    return predicted, np.array(covariance, copy=True)


def update_estimator_sample(
    state: EstimatorState,
    regressor: object,
    received: complex,
    config: AdaptiveMultipathReceiverConfig,
    *,
    sample_index: int,
) -> tuple[EstimatorState, complex]:
    x = np.asarray(regressor, dtype=np.complex128)
    y = complex(received)
    if x.shape != state.mean.shape or not np.all(np.isfinite(x)):
        raise ValueError("regressor must be a finite vector matching path count")
    if not np.isfinite(y.real) or not np.isfinite(y.imag):
        raise ValueError("received sample must be finite")
    prior, _ = predict_estimator_sample(state, config, sample_index=sample_index)
    # Model is y = x.T h + w; conventional complex Kalman uses z=conj(x).
    z = np.conjugate(x)
    innovation = y - np.vdot(z, prior.mean)
    covariance = np.asarray(prior.covariance)
    projected = covariance @ z
    denominator = float(config.observation_noise_variance + np.vdot(z, projected).real)
    denominator = max(denominator, config.numerical_tolerance)
    gain = projected / denominator
    mean = prior.mean + gain * innovation
    updated = covariance - np.outer(gain, np.conjugate(z) @ covariance)
    updated = (updated + updated.conj().T) * 0.5
    # Clamp tiny negative eigenvalues created by finite precision only.
    eigenvalues, eigenvectors = np.linalg.eigh(updated)
    if eigenvalues[0] < -config.numerical_tolerance:
        raise FloatingPointError("estimator covariance lost positive semidefiniteness")
    if eigenvalues[0] < config.covariance_floor:
        updated = (
            eigenvectors * np.maximum(eigenvalues, config.covariance_floor)
        ) @ eigenvectors.conj().T
        updated = (updated + updated.conj().T) * 0.5
    result = EstimatorState(mean, updated, sample_index, state.hypothesis_node_id)
    return result, complex(innovation)


def _symbol(phase: int, amplitude: float, offset: float, increment: float) -> complex:
    return amplitude * complex(
        np.cos(offset + phase * increment), np.sin(offset + phase * increment)
    )


def build_delayed_regressor(
    transition: AugmentedTransition,
    trellis: AugmentedTrellis,
    *,
    symbol_index: int,
    frame_symbols: int,
    delays_samples: tuple[int, ...],
    sample_indices: object,
    amplitude: float,
    phase_offset_rad: float,
    phase_increment_rad: float,
) -> NDArray[np.complex128]:
    """Return X[n,l], with current/previous ZOH symbols and zero-extension."""
    indices = np.asarray(sample_indices)
    if indices.ndim != 1 or indices.dtype.kind not in "iu":
        raise ValueError("sample_indices must be a one-dimensional integer vector")
    if symbol_index < 0 or symbol_index >= frame_symbols:
        raise ValueError("symbol_index must lie within frame")
    # The trellis stores memory from maximum delay, not the number of paths.
    if (max(delays_samples) + 7) // 8 != len(trellis.nodes[0].phase_history):
        raise ValueError("trellis history depth does not match delay profile")
    source_node = trellis.nodes[transition.source_node_id]
    result = np.zeros((indices.size, len(delays_samples)), dtype=np.complex128)
    tx_length = frame_symbols * 8
    for path_index, delay in enumerate(delays_samples):
        source_indices = indices.astype(np.int64, copy=False) - delay
        valid = (source_indices >= 0) & (source_indices < tx_length)
        for row in np.flatnonzero(valid):
            source_symbol = int(source_indices[row] // 8)
            if source_symbol == symbol_index:
                phase = transition.phase_index
            elif source_symbol < symbol_index:
                age = symbol_index - source_symbol
                if age > len(source_node.phase_history):
                    raise ValueError("augmented trellis does not retain required symbol history")
                phase = source_node.phase_history[age - 1]
                if phase < 0:
                    continue
            else:
                continue
            result[row, path_index] = _symbol(
                phase, amplitude, phase_offset_rad, phase_increment_rad
            )
    return result
