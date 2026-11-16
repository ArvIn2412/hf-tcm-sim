from __future__ import annotations

import json
import threading
import urllib.request

import numpy as np
import pytest

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.coding.trellis import STATES
from hf_tcm.evaluation.m9b_fixed_policy_evaluation_runner import (
    _receiver_configuration,
    _receiver_kwargs,
    resolve_m9_clock_origins,
)
from hf_tcm.evaluation.m11a_demo_studio import (
    DEFENSE_DEMO_REQUEST,
    DEMO_BIT_PATTERNS,
    DemoRequest,
    build_dataset_coverage,
    build_demo_trace,
    build_parameter_registry,
    build_stage_coverage_audit,
    pipeline_stage_catalog,
)
from hf_tcm.receiver.reconstruction_conditional_decode import (
    decode_reconstruction_conditional_sequence,
)
from hf_tcm.studio.server import make_server


def test_demo_trace_has_full_actual_pipeline_and_symbol_values() -> None:
    trace = build_demo_trace(DemoRequest())

    assert trace["classification"] == "DETERMINISTIC DEMONSTRATION — NOT SCIENTIFIC EVIDENCE"
    assert len(trace["stages"]) == 28
    assert len(trace["arms"]) == 2
    assert len(trace["symbols"]) == len(DEMO_BIT_PATTERNS["alternating"]) // 2
    assert trace["arms"][0]["candidate_id"] == "historical_frozen_B"
    assert trace["arms"][1]["candidate_id"] == "anch_a085_k025"
    assert trace["input"]["rng_used"] is False
    assert trace["input"]["channel_truth_passed_to_receiver"] is False
    assert trace["input"]["reference_bits_passed_to_receiver"] is False
    assert trace["pairing"]["same_received_sha256"] is True
    frozen_first = trace["arms"][0]["symbols"][0]
    anchored_first = trace["arms"][1]["symbols"][0]
    assert frozen_first["pre_state"]["full_iq"] == anchored_first["pre_state"]["full_iq"]
    np.testing.assert_array_equal(frozen_first["predicted_iq"], anchored_first["predicted_iq"])
    np.testing.assert_array_equal(
        frozen_first["candidate_metrics"], anchored_first["candidate_metrics"]
    )
    np.testing.assert_array_equal(frozen_first["posterior"], anchored_first["posterior"])
    assert trace["stage_status"] == "AVAILABLE_RAW_AND_DERIVED_WITH_STAGE28_PARTIAL"
    assert len(trace["canonical_hypothesis_order"]) == 16
    assert trace["canonical_hypothesis_order"] == list(range(16))

    row = trace["arms"][1]["symbols"][0]
    assert len(row["sample_indices"]) == 8
    assert len(row["transmitted_samples"]) == 8
    assert len(row["noise_samples"]) == 8
    assert len(row["received_samples"]) == 8
    assert np.asarray(row["predicted_iq"]).shape == (16, 2)
    assert np.asarray(row["candidate_metrics"]).shape == (16,)
    assert np.asarray(row["posterior"]).shape == (16,)
    assert row["posterior_normalized"] is True
    assert len(row["channel_contribution"]) == 8
    for tx, channel in zip(row["transmitted_samples"], row["channel_contribution"], strict=True):
        assert channel["real"] == pytest.approx(0.75 * tx["real"])
        assert channel["imag"] == pytest.approx(0.75 * tx["imag"])
    assert row["pre_state"]["time_index"] + 1 == row["post_state"]["time_index"]
    assert len(trace["arms"][1]["viterbi"]["decoded_bits"]) == 2 * len(trace["symbols"])
    assert trace["arms"][1]["viterbi"]["survivor_metrics_shape"] == [
        len(trace["symbols"]),
        4,
    ]
    assert trace["arms"][1]["viterbi"]["decoder_calls"] == 1
    for f, symbol in enumerate(trace["arms"][1]["symbols"]):
        assert symbol["sample_indices"] == list(range(f * 8, f * 8 + 8))
        assert symbol["prediction_cutoff_sample"] == f * 8 - 1
        assert symbol["observation_cutoff_sample"] == f * 8 + 7
        assert symbol["hypothesis_ids"] == list(range(16))
        assert len(symbol["edge_definitions"]) == 16
        assert [edge["edge_id"] for edge in symbol["edge_definitions"]] == list(range(16))
        assert np.asarray(symbol["sample_predictions_iq"]).shape == (16, 8, 2)


def test_demo_parameters_are_pending_until_trace_is_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def counted(request: DemoRequest) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return build_demo_trace(request)

    server = make_server("127.0.0.1", 0, trace_builder=counted)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        address = f"http://127.0.0.1:{server.server_port}"
        request = urllib.request.Request(
            f"{address}/api/demo",
            data=json.dumps(
                {
                    "bits": "01011010",
                    "receiver_mode": "anchored",
                    "alpha_prime": 0.85,
                    "k_tilde": [0.0875, -0.05],
                    "beta": 0.7,
                    "noise_fixture": "low_amplitude_a",
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(f"{address}/api/metadata") as response:
            metadata = json.load(response)
        assert calls == 0
        assert metadata["paper_exact"] is False
        assert metadata["receiver_enabled"] is False

        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        assert calls == 1
        assert result["arms"][0]["candidate_id"] == "anch_a085_k025"
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_parameter_registry_and_coverage_are_explicit() -> None:
    registry = build_parameter_registry()
    assert {entry["group"] for entry in registry} >= {
        "Encoder/TCM",
        "State transition mapping",
        "8PSK modulation",
        "Waveform and sampling",
        "Channel and AWGN",
        "Receiver IQ conventions",
        "Candidate prediction",
        "Candidate metric",
        "Posterior normalization",
        "Estimator recursion",
        "Viterbi decoding",
        "Evaluation/statistics",
        "Dataset provenance",
        "Scientific limitations",
    }
    assert all("source" in entry and "status" in entry for entry in registry)
    assert all("symbol" in entry and "unit" in entry for entry in registry)
    assert all("default_value" in entry and "constraints" in entry for entry in registry)
    assert all("type" in entry and "allowed_range" in entry for entry in registry)
    assert all("description" in entry for entry in registry)
    assert all(
        entry["default_value"] is None for entry in registry if entry["status"] == "read_only"
    )
    beta = next(entry for entry in registry if entry["parameter"] == "anch_a085_k025.beta")
    assert beta["default_value"] == beta["value"]
    assert beta["allowed_range"] == "> 0"
    constellation_entry = next(
        entry for entry in registry if entry["parameter"] == "constellation_points"
    )
    assert len(constellation_entry["value"]) == 8
    assert (
        next(entry for entry in registry if entry["parameter"].endswith("alpha_prime"))["symbol"]
        == "α′"
    )
    assert all(entry["status"] in {"read_only", "demo_editable"} for entry in registry)

    coverage = build_dataset_coverage()
    assert set(coverage["datasets"]) >= {
        "deterministic_demo",
        "M6b",
        "M6g",
        "M6h",
        "M5j",
        "M7b",
        "M8b",
        "M9b",
        "M10b",
    }
    assert coverage["stages"]["14"]["M5j"] == "UNAVAILABLE"
    assert coverage["stages"]["28"]["deterministic_demo"] == "AVAILABLE_RAW"
    assert coverage["stages"]["14"]["M6g"] == "AVAILABLE_RAW"
    assert coverage["stages"]["08"]["M10b"] == "AVAILABLE_RAW"
    assert coverage["stages"]["09"]["M10b"] == "AVAILABLE_DERIVED"
    assert coverage["stages"]["10"]["M10b"] == "AVAILABLE_RAW"
    assert coverage["stages"]["11"]["M10b"] == "AVAILABLE_DERIVED"
    assert all(set(row) == set(coverage["datasets"]) for row in coverage["stages"].values())

    stages = pipeline_stage_catalog()
    assert [stage["stage_id"] for stage in stages] == [f"{index:02d}" for index in range(1, 29)]


def test_runtime_parameter_inspector_indexes_actual_symbol_and_study_values() -> None:
    trace = build_demo_trace(DEFENSE_DEMO_REQUEST)
    anchored = trace["arms"][1]
    symbol = anchored["symbols"][15]
    assert trace["input"]["symbol_count"] == 32
    assert len(symbol["candidate_metrics"]) == len(symbol["posterior"]) == 16
    assert symbol["symbol_index"] == 15
    assert len(anchored["viterbi"]["decoded_edge_path"]) == 32
    assert set(anchored["reference_comparison"]) >= {"ber", "ser"}

    coverage = build_dataset_coverage()["experiments"]
    assert coverage["M9b"]["bootstrap"]["delta_ber_ci"] == [
        -0.00322265625,
        0.00068359375,
    ]
    assert coverage["M10b"]["primary_95_percent_ci"] == [
        -0.00205126953125,
        0.0014453125,
    ]

    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "src/hf_tcm/studio/static/studio.js").read_text(
        encoding="utf-8"
    )
    assert "function runtimeInspectorEntries" in script
    assert "candidate_metrics" in script
    assert "posterior_weights" in script
    assert "delta_ber_ci" in script


def test_invalid_demo_request_is_rejected_before_receiver_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hf_tcm.evaluation import m11a_demo_studio

    def fail_if_called(**kwargs: object) -> None:
        pytest.fail("receiver must not run for invalid form values")

    monkeypatch.setattr(
        m11a_demo_studio,
        "run_reconstruction_posterior_estimator_sequence",
        fail_if_called,
    )
    with pytest.raises(ValueError):
        build_demo_trace(DemoRequest(bits=(0, 1, 2, 0), alpha_prime=float("nan")))


def test_trace_matches_direct_conditional_receiver_and_real_viterbi() -> None:
    trace = build_demo_trace(DemoRequest(receiver_mode="frozen"))
    received = np.asarray(
        [complex(item["real"], item["imag"]) for item in trace["transmitter"]["received_samples"]],
        dtype=np.complex128,
    )
    received.setflags(write=False)
    policy = trace["arms"][0]["parameters"]
    receiver_config = _receiver_configuration()
    clocks = resolve_m9_clock_origins(receiver_config)
    kwargs = _receiver_kwargs(
        policy=policy,
        received=received,
        receiver_configuration=receiver_config,
        clocks=clocks,
    )
    direct = decode_reconstruction_conditional_sequence(**kwargs)
    np.testing.assert_array_equal(
        direct.candidate_metrics, trace["arms"][0]["frozen_metric_sequence"]
    )
    assert list(direct.decoded_hypothesis_path) == trace["arms"][0]["viterbi"]["decoded_edge_path"]
    np.testing.assert_array_equal(
        direct.final_estimator_state.full_iq[0], trace["arms"][0]["final_state"]["full_iq"]
    )
    assert direct.decoder_result.survivor_metrics.shape == (len(trace["symbols"]), 4)


def test_studio_serves_actual_local_frontend_without_running_receiver() -> None:
    calls = 0

    def unexpected(_: DemoRequest) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise AssertionError("GET routes must not invoke a receiver")

    server = make_server("127.0.0.1", 0, trace_builder=unexpected)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base) as response:
            html = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{base}/static/studio.js") as response:
            script = response.read().decode("utf-8")
        assert 'id="view-pipeline"' in html
        assert 'id="run-demo"' in html
        assert "new_independent_sequence" not in script or "decode" in script.lower()
        assert calls == 0
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_automated_stage_audit_checks_real_render_data_for_all_28_stages() -> None:
    trace = build_demo_trace(DemoRequest(bits=tuple([0, 1] * 16)))
    audit = build_stage_coverage_audit(trace)

    assert len(audit) == 28
    assert [row["stage_id"] for row in audit] == [f"{n:02d}" for n in range(1, 29)]
    for row in audit[:-1]:
        assert row["runtime_coverage"] == "IMPLEMENTED_WITH_VALUES"
        assert row["actual_renderer"]
        assert row["data_source"]
        assert row["formula_source"]
    assert audit[-1]["runtime_coverage"] == "PARTIAL_BY_DESIGN"
    assert "independent" in audit[-1]["unavailable_explanation"].lower()


def test_f32_preset_has_fixed_inputs_and_reproducible_shared_receive() -> None:
    from hf_tcm.evaluation.m11a_demo_studio import DEFENSE_DEMO_REQUEST

    first = build_demo_trace(DEFENSE_DEMO_REQUEST)
    second = build_demo_trace(DEFENSE_DEMO_REQUEST)
    assert len(first["input"]["information_bits"]) == 64
    assert first["input"]["sample_count"] == 256
    assert first["input"]["rng_used"] is False
    assert first["input"]["received_sha256"] == second["input"]["received_sha256"]
    assert first["pairing"]["same_received_sha256"] is True
    assert first["arms"][0]["candidate_id"] == "historical_frozen_B"
    assert first["arms"][1]["candidate_id"] == "anch_a085_k025"


def test_f32_boundaries_have_synchronized_samples_ticks_and_safe_final_prediction() -> None:
    from hf_tcm.evaluation.m11a_demo_studio import DEFENSE_DEMO_REQUEST

    trace = build_demo_trace(DEFENSE_DEMO_REQUEST)
    arm = trace["arms"][1]
    for symbol in (0, 1, 15, 16, 30, 31):
        row = arm["symbols"][symbol]
        assert row["symbol_index"] == symbol
        assert row["sample_indices"] == list(range(symbol * 8, symbol * 8 + 8))
        assert (
            row["estimator_tick"]
            == trace["input"]["clock_origins"]["estimator_time_index_origin"] + symbol
        )
        assert len(row["input_bit_pair"]) == 2
        assert len(row["transmitted_samples"]) == 8
        assert len(row["noise_samples"]) == 8
        assert len(row["received_samples"]) == 8
        assert (
            len(row["predicted_iq"]) == len(row["candidate_metrics"]) == len(row["posterior"]) == 16
        )
        assert row["posterior_normalized"] is True
        assert row["post_state"] == row["next_symbol_pre_state"]
    assert len(arm["symbols"]) == 32


def test_canonical_tcm_edges_states_and_adr002_phase_mapping() -> None:
    from hf_tcm.receiver.reconstruction_labeling import (
        ASSUMED_NATURAL_BINARY,
        OUTPUT_BIT_ORDER,
        hypothesis_to_phase_index,
    )

    trace = build_demo_trace(DemoRequest(bits=tuple([0, 1] * 8)))
    assert len(set(STATES)) == 4
    assert len(HYPOTHESES) == len(trace["canonical_hypothesis_order"]) == 16
    assert trace["canonical_hypothesis_order"] == list(range(16))
    for edge in trace["arms"][0]["symbols"][0]["edge_definitions"]:
        canonical = HYPOTHESES[edge["edge_id"]]
        assert edge["source_state"] == list(canonical.current_state)
        assert edge["target_state"] == list(canonical.next_state)
        assert edge["input_bits"] == list(canonical.input_bits)
        assert edge["output_bits"] == list(canonical.output_bits)
        assert edge["phase_index"] == hypothesis_to_phase_index(
            canonical, profile=ASSUMED_NATURAL_BINARY, bit_order=OUTPUT_BIT_ORDER
        )


def test_historical_dashboard_values_are_read_from_archived_summaries() -> None:
    coverage = build_dataset_coverage()
    dashboard = coverage["experiments"]
    assert dashboard["M9b"]["paired_estimands"]["delta_ber"] == -0.0011328125
    assert dashboard["M9b"]["bootstrap"]["delta_ber_ci"] == [
        -0.00322265625,
        0.00068359375,
    ]
    assert dashboard["M9b"]["delta_ber_95_ci_contains_zero"] is True
    assert dashboard["M10b"]["primary_delta_ber"] == -0.0003125
    assert dashboard["M10b"]["primary_95_percent_ci"] == [
        -0.00205126953125,
        0.0014453125,
    ]
    assert dashboard["M10b"]["primary_95_percent_ci_contains_zero"] is True


def test_frontend_exposes_18_presentation_steps_and_edge_graph_selection() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "src/hf_tcm/studio/static/index.html").read_text(encoding="utf-8")
    script = (root / "src/hf_tcm/studio/static/studio.js").read_text(encoding="utf-8")
    assert "Reset presentation" in html
    assert "data-edge-graph" in script
    assert "function stageValue" in script
    assert "UNAVAILABLE: final frame symbol" in script


def test_windows_launcher_is_root_relative_local_only_and_never_installs_packages() -> None:
    from pathlib import Path

    launcher = Path(__file__).resolve().parents[1] / "start_demo.ps1"
    assert launcher.is_file()
    script = launcher.read_text(encoding="utf-8")
    assert "Set-Location -LiteralPath $PSScriptRoot" in script
    assert "Get-Command -Name python" in script
    assert "import numpy" in script
    assert "Test-NetConnection -ComputerName 127.0.0.1" in script
    assert '"--host", "127.0.0.1"' in script
    assert '"hf_tcm.demo_studio"' in script
    assert "$LASTEXITCODE" in script
    assert "pip install" not in script.lower()
    wrapper = Path(__file__).resolve().parents[1] / "start_demo.cmd"
    assert wrapper.is_file()
    command = wrapper.read_text(encoding="utf-8")
    assert "-ExecutionPolicy Bypass -File" in command
    assert "%*" in command


def test_server_rejects_remote_bind_and_oversized_or_invalid_demo_requests() -> None:
    with pytest.raises(ValueError, match="local machine"):
        make_server("0.0.0.0", 0)

    server = make_server("127.0.0.1", 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for body in (b"x" * 8193, b'{"bits":"101"}'):
            request = urllib.request.Request(
                f"{base}/api/demo",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            assert error.value.code == 400
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_missing_historical_datasets_are_reported_without_trace_synthesis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    from pathlib import Path

    from hf_tcm.evaluation import m11a_demo_studio

    monkeypatch.setattr(m11a_demo_studio, "ROOT", Path(str(tmp_path)))
    coverage = m11a_demo_studio.build_dataset_coverage()
    assert all(not entry["exists"] for entry in coverage["sources"].values())
    assert all(
        status == "UNAVAILABLE"
        for stage in coverage["stages"].values()
        for dataset, status in stage.items()
        if dataset != "deterministic_demo"
    )
    assert "not expanded into traces" in coverage["sources"]["M5j"]["note"]


def test_offline_frontend_uses_grouped_parameter_inspector_and_local_routes() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "src/hf_tcm/studio/static/index.html").read_text(encoding="utf-8")
    script = (root / "src/hf_tcm/studio/static/studio.js").read_text(encoding="utf-8")
    assert 'id="parameter-search"' in html
    assert 'id="parameter-groups"' in html
    assert '$("parameter-groups")' in script
    assert "allowed_range" in script
    assert "Not specified" in script
    assert "https://" not in html + script
    assert 'fetch("/api/metadata")' in script
    assert 'fetch("/api/demo"' in script
