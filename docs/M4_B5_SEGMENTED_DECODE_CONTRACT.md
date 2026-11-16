# M4.7v/B5d — segmented single-path reconstruction decode contract

## Scope and status

This contract covers one independent received sequence under the accepted
`reconstructed_offline`, L=1, real-channel experiment, zero-delay, rectangular
ZOH, 8-samples/symbol profile, with ADR-012 observations and ADR-013 conditional
full Viterbi. The result is **isolated segmented single-path reconstruction
decode, NOT paper-exact joint receiver, NOT general frame-constant channel
integration**. ADR-001/002/003/004/005/006/007/008/010/012/013 remain accepted;
ADR-009/011 remain proposed. `paper_exact:false`, `receiver_enabled:false`, and
SCI-METRIC-02 open are unchanged.

## Segment input contract

`ReconstructionSequenceSegment` explicitly records:

- `first_symbol_index`: first absolute symbol label in this segment;
- `received_start_offset`: first complex sample's offset in the one complete
  received buffer;
- `symbol_count`: positive number of whole symbols in the segment.

Descriptors are ordered and nonempty. They must partition the buffer with no
gap or overlap: the first buffer offset is zero and each next offset equals the
previous offset plus `8 * previous.symbol_count`. Absolute symbol labels must
also be contiguous. The complete received buffer contains exactly eight
complex samples for every symbol and has contiguous explicit absolute sample
labels. For origin sample `O` and absolute symbol `f`, the segment's expected
window is `[O+8f, O+8f+7]`; the first buffer sample must be
`O+8*sequence_origin_symbol_index`. Incomplete final symbols, duplicated or
skipped labels, and inconsistent offsets are rejected before processing.

Segmentation describes how one contiguous independent sequence is passed to
B4d. It does not declare a new codeword, frame reset, estimator reset, posterior
reset, termination, new channel/noise model, or new ADR-004 prior.

## B4d lifecycle and frozen rows

The first segment invokes B4d as `new_independent_sequence`. Only its first
symbol receives the ADR-004 initial edge prior and current likelihood without a
transition. Every later symbol—including the first symbol of each later
segment—invokes B4d as `continuation`, with the previous segment's exact final
estimator state and posterior plus the immediately preceding symbol and
estimator-time labels. The first edge is never reinitialized at a segment
boundary.

Each B4d call requests immutable per-symbol history. B5d copies the exact
`b4c_result.candidate_result.metrics` vectors used by B4a, retaining canonical
`HYPOTHESES` column order. It does not rerun B4b or recalculate earlier costs
with final estimates. The joined frozen matrix has shape `(F,16)`. Posterior
rows are retained as immutable `(F,16)` diagnostics so their segmented history
can be compared with a monolithic B4d pass.

The returned symbol schedule records each row's absolute sample and symbol
labels, estimator `time_index`, segment index, segment-local position,
independent-sequence position, edge mode, prediction cutoff, observation
cutoff, profile ID, and hypothesis order. Segment-boundary metadata carries
absolute first/last symbols and samples, buffer offsets, sequence-position
range, and estimator clocks before/after the segment.

For symbol `f`, with explicit origin `O`:

- prediction cutoff is `O+8f-1`;
- the current eight samples end at `O+8f+7`;
- B4b metric, B4a posterior and estimator update are available only after that
  final sample;
- the updated state is passed only to the next symbol or later.

The estimator clock starts at the caller's explicit `initial_estimator_time_index`
and advances exactly once per symbol. It is not inferred from the symbol index.

## One final B5b call

Only after all segments finish does B5d stack the exact history rows in original
sequence order and call `decode_reconstruction_viterbi()` once. The decoder
starts from `(0,0)` because the B5d input is one complete independent sequence;
it uses the accepted ADR-013 free-final-state, no-tail, full-traceback policy.
Intermediate segments produce no final decoded-bit output. No Viterbi or
estimator reset happens at segment boundaries.

The result contains a B5c-compatible decode result, frozen metrics `(F,16)`,
posterior history `(F,16)`, decoded input pairs `(F,2)`, decoded information
bits `(2F,)`, selected hypothesis path `(F,)`, final encoder state, final
estimator state and posterior, segment boundaries, symbol schedule, and
per-row metric provenance. Returned arrays are read-only defensive copies. No
ChannelTruth, reference bits, or BER/SER values are accepted or retained.

## Segments, reporting frames, and independent sequences

1. **Processing segments** are arbitrary nonempty contiguous pieces of one
   received buffer. They preserve B4d state and posterior.
2. **Reporting frames** group outputs only. A reporting boundary causes no
   estimator, posterior, or trellis reset.
3. **Independent coded sequences** are separate codewords. Only a new such
   sequence may start from `(0,0)` and use the initial edge prior.
4. **Frame-constant `reconstruction_forward.py` coefficients** remain a
   separate convention. B5d does not schedule its symbol-varying B4d estimates
   into that forward model and does not establish equivalence with it.

## Equivalence evidence and limits

Tests compare monolithic B5c with segmented B5d for F=1, F=2, F=4 and F=6,
including the requested partitions `[1]`, `[2]`, `[1,1]`, `[4]`, `[1,3]`,
`[2,2]`, `[3,1]`, `[1,1,1,1]`, and uneven six-symbol partitions. For identical
received samples, initial state, explicit parameters, and clocks, they assert
identical frozen metric rows, posterior history/final posterior, final
estimator state, decoded path/bits, and conditional path cost. Additional tests
cover explicit per-symbol parameter schedules, nonzero sample origin, clock
separation, invalid partitions and labels, exact continuation handoff, one
final Viterbi invocation, immutability, repeatability, and the no-truth boundary.
This is deterministic reconstruction equivalence evidence; it is not a
statistical channel or BER/SER claim.

The conditional cost remains the sum of frozen B4b aggregate residuals. B4a
posterior, [A](1) estimate updates, B5b path cost, and [A](2) paper metric are
different quantities. B5d does not globally optimize unknown channel
trajectories and trellis paths together. `U0`/`U**` remain distinct open source
questions.

## Readiness

- Segmented B4d continuation and one final B5b call for the narrow profile:
  **READY as isolated reconstruction**.
- Monolithic/segmented equality for the tested deterministic cases:
  **READY and tested**.
- General frame-constant channel integration, complex fading, multipath, and
  online receiver: **BLOCKED/out of scope**.
- BER/SER evaluation: requires a separate evaluation layer that supplies
  reference bits outside the receiver, defines matched baselines and sampling,
  records raw error counts across independent runs, and reports uncertainty
  and sensitivity. No such layer is implemented here.

No new ADR is needed. ADR-009 beam search and ADR-011 multipath pseudo-path
observations remain proposed and unused.
