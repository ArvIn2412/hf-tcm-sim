from pathlib import Path

import numpy as np

from hf_tcm.repro.energy_experiment import EnergyTrialSpec, atomic_json, run_energy_trial

R = Path("outputs/scientific_exp_01")
checks = []
for si, sc in enumerate(["awgn", "static", "rician"]):
    for t in range(3):
        specs = [
            EnergyTrialSpec("validation", sc, s, 3.0, 1, t, 256) for s in ["amplitude", "noise"]
        ]
        seeds = [22000 + si * 100 + t * 10 + i for i in range(3)]
        rows = [run_energy_trial(s, R, seed_override=seeds) for s in specs]
        paths = [
            R / "validation" / sc / s / f"p01/t{t:04d}/arrays.npz" for s in ["amplitude", "noise"]
        ]
        with np.load(paths[0]) as a, np.load(paths[1]) as b:
            checks.append(
                {
                    "scenario": sc,
                    "trial": t,
                    "F": 256,
                    "gamma_db": 3.0,
                    "received_scaled_max_difference": float(
                        np.max(
                            abs(a["received_samples"] / specs[0].amplitude - b["received_samples"])
                        )
                    ),
                    "coefficients_identical": bool(
                        np.array_equal(a["coefficients"], b["coefficients"])
                    ),
                    "decoded_bit_differences": {
                        arm: int(np.sum(a[arm + "_decoded_bits"] != b[arm + "_decoded_bits"]))
                        for arm in rows[0]["ber"]
                    },
                    "purpose": "posthoc scaling diagnostic; excluded from inferential trial groups",
                }
            )
        print(checks[-1], flush=True)
atomic_json(R / "scaling_diagnostic.json", checks)
