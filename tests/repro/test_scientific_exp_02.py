from __future__ import annotations

import json
import math
import threading
import urllib.request
from dataclasses import replace

import numpy as np
import pytest

from hf_tcm.repro.exp02_prior_sensitivity import PRIOR_VARIANTS, prior_means_for_variant
from scripts.run_scientific_exp02_prior_sensitivity import (
    _load_protocol,
    _observation_and_evaluation_bits,
    _trial_rows,
    _validate_trial_files,
)

NOMINAL = (complex(0.8944271909999159, 0.0), complex(0.3420478245655483, 0.2881029081942352))


def test_prior_variants_are_frozen_public_perturbations() -> None:
    assert set(PRIOR_VARIANTS) == {
        "exact",
        "neutral",
        "amplitude_minus_10pct",
        "amplitude_plus_10pct",
        "phase_minus_15deg",
        "phase_plus_15deg",
    }
    assert prior_means_for_variant(NOMINAL, "exact") == NOMINAL
    assert prior_means_for_variant(NOMINAL, "neutral") == (0j, 0j)
    assert prior_means_for_variant(NOMINAL, "amplitude_minus_10pct") == tuple(
        value * 0.9 for value in NOMINAL
    )
    assert prior_means_for_variant(NOMINAL, "amplitude_plus_10pct") == tuple(
        value * 1.1 for value in NOMINAL
    )
    for name, angle in (("phase_minus_15deg", -15), ("phase_plus_15deg", 15)):
        scale = complex(math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        assert prior_means_for_variant(NOMINAL, name) == tuple(value * scale for value in NOMINAL)


def test_unknown_prior_variant_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown prior variant"):
        prior_means_for_variant(NOMINAL, "truth")


def test_prior_builder_rejects_empty_or_nonfinite_coefficients() -> None:
    with pytest.raises(ValueError):
        prior_means_for_variant((), "exact")
    with pytest.raises(ValueError):
        prior_means_for_variant((complex(float("nan"), 0),), "exact")


def test_exact_prior_redecode_reuses_identical_public_observation() -> None:
    from hf_tcm.repro.adaptive_multipath_config import AdaptiveMultipathReceiverConfig
    from hf_tcm.repro.adaptive_multipath_receiver import run_adaptive_multipath_receiver

    protocol = _load_protocol()
    trial = next(
        row
        for row in _trial_rows(protocol)
        if row["record"]["gamma_db"] == 2.0 and row["record"]["trial_index"] == 0
    )
    _validate_trial_files(trial)
    observation, _, saved_joint = _observation_and_evaluation_bits(trial)
    assert observation.sha256 == trial["record"]["observation_sha256"]
    source_config = AdaptiveMultipathReceiverConfig.from_dict(
        trial["record"]["receiver_configs"]["joint"]
    )
    means = prior_means_for_variant(
        tuple(complex(*pair) for pair in protocol["channel"]["public_nominal_coefficients"]),
        "exact",
    )
    config = replace(
        source_config,
        paths=tuple(
            replace(path, prior_mean=mean)
            for path, mean in zip(source_config.paths, means, strict=True)
        ),
    )
    result = run_adaptive_multipath_receiver(observation, config)
    assert result.observation_sha256 == observation.sha256
    assert np.array_equal(result.decoded_information_bits, saved_joint)


def test_exp01b_static_series_opens_through_saved_study_route() -> None:
    from hf_tcm.studio.server import make_server

    server = make_server("127.0.0.1", 0, default_view="scientific")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        address = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(
            f"{address}/api/scientific/energy-studies/historical/exp01b-static-amplitude-005",
            timeout=30,
        ) as response:
            result = json.load(response)
        assert result["experiment_id"] == "scientific-exp01b-confirmatory-static-amplitude"
        assert result["completed_trials"] == 1160
        assert result["provenance"]["verified_total_source_trials"] == 2160
        assert result["analyses"]["b0"]["gain_db"] == pytest.approx(5.7799887361185665)
        assert result["analyses"]["b1"]["gain_db"] == pytest.approx(2.4560630949253532)
        assert len(result["analyses"]["b0"]["aggregate"]) == 29
        assert {record["scenario"] for record in result["records"]} == {"static"}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
