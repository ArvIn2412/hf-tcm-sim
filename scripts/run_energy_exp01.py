import json
import sys
import time
from pathlib import Path

from hf_tcm.repro.energy_experiment import (
    EnergyTrialSpec,
    atomic_json,
    canonical,
    digest,
    run_energy_trial,
)

R = Path("outputs/scientific_exp_01")
R.mkdir(exist_ok=True, parents=True)
protocol = {
    "id": "scientific-exp01-v1",
    "targets": [0.01, 0.05],
    "metric": "squared_euclidean",
    "noise": "complex_awgn_sample_domain",
    "fixed_variance_amplitude_sweep": 1.0,
    "fixed_amplitude_noise_sweep": 1.0,
    "eb_d": "sum|tx|^2 / payload_bits = 4 A^2",
    "phase_seeds": {"pilot": 1, "confirmatory": 2, "long": 3, "validation": 4},
    "seed_plan": "SeedSequence([83101,phase,scenario,sweep,point,trial,stream]) PCG64; independent across grid/sweep/trial; common within arms",
    "powers": [0.8, 0.2],
    "delays": [0, 3],
    "K": [4, 1],
    "rho": 0.98,
    "targets_interpretation": "project-defined decoded information BER, not source p*",
    "interpolation": "linear log10(BER) vs gamma_dB within adjacent measured positive brackets, no extrapolation",
    "bootstrap": "paired trial clusters independently resampled within each grid point; ratio of sums; 95% valid crossing requirement",
    "pilot": {
        "F": 256,
        "trials_per_point": 3,
        "gamma_grid": [-6, 0, 6, 12, 18],
        "budget_seconds": 300,
    },
    "confirmatory": {
        "F": 256,
        "trials_per_point": 20,
        "budget_seconds": 1000,
        "max_pairs": 840,
        "sample_size_rationale": "20 independent clusters and 10240 bits/point; about102 errors if BER=.01; precision remains limited, zero-error trial bound reported",
    },
    "long": {"F": 20000, "max_pairs": 2, "budget_seconds": 360},
    "wall_policy": "sequential; soft budget checked between completed pairs; no partial pairs aggregated",
    "disk_budget_bytes": 400000000,
    "paper_exact": False,
}
p = R / "protocol.json"
if p.exists() and p.read_bytes() != canonical(protocol):
    raise ValueError("frozen protocol mismatch")
atomic_json(p, protocol)
phase = sys.argv[1] if len(sys.argv) > 1 else "pilot"
if phase == "pilot":
    grid = {s: protocol["pilot"]["gamma_grid"] for s in ["awgn", "static", "rician"]}
    count = 3
    F = 256
    budget = 300
elif phase == "confirmatory":
    pilot = [json.loads(p.read_text()) for p in (R / "pilot").rglob("record.json")]
    # Freeze a denser main grid enclosing all observed brackets; never reuse pilot observations in estimates.
    grid = {}
    for sc in ["awgn", "static", "rician"]:
        rows = [r for r in pilot if r["scenario"] == sc and r["sweep"] == "amplitude"]
        gs = sorted({r["gamma_db"] for r in rows})
        needed = set()
        for arm in ["joint", "b0"] + ([] if sc == "rician" else ["b1"]):
            rates = [
                sum(r["bit_errors"][arm] for r in rows if r["gamma_db"] == g)
                / sum(r["bits"] for r in rows if r["gamma_db"] == g)
                for g in gs
            ]
            for target in [0.01, 0.05]:
                for i in range(len(gs) - 1):
                    if rates[i] >= target >= rates[i + 1]:
                        needed.update([gs[i], (gs[i] + gs[i + 1]) / 2, gs[i + 1]])
        grid[sc] = sorted(needed or set(gs))
        if len(grid[sc]) > 7:
            grid[sc] = gs
    plan = {
        "protocol_sha256": digest(canonical(protocol)),
        "grid": grid,
        "F": 256,
        "trials_per_point": 20,
        "pilot_record_sha256": sorted(
            digest(p.read_bytes()) for p in (R / "pilot").rglob("record.json")
        ),
        "phase": "confirmatory",
        "budget_seconds": 1000,
    }
    frozen = R / "confirmatory_plan.json"
    if frozen.exists() and canonical(plan) != frozen.read_bytes():
        raise ValueError("main design mutated")
    atomic_json(frozen, plan)
    count = 20
    F = 256
    budget = 1000
else:
    grid = {"awgn": [6.0], "rician": [6.0]}
    count = 1
    F = 20000
    budget = 360
started = time.monotonic()
completed = 0
stop = False
for sc, gs in grid.items():
    for sweep in ["amplitude", "noise"] if phase != "long" else ["amplitude"]:
        for i, g in enumerate(gs):
            for trial in range(count):
                if time.monotonic() - started >= budget:
                    stop = True
                    break
                if (
                    sum(p.stat().st_size for p in R.rglob("*") if p.is_file())
                    > protocol["disk_budget_bytes"]
                ):
                    stop = True
                    break
                spec = EnergyTrialSpec(phase, sc, sweep, float(g), i, trial, F)
                row = run_energy_trial(spec, R)
                completed += 1
                print(
                    phase,
                    sc,
                    sweep,
                    g,
                    trial,
                    row["ber"],
                    round(row["elapsed_seconds"], 2),
                    flush=True,
                )
            if stop:
                break
        if stop:
            break
    if stop:
        break
atomic_json(
    R / (phase + "_execution.json"),
    {
        "phase": phase,
        "completed_or_verified_pairs": completed,
        "elapsed_seconds": time.monotonic() - started,
        "status": "INCOMPLETE" if stop else "COMPLETE",
        "grid": grid,
        "F": F,
        "trials_per_point": count,
    },
)
