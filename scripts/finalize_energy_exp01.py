import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from hf_tcm.repro.energy_experiment import atomic_json
from hf_tcm.repro.energy_statistics import analyze_energy_records

R = Path("outputs/scientific_exp_01")
D = Path("docs/research")
g = json.loads((R / "analysis/gains.json").read_text())
rows = [
    json.loads(p.read_text())
    for p in R.glob("*/*/*/p*/t*/record.json")
    if (p.parent / "manifest.json").exists()
]
# Diagnostic neighbor-point omission: separate from preregistered primary interpolation.
sensitivity = []
for a in g["analyses"]:
    if a["phase"] != "confirmatory":
        continue
    selected = [
        r
        for r in rows
        if (r["phase"], r["scenario"], r["sweep"]) == (a["phase"], a["scenario"], a["sweep"])
    ]
    gammas = sorted({r["gamma_db"] for r in selected})
    for omitted in gammas:
        keep = [r for r in selected if r["gamma_db"] != omitted]
        if not keep:
            continue
        x = analyze_energy_records(
            keep, a["target_ber"], arm=a["separate_arm"], replicates=100, seed=71401
        )
        sensitivity.append(
            {
                "phase": a["phase"],
                "scenario": a["scenario"],
                "sweep": a["sweep"],
                "arm": a["separate_arm"],
                "target": a["target_ber"],
                "omitted_gamma_db": omitted,
                "gain_db": x["gain_db"],
                "crossings": x["crossings"],
                "interpretation": "posthoc neighboring-grid omission diagnostic; not a new primary estimate or CI",
            }
        )
atomic_json(R / "neighbor_sensitivity.json", sensitivity)
validation = []
for p in (R / "analysis/plots").glob("*"):
    if p.suffix == ".png":
        im = np.asarray(Image.open(p).convert("RGBA"))
        assert np.all(im[:, :, 3] == 255)
        nonwhite = int(np.any(im[:, :, :3] < 245, axis=2).sum())
        assert nonwhite > 500
        validation.append(
            {
                "path": p.as_posix(),
                "size_bytes": p.stat().st_size,
                "width": int(im.shape[1]),
                "height": int(im.shape[0]),
                "nonwhite_opaque_pixels": nonwhite,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "status": "PASS",
            }
        )
    elif p.suffix == ".svg":
        root = ET.parse(p).getroot()
        assert root.tag.endswith("svg")
        assert len(list(root.iter())) > 10
        validation.append(
            {
                "path": p.as_posix(),
                "size_bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "status": "PASS",
            }
        )
atomic_json(R / "graph_validation.json", validation)
longstats = []
for p in (R / "long").rglob("record.json"):
    r = json.loads(p.read_text())
    with np.load(p.parent / "arrays.npz") as a:
        w = a["noise_samples"]
        x = a["tx_samples"]
        h = a["coefficients"]
        longstats.append(
            {
                "scenario": r["scenario"],
                "noise_complex_power": float(np.mean(abs(w) ** 2)),
                "noise_i_variance": float(np.var(w.real)),
                "noise_q_variance": float(np.var(w.imag)),
                "path_powers_empirical": np.mean(abs(h) ** 2, axis=1).tolist(),
                "tx_energy": float(np.vdot(x, x).real),
                "tx_eb": float(np.vdot(x, x).real / len(a["information_bits"])),
                "rx_signal_energy": float(np.sum(abs(a["received_samples"] - w) ** 2)),
                "peak_process_bytes": r.get("peak_working_set_process_bytes"),
                "seconds": r["elapsed_seconds"],
            }
        )
atomic_json(
    R / "energy_validation.json",
    {
        "sps": 8,
        "info_bits_per_symbol": 2,
        "amplitude_unit_tests": [
            {"A": 0.25, "expected_eb": 0.25},
            {"A": 1, "expected_eb": 4},
            {"A": 2.5, "expected_eb": 25},
        ],
        "long_measurements": longstats,
        "physical_ebn0_calibrated": False,
    },
)
impact = """\n\n## Підсумок validation та чутливість\n\nФінальний full pytest: **1212 passed in 67.75s**; Ruff check/format пройшли; historical fingerprints **694/694**, artifacts76/76. Незалежний replay перевіряє всі manifested control/series arrays. Додаткова posthoc діагностика F256, γ=3dB, 3 seeds×3 scenarios×2 sweeps не включена в inference: після нормування вектори received відрізняються лише на floating-point rounding, коефіцієнти ідентичні, decoded bits усіх arms ідентичні. Див. scaling_diagnostic.json.\n\nПри target0.05 static amplitude-sweep log-BER estimate Joint/B0=6.76779dB, 95%pointwise bootstrapCI[6.20976,7.51817]; Joint/B1=2.96415dB, CI[2.71560,3.22877]. Альтернативна linear-BER інтерполяція дає5.97000dB і2.60952dB відповідно: напрямок зберігається, але точна величина чутлива до грубої сітки. Ця modeling/interpolation uncertainty НЕ включена до наведених статистичних CI. Neighbor omission diagnostic у neighbor_sensitivity.json показує, коли втрачається допустимий bracket; це підстава для finer independently frozen follow-up grid, а не прихованої заміни поточної оцінки.\n\nПри primary target0.01 AWGN amplitude point estimate3.92381dB (EbJ2.69992, EbB0/B1=6.66395), static Joint/B0=9.98668dB (EbJ1.95649, EbB0=19.50502) і Joint/B1=3.97781dB (EbB1=4.88944). Для цих контрастів valid bootstrap crossing fraction нижча95%; безумовний95%CI не публікується. Rician B0 не має підтвердженого перетину target на виміряній сітці; main Rician trial count0 через бюджет.\n\nНові tooling defects виправлено до фінальної regression: tuple/list cache round-trip та глобальна ctypes signature у RAM probe. Це metadata/orchestration corrections; не зміни receiver/channel mathematics. Main memory fields можуть бути unavailable, long-frame measurements доступні. Не трактувати RAM unavailable як0.\n\nФінальні статуси: SCIENTIFIC_EXP_01_PARTIAL; ENERGY_NORMALIZATION_VALIDATED; BER_CURVES_PARTIAL (main Rician відсутній); ENERGY_GAIN_ESTIMATED лише для зазначених model contrasts; STATISTICAL_CONFIDENCE_PARTIAL; ARTICLE_1_5_DB_INSUFFICIENT_DATA. Фізичний виграш не доведений. Наступні роботи не запускалися.\n"""
for name in [
    "SCIENTIFIC_EXP_01_FINAL_REPORT.md",
    "SCIENTIFIC_EXP_01_ENERGY_GAIN_RESULTS.md",
    "SCIENTIFIC_EXP_01_STATISTICAL_VALIDATION.md",
]:
    p = D / name
    p.write_text(p.read_text("utf8") + impact, "utf8")
atomic_json(
    R / "final_status.json",
    {
        "status": "SCIENTIFIC_EXP_01_PARTIAL",
        "energy_normalization": "VALIDATED",
        "ber_curves": "PARTIAL",
        "energy_gain": "ESTIMATED_MODEL_CONTRASTS_ONLY",
        "statistical_confidence": "PARTIAL",
        "article_1_5_db": "INSUFFICIENT_DATA",
        "paper_exact": False,
        "main_planned_pairs": 680,
        "main_completed_pairs": 461,
        "pilot_pairs": 90,
        "long_pairs": 2,
        "inference_information_bits": 362112,
        "pytest_passed": 1212,
        "historical_fingerprints": [694, 694],
        "graphics_verified": len(validation),
    },
)
print("Validated graphics", len(validation), "long stats", longstats)
