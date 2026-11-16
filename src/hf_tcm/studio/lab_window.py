"""Bounded read-only windows over verified metric NPZ files (no receiver calls)."""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from hf_tcm.repro.encoder import encode
from hf_tcm.repro.metric_isolation import build_pilot_schedule

_CACHE: OrderedDict[tuple, tuple[dict, int]] = OrderedDict()
_LOCK = RLock()
_BUDGET = 64 * 1024 * 1024


def _dataset(root: Path, study_id: str, point: int, trial: int) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", study_id):
        raise ValueError("invalid study ID")
    if min(point, trial) < 0:
        raise ValueError("invalid trial index")
    folder = root / study_id
    if not folder.resolve().is_relative_to(root.resolve()):
        raise ValueError("study path outside root")
    stem = f"p{point:03d}-t{trial:04d}"
    files = [
        folder / p
        for p in ("manifest.json", "config.json", f"trials/{stem}.json", f"trials/{stem}.npz")
    ]
    key = (
        str(folder.resolve()),
        point,
        trial,
        *((p.stat().st_mtime_ns, p.stat().st_size) for p in files),
    )
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key][0]
    manifest = json.loads(files[0].read_text(encoding="utf8"))
    for path in files[1:]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest["files"].get(path.relative_to(folder).as_posix()) != digest:
            raise ValueError("window source SHA-256 mismatch")
    config = json.loads(files[1].read_text(encoding="utf8"))
    record = json.loads(files[2].read_text(encoding="utf8"))
    if (
        record["observation_sha256"] != record["paired_observation_sha256"]
        or record["frontend_output_sha256_hamming"] != record["frontend_output_sha256_euclidean"]
    ):
        raise ValueError("window observations are not paired")
    if hashlib.sha256(files[3].read_bytes()).hexdigest() != record["array_file_sha256"]:
        raise ValueError("window array SHA-256 mismatch")
    with np.load(files[3], allow_pickle=False) as source:
        keys = [
            "transmitted_samples",
            "received_samples",
            "equalized_symbols",
            "payload_mask",
            "reference_payload_pairs",
            "decoded_hamming_pairs",
            "decoded_euclidean_pairs",
        ]
        data = {k: source[k] for k in keys}
    n = len(data["payload_mask"])
    inputs = np.zeros((n, 2), dtype=np.int8)
    inputs[data["payload_mask"]] = data["reference_payload_pairs"]
    if config["frontend_mode"] != "awgn_direct_control":
        schedule = build_pilot_schedule(
            frame_symbols=n,
            preamble_symbols=config["preamble_symbols"],
            pilot_period=config["pilot_period"],
            pilot_burst_symbols=config["pilot_burst_symbols"],
        )
        inputs[~data["payload_mask"]] = schedule.pilot_input_pairs[~data["payload_mask"]]
    encoded = encode(inputs)
    data.update(
        inputs=inputs, coded=encoded.coded_triples, pre=encoded.pre_states, post=encoded.post_states
    )
    positions = np.flatnonzero(data["payload_mask"])
    inverse = np.full(n, -1, dtype=np.int64)
    inverse[positions] = np.arange(len(positions))
    data.update(positions=positions, inverse=inverse, config=config, record=record)
    data["errors"] = np.any(data["decoded_hamming_pairs"] != inputs, axis=1) | np.any(
        data["decoded_euclidean_pairs"] != inputs, axis=1
    )
    cost = sum(a.nbytes for a in data.values() if isinstance(a, np.ndarray))
    if cost <= _BUDGET:
        with _LOCK:
            while _CACHE and sum(v[1] for v in _CACHE.values()) + cost > _BUDGET:
                _CACHE.popitem(last=False)
            _CACHE[key] = (data, cost)
    return data


def load_lab_window(
    root: Path,
    study_id: str,
    *,
    start: int = 0,
    count: int = 160,
    selected: int = 0,
    bins: int = 800,
    point: int = 0,
    trial: int = 0,
    domain: str = "sample",
    index: int = 0,
    direction: int = 0,
) -> dict[str, Any]:
    """Return at most bins envelope buckets, 2000 cloud points and one exact inspector."""
    if not 32 <= bins <= 1600 or count < 1 or start < 0:
        raise ValueError("invalid window bounds")
    d = _dataset(root, study_id, point, trial)
    n = len(d["payload_mask"])
    total = n * 8
    sizes = {
        "symbol": n,
        "trellis": n,
        "sample": total,
        "information": len(d["positions"]) * 2,
        "coded": n * 3,
    }
    if domain not in sizes or not 0 <= index < sizes[domain]:
        raise ValueError("invalid domain index")
    if domain != "sample":
        symbol = (
            int(d["positions"][index // 2])
            if domain == "information"
            else index // 3
            if domain == "coded"
            else index
        )
        selected = symbol * 8
    if not 0 <= selected < total or start >= total or count > total:
        raise ValueError("sample outside frame")
    if direction not in (-1, 0, 1):
        raise ValueError("invalid error direction")
    if direction:
        errors = np.flatnonzero(d["errors"])
        candidates = (
            errors[errors > selected // 8] if direction > 0 else errors[errors < selected // 8]
        )
        if len(candidates):
            selected = int(candidates[0] if direction > 0 else candidates[-1]) * 8
            start = max(0, min(total - count, selected - count // 2))
    stop = min(total, start + count)
    k = selected // 8
    rank = int(d["inverse"][k])
    tx, rx = d["transmitted_samples"], d["received_samples"]

    def series(a: np.ndarray, lo: int, hi: int) -> dict:
        width = max(1, int(np.ceil((hi - lo) / bins)))
        if width == 1:
            return {"raw": True, "points": [[i, float(a[i])] for i in range(lo, hi)]}
        return {
            "raw": False,
            "points": [
                [
                    i,
                    float(np.min(a[i : min(i + width, hi)])),
                    float(np.max(a[i : min(i + width, hi)])),
                ]
                for i in range(lo, hi, width)
            ],
        }

    components = {"TX I": tx.real, "TX Q": tx.imag, "RX I": rx.real, "RX Q": rx.imag}
    indices = np.union1d(
        np.linspace(start, stop - 1, min(2000, stop - start), dtype=int), [selected]
    )
    cloud = []
    for s in indices:
        j = int(s) // 8
        z, f = rx[s], d["equalized_symbols"][j]
        phase = int(round(np.angle(tx[j * 8]) * 4 / np.pi)) % 8
        cloud.append(
            {
                "sample": int(s),
                "symbol": j,
                "i": float(z.real),
                "q": float(z.imag),
                "fi": float(f.real),
                "fq": float(f.imag),
                "phase": phase,
                "pilot": not bool(d["payload_mask"][j]),
                "hard_error": (int(round(np.angle(f) * 4 / np.pi)) % 8) != phase,
                "hamming": d["decoded_hamming_pairs"][j].tolist(),
                "euclidean": d["decoded_euclidean_pairs"][j].tolist(),
            }
        )
    return {
        "run_id": study_id,
        "amplitude": d["record"]["amplitude"],
        "total_samples": total,
        "total_symbols": n,
        "domain_sizes": sizes,
        "start": start,
        "stop": stop,
        "selected": selected,
        "seed": d["config"].get("root_seed"),
        "frontend": d["config"]["frontend_mode"],
        "observation_sha256": d["record"]["observation_sha256"],
        "frontend_sha256": d["record"]["frontend_output_sha256_hamming"],
        "series": {name: series(a, start, stop) for name, a in components.items()},
        "overview": series(rx.real, 0, total),
        "cloud": cloud,
        "events": [
            [int(i), bool(d["payload_mask"][i]), bool(d["errors"][i])]
            for i in range(start // 8, min(n, (stop + 7) // 8))
        ]
        if count <= 1600
        else [],
        "overview_events": [
            [
                int(i),
                bool(np.any(d["errors"][i : min(i + max(1, n // bins), n)])),
                int(np.count_nonzero(~d["payload_mask"][i : min(i + max(1, n // bins), n)])),
            ]
            for i in range(0, n, max(1, n // bins))
        ],
        "inspector": {
            "symbol": k,
            "sample": selected,
            "kind": "data" if rank >= 0 else "pilot",
            "information_bits": None if rank < 0 else [rank * 2, rank * 2 + 1],
            "input": d["inputs"][k].tolist(),
            "coded": d["coded"][k].tolist(),
            "pre": d["pre"][k].tolist(),
            "post": d["post"][k].tolist(),
            "tx_i": float(tx[selected].real),
            "tx_q": float(tx[selected].imag),
            "rx_i": float(rx[selected].real),
            "rx_q": float(rx[selected].imag),
            "hamming": d["decoded_hamming_pairs"][k].tolist(),
            "euclidean": d["decoded_euclidean_pairs"][k].tolist(),
        },
    }
