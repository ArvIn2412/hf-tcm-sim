"""Separated, hash-manifested REPRO-03 observation and evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.channel_result import ChannelResult


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _save_npz(path: Path, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    np.savez_compressed(path, **arrays)
    return {
        "file": path.name,
        "sha256": _digest(path.read_bytes()),
        "arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "sha256": _digest(np.ascontiguousarray(array).tobytes()),
            }
            for name, array in arrays.items()
        },
    }


def save_channel_result(result: ChannelResult, output_dir: str | Path) -> dict[str, Any]:
    """Persist public receiver input separately from latent evaluation truth."""
    if not isinstance(result, ChannelResult):
        raise TypeError("result must be a ChannelResult")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    obs = result.receiver_observation
    truth = result.evaluation_truth
    observation_meta = _save_npz(
        root / "receiver_observation.npz",
        {
            "received_samples": obs.received_samples,
            "absolute_sample_index": obs.absolute_sample_index,
            "sample_symbol_index": obs.sample_symbol_index,
            "sample_local_index": obs.sample_local_index,
        },
    )
    truth_meta = _save_npz(
        root / "evaluation_truth.npz",
        {
            "transmitter_samples": truth.transmitter_samples,
            "transmitter_information_bits": truth.transmitter_information_bits,
            "transmitter_symbols": truth.transmitter_symbols,
            "source_sample_indices": truth.source_sample_indices,
            "coefficients": truth.coefficients,
            "path_contributions": truth.path_contributions,
            "faded_signal": truth.faded_signal,
            "noise_samples": truth.noise_samples,
        },
    )
    public = {
        "schema_version": "repro03-channel-v1",
        "profile_id": obs.profile_id,
        "model_id": obs.model_id,
        "sampling_convention": obs.sampling_convention,
        "boundary_policy": obs.boundary_policy,
        "output_length_policy": obs.output_length_policy,
        "noise_model": obs.noise_model,
        "noise_complex_variance": obs.noise_complex_variance,
        "samples_per_symbol": obs.samples_per_symbol,
        "sample_count": int(len(obs.received_samples)),
        "receiver_observation_sha256": obs.sha256,
        "npz": observation_meta,
    }
    (root / "receiver_observation.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "channel_config.json").write_text(
        json.dumps(result.config_snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": "repro03-channel-v1",
        "channel_model_id": result.channel_model_id,
        "profile_id": obs.profile_id,
        "sample_count": int(len(obs.received_samples)),
        "transmitter_sample_count": int(len(truth.transmitter_samples)),
        "path_count": len(truth.path_delays_samples),
        "output_length_policy": result.config_snapshot["output_length_policy"],
        "paper_exact": False,
        "receiver_enabled": False,
        "receiver_observation_sha256": obs.sha256,
        "evaluation_truth_npz": truth_meta["file"],
        "config": result.config_snapshot,
        "reproducibility": result.reproducibility_metadata,
        "array_storage_bytes": result.array_storage_bytes,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files = (
        "channel_config.json",
        "receiver_observation.npz",
        "receiver_observation.json",
        "evaluation_truth.npz",
        "summary.json",
    )
    manifest = {
        "schema_version": "repro03-channel-v1",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "channel_config_sha256": _digest(
            json.dumps(result.config_snapshot, sort_keys=True, separators=(",", ":")).encode()
        ),
        "receiver_observation_sha256": obs.sha256,
        "files": {name: _digest((root / name).read_bytes()) for name in files},
        "receiver_observation": observation_meta,
        "evaluation_truth": truth_meta,
        "reproducibility": result.reproducibility_metadata,
        "paper_exact": False,
        "receiver_enabled": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
