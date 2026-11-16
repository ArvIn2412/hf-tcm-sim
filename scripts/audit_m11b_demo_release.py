"""Regenerate the M11b stage and parameter coverage report from a fixed trace."""

from __future__ import annotations

import json
from pathlib import Path

from hf_tcm.evaluation.m11a_demo_studio import (
    DEFENSE_DEMO_REQUEST,
    build_demo_trace,
    build_stage_coverage_audit,
)

ROOT = Path(__file__).resolve().parents[1]

CATEGORIES = (
    (
        "Information bits",
        "DEMO_BIT_PATTERNS; runtime.input.information_bits",
        "Explicit deterministic input; not passed to receiver.",
    ),
    (
        "TCM encoder",
        "encode_step; runtime selected edge/output/state",
        "Canonical encoder implementation and trace fields.",
    ),
    (
        "Four hidden states",
        "trellis.state[0..3]",
        "STATES tuple; four distinct canonical state IDs.",
    ),
    (
        "Sixteen transitions",
        "trellis.edge[0..15]",
        "HYPOTHESES canonical order; all 16 rendered in graph/table.",
    ),
    (
        "Edge-to-phase mapping",
        "phase_index",
        "ADR-002 reconstructed mapping; not author-confirmed.",
    ),
    (
        "8PSK",
        "constellation_size; constellation_points",
        "M1 constellation function; normalized points.",
    ),
    (
        "Sampling and ZOH",
        "samples_per_symbol; sample_indices; transmitted_samples",
        "ADR-012 profile and rectangular ZOH rule; eight samples/symbol.",
    ),
    (
        "Channel gain",
        "profile.real_channel_gain; runtime.channel_gain",
        "M9 approved fixed-gain profile for the deterministic demo.",
    ),
    (
        "AWGN/noise",
        "noise_fixtures; runtime.noise_samples",
        "Explicit deterministic fixture formula; no RNG.",
    ),
    (
        "Observed IQ",
        "runtime.observed_iq_samples; observed_iq",
        "Actual B4d observation window under ADR-012.",
    ),
    (
        "Estimator initialization",
        "policy initial_fluctuating_iq / initial_full_iq; sequence_origin",
        "Approved M9 policy configs and resolved clock origins.",
    ),
    (
        "Alpha and K",
        "historical_frozen_B.alpha_prime/k_tilde; anch_a085_k025.alpha_prime/k_tilde",
        "Exact policy config values; anchored controls editable only in demo form.",
    ),
    ("Anchor mu0", "both policy mu0 values", "Approved policy configuration; read-only."),
    (
        "Innovation",
        "runtime per-symbol innovation",
        "Derived from actual posterior and predictions; project reconstruction.",
    ),
    (
        "Candidate predictions",
        "runtime predicted_iq and sample_predictions_iq",
        "Actual B4d history, pre-update state.",
    ),
    ("Metrics", "runtime candidate_metrics; frozen_metric_sequence", "Actual B4d metric arrays."),
    (
        "Beta and pseudo-likelihood",
        "policy beta; runtime pseudo_likelihood",
        "M9 approved config and ADR-005 reconstructed likelihood.",
    ),
    (
        "Posterior",
        "runtime posterior/posterior_sum/posterior_normalized",
        "Actual B4c posterior; 16 weights.",
    ),
    (
        "Recursive update",
        "runtime pre_state/post_state/alpha_contribution/correction_contribution",
        "Actual B4d state plus trace operands.",
    ),
    (
        "Viterbi",
        "runtime survivor metrics/predecessors/decoded edge path/state path/decoded bits",
        "Actual conditional Viterbi; no forward-backward claim.",
    ),
    (
        "Error counting",
        "runtime bit_errors/symbol_errors/flags",
        "Existing raw count functions; evaluation-side comparison.",
    ),
    (
        "Experimental statistics",
        "M5j/M9b/M10b archived summaries; deterministic demo BER/SER",
        "Archived results are read only. Single-fixture inference is unavailable.",
    ),
    (
        "Scientific assumptions",
        "paper_exact; receiver_enabled; source_mapping_status; SCI-METRIC-02",
        "ADR-002/005 reconstructed; ADR-016 evaluation-only; SCI-02/03/SCI-METRIC-02 open.",
    ),
    (
        "Dataset provenance",
        "historical_dataset_roots; artifact paths/SHA-256; runtime trace origins",
        "M5-M10 archived sources and current deterministic trace provenance.",
    ),
)


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def write_coverage_report() -> None:
    trace = build_demo_trace(DEFENSE_DEMO_REQUEST)
    audit = build_stage_coverage_audit(trace)
    stage_rows = []
    for row in audit:
        status = (
            "PARTIAL BY DESIGN" if row["runtime_coverage"] == "PARTIAL_BY_DESIGN" else "IMPLEMENTED"
        )
        values = [
            row["stage_id"],
            row["stage_name"],
            row["actual_renderer"],
            row["data_source"],
            row["raw_derived_provenance"],
            row["parameter_source"],
            row["formula_source"],
            row["runtime_coverage"],
            row["test_coverage"],
            status,
        ]
        stage_rows.append("| " + " | ".join(map(_cell, values)) + " |")

    category_rows = ["| " + " | ".join(category) + " |" for category in CATEGORIES]
    parameter_rows = []
    for parameter in trace["parameter_registry"]:
        value = json.dumps(parameter["value"], ensure_ascii=False, separators=(",", ":"))
        default = (
            "Not specified"
            if parameter["default_value"] is None
            else json.dumps(parameter["default_value"], ensure_ascii=False, separators=(",", ":"))
        )
        allowed = parameter["allowed_range"] or "Not specified"
        fields = [
            parameter["parameter"],
            parameter["symbol"],
            parameter["type"],
            value,
            parameter["unit"],
            allowed,
            default,
            parameter["source"],
            parameter["status"],
            parameter["description"],
        ]
        parameter_rows.append("| " + " | ".join(map(_cell, fields)) + " |")
    if len(parameter_rows) != len(trace["parameter_registry"]):
        raise RuntimeError("parameter inventory row count does not match the live registry")

    content = "\n".join(
        [
            "# M11b stage and parameter coverage",
            "",
            "This audit is generated from the explicit deterministic F=32 trace and live parameter registry. It does not run from GET. Stage source inputs and outputs are evaluated at center symbol 16; browser QA separately inspected all 28 stage details. Stage 28 remains partial by design.",
            "",
            "## Automated 28-stage audit",
            "",
            "| stage_id | stage_name | actual renderer | data source | raw/derived provenance | parameter source | formula source | runtime coverage | test coverage | status |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
            *stage_rows,
            "",
            "## Parameter category coverage",
            "",
            "| Requirement category | Exact registry/trace fields | Source and qualification |",
            "|---|---|---|",
            *category_rows,
            "",
            "## Complete searchable inventory",
            "",
            "The Inspector groups exact registry entries by domain and supports search by name, symbol, group, value, source, or description. Read-only entries have no decorative sliders. Repository-undefined ranges/defaults are marked Not specified; the only allowed range shown is the existing beta > 0 API condition for the demo-editable beta field.",
            "",
            "| exact name | symbol | type | actual value | unit | allowed range | default | scientific/project source | status | description |",
            "|---|---|---|---|---|---|---|---|---|---|",
            *parameter_rows,
            "",
            "## Statistical boundary",
            "",
            "The deterministic fixture displays raw BER/SER counts. Paired confidence inference is unavailable for one fixture and remains PARTIAL BY DESIGN; it is appropriate only for archived independent studies. Historical M9/M10 dashboard intervals are read from saved summaries and both contain zero.",
            "",
        ]
    )
    (ROOT / "docs/DEMO_PARAMETER_COVERAGE.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    write_coverage_report()
