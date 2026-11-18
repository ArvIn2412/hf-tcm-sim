from pathlib import Path

from hf_tcm.studio.scientific import ScientificRunConfig, run_scientific_run


def test_paired_system_runtime_covers_receivers_not_gui_or_archive_loading(tmp_path: Path):
    result = run_scientific_run(
        ScientificRunConfig(run_id="runtime-scope", frame_symbols=8, output_root=str(tmp_path))
    )
    assert result["paired_observation_verified"]
    assert result["information_bit_count"] == 16
    for key in ("joint", "separate"):
        assert result[key]["runtime_scope"] == "complete_receiver_call"
        assert result[key]["runtime_seconds"] > 0
        assert result[key]["compared_bits"] == 16
    assert result["elapsed_seconds"] >= sum(
        result[key]["runtime_seconds"] for key in ("joint", "separate")
    )
