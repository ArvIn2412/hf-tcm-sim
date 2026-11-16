"""Deterministic validation of the M6d source-evidence dossier."""

import ast
import hashlib
import json
from pathlib import Path

from hf_tcm.coding.hypotheses import HYPOTHESES
from hf_tcm.receiver.reconstruction_labeling import (
    ASSUMED_NATURAL_BINARY,
    OUTPUT_BIT_ORDER,
    hypothesis_to_phase_index,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "configs/m6d_source_evidence_matrix.json"


def _load_matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _m6b_tree_hashes() -> tuple[dict[str, str], str]:
    root = ROOT / "outputs/m6b_trace_diagnostics/m6b_causal_trace_20261030_v1"
    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    actual = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in root.rglob("*")
        if path.is_file() and path.name != "integrity.json"
    }
    expected = {item["path"]: item["sha256"] for item in integrity["files"]}
    assert actual == expected
    pairs = [f"{name} {digest}" for name, digest in sorted(actual.items())]
    tree_digest = hashlib.sha256("\\n".join(pairs).encode("utf-8")).hexdigest()
    assert len(actual) == integrity["file_count"]
    assert tree_digest == integrity["output_tree_sha256_excluding_integrity_json"]
    return actual, tree_digest


def test_evidence_matrix_is_schema_valid_and_round_trips() -> None:
    matrix = _load_matrix()
    assert matrix["schema_version"] == 1
    assert matrix["artifact_type"] == "source_evidence_matrix_not_author_confirmed_config"
    assert json.loads(json.dumps(matrix, ensure_ascii=False)) == matrix


def test_primary_source_and_available_page_fingerprints_match_ledger() -> None:
    matrix = _load_matrix()
    for source in matrix["source_files"]:
        assert _sha256(ROOT / source["path"]) == source["sha256"]


def test_project_edge_table_has_all_sixteen_unique_rows_and_valid_phases() -> None:
    matrix = _load_matrix()
    edges = matrix["project_reconstructed_edges"]
    assert len(edges) == 16
    assert [edge["edge_id"] for edge in edges] == list(range(16))
    assert len({edge["edge_id"] for edge in edges}) == 16

    for edge, hypothesis in zip(edges, HYPOTHESES, strict=True):
        phase = hypothesis_to_phase_index(
            hypothesis,
            profile=ASSUMED_NATURAL_BINARY,
            bit_order=OUTPUT_BIT_ORDER,
        )
        assert edge["source_state"] == list(hypothesis.current_state)
        assert edge["input_pair"] == list(hypothesis.input_bits)
        assert edge["next_state"] == list(hypothesis.next_state)
        assert edge["encoder_output_bits"] == list(hypothesis.output_bits)
        assert edge["project_phase_index"] == phase
        assert edge["project_b"] == phase
        assert 0 <= edge["project_b"] <= 7
        assert edge["mapping_status"] == "project_reconstructed_source_unresolved"
        assert edge["source_mapping_evidence_status"] == "UNAVAILABLE"


def test_source_explicit_claims_have_exact_locators_and_no_author_confirmation() -> None:
    matrix = _load_matrix()
    claims = matrix["claims"]
    assert claims
    allowed = {
        "SOURCE_EXPLICIT",
        "SOURCE_DERIVABLE",
        "SOURCE_AMBIGUOUS",
        "RECONSTRUCTION_ASSUMPTION",
        "EXTERNAL_REFERENCE_ONLY",
        "UNAVAILABLE",
    }
    for claim in claims:
        assert claim["evidence_status"] in allowed
        assert claim["evidence_status"] != "AUTHOR_CONFIRMED"
        if claim["evidence_status"] in {"SOURCE_EXPLICIT", "SOURCE_DERIVABLE"}:
            locator = claim["locator"]
            assert locator["document"] == "[A]"
            assert locator["version"]
            assert locator["printed_page"] >= 1
            assert locator["object"]
            assert locator["visual_locator"]

    assert matrix["author_confirmation_records"] == []
    assert (
        matrix["author_edge_to_b_status"]
        == "AUTHOR_MAPPING_NOT_IDENTIFIABLE_FROM_AVAILABLE_SOURCE_EVIDENCE"
    )
    assert matrix["author_b_to_phase_status"] == "SOURCE_DERIVABLE_PHASE_INCREMENT_ONLY"


def test_unresolved_source_mapping_stays_distinct_from_adr002() -> None:
    matrix = _load_matrix()
    mapping_claim = next(claim for claim in matrix["claims"] if claim["claim_id"] == "A-EDGE-TO-B")
    assert mapping_claim["evidence_status"] == "SOURCE_AMBIGUOUS"
    assert (
        mapping_claim["source_mapping_status"]
        == "AUTHOR_MAPPING_NOT_IDENTIFIABLE_FROM_AVAILABLE_SOURCE_EVIDENCE"
    )
    assert mapping_claim["reconstruction_status"] == "RECONSTRUCTION_ASSUMPTION"
    assert matrix["scientific_status_flags"] == {
        "paper_exact": False,
        "receiver_enabled": False,
    }


def test_m6d_validation_has_no_random_or_receiver_evaluation_imports() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not imported.intersection({"random", "secrets"})
    assert "evaluation" not in imported


def test_historical_configs_and_m6b_trace_hashes_remain_unchanged() -> None:
    expected_files = {
        "configs/m5j_confirmatory_approved_run.json": "8a9cb4c2d42a0b7014a40d5b83b9da13e7d1a65fe2fa3a68e1d90d5a53607840",
        "configs/m6b_trace_diagnostic_draft.json": "218881f447919b27c4b598269e6d9c9184187ee51cb353d3a3acacfe2a2dc844",
        "configs/m6b_trace_diagnostic_approved_run.json": "700f4af81b5dc92ae4b1a685d93d25cfcdf85b344e458fa538b690a452f119ee",
    }
    for relative, expected in expected_files.items():
        assert _sha256(ROOT / relative) == expected

    files, tree_digest = _m6b_tree_hashes()
    assert len(files) == 25
    assert tree_digest == "19b58bd057ffc1c8b725b225f4698a26b120c88dec6950fbaecd058c206a9ba3"
