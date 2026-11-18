"""Whole-frame view of one verified metric-isolation trial (read-only).

Serves the «Канал у часі» and «Декодування» tabs: per-symbol effective SNR of the
shared frontend output, the offset of z_k from the transmitted point, both arms'
replayed decoded paths against the transmitted path, and error events. Sources are
checked by manifest/array SHA-256 and the decoders are replayed exactly as in
``metric_trace``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from hf_tcm.repro.encoder import STATE_ORDER, encode, transition_table
from hf_tcm.studio.metric_trace import open_verified_trial, pilot_constraints, replay_arm

ARMS = ("hamming", "euclidean")


def error_events(decoded_edges: np.ndarray, true_edges: np.ndarray) -> list[dict[str, int]]:
    """Maximal runs of steps where the decoded transition differs from the sent one.

    A run starts where the decoded path leaves the transmitted path (or takes a
    parallel transition) and ends where both paths use the same edge again.
    """
    wrong = np.asarray(decoded_edges) != np.asarray(true_edges)
    events = []
    k = 0
    size = len(wrong)
    while k < size:
        if not wrong[k]:
            k += 1
            continue
        start = k
        while k < size and wrong[k]:
            k += 1
        events.append({"start": int(start), "stop": int(k)})
    return events


def _bins(values: np.ndarray, bins: int) -> list[list[float]]:
    width = max(1, int(np.ceil(len(values) / bins)))
    out = []
    for i in range(0, len(values), width):
        chunk = values[i : i + width]
        out.append([int(i), float(chunk.min()), float(chunk.max())])
    return out


def load_metric_frame(
    root: Path, study_id: str, *, point: int = 0, trial: int = 0, bins: int = 1200
) -> dict[str, Any]:
    if not 64 <= bins <= 4000:
        raise ValueError("invalid bin count")
    config, record, array_path = open_verified_trial(root, study_id, point=point, trial=trial)
    with np.load(array_path, allow_pickle=False) as data:
        if "equalized_symbols" not in data.files:
            raise ValueError(
                "this trial stores compact recount arrays only; open a sampled trial "
                "(trial index divisible by full_array_stride)"
            )
        z = data["equalized_symbols"]
        size = len(z)
        constraints = pilot_constraints(config, size)
        payload_mask = data["payload_mask"]
        inputs = np.empty((size, 2), dtype=np.int8)
        inputs[payload_mask] = data["reference_payload_pairs"]
        if constraints is not None:
            inputs[~payload_mask] = constraints[~payload_mask]
        sent = encode(inputs)
        true_edges = np.asarray(sent.edge_ids, dtype=int)
        tx = data["transmitted_samples"].reshape(size, 8)[:, 0]
        amplitude = float(record["amplitude"])
        sent_points = tx / np.maximum(np.abs(tx), 1e-300) * amplitude
        variance = np.asarray(data["output_noise_variance"], dtype=float)
        with np.errstate(divide="ignore"):
            snr_db = 10.0 * np.log10(amplitude**2 / np.maximum(variance, 1e-300))
        gain = np.abs(data["estimated_composite_gain"])
        rx = data["received_samples"][: size * 8]
        edges = transition_table()
        state_index = {state: i for i, state in enumerate(STATE_ORDER)}
        target = np.array([state_index[e[4]] for e in edges])
        arms = {}
        for arm in ARMS:
            replay = replay_arm(data, arm, constraints)
            decoded = np.asarray(replay.decoded_edge_ids, dtype=int)
            pair_errors = np.any(data[f"decoded_{arm}_pairs"] != inputs, axis=1)
            arms[arm] = {
                "decoded_states": target[decoded].tolist(),
                "pair_errors": pair_errors.tolist(),
                "events": error_events(decoded, true_edges),
                "statistics": record[arm],
            }
    phases = np.mod(np.rint(np.angle(tx) * 4 / np.pi), 8).astype(int)
    points = amplitude * np.exp(1j * np.arange(8) * np.pi / 4)
    hard = np.argmin(np.abs(z[:, None] - points[None, :]), axis=1)
    return {
        "study_id": study_id,
        "trial_id": record["trial_id"],
        "configuration": config,
        "gamma_b_discrete_db": record["gamma_b_discrete_db"],
        "amplitude": amplitude,
        "size": size,
        "states": STATE_ORDER,
        "payload_mask": payload_mask.tolist(),
        "true_states": target[true_edges].tolist(),
        "effective_snr_db": [round(float(v), 4) if np.isfinite(v) else None for v in snr_db],
        "channel_gain": np.round(gain, 5).tolist(),
        "offset": np.round(np.abs(z - sent_points), 5).tolist(),
        "hard_correct": (hard == phases).tolist(),
        "rx_i": _bins(rx.real, bins),
        "rx_q": _bins(rx.imag, bins),
        "samples_per_symbol": 8,
        "arms": arms,
        "replay_verified": True,
    }
