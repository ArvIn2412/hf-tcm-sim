import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

from hf_tcm.repro.energy_experiment import atomic_json
from hf_tcm.repro.repro08_channel_aware_hard import PublicStaticTap, Repro08HardReceiverConfig

R = Path("outputs/scientific_exp_01")
rows = [
    json.loads(p.read_text())
    for p in R.glob("*/*/*/p*/t*/record.json")
    if (p.parent / "manifest.json").exists()
]
rows = [r for r in rows if r["phase"] in {"pilot", "confirmatory", "long"}]
supp = []
for r in rows:
    if "b1" in r["ber"]:
        taps = tuple(
            PublicStaticTap(p["delay_samples"], complex(*p["constant_coefficient"]))
            for p in r["channel_config"]["paths"]
        )
        supp.append(
            {
                "trial": [
                    r[k] for k in ["phase", "scenario", "sweep", "point_index", "trial_index"]
                ],
                "provenance": "configuration replay from persisted public static path specification, not hidden fading",
                "config": Repro08HardReceiverConfig(
                    r["frame_symbols"], taps, amplitude=r["amplitude"]
                ).to_dict(),
            }
        )
atomic_json(R / "b1_configuration_supplement.json", supp)
contrasts = []
for phase in ["pilot", "confirmatory"]:
    for sc in ["awgn", "static", "rician"]:
        gammas = sorted(
            {r["gamma_db"] for r in rows if r["phase"] == phase and r["scenario"] == sc}
        )
        for i, g in enumerate(gammas):
            a = [
                r
                for r in rows
                if (r["phase"], r["scenario"], r["gamma_db"], r["sweep"])
                == (phase, sc, g, "amplitude")
            ]
            b = [
                r
                for r in rows
                if (r["phase"], r["scenario"], r["gamma_db"], r["sweep"]) == (phase, sc, g, "noise")
            ]
            if not a or not b:
                continue
            rng = np.random.default_rng(
                np.random.SeedSequence(
                    [
                        94201,
                        1 if phase == "pilot" else 2,
                        {"awgn": 1, "static": 2, "rician": 3}[sc],
                        i,
                    ]
                )
            )
            ia = rng.integers(len(a), size=(2000, len(a)))
            ib = rng.integers(len(b), size=(2000, len(b)))
            for arm in a[0]["ber"]:
                ba = np.array([r["bits"] for r in a])
                bb = np.array([r["bits"] for r in b])
                ea = np.array([r["bit_errors"][arm] for r in a])
                eb = np.array([r["bit_errors"][arm] for r in b])
                dif = ea[ia].sum(axis=1) / ba[ia].sum(axis=1) - eb[ib].sum(axis=1) / bb[ib].sum(
                    axis=1
                )
                contrasts.append(
                    {
                        "phase": phase,
                        "scenario": sc,
                        "gamma_db": g,
                        "arm": arm,
                        "trials": [len(a), len(b)],
                        "difference_ber_amplitude_minus_noise": float(
                            ea.sum() / ba.sum() - eb.sum() / bb.sum()
                        ),
                        "pointwise_ci95": np.quantile(dif, [0.025, 0.975]).tolist(),
                        "method": "independent trial clusters per sweep, paired arms within sweep; percentile2000",
                        "multiple_comparison_control": False,
                        "interpretation": "not an equivalence test; zero-degenerate intervals not probability bounds",
                    }
                )
atomic_json(R / "sweep_contrast_ci.json", contrasts)
atomic_json(
    R / "source_fingerprints.json",
    {
        p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path("src/hf_tcm/repro").rglob("*.py"))
        if "__pycache__" not in p.parts
    },
)
atomic_json(
    R / "environment.json",
    {
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "new_infrastructure_fixes": [
            "canonical tuple/list replay",
            "private ctypes library instances avoid legacy contract pollution",
        ],
        "memory_note": "main peak fields unavailable in process loaded before private-handle fix; long process records measured OS high-water; batch memory not bounded-core benchmark",
    },
)
print(len(rows), "records supplemented", len(supp), "sweep contrasts", len(contrasts))
