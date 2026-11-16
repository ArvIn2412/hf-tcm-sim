"""REPRO-04 observation/result NPZ serialization with receiver-only inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.channel_result import ReceiverObservation, readonly
from hf_tcm.repro.receiver_evaluation import ReceiverEvaluation
from hf_tcm.repro.separate_receiver import SeparateReceiverResult, _readonly


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_receiver_observation(directory: str | Path) -> ReceiverObservation:
    """Load only the public REPRO-03 NPZ/JSON pair; never open evaluation_truth.npz."""
    root = Path(directory)
    metadata = json.loads((root / "receiver_observation.json").read_text(encoding="utf-8"))
    npz_path = root / "receiver_observation.npz"
    if _sha256(npz_path.read_bytes()) != metadata["npz"]["sha256"]:
        raise ValueError("receiver observation NPZ SHA-256 does not match sidecar")
    with np.load(npz_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    required = {
        "received_samples",
        "absolute_sample_index",
        "sample_symbol_index",
        "sample_local_index",
    }
    if set(arrays) != required:
        raise ValueError("receiver observation NPZ has unexpected arrays")
    observation = ReceiverObservation(
        received_samples=readonly(arrays["received_samples"]),
        absolute_sample_index=readonly(arrays["absolute_sample_index"]),
        sample_symbol_index=readonly(arrays["sample_symbol_index"]),
        sample_local_index=readonly(arrays["sample_local_index"]),
        samples_per_symbol=int(metadata["samples_per_symbol"]),
        profile_id=metadata["profile_id"],
        model_id=metadata["model_id"],
        sampling_convention=metadata["sampling_convention"],
        boundary_policy=metadata["boundary_policy"],
        output_length_policy=metadata["output_length_policy"],
        noise_model=metadata["noise_model"],
        noise_complex_variance=metadata["noise_complex_variance"],
    )
    if observation.sha256 != metadata["receiver_observation_sha256"]:
        raise ValueError("semantic receiver observation hash does not match sidecar")
    return observation


def save_separate_receiver_result(
    result: SeparateReceiverResult,
    output_dir: str | Path,
    *,
    evaluation: ReceiverEvaluation | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    decisions = result.diagnostics.get("decision_records", [])
    arrays = {
        "processed_sample_ranges": result.processed_sample_ranges,
        "processed_sample_indices": result.processed_sample_indices,
        "unprocessed_sample_indices": result.unprocessed_sample_indices,
        "hard_phase_indices": result.hard_phase_indices,
        "hard_coded_triples": result.hard_coded_triples,
        "hard_symbol_squared_distances": result.hard_symbol_squared_distances,
        "hamming_branch_metrics": result.hamming_branch_metrics,
        "accumulated_state_metrics": result.accumulated_state_metrics,
        "survivor_edge_ids": result.survivor_edge_ids,
        "decoded_edge_ids": result.decoded_edge_ids,
        "decoded_state_path": result.decoded_state_path,
        "decoded_information_pairs": result.decoded_information_pairs,
        "decoded_information_bits": result.decoded_information_bits,
        "decoded_frame_information_bits": result.decoded_frame_information_bits,
        "decision_symbol_index": np.asarray(
            [row["symbol_index"] for row in decisions], dtype=np.int64
        ),
        "decision_available_at": np.asarray(
            [row["decision_available_at"] for row in decisions], dtype=np.int64
        ),
        "decision_traceback_depth_used": np.asarray(
            [row["traceback_depth_used"] for row in decisions], dtype=np.int64
        ),
        "decision_selected_edge_id": np.asarray(
            [row["edge_id"] for row in decisions], dtype=np.int16
        ),
        "decision_input_pairs": np.asarray(
            [row["input_pair"] for row in decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "decision_source_states": np.asarray(
            [row["source_state"] for row in decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "decision_target_states": np.asarray(
            [row["target_state"] for row in decisions], dtype=np.int8
        ).reshape((-1, 2)),
    }
    npz_path = root / "receiver_result.npz"
    np.savez_compressed(npz_path, **arrays)
    summary: dict[str, Any] = {
        "schema_version": "repro04-separate-receiver-v1",
        "receiver_config": result.receiver_config,
        "observation_sha256": result.observation_sha256,
        "output_npz_sha256": _sha256(npz_path.read_bytes()),
        "output_arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "sha256": _sha256(np.ascontiguousarray(array).tobytes()),
            }
            for name, array in arrays.items()
        },
        "final_state": list(result.final_state),
        "final_path_metric": result.final_path_metric,
        "edge_order_id": result.edge_order_id,
        "mapping_id": result.mapping_id,
        "mapping_status": result.mapping_status,
        "traceback_mode": result.traceback_mode,
        "decoder_depth": result.decoder_depth,
        "diagnostics": result.diagnostics,
        "reproducibility_metadata": result.reproducibility_metadata,
        "paper_exact": False,
        "receiver_enabled": False,
    }
    if evaluation is not None:
        summary["evaluation_only"] = {
            "compared_information_bit_count": evaluation.compared_information_bit_count,
            "bit_errors": evaluation.bit_errors,
            "ber": evaluation.ber,
            "compared_symbol_count": evaluation.compared_symbol_count,
            "symbol_errors": evaluation.symbol_errors,
            "ser": evaluation.ser,
            "bit_error_positions": evaluation.bit_error_positions.tolist(),
            "symbol_error_positions": evaluation.symbol_error_positions.tolist(),
            "evidence_scope": evaluation.evidence_scope,
        }
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "repro04-separate-receiver-v1",
        "files": {
            "receiver_result.npz": _sha256(npz_path.read_bytes()),
            "summary.json": _sha256(summary_path.read_bytes()),
        },
        "observation_sha256": result.observation_sha256,
        "receiver_output_arrays_sha256": result.reproducibility_metadata["output_arrays_sha256"],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def load_separate_receiver_result(directory: str | Path) -> SeparateReceiverResult:
    """Verify and reconstruct a saved receiver result without evaluation references."""
    root = Path(directory)
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    npz_path = root / "receiver_result.npz"
    if _sha256(npz_path.read_bytes()) != summary["output_npz_sha256"]:
        raise ValueError("receiver result NPZ SHA-256 does not match summary")
    with np.load(npz_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    declared = summary["output_arrays"]
    if set(arrays) != set(declared):
        raise ValueError("receiver result NPZ array set differs from summary")
    for name, array in arrays.items():
        metadata = declared[name]
        if list(array.shape) != metadata["shape"] or str(array.dtype) != metadata["dtype"]:
            raise ValueError(f"receiver result array schema mismatch: {name}")
        if _sha256(np.ascontiguousarray(array).tobytes()) != metadata["sha256"]:
            raise ValueError(f"receiver result array hash mismatch: {name}")
    names = (
        "processed_sample_ranges",
        "processed_sample_indices",
        "unprocessed_sample_indices",
        "hard_phase_indices",
        "hard_coded_triples",
        "hard_symbol_squared_distances",
        "hamming_branch_metrics",
        "accumulated_state_metrics",
        "survivor_edge_ids",
        "decoded_edge_ids",
        "decoded_state_path",
        "decoded_information_pairs",
        "decoded_information_bits",
        "decoded_frame_information_bits",
    )
    return SeparateReceiverResult(
        receiver_config=summary["receiver_config"],
        observation_sha256=summary["observation_sha256"],
        **{name: _readonly(arrays[name]) for name in names},
        final_state=tuple(summary["final_state"]),
        final_path_metric=int(summary["final_path_metric"]),
        edge_order_id=summary["edge_order_id"],
        mapping_id=summary["mapping_id"],
        mapping_status=summary["mapping_status"],
        traceback_mode=summary["traceback_mode"],
        decoder_depth=summary["decoder_depth"],
        diagnostics=summary["diagnostics"],
        reproducibility_metadata=summary["reproducibility_metadata"],
    )
