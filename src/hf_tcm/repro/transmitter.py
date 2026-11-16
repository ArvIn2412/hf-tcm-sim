"""End-to-end REPRO-02 transmitter; no channel or receiver is invoked."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from hf_tcm.repro.config import TransmitterConfig
from hf_tcm.repro.encoder import EDGE_ORDER_ID, EncoderResult, encode, transition_table
from hf_tcm.repro.identifiers import ENCODER_ID
from hf_tcm.repro.labeling import build_edge_mapping
from hf_tcm.repro.modulator import modulate
from hf_tcm.repro.source_bits import InformationBits, generate_information_bits
from hf_tcm.repro.waveform import rectangular_zoh

SOURCE_PAPER_SHA256 = "a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8"
SOURCE_SPEC_ID = "REPRO-01-ENCODER-A-v1"


@dataclass(frozen=True, slots=True)
class TransmitterResult:
    information_bits: NDArray[np.int8]
    payload_input_pairs: NDArray[np.int8]
    input_pairs: NDArray[np.int8]
    coded_triples: NDArray[np.int8]
    pre_states: NDArray[np.int8]
    post_states: NDArray[np.int8]
    state_history: NDArray[np.int8]
    edge_ids: NDArray[np.int16]
    phase_indices: NDArray[np.int8]
    phase_values_rad: NDArray[np.float64]
    symbols: NDArray[np.complex128]
    symbol_i: NDArray[np.float64]
    symbol_q: NDArray[np.float64]
    symbol_energies: NDArray[np.float64]
    tx_samples: NDArray[np.complex128]
    absolute_sample_index: NDArray[np.int64]
    sample_symbol_index: NDArray[np.int64]
    sample_local_index: NDArray[np.int64]
    sample_tx_i: NDArray[np.float64]
    sample_tx_q: NDArray[np.float64]
    final_state: tuple[int, int]
    termination_metadata: dict[str, Any]
    source_metadata: dict[str, Any]
    config_snapshot: dict[str, Any]
    encoder_id: str
    mapping_id: str
    mapping_status: str
    mapping_table: tuple[dict[str, object], ...]
    mapping_fingerprint: str
    source_spec_id: str
    source_file_sha256: str
    source_fingerprint: str
    waveform_rule: str
    samples_per_symbol: int
    paper_exact: bool = False
    receiver_enabled: bool = False


def _source_fingerprint() -> str:
    payload = {
        "source_spec_id": SOURCE_SPEC_ID,
        "source_file_sha256": SOURCE_PAPER_SHA256,
        "generator_matrix": [["1", "0", "0"], ["0", "D^2+1", "D"]],
        "equation_reference": "S1, printed pages 5-6, figures 2-3",
        "status": "source edition not confirmed as supervisor v7",
        "edge_order_id": EDGE_ORDER_ID,
        "transitions": [
            {
                "edge_id": edge_id,
                "state": state,
                "input": pair,
                "output": output,
                "next_state": next_state,
            }
            for edge_id, state, pair, output, next_state in transition_table()
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_transmitter(config: TransmitterConfig) -> TransmitterResult:
    """Generate bits, encode, map, modulate, and form 8-sample ZOH symbols."""
    if not isinstance(config, TransmitterConfig):
        raise TypeError("config must be a TransmitterConfig")
    source: InformationBits = generate_information_bits(config)
    pairs = source.information_bits.reshape(config.frame_symbols, 2)
    encoded: EncoderResult = encode(
        pairs,
        initial_state=config.initial_state,
        termination_policy=config.termination_policy,  # type: ignore[arg-type]
    )
    mapping = build_edge_mapping(encoded)
    modulation = modulate(
        mapping.phase_indices,
        amplitude=config.amplitude,
        phase_offset_rad=config.phase_offset_rad,
        phase_increment_rad=config.phase_increment_rad,
    )
    waveform = rectangular_zoh(
        modulation.symbols,
        samples_per_symbol=config.samples_per_symbol,
    )
    return TransmitterResult(
        information_bits=source.information_bits,
        payload_input_pairs=encoded.payload_input_pairs,
        input_pairs=encoded.input_pairs,
        coded_triples=encoded.coded_triples,
        pre_states=encoded.pre_states,
        post_states=encoded.post_states,
        state_history=encoded.state_history,
        edge_ids=encoded.edge_ids,
        phase_indices=mapping.phase_indices,
        phase_values_rad=modulation.phase_values_rad,
        symbols=modulation.symbols,
        symbol_i=modulation.symbol_i,
        symbol_q=modulation.symbol_q,
        symbol_energies=modulation.symbol_energies,
        tx_samples=waveform.tx_samples,
        absolute_sample_index=waveform.absolute_sample_index,
        sample_symbol_index=waveform.symbol_index,
        sample_local_index=waveform.local_sample_index,
        sample_tx_i=waveform.sample_tx_i,
        sample_tx_q=waveform.sample_tx_q,
        final_state=encoded.final_state,
        termination_metadata=dict(encoded.termination_metadata),
        source_metadata=source.metadata,
        config_snapshot=config.to_dict(),
        encoder_id=ENCODER_ID,
        mapping_id=mapping.mapping_id,
        mapping_status=mapping.status,
        mapping_table=mapping.table,
        mapping_fingerprint=mapping.fingerprint,
        source_spec_id=SOURCE_SPEC_ID,
        source_file_sha256=SOURCE_PAPER_SHA256,
        source_fingerprint=_source_fingerprint(),
        waveform_rule=waveform.waveform_rule,
        samples_per_symbol=waveform.samples_per_symbol,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; no-argument invocation only prints help."""
    from hf_tcm.repro.cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
