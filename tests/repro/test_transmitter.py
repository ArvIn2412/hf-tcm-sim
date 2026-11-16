from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import encode
from hf_tcm.repro.labeling import MAPPING_ID, build_edge_mapping
from hf_tcm.repro.modulator import modulate
from hf_tcm.repro.serialization import load_transmitter_arrays, save_transmitter_result
from hf_tcm.repro.source_bits import generate_information_bits
from hf_tcm.repro.transmitter import run_transmitter
from hf_tcm.repro.waveform import rectangular_zoh

REPO_ROOT = Path(__file__).parents[2]
VECTOR_PATH = REPO_ROOT / "docs/repro/REPRO_01_ENCODER_TEST_VECTORS.json"


def _config(**changes: object) -> TransmitterConfig:
    values: dict[str, object] = {
        "source_mode": "pattern",
        "frame_symbols": 4,
        "pattern_id": "alternating",
        "initial_state": (0, 0),
        "termination_policy": "none",
    }
    values.update(changes)
    if values["source_mode"] != "pattern":
        values.pop("pattern_id", None)
    if values["source_mode"] != "pattern" or values.get("pattern_id") != "repeat":
        values.pop("repeat_pattern", None)
    if values["source_mode"] != "manual":
        values.pop("manual_bits", None)
    if values["source_mode"] != "seeded_random":
        values.pop("seed", None)
    return TransmitterConfig.from_dict(values)


def _independent_transition(state: tuple[int, int], pair: tuple[int, int]):
    previous_1, previous_2 = state
    u0, u1 = pair
    return (u0, u1 ^ previous_2, previous_1), (u1, previous_1)


def test_manual_bits_are_exactly_parsed_and_reject_implicit_padding() -> None:
    config = _config(source_mode="manual", manual_bits="01100110")
    result = generate_information_bits(config)
    assert result.information_bits.shape == (8,)
    assert result.information_bits.dtype == np.int8
    assert result.information_bits.tolist() == [0, 1, 1, 0, 0, 1, 1, 0]
    assert not result.information_bits.flags.writeable
    with pytest.raises(ValueError, match="only characters 0 and 1"):
        generate_information_bits(_config(source_mode="manual", manual_bits="01 10"))
    with pytest.raises(ValueError, match="even"):
        generate_information_bits(_config(source_mode="manual", manual_bits="010"))
    with pytest.raises(ValueError, match="frame_symbols"):
        generate_information_bits(
            _config(source_mode="manual", manual_bits="0101", frame_symbols=3)
        )


@pytest.mark.parametrize(
    ("pattern_id", "expected"),
    [
        ("all_zeros", [0] * 8),
        ("all_ones", [1] * 8),
        ("alternating", [0, 1] * 4),
    ],
)
def test_deterministic_patterns(pattern_id: str, expected: list[int]) -> None:
    result = generate_information_bits(_config(pattern_id=pattern_id))
    assert result.information_bits.tolist() == expected


def test_repeating_pattern_and_seeded_source_are_reproducible() -> None:
    repeated = generate_information_bits(_config(pattern_id="repeat", repeat_pattern="1010"))
    assert repeated.information_bits.tolist() == [1, 0] * 4
    config = _config(source_mode="seeded_random", seed=123456)
    first = generate_information_bits(config)
    second = generate_information_bits(config)
    assert np.array_equal(first.information_bits, second.information_bits)
    assert first.metadata == second.metadata
    assert first.metadata["rng_algorithm"] == "PCG64"
    assert first.metadata["seed"] == 123456
    with pytest.raises(ValueError, match="seed"):
        generate_information_bits(_config(source_mode="seeded_random", seed=None))


def test_config_json_schema_rejects_unknown_and_inconsistent_fields() -> None:
    with pytest.raises(ValueError, match="unexpected"):
        TransmitterConfig.from_dict({"source_mode": "pattern", "frame_symbols": 1, "surprise": 4})
    with pytest.raises(ValueError, match="samples_per_symbol"):
        _config(samples_per_symbol=4)
    with pytest.raises(ValueError, match="phase_increment"):
        _config(phase_increment_rad=0.5)
    config = _config()
    assert TransmitterConfig.from_dict(config.to_dict()) == config


def test_all_sixteen_edges_match_independent_reference_vectors() -> None:
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["transitions"]
    state_order = ((0, 0), (1, 0), (0, 1), (1, 1))
    input_order = ((0, 0), (0, 1), (1, 0), (1, 1))
    for row in vectors:
        expected_output, expected_state = _independent_transition(
            tuple(row["state"]), tuple(row["input"])
        )
        assert tuple(row["output"]) == expected_output
        assert tuple(row["next"]) == expected_state
        state_rank = state_order.index(tuple(row["state"]))
        input_rank = input_order.index(tuple(row["input"]))
        actual = encode(
            np.asarray([row["input"]], dtype=np.int8),
            initial_state=tuple(row["state"]),
            termination_policy="none",
        )
        assert actual.coded_triples.shape == (1, 3)
        assert actual.pre_states[0].tolist() == row["state"]
        assert actual.input_pairs[0].tolist() == row["input"]
        assert tuple(actual.coded_triples[0].tolist()) == expected_output
        assert tuple(actual.post_states[0].tolist()) == expected_state
        assert int(actual.edge_ids[0]) == state_rank * 4 + input_rank


def test_encoder_supports_nonzero_initial_state_and_two_zero_pair_termination() -> None:
    result = encode(
        np.asarray([[1, 1]], dtype=np.int8),
        initial_state=(1, 0),
        termination_policy="zero_tail_2",
    )
    assert result.initial_state == (1, 0)
    assert result.input_pairs.tolist() == [[1, 1], [0, 0], [0, 0]]
    assert result.coded_triples.shape == (3, 3)
    assert result.final_state == (0, 0)
    assert result.termination_metadata["tail_steps"] == 2


def test_encoder_zero_alternating_and_full_state_traversal_are_deterministic() -> None:
    zero = encode(np.zeros((8, 2), dtype=np.int8))
    alternating = encode(np.tile(np.asarray([[0, 1], [1, 0]], dtype=np.int8), (4, 1)))
    assert zero.coded_triples.shape == (8, 3)
    assert alternating.coded_triples.shape == (8, 3)
    traversal = encode(np.asarray([[0, 1], [0, 1], [0, 0], [0, 0]], dtype=np.int8))
    assert set(map(tuple, traversal.pre_states)) == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert np.array_equal(encode(traversal.input_pairs).coded_triples, traversal.coded_triples)


def test_edge_mapping_uses_output_bits_and_has_stable_fingerprint() -> None:
    encoder = encode(np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int8))
    mapping = build_edge_mapping(encoder)
    repeated = build_edge_mapping(encoder)
    expected = [4 * int(c2) + 2 * int(c1) + int(c0) for c2, c1, c0 in encoder.coded_triples]
    assert mapping.mapping_id == MAPPING_ID
    assert mapping.phase_indices.tolist() == expected
    assert mapping.fingerprint == repeated.fingerprint
    assert len(mapping.fingerprint) == 64
    assert mapping.edge_ids.tolist() == encoder.edge_ids.tolist()
    assert mapping.status == "PROJECT_RECONSTRUCTION_ADR002"


def test_mapping_covers_all_sixteen_reference_edges() -> None:
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["transitions"]
    expected = []
    for row in vectors:
        c2, c1, c0 = row["output"]
        expected.append(4 * c2 + 2 * c1 + c0)
    observed = []
    for row in vectors:
        one_edge = encode(
            np.asarray([row["input"]], dtype=np.int8),
            initial_state=tuple(row["state"]),
        )
        observed.append(int(build_edge_mapping(one_edge).phase_indices[0]))
    assert observed == expected


def test_all_eight_8psk_points_have_explicit_phase_and_energy() -> None:
    result = modulate(np.arange(8, dtype=np.int8), amplitude=1.0, phase_offset_rad=0.0)
    expected_phases = np.arange(8) * (np.pi / 4.0)
    np.testing.assert_allclose(result.phase_values_rad, expected_phases, atol=1e-15, rtol=0.0)
    np.testing.assert_allclose(result.symbols, np.exp(1j * expected_phases), atol=1e-15)
    np.testing.assert_allclose(result.symbol_energies, np.ones(8), atol=1e-15, rtol=0.0)
    rotated = modulate([0], amplitude=2.0, phase_offset_rad=0.37)
    assert rotated.symbols[0] == pytest.approx(2.0 * np.exp(0.37j))
    assert rotated.symbol_energies[0] == pytest.approx(4.0)


def test_zoh_repeats_each_symbol_and_tracks_absolute_indices() -> None:
    symbols = np.asarray([1 + 2j, -1 - 0.5j], dtype=np.complex128)
    result = rectangular_zoh(symbols, samples_per_symbol=8)
    assert result.tx_samples.shape == (16,)
    assert result.symbol_index.tolist() == [0] * 8 + [1] * 8
    assert result.local_sample_index.tolist() == list(range(8)) * 2
    assert result.absolute_sample_index.tolist() == list(range(16))
    np.testing.assert_array_equal(result.tx_samples[:8], np.full(8, symbols[0]))
    np.testing.assert_array_equal(result.tx_samples[8:], np.full(8, symbols[1]))
    assert result.tx_samples.flags.writeable is False
    with pytest.raises(ValueError, match="nonempty"):
        rectangular_zoh(np.asarray([], dtype=np.complex128), samples_per_symbol=8)


def test_transmitter_end_to_end_shapes_provenance_and_determinism() -> None:
    config = _config()
    result = run_transmitter(config)
    repeated = run_transmitter(config)
    assert result.information_bits.shape == (8,)
    assert result.input_pairs.shape == (4, 2)
    assert result.coded_triples.shape == (4, 3)
    assert result.state_history.shape == (5, 2)
    assert result.phase_indices.shape == (4,)
    assert result.symbols.shape == (4,)
    assert result.tx_samples.shape == (32,)
    assert result.sample_symbol_index[-1] == 3
    assert np.array_equal(result.tx_samples, repeated.tx_samples)
    assert result.mapping_fingerprint == repeated.mapping_fingerprint
    assert result.source_fingerprint == repeated.source_fingerprint
    assert result.config_snapshot == config.to_dict()
    assert result.paper_exact is False
    assert result.receiver_enabled is False


def test_transmitter_payload_changes_coded_and_waveform_outputs() -> None:
    first = run_transmitter(_config(pattern_id="all_zeros"))
    second = run_transmitter(_config(pattern_id="all_ones"))
    assert not np.array_equal(first.information_bits, second.information_bits)
    assert not np.array_equal(first.coded_triples, second.coded_triples)
    assert not np.array_equal(first.phase_indices, second.phase_indices)
    assert not np.array_equal(first.tx_samples, second.tx_samples)


def test_serialization_round_trip_hash_manifest_and_no_object_arrays() -> None:
    result = run_transmitter(_config())
    output_dir = REPO_ROOT / "outputs/repro02/.test-serialization"
    manifest = save_transmitter_result(result, output_dir)
    try:
        assert (output_dir / "input_config.json").is_file()
        assert (output_dir / "summary.json").is_file()
        assert (output_dir / "mapping_table.json").is_file()
        assert (output_dir / "arrays.npz").is_file()
        stored = load_transmitter_arrays(output_dir / "arrays.npz")
        assert np.array_equal(stored["tx_samples"], result.tx_samples)
        assert stored["tx_samples"].dtype == np.complex128
        assert (
            manifest["arrays"]["tx_samples"]["sha256"]
            == hashlib.sha256(np.ascontiguousarray(result.tx_samples).tobytes()).hexdigest()
        )
        assert manifest["schema_version"] == "repro02-transmitter-v1"
    finally:
        for filename in (
            "input_config.json",
            "mapping_table.json",
            "summary.json",
            "arrays.npz",
            "manifest.json",
        ):
            (output_dir / filename).unlink(missing_ok=True)


def test_large_reference_frame_has_exact_symbol_and_sample_lengths() -> None:
    result = run_transmitter(_config(frame_symbols=20_000, pattern_id="all_zeros"))
    assert result.information_bits.shape == (40_000,)
    assert result.coded_triples.shape == (20_000, 3)
    assert result.symbols.shape == (20_000,)
    assert result.tx_samples.shape == (160_000,)
