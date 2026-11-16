"""Channel outputs with a strict receiver-observation / evaluation-truth boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


def readonly(array: NDArray[Any]) -> NDArray[Any]:
    result = np.ascontiguousarray(array)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class ReceiverObservation:
    """Only data intended to be passed to a future receiver implementation."""

    received_samples: NDArray[np.complex128]
    absolute_sample_index: NDArray[np.int64]
    sample_symbol_index: NDArray[np.int64]
    sample_local_index: NDArray[np.int64]
    samples_per_symbol: int
    profile_id: str
    model_id: str
    sampling_convention: str
    boundary_policy: str
    output_length_policy: str
    noise_model: str
    noise_complex_variance: float | None

    @property
    def sha256(self) -> str:
        digest = hashlib.sha256()
        for name in (
            "received_samples",
            "absolute_sample_index",
            "sample_symbol_index",
            "sample_local_index",
        ):
            array = np.ascontiguousarray(getattr(self, name))
            digest.update(name.encode("utf-8"))
            digest.update(str(array.dtype).encode("ascii"))
            digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
            digest.update(array.tobytes())
        public = {
            "samples_per_symbol": self.samples_per_symbol,
            "profile_id": self.profile_id,
            "model_id": self.model_id,
            "sampling_convention": self.sampling_convention,
            "boundary_policy": self.boundary_policy,
            "output_length_policy": self.output_length_policy,
            "noise_model": self.noise_model,
            "noise_complex_variance": self.noise_complex_variance,
        }
        digest.update(json.dumps(public, sort_keys=True, separators=(",", ":")).encode())
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluationTruth:
    """Evaluation-only truth. Never pass this object to a receiver."""

    transmitter_samples: NDArray[np.complex128]
    transmitter_information_bits: NDArray[np.int8]
    transmitter_symbols: NDArray[np.complex128]
    path_delays_samples: tuple[int, ...]
    path_average_powers: tuple[float, ...]
    path_k_factors: tuple[float, ...]
    path_los_phases_rad: tuple[float, ...]
    source_sample_indices: NDArray[np.int64]
    coefficients: NDArray[np.complex128]
    path_contributions: NDArray[np.complex128]
    faded_signal: NDArray[np.complex128]
    noise_samples: NDArray[np.complex128]


@dataclass(frozen=True, slots=True)
class ChannelResult:
    """Full evaluator result; receiver-facing payload is only `.receiver_observation`."""

    receiver_observation: ReceiverObservation
    evaluation_truth: EvaluationTruth
    config_snapshot: dict[str, Any]
    reproducibility_metadata: dict[str, Any]
    channel_model_id: str

    @property
    def received_samples(self) -> NDArray[np.complex128]:
        """Convenience alias; the receiver contract is still the observation object."""
        return self.receiver_observation.received_samples

    @property
    def array_storage_bytes(self) -> int:
        arrays = (
            self.receiver_observation.received_samples,
            self.receiver_observation.absolute_sample_index,
            self.receiver_observation.sample_symbol_index,
            self.receiver_observation.sample_local_index,
            self.evaluation_truth.transmitter_samples,
            self.evaluation_truth.transmitter_information_bits,
            self.evaluation_truth.transmitter_symbols,
            self.evaluation_truth.source_sample_indices,
            self.evaluation_truth.coefficients,
            self.evaluation_truth.path_contributions,
            self.evaluation_truth.faded_signal,
            self.evaluation_truth.noise_samples,
        )
        return sum(int(array.nbytes) for array in arrays)
