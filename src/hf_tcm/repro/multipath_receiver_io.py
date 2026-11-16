"""NPZ/JSON persistence and SHA-256 verification for REPRO-06B outputs."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.channel_result import ReceiverObservation
from hf_tcm.repro.multipath_evaluation import MultipathReceiverEvaluation
from hf_tcm.repro.multipath_joint_receiver import MultipathJointReceiverResult


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    return _sha_bytes(np.ascontiguousarray(array).tobytes())


def save_multipath_receiver_result(
    result: MultipathJointReceiverResult,
    observation: ReceiverObservation,
    output_dir: str | Path,
    *,
    evaluation: MultipathReceiverEvaluation | None = None,
) -> dict[str, Any]:
    """Save receiver observations/results without copying EvaluationTruth."""
    if not isinstance(result, MultipathJointReceiverResult):
        raise TypeError("result must be MultipathJointReceiverResult")
    if (
        type(observation) is not ReceiverObservation
        or observation.sha256 != result.observation_sha256
    ):
        raise ValueError("observation must match the receiver result SHA-256")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "receiver_config.json"
    config_path.write_text(
        json.dumps(result.receiver_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    observation_path = root / "receiver_observation.npz"
    observation_arrays = {
        "received_samples": observation.received_samples,
        "absolute_sample_index": observation.absolute_sample_index,
        "sample_symbol_index": observation.sample_symbol_index,
        "sample_local_index": observation.sample_local_index,
    }
    np.savez_compressed(observation_path, **observation_arrays)
    output_arrays: dict[str, np.ndarray] = {
        "sample_indices": result.sample_indices,
        "sample_ranges": result.sample_ranges,
        "branch_metric_rows": result.branch_metric_rows,
        "diagnostic_sample_indices": result.diagnostic_sample_indices,
        "diagnostic_candidate_predictions": result.diagnostic_candidate_predictions,
        "survivor_state_metrics": result.survivor_state_metrics,
        "survivor_expanded_edge_ids": result.survivor_expanded_edge_ids,
        "decision_base_edge_ids": result.decision_base_edge_ids,
        "decoded_edge_ids": result.decoded_edge_ids,
        "decoded_state_path": result.decoded_state_path,
        "decoded_information_pairs": result.decoded_information_pairs,
        "decoded_information_bits": result.decoded_information_bits,
        "expanded_node_encoder_states": np.asarray(
            [node["encoder_state"] for node in result.expanded_nodes], dtype=np.int8
        ),
        "expanded_node_phase_history": np.asarray(
            [node["previous_phase_history"] for node in result.expanded_nodes], dtype=np.int8
        ),
        "expanded_edges": np.asarray(
            [
                [
                    edge["expanded_edge_id"],
                    edge["source_node_id"],
                    edge["target_node_id"],
                    edge["base_edge_id"],
                    *edge["input_pair"],
                    edge["phase_index"],
                ]
                for edge in result.expanded_edges
            ],
            dtype=np.int32,
        ),
        "decision_symbol_index": np.asarray(
            [decision.symbol_index for decision in result.decisions], dtype=np.int64
        ),
        "decision_available_at": np.asarray(
            [decision.decision_available_at for decision in result.decisions], dtype=np.int64
        ),
        "decision_traceback_depth": np.asarray(
            [decision.traceback_depth_used for decision in result.decisions], dtype=np.int16
        ),
        "decision_expanded_edge_id": np.asarray(
            [decision.expanded_edge_id for decision in result.decisions], dtype=np.int32
        ),
        "decision_base_edge_id": np.asarray(
            [decision.base_edge_id for decision in result.decisions], dtype=np.int16
        ),
        "decision_input_pair": np.asarray(
            [decision.input_pair for decision in result.decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "decision_encoder_source_state": np.asarray(
            [decision.encoder_source_state for decision in result.decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "decision_encoder_target_state": np.asarray(
            [decision.encoder_target_state for decision in result.decisions], dtype=np.int8
        ).reshape((-1, 2)),
        "decision_source_node_id": np.asarray(
            [decision.source_node_id for decision in result.decisions], dtype=np.int32
        ),
        "decision_target_node_id": np.asarray(
            [decision.target_node_id for decision in result.decisions], dtype=np.int32
        ),
    }
    if evaluation is not None:
        output_arrays.update(
            {
                "evaluation_bit_error_positions": evaluation.bit_error_positions,
                "evaluation_symbol_error_positions": evaluation.symbol_error_positions,
                "evaluation_reference_phase_indices": evaluation.reference_phase_indices,
            }
        )
    result_path = root / "multipath_receiver_result.npz"
    np.savez_compressed(result_path, **output_arrays)
    compact_diagnostics = {
        key: value for key, value in result.diagnostics.items() if key != "decision_records"
    }
    compact_diagnostics["decision_record_count"] = len(result.decisions)
    compact_diagnostics["decision_records_storage"] = (
        "multipath_receiver_result.npz decision_* arrays"
    )
    summary: dict[str, Any] = {
        "schema_version": "repro06b-multipath-joint-v1",
        "receiver_config": result.receiver_config,
        "observation_sha256": result.observation_sha256,
        "config_sha256": result.config_sha256,
        "result_sha256": result.result_sha256,
        "receiver_profile_id": result.receiver_profile_id,
        "metric_profile": result.metric_profile,
        "encoder_id": result.encoder_id,
        "mapping_id": result.mapping_id,
        "mapping_status": result.mapping_status,
        "trellis": {
            "state_count": result.trellis_state_count,
            "edge_count": result.trellis_edge_count,
            "channel_memory_symbols": result.channel_memory_symbols,
            "nodes": result.expanded_nodes,
            "edges": result.expanded_edges,
        },
        "traceback": {
            "mode": result.decoder_mode,
            "depth": result.traceback_depth,
            "survivor_buffer_max_rows": result.survivor_buffer_max_rows,
            "terminal_survivor_node_id": result.terminal_survivor_node_id,
        },
        "final_state": list(result.final_state),
        "final_path_metric": result.final_path_metric,
        "diagnostic_symbol_index": result.diagnostic_symbol_index,
        "diagnostics": compact_diagnostics,
        "reproducibility_metadata": result.reproducibility_metadata,
        "result_arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "sha256": _array_hash(array),
            }
            for name, array in output_arrays.items()
        },
        "paper_exact": False,
        "receiver_enabled": False,
    }
    if evaluation is not None:
        summary["evaluation_only"] = {
            "bit_errors": evaluation.bit_errors,
            "ber": evaluation.ber,
            "symbol_errors": evaluation.symbol_errors,
            "ser": evaluation.ser,
            "compared_information_bit_count": evaluation.compared_information_bit_count,
            "compared_symbol_count": evaluation.compared_symbol_count,
            "evidence_scope": evaluation.evidence_scope,
        }
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    file_paths = (config_path, observation_path, result_path, summary_path)
    manifest = {
        "schema_version": "repro06b-multipath-joint-v1",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "observation_sha256": result.observation_sha256,
        "config_sha256": result.config_sha256,
        "result_sha256": result.result_sha256,
        "files": {
            path.name: {
                "size_bytes": path.stat().st_size,
                "sha256": _sha_bytes(path.read_bytes()),
            }
            for path in file_paths
        },
        "paper_exact": False,
        "receiver_enabled": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_multipath_receiver_manifest(output_dir: str | Path) -> dict[str, int]:
    """Check every listed file's exact size and SHA; no files are changed."""
    root = Path(output_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    verified = failed = 0
    for name, entry in manifest["files"].items():
        path = root / name
        if not path.is_file():
            failed += 1
            continue
        if (
            path.stat().st_size != entry["size_bytes"]
            or _sha_bytes(path.read_bytes()) != entry["sha256"]
        ):
            failed += 1
        else:
            verified += 1
    return {"verified": verified, "failed": failed}
