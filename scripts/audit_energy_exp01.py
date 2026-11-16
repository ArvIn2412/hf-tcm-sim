"""Independent replay of completed energy records; no decoder is called."""

import hashlib
import json
from pathlib import Path

import numpy as np

from hf_tcm.repro.energy_experiment import atomic_json

R = Path("outputs/scientific_exp_01")
rows = []
seeds = set()
max_error = 0.0
for p in sorted(R.glob("*/*/*/p*/t*/record.json")):
    r = json.loads(p.read_text())
    d = p.parent
    m = json.loads((d / "manifest.json").read_text())
    for f, h in m["files"].items():
        assert hashlib.sha256((d / f).read_bytes()).hexdigest() == h
    with np.load(d / "arrays.npz", allow_pickle=False) as a:
        bits = a["information_bits"]
        x = a["tx_samples"]
        y = a["received_samples"]
        w = a["noise_samples"]
        h = a["coefficients"]
        N = len(y)
        ind = np.arange(N, dtype=np.int64)
        assert len(bits) == 2 * r["frame_symbols"]
        assert len(x) == 8 * r["frame_symbols"]
        assert N == len(x) + max(r["delays"])
        manual = np.zeros(N, dtype=complex)
        for path, delay in enumerate(r["delays"]):
            manual[delay : delay + len(x)] += h[path, delay : delay + len(x)] * x
        err = float(np.max(abs(y - manual - w)))
        assert err < 1e-11
        max_error = max(err, max_error)
        energy = float(sum(v.real * v.real + v.imag * v.imag for v in x))
        assert np.isclose(energy, r["tx_energy"])
        assert np.isclose(energy / len(bits), 4 * r["amplitude"] ** 2)
        obs = hashlib.sha256()
        for name, array in [
            ("received_samples", y),
            ("absolute_sample_index", ind),
            ("sample_symbol_index", ind // 8),
            ("sample_local_index", ind % 8),
        ]:
            array = np.ascontiguousarray(array)
            obs.update(name.encode())
            obs.update(str(array.dtype).encode())
            obs.update(np.asarray(array.shape, dtype=np.int64).tobytes())
            obs.update(array.tobytes())
        public = {
            "samples_per_symbol": 8,
            "profile_id": "energy01_" + r["scenario"],
            "model_id": "repro03_discrete_complex_baseband_v1",
            "sampling_convention": "discrete_complex_baseband_absolute_sample_index",
            "boundary_policy": "zero_extension",
            "output_length_policy": "tx_plus_max_delay",
            "noise_model": "complex_awgn_sample_domain",
            "noise_complex_variance": None,
        }
        obs.update(json.dumps(public, sort_keys=True, separators=(",", ":")).encode())
        assert obs.hexdigest() == r["observation_sha256"]
        for arm in r["bit_errors"]:
            dec = a[arm + "_decoded_bits"]
            mismatches = dec != bits
            be = sum(int(v) for v in mismatches)
            pe = sum(bool(mismatches[i]) or bool(mismatches[i + 1]) for i in range(0, len(bits), 2))
            assert (
                be == r["bit_errors"][arm]
                and pe == r["pair_errors"][arm]
                and int(be > 0) == r["frame_errors"][arm]
            )
            assert r["receiver_observation_hashes"][arm] == obs.hexdigest()
        if r["phase"] in {"pilot", "confirmatory"}:
            for s in r["seeds"].values():
                assert s not in seeds
                seeds.add(s)
        rows.append(
            {
                "record": p.as_posix(),
                "record_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "tx_bits_sha256": hashlib.sha256(bits.tobytes()).hexdigest(),
                "received_buffer_sha256": hashlib.sha256(y.tobytes()).hexdigest(),
                "noise_variance_complex_empirical": float(np.mean(abs(w) ** 2)),
                "noise_i_variance": float(np.var(w.real)),
                "noise_q_variance": float(np.var(w.imag)),
                "path_powers_measured": np.mean(abs(h) ** 2, axis=1).tolist(),
                "verified": True,
            }
        )
atomic_json(
    R / "independent_replay.json",
    {
        "completed_records": len(rows),
        "status": "PASS",
        "max_signal_law_residual": max_error,
        "records": rows,
    },
)
print("Independent replay PASS", len(rows), max_error)
