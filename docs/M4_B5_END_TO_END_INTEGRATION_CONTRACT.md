# M4.7u/B5c — B4d-to-B5b isolated integration contract

## Scope and status

This integration is limited to the accepted `reconstructed_offline` profile:
one path (`L=1`), the ADR-012 real-channel experiment, zero delay, rectangular
ZOH, and eight samples per symbol. It composes the existing B4d sequence runner
with the accepted B5b conditional Viterbi decoder. The result is an **isolated
end-to-end single-path reconstructed receiver, NOT paper-exact joint receiver,
NOT general multipath receiver**. `paper_exact:false` and
`receiver_enabled:false` remain unchanged. ADR-009 and ADR-011 remain proposed.

The path does not claim the paper's reported 1.5 dB result. SCI-02, SCI-03,
SCI-METRIC-02, and the `U0`/`U**` correspondence remain open.

## Causal processing and frozen metric history

`run_reconstruction_posterior_estimator_sequence(..., include_history=True)`
already returns an immutable per-symbol history. Each entry contains the exact
B4c result used for that symbol's posterior update, including
`b4c_result.candidate_result.metrics` and its canonical hypothesis IDs,
absolute sample labels, target symbol, estimator tick, prediction cutoff,
metric availability cutoff, and profile provenance. The integration copies
these vectors into a read-only `(F,16)` matrix in history order. It does not
recompute metrics from the final estimator state or rerun B4b.

For each absolute symbol `f`, with explicitly supplied origin sample `O`:

| Event | Samples / label | Availability |
|---|---|---|
| Pre-observation state and candidate prediction | state at caller-supplied estimator tick `i`; symbol window begins `O+8f` | predictions use data only through `O+8f-1` |
| Received symbol window | absolute samples `O+8f` through `O+8f+7` | complete only at `O+8f+7` |
| B4b metrics and B4a posterior | same symbol row `f`, canonical 16-edge order | after `O+8f+7` |
| [A](1) update | explicit operands and current posterior | produces state `i+1`, usable for `f+1` or later |

The caller explicitly supplies the initial estimator-time/symbol-time mapping.
The sequence checks and advances the estimator tick and absolute symbol index
separately; it never assumes `i=f`. The B5b row `t` receives the metrics and
absolute symbol/estimator labels from the same B4d history entry. B5b's local
edge row index is separate from both clocks.

## First edge, continuation, and reset

The end-to-end adapter accepts one complete new independent sequence. Its
first symbol uses initial encoder state `(0,0)` and ADR-004 initial edge prior;
the first likelihood update has no transition. Each later B4d symbol uses the
posterior from the preceding symbol and performs exactly one transition.
Estimator state is handed from symbol to symbol. After the completed B4d pass,
the adapter freezes the actual metric history and invokes B5b exactly once for
the whole sequence, starting at `(0,0)` with ADR-013 free-final-state and
full-traceback policy.

The adapter rejects continuation mode: it does not treat a mid-trellis fragment
as an independent sequence, and does not silently reset B4d or B5b. B4d itself
supports an explicit continuation call. Two compatible B4d fragments can be
joined by their exact history rows and passed once to B5b as one independent
sequence; this is tested as a composition contract. The end-to-end adapter does
not provide automatic split-fragment stitching. Reporting frame boundaries do
not reset estimator, posterior, or trellis state. A separate frame scheduler is
not implemented.

## Result and invariants

`ReconstructionConditionalDecodeResult` contains the immutable B5b result,
final estimator state, final `(16,)` posterior, frozen finite nonnegative
candidate metrics `(F,16)`, and immutable per-row provenance. It exposes decoded
input pairs `(F,2)`, information bits `(2F,)`, selected hypothesis path `(F,)`,
best conditional path cost, final encoder state, canonical order, absolute
symbol labels, estimator-time labels, and per-symbol prediction/observation
cutoffs. No truth or BER/SER values are accepted or stored.

Hypothesis columns remain exactly `coding.hypotheses.HYPOTHESES` order. The
matrix rows are the B4b values B4a actually consumed, not metrics evaluated
again after coefficient updates. Arrays returned by the integration are
defensive read-only copies; input received samples and the initial state are not
mutated.

## Mathematical meanings kept separate

- **B4b `F_rx[f,h]`:** local aggregate squared residual over all eight I/Q
  samples for candidate edge `h`; history-conditioned on the pre-observation
  estimator state.
- **B4a posterior:** normalized project edge mass from the explicit prior or
  previous posterior, accepted transition rule, current B4b metric, and explicit
  beta. It is not a Viterbi branch cost.
- **[A](1):** causal coefficient recursion using the current posterior and
  explicit mean-of-eight observed I/Q and candidate predictions.
- **B5b conditional path cost:** sum of the frozen B4b costs along a valid
  trellis path. B5b performs no posterior or channel update.
- **[A](2):** distinct paper metric; SCI-METRIC-02 remains open and
  `paper_metric.py` is not changed by this integration.

Thus B5c performs one causal B4d pass followed by a conditional Viterbi pass on
the frozen resulting costs. It does not jointly optimize unknown channel
trajectories and trellis paths. `U0` and `U**` remain distinct unresolved source
quantities; the integration does not identify either with its candidate
prediction.

## Readiness and remaining limits

- Full received-buffer to decoded-information-bits composition for one
  explicitly labelled independent sequence: **READY as isolated reconstruction**.
- B4d split continuation plus exact metric-row concatenation and one B5b call:
  **READY as a tested caller-side composition**; automatic stitching is not
  provided.
- Frame integration and frame-constant forward-model scheduling: **BLOCKED**;
  no frame scheduler or equivalence between B4d's symbol-varying state and the
  existing frame-constant forward convention has been approved.
- General complex fading and multipath: **BLOCKED**; ADR-011 remains proposed.
- BER/SER claims: **BLOCKED** pending a separate evaluation layer with reference
  bits, matched baselines, repeated runs, error counts, uncertainty, and
  sensitivity analysis.
- Author-exact/joint receiver and the 1.5 dB claim: **NOT ESTABLISHED**.

No new ADR is needed for this composition of accepted B4d/B5b contracts. No CLI,
pipeline, decoder activation, or receiver default is changed.

## M4.7v/B5d segmented processing

The separate [segmented decode contract](M4_B5_SEGMENTED_DECODE_CONTRACT.md)
adds explicit nonempty sample-buffer segment descriptors for one independent
sequence. The first B4d segment uses the ADR-004 prior; each later segment uses
B4d continuation with the preceding exact state, posterior, and clock labels.
The adapter validates that segment symbols and sample-buffer offsets partition
the received buffer without gaps or overlap, retains exact per-symbol B4c
metric/posterior history with segment-local and sequence positions, then calls
B5b once after the final segment. It does not call the B5c whole-sequence
wrapper once per segment and does not reset at a reporting-frame boundary.

For tested deterministic operands, B5d segmented results equal a monolithic
B5c pass in frozen metrics, per-symbol posterior history, final state/posterior,
decoded path/bits, and conditional path cost. This validates the B4d continuation
contract under the narrow profile only. It does not establish compatibility
with `reconstruction_forward.py`'s frame-constant coefficients. The result is
**isolated segmented single-path reconstruction decode, NOT paper-exact joint
receiver, NOT general frame-constant channel integration**. No new ADR was
required.
