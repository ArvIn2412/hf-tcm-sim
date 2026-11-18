"""End-to-end validation of the discrete Eb/N0 convention (defense plan P0-4).

Uses the project's own transmitter, REPRO-03 AWGN channel and the
``awgn_direct_control`` 8-sample frontend, then compares the measured 8PSK
symbol error rate of nearest-phase (hard) decisions with the exact Craig
integral at the predicted Es/N0 = 8 A^2 / sigma^2 = 2 * gamma_b,d.
Agreement within the binomial confidence interval shows that the project
axis gamma_b,d = Eb/sigma^2 equals Eb/N0 for this discrete model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from hf_tcm.evaluation.theory_curves import (
    INFORMATION_BITS_PER_TCM_SYMBOL,
    SAMPLES_PER_SYMBOL,
    db_to_linear,
    mpsk_symbol_error_probability,
    wilson_interval,
)
from hf_tcm.repro.channel_config import ChannelConfig, ChannelPathConfig
from hf_tcm.repro.channel_runner import run_channel
from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.metric_isolation import hard_phase_decisions, run_awgn_direct_frontend
from hf_tcm.repro.transmitter import run_transmitter


@dataclass(frozen=True, slots=True)
class Ebn0ValidationPoint:
    eb_n0_db: float
    amplitude: float
    noise_complex_variance: float
    measured_gamma_b_db: float
    symbols: int
    symbol_errors: int
    measured_ser: float
    ser_ci95: tuple[float, float]
    theory_ser: float
    theory_inside_ci95: bool
    measured_noise_variance: float


def _awgn_channel(variance: float, seed: int) -> ChannelConfig:
    return ChannelConfig(
        profile_id="awgn",
        paths=(ChannelPathConfig(0, 1.0, 0.0, constant_coefficient=1 + 0j),),
        fading_mode="constant",
        noise_model="complex_awgn_sample_domain",
        noise_complex_variance=variance,
        fading_seed=seed,
        noise_seed=seed + 1,
        reveal_noise_variance=True,
    )


def validate_point(
    eb_n0_db: float,
    *,
    symbols: int = 20_000,
    noise_complex_variance: float = 1.0,
    seed: int = 20261117,
) -> Ebn0ValidationPoint:
    """Simulate one Eb/N0 point; the amplitude is derived from the convention."""
    if symbols < 100:
        raise ValueError("symbols must be >= 100")
    eb_n0 = db_to_linear(eb_n0_db)
    # Eb = 8 A^2 / 2 and N0 = sigma^2  ->  A = sqrt(Eb/N0 * sigma^2 * 2 / 8)
    amplitude = math.sqrt(
        eb_n0 * noise_complex_variance * INFORMATION_BITS_PER_TCM_SYMBOL / SAMPLES_PER_SYMBOL
    )
    transmitter = run_transmitter(
        TransmitterConfig(
            source_mode="seeded_random", frame_symbols=symbols, seed=seed, amplitude=amplitude
        )
    )
    channel = run_channel(transmitter, _awgn_channel(noise_complex_variance, seed + 7))
    frontend = run_awgn_direct_frontend(channel.receiver_observation, symbol_count=symbols)
    decisions = hard_phase_decisions(frontend.symbols, amplitude=amplitude)
    sent = np.asarray(transmitter.phase_indices[:symbols], dtype=np.int64)
    errors = int(np.count_nonzero(decisions != sent))

    tx = np.asarray(transmitter.tx_samples, dtype=np.complex128)
    energy_per_bit = float(np.sum(np.abs(tx) ** 2)) / (INFORMATION_BITS_PER_TCM_SYMBOL * symbols)
    noise = np.asarray(channel.evaluation_truth.noise_samples, dtype=np.complex128)
    measured_variance = float(np.mean(np.abs(noise) ** 2))
    theory = mpsk_symbol_error_probability(2.0 * eb_n0)
    interval = wilson_interval(errors, symbols)
    return Ebn0ValidationPoint(
        eb_n0_db=float(eb_n0_db),
        amplitude=amplitude,
        noise_complex_variance=noise_complex_variance,
        measured_gamma_b_db=10.0 * math.log10(energy_per_bit / noise_complex_variance),
        symbols=symbols,
        symbol_errors=errors,
        measured_ser=errors / symbols,
        ser_ci95=(float(interval[0]), float(interval[1])),
        theory_ser=theory,
        theory_inside_ci95=bool(interval[0] <= theory <= interval[1]),
        measured_noise_variance=measured_variance,
    )
