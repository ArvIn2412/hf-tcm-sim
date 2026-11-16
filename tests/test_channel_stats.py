"""M3 path-wise channel power, delay, and correlation diagnostics."""

import numpy as np
import pytest

from hf_tcm.analysis.channel_stats import channel_statistics
from hf_tcm.channels.multipath import MultipathConfig, PathSpec, apply_multipath


@pytest.mark.statistical
def test_channel_statistics_report_configured_power_delay_and_correlation() -> None:
    config = MultipathConfig(
        paths=(PathSpec(delay_samples=2, average_power=0.4, k_factor=0.0),),
        fading_mode="approximate_ar1",
        correlation=0.35,
    )
    output = apply_multipath(
        np.ones(80_000, dtype=np.complex128), config, rng=np.random.default_rng(2026)
    )

    stats = channel_statistics(output.truth)[0]

    assert stats.delay_samples == 2
    assert stats.configured_average_power == 0.4
    assert stats.measured_average_power == pytest.approx(0.4, rel=0.02)
    assert stats.lag_one_correlation.real == pytest.approx(0.35, abs=0.015)
