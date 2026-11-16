"""Evaluation-only CLI kept separate from receiver decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from hf_tcm.repro.receiver_evaluation import evaluate_separate_receiver
from hf_tcm.repro.receiver_io import load_separate_receiver_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluation-only REPRO-04 BER/SER recount")
    parser.add_argument("--receiver-output", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, required=True, help="JSON with information_bits and phase_indices"
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/repro04/evaluation"))
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)
    reference_path = args.reference
    raw = reference_path.read_bytes()
    reference = json.loads(raw)
    if set(reference) != {"information_bits", "phase_indices"}:
        raise ValueError("reference JSON must contain exactly information_bits and phase_indices")
    result = load_separate_receiver_result(args.receiver_output)
    evaluation = evaluate_separate_receiver(
        result,
        np.asarray(reference["information_bits"]),
        np.asarray(reference["phase_indices"]),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "repro04-evaluation-v1",
        "receiver_output_observation_sha256": result.observation_sha256,
        "reference_sha256": hashlib.sha256(raw).hexdigest(),
        "compared_information_bit_count": evaluation.compared_information_bit_count,
        "bit_errors": evaluation.bit_errors,
        "ber": evaluation.ber,
        "compared_symbol_count": evaluation.compared_symbol_count,
        "symbol_errors": evaluation.symbol_errors,
        "ser": evaluation.ser,
        "bit_error_positions": evaluation.bit_error_positions.tolist(),
        "symbol_error_positions": evaluation.symbol_error_positions.tolist(),
        "evidence_scope": evaluation.evidence_scope,
        "receiver_decision_uses_reference": False,
    }
    target = args.output / "evaluation.json"
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
