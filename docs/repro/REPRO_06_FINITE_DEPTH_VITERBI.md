# REPRO-06 — finite-depth Viterbi η=20

## Contract

The project convention defines `η` as the number of trellis transitions in a traceback window. At zero-based transition `k`, once rows `k-η+1 … k` have been consumed, the decoder emits a delayed decision for symbol `k-η+1`. For η=20 the first ordinary decision for symbol 0 is available after consuming symbol 19; its latency is 19 subsequent symbols.

This convention is consistent with a 20-transition window. REPRO-01 records that the printed A(2) summation limits may literally include η+1 indices; that source ambiguity remains unresolved and is not silently reinterpreted as an author-confirmed decoder implementation.

## API and algorithm

`FiniteDepthViterbiDecoder(ViterbiConfig(...))` accepts one 16-edge metric row through `consume_metric_row(row)`. It returns zero or one `DecisionRecord`; `flush()` returns only the remaining records; `result()` returns the completed arrays. `run_viterbi(rows, config)` is the batch wrapper around that same row-wise engine. Rows may be integer Hamming costs or finite nonnegative floating Euclidean costs, with a fixed dtype family for the frame.

The four accumulated state metrics use Encoder A's canonical state/edge order. A strict improvement replaces a survivor; equal branch/path costs preserve the first canonical edge. A final equal-cost endpoint resolves to the first state in `STATE_ORDER`. No metric normalization is applied. The streaming core stores at most η predecessor rows. Full diagnostics are an explicitly selected observer output; `trace_output_mode="compact"` omits the historical state/survivor matrices.

Each decision records its symbol index, availability index, actual traceback depth, locally selected survivor edge, input pair, local source/target states, decoder mode, and whether it was a regular or frame-flush decision. Since independently committed finite-depth decisions come from overlapping survivor paths, their local survivor edges are not guaranteed to join at every boundary. The delivered information pairs are re-encoded from the configured initial state to provide a valid decoded Encoder A state/edge path; local survivor-edge evidence remains separately recorded in decision records. `final_path_metric` is the metric of the terminal survivor, and `terminal_survivor_state` is recorded separately from the re-encoded output path's final state.

## Frame end and termination

`none` leaves the terminal state free and flushes from the minimum available survivor; no transmitter final-state truth is read. `zero_tail_2` requires a declared frame length, constrains the last two transitions to input `(0,0)`, and may select the resulting public terminal state `(0,0)`. For `F<η`, the available traceback depths are `F, F-1, …, 1`; at `F=η`, one ordinary η-depth decision is emitted and the other `η-1` decisions flush; at `F>η`, ordinary decisions precede a flush of the last `η-1` symbols. Every frame symbol is emitted exactly once.

## Receiver integration and limits

REPRO-04 applies finite-depth decoding after the unchanged hard 8PSK decisions and Hamming rows. REPRO-05 applies it only after the unchanged candidate metrics, posterior, and causal estimator pass have completed. Thus changing decoder mode cannot change metric rows or estimator histories. Both APIs still receive only `ReceiverObservation`; `EvaluationTruth` remains evaluation-only.

Existing receiver configs remain `full_frame` with `traceback_depth=null` by default. `SeparateReceiverConfig.article_oriented(...)` and `JointReceiverConfig.article_oriented(...)` select the project η=20 convention and compact trace output unless full diagnostics are explicitly requested. The CLI accepts `--decoder-mode finite_depth --traceback-depth 20`. Full-frame and finite-depth paths may differ; that is expected and is not a performance claim. Joint delayed multipath remains `MULTIPATH_JOINT_RECEIVER_PARTIAL`.

`paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN are preserved.
