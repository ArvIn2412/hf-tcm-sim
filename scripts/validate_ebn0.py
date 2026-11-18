"""Generate the Eb/N0 validation tables and figure (defense plan P0-4).

Usage: python scripts/validate_ebn0.py [--out docs/figures/ebn0_validation]

Part 1: uncoded 8PSK SER of the project's transmitter/channel/frontend vs the
exact Craig integral at Es/N0 = 2 * Eb/N0.
Part 2: AWGN BER of the Hamming (hard) and Euclidean (soft) TCM decoders on the
same observations vs uncoded QPSK and the 4-state TCM dominant term.
Small, deterministic and exploratory; not a confirmatory series.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from hf_tcm.evaluation.ebn0_validation import validate_point
from hf_tcm.evaluation.theory_curves import (
    db_to_linear,
    qpsk_bit_error_probability,
    tcm4_8psk_dominant_term_ber,
    wilson_interval,
)
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.metric_experiment import MetricTrialSpec, run_metric_trial

SER_GRID_DB = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)
TCM_GRID_DB = (2.0, 3.0, 4.0, 5.0, 6.0, 7.0)


def tcm_point(eb_n0_db: float, *, frames: int, frame_symbols: int, seed: int) -> dict[str, float]:
    sigma2 = 1.0
    amplitude = math.sqrt(db_to_linear(eb_n0_db) * sigma2 * 2 / 8)
    errors = {"hamming": 0, "euclidean": 0}
    bits = 0
    for frame in range(frames):
        channel = ChannelConfig(
            profile_id="awgn",
            paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
            fading_mode="constant",
            noise_model="complex_awgn_sample_domain",
            noise_complex_variance=sigma2,
            fading_seed=seed + frame,
            noise_seed=seed + 100_000 + frame,
            reveal_noise_variance=True,
        )
        result = run_metric_trial(
            MetricTrialSpec(
                f"ebn0-{frame}",
                frame_symbols,
                seed + 200_000 + frame,
                channel,
                "awgn_direct_control",
                amplitude=amplitude,
            )
        )
        for arm in errors:
            errors[arm] += result.summary[arm]["bit_errors"]
        bits += result.summary["euclidean"]["bits"]
        gamma = result.summary["gamma_b_discrete_db"]
    row: dict[str, float] = {"eb_n0_db": eb_n0_db, "gamma_b_d_db": gamma, "bits": bits}
    for arm, count in errors.items():
        low, high = wilson_interval(count, bits)
        row |= {
            f"{arm}_errors": count,
            f"{arm}_ber": count / bits,
            f"{arm}_lo": low,
            f"{arm}_hi": high,
        }
    row["qpsk_uncoded_ber"] = qpsk_bit_error_probability(db_to_linear(eb_n0_db))
    row["tcm_dominant_ber"] = tcm4_8psk_dominant_term_ber(db_to_linear(eb_n0_db))
    return row


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(out: Path, ser_rows: list[dict[str, float]], tcm_rows: list[dict[str, float]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "Times New Roman"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    x = [r["eb_n0_db"] for r in ser_rows]
    ax.semilogy(x, [r["theory_ser"] for r in ser_rows], "k-", label="Теорія 8PSK (точна)")
    ax.errorbar(
        x,
        [r["measured_ser"] for r in ser_rows],
        yerr=[
            [r["measured_ser"] - r["ci_lo"] for r in ser_rows],
            [r["ci_hi"] - r["measured_ser"] for r in ser_rows],
        ],
        fmt="o",
        color="#087f8c",
        label="Моделювання (95% ДІ)",
    )
    ax.set_xlabel("Eb/N0, дБ")
    ax.set_ylabel("SER (некодована 8PSK)")
    ax.set_title("а) Валідація енергетичної шкали")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()

    ax = axes[1]
    x = [r["eb_n0_db"] for r in tcm_rows]
    ax.semilogy(x, [r["qpsk_uncoded_ber"] for r in tcm_rows], "k--", label="Некодована QPSK")
    ax.semilogy(x, [r["tcm_dominant_ber"] for r in tcm_rows], "k:", label="TCM, домінантний член")
    for arm, label, color in (
        ("hamming", "Хемінг (жорстке рішення)", "#bb6518"),
        ("euclidean", "Евклід (м’яке рішення)", "#087f8c"),
    ):
        pairs = [(r["eb_n0_db"], r[f"{arm}_ber"]) for r in tcm_rows if r[f"{arm}_ber"] > 0]
        ax.semilogy([p[0] for p in pairs], [p[1] for p in pairs], "o-", color=color, label=label)
    ax.set_xlabel("Eb/N0, дБ")
    ax.set_ylabel("BER")
    ax.set_title("б) TCM 4 стани, 8PSK, AWGN, η = 20")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "ebn0_validation.png", dpi=300)
    fig.savefig(out / "ebn0_validation.svg")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/figures/ebn0_validation")
    parser.add_argument("--symbols", type=int, default=20_000)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--frame-symbols", type=int, default=2000)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ser_rows = []
    for value in SER_GRID_DB:
        p = validate_point(value, symbols=args.symbols)
        ser_rows.append(
            {
                "eb_n0_db": p.eb_n0_db,
                "measured_gamma_b_db": p.measured_gamma_b_db,
                "symbols": p.symbols,
                "symbol_errors": p.symbol_errors,
                "measured_ser": p.measured_ser,
                "ci_lo": p.ser_ci95[0],
                "ci_hi": p.ser_ci95[1],
                "theory_ser": p.theory_ser,
                "theory_inside_ci95": int(p.theory_inside_ci95),
                "measured_noise_variance": p.measured_noise_variance,
            }
        )
    tcm_rows = [
        tcm_point(v, frames=args.frames, frame_symbols=args.frame_symbols, seed=9100 + i)
        for i, v in enumerate(TCM_GRID_DB)
    ]
    write_csv(out / "uncoded_8psk_ser.csv", ser_rows)
    write_csv(out / "tcm_awgn_ber.csv", tcm_rows)
    plot(out, ser_rows, tcm_rows)
    for row in ser_rows:
        print(
            f"SER  {row['eb_n0_db']:5.1f} dB  sim {row['measured_ser']:.5f} "
            f"[{row['ci_lo']:.5f}; {row['ci_hi']:.5f}]  theory {row['theory_ser']:.5f}  "
            f"inside={bool(row['theory_inside_ci95'])}"
        )
    for row in tcm_rows:
        print(
            f"TCM  {row['eb_n0_db']:4.1f} dB  H {row['hamming_ber']:.2e}  E {row['euclidean_ber']:.2e}"
            f"  QPSK {row['qpsk_uncoded_ber']:.2e}  dom {row['tcm_dominant_ber']:.2e}  bits {row['bits']}"
        )


if __name__ == "__main__":
    main()
