# REPRO-06 — REPRO-04 Hamming integration

`SeparateReceiverConfig` adds `decoder_mode`, `traceback_depth`, `initial_state_policy`, `final_state_policy`, `tie_break_policy`, and `trace_output_mode`. Existing JSON without these fields deserializes to the existing full-frame behavior. The convenience `article_oriented(expected_symbol_count=...)` chooses finite depth 20. CLI overrides are `--decoder-mode`, `--traceback-depth`, and `--trace-output-mode`.

Hard 8PSK classification and integer Hamming rows are computed exactly as before. The finite decoder receives `(F,16)` integer rows and accumulates integer costs; it does not see Euclidean distances. In full-frame mode the established `decode_hamming_viterbi` remains the compatibility implementation.

The result records actual traceback mode/depth, per-symbol decision and latency records, survivor-buffer maximum, final-state policy, and optional state/survivor diagnostic matrices. Decision arrays are stored in NPZ; full decision metadata is also included in the summary. Evaluation remains outside the decoder.
