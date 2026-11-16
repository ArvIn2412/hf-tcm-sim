# REPRO-02 — схема виходу transmitter

## JSON configuration

`schema_version: repro02-transmitter-v1`. Unknown fields відхиляються. Поля: `source_mode`, `frame_symbols`, один із manual/pattern/seed settings, `rng_algorithm=PCG64`, `initial_state`, `termination_policy`, `encoder_id`, `mapping_id`, `amplitude`, `phase_offset_rad`, `phase_increment_rad=π/4`, `samples_per_symbol=8`.

`frame_symbols` рахує TCM input-pair steps у payload. Manual input має рівно `2*frame_symbols` бітів. Вихідна довжина може зрости лише при явній `zero_tail_2` політиці.

## TransmitterResult arrays

| Field | Shape | dtype | Meaning |
|---|---:|---|---|
| `information_bits` | `(2F,)` | int8 | payload bits, left-to-right |
| `payload_input_pairs` | `(F,2)` | int8 | `(u0,u1)` payload pairs |
| `input_pairs` | `(F+T,2)` | int8 | payload plus explicit termination |
| `coded_triples` | `(F+T,3)` | int8 | `(c2,c1,c0)` |
| `pre_states`, `post_states` | `(F+T,2)` | int8 | state before/after each edge |
| `state_history` | `(F+T+1,2)` | int8 | initial state then each destination |
| `edge_ids`, `phase_indices` | `(F+T,)` | int16, int8 | stable branch ID and reconstructed b |
| `symbols`, `phase_values_rad`, `symbol_energies` | `(F+T,)` | complex128, float64 | modulated symbols and values |
| `tx_samples` | `(8(F+T),)` | complex128 | rectangular ZOH complex envelope |
| sample index arrays | `(8(F+T),)` | int64 | absolute, symbol and within-symbol index |

## Persisted run

CLI writes `input_config.json`, `arrays.npz` (NumPy numeric arrays; load with `allow_pickle=False`), `mapping_table.json`, `summary.json`, `performance.json`, and `manifest.json`. The manifest contains array dtype, shape and SHA-256 plus configuration, source/mapping fingerprints, environment and RNG reproducibility metadata. Complex arrays remain native NumPy complex values in NPZ; JSON summary contains only JSON-compatible scalar/list metadata and no lossy complex serialization.

`paper_exact:false`, `receiver_enabled:false` are explicit fields. Output directory is restricted to `outputs/repro02/`; historical experiment namespaces are not valid destinations.
