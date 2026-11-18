"""Read-only visualization adapter over verified saved metric trials."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.encoder import STATE_ORDER, encode, transition_table
from hf_tcm.repro.metric_isolation import build_pilot_schedule, run_metric_viterbi


@lru_cache(maxsize=4)
def _replay(rows_bytes: bytes, dtype: str, size: int, constraint_bytes: bytes | None) -> Any:
    """Bounded immutable-key cache; source hashes are checked on every request."""
    rows = np.frombuffer(rows_bytes, dtype=dtype).reshape(size, -1)
    constraints = (
        None
        if constraint_bytes is None
        else np.frombuffer(constraint_bytes, dtype=np.int8).reshape(size, 2)
    )
    return run_metric_viterbi(rows, allowed_input_pairs=constraints)


def load_metric_trace(
    root: Path,
    study_id: str,
    *,
    point: int = 0,
    trial: int = 0,
    start: int = 0,
    count: int = 20,
    limit: int = 1000,
    compact: bool = False,
) -> dict[str, Any]:
    """Replay maintained decoder and require exact agreement with persisted bits."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", study_id):
        raise ValueError("invalid study ID")
    if min(point, trial, start) < 0 or not 1 <= count <= 80 or not 8 <= limit <= 4000:
        raise ValueError("invalid trace range")
    folder = root / study_id
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
    stem = f"p{point:03d}-t{trial:04d}"
    for relative in ("config.json", f"trials/{stem}.json", f"trials/{stem}.npz"):
        expected = manifest.get("files", {}).get(relative)
        if not expected or hashlib.sha256((folder / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("trace source manifest SHA-256 mismatch")
    config = json.loads((folder / "config.json").read_text(encoding="utf8"))
    record = json.loads((folder / "trials" / f"{stem}.json").read_text(encoding="utf8"))
    array_path = folder / "trials" / f"{stem}.npz"
    if hashlib.sha256(array_path.read_bytes()).hexdigest() != record["array_file_sha256"]:
        raise ValueError("trial array SHA-256 mismatch")
    with np.load(array_path, allow_pickle=False) as data:
        if "equalized_symbols" not in data.files:
            raise ValueError(
                "this trial stores compact recount arrays only; open a sampled trial "
                "(trial index divisible by full_array_stride)"
            )
        size = len(data["equalized_symbols"])
        if start >= size:
            raise ValueError("trace start is outside frame")
        stop = min(size, start + count)
        constraints = None
        if config["frontend_mode"] != "awgn_direct_control":
            schedule = build_pilot_schedule(
                frame_symbols=size,
                preamble_symbols=config["preamble_symbols"],
                pilot_period=config["pilot_period"],
                pilot_burst_symbols=config["pilot_burst_symbols"],
            )
            constraints = np.full((size, 2), -1, dtype=np.int8)
            constraints[schedule.pilot_mask] = schedule.pilot_input_pairs[schedule.pilot_mask]
        edges = transition_table()
        arms = {}
        for arm in ("hamming", "euclidean"):
            rows = data[f"{arm}_branch_metrics"]
            replay = _replay(
                rows.tobytes(),
                rows.dtype.str,
                size,
                None if constraints is None else constraints.tobytes(),
            )
            if not np.array_equal(replay.information_pairs, data[f"decoded_{arm}_pairs"]):
                raise ValueError("decoder trace replay does not match saved result")
            metrics = np.array(replay.state_metrics[start : stop + 1], dtype=float, copy=True)
            metrics[metrics > 1e18] = np.inf
            arms[arm] = {
                "branch_metrics": rows[start:stop].tolist(),
                "state_metrics": [
                    [float(v) if np.isfinite(v) else None for v in row] for row in metrics
                ],
                "survivors": replay.survivor_edge_ids[start:stop].tolist(),
                "decoded_edges": replay.decoded_edge_ids[start:stop].tolist(),
                "bits": replay.information_pairs[start:stop].tolist(),
                "decisions": [asdict(d) for d in replay.decisions[start:stop]],
                "decoded_phases": [
                    4 * edges[e][3][0] + 2 * edges[e][3][1] + edges[e][3][2]
                    for e in replay.decoded_edge_ids
                ],
                "statistics": record[arm],
            }
        tx = data["transmitted_samples"].reshape(size, 8)[:, 0]
        inputs = np.empty((size, 2), dtype=np.int8)
        payload_mask = data["payload_mask"]
        payload_positions = np.flatnonzero(payload_mask)
        payload_indices = np.full(size, -1, dtype=int)
        payload_indices[payload_positions] = np.arange(len(payload_positions))
        inputs[payload_mask] = data["reference_payload_pairs"]
        if constraints is not None:
            inputs[~payload_mask] = constraints[~payload_mask]
        encoded = encode(inputs)
        for arm in arms:
            arms[arm]["pair_error_mask"] = np.any(
                data[f"decoded_{arm}_pairs"] != inputs, axis=1
            ).tolist()
        phases = np.mod(np.rint(np.angle(tx) * 4 / np.pi), 8).astype(int)
        # Include every exact sample in the selected window, even when the
        # deterministic overview sample would otherwise miss that position.
        indices = np.union1d(
            np.linspace(0, size * 8 - 1, min(limit, size * 8), dtype=int),
            np.arange(start * 8, stop * 8),
        )
        symbol_indices = np.unique(indices // 8)
        rx = data["received_samples"][indices]
        frontend = data["equalized_symbols"][symbol_indices]
        points = [
            {
                "sample": int(i),
                "symbol": int(i // 8),
                "tx_phase": int(phases[i // 8]),
                "i": float(z.real),
                "q": float(z.imag),
            }
            for i, z in zip(indices, rx, strict=True)
        ]
        processed = [
            {"symbol": int(i), "tx_phase": int(phases[i]), "i": float(z.real), "q": float(z.imag)}
            for i, z in zip(symbol_indices, frontend, strict=True)
        ]
        result = {
            "study_id": study_id,
            "trial_id": record["trial_id"],
            "configuration": config,
            "record": record,
            "observation_sha256": record["observation_sha256"],
            "frontend_sha256": record["frontend_output_sha256_hamming"],
            "pairing_verified": record["frontend_output_sha256_hamming"]
            == record["frontend_output_sha256_euclidean"]
            and record["observation_sha256"] == record["paired_observation_sha256"],
            "replay_verified": True,
            "total_symbols": size,
            "payload_positions": payload_positions.tolist(),
            "payload_pair_indices": payload_indices[start:stop].tolist(),
            "payload_mask": payload_mask[start:stop].tolist(),
            "total_received_samples": len(data["received_samples"]),
            "start": start,
            "stop": stop,
            "states": STATE_ORDER,
            "edges": edges,
            "arms": arms,
            "received": points,
            "processed": processed,
            "amplitude": record["amplitude"],
            "tx_phases": phases[start:stop].tolist(),
            "transmitter": {
                "input_pairs": inputs[start:stop].tolist(),
                "coded_triples": encoded.coded_triples[start:stop].tolist(),
                "pre_states": encoded.pre_states[start:stop].tolist(),
                "post_states": encoded.post_states[start:stop].tolist(),
                "tx_i": data["transmitted_samples"][start * 8 : stop * 8].real.tolist(),
                "tx_q": data["transmitted_samples"][start * 8 : stop * 8].imag.tolist(),
                "rx_i": data["received_samples"][start * 8 : stop * 8].real.tolist(),
                "rx_q": data["received_samples"][start * 8 : stop * 8].imag.tolist(),
            },
            "visualization_only_sampling": True,
        }
        if compact:
            result["payload_count"] = len(payload_positions)
            del result["payload_positions"]
            result["compact"] = True
            for arm in arms.values():
                arm["decoded_phases"] = arm["decoded_phases"][start:stop]
                arm["pair_error_mask"] = arm["pair_error_mask"][start:stop]
        return result
