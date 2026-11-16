# M4.7n/B3c-4 — causal one-path integration contract

**Scope:** `L=1`, `reconstructed_offline`, accepted project assumption ADR-012. This is not a source-faithful observation algorithm or a complete paper-exact receiver. The adapter remains isolated from CLI, pipeline, decoder, and forward orchestration.

## Source and API boundary

[A](3)–(4) describe a real passband waveform and received sum of path quadratures plus additive disturbance. [A](5) maps a supplied discrete phase value to two quadratures, and [A](6) defines path coefficients. These equations do not specify a digital operator from M3's complex baseband `ChannelOutput.received` to [A](1)'s path-indexed observation. ADR-012 chooses a narrow project transform; it is not presented as a derivation from [A].

M3 `received` is a complex `(N,)` aggregate baseband buffer; its diagnostic `truth` is separate and excluded. A `(N,2)` `(I,Q)` view is a representation conversion. The ADR-012 observed-IQ adapter reads only the selected complex samples and explicit absolute labels. It has no argument for a channel coefficient, truth, generator state, transmitted bits, or symbol phase.

## Accepted ADR-012 profile

The user explicitly accepted ADR-012 on 2026-10-28 for this narrow research reconstruction:

- profile `reconstructed_offline`, one path, real-channel experiment, zero delay;
- rectangular zero-order hold, exactly eight samples per symbol;
- each sample maps to `(-Im(received[n]), Re(received[n]))`;
- the observation for one symbol is the arithmetic mean of exactly its eight mapped samples;
- one estimator transition occurs only after the final sample of that symbol arrives;
- the updated snapshot is eligible only for the next symbol or later.

The real coefficient `a` may be known by a synthetic simulation fixture to construct an independent oracle. It is never an input to the observation or estimator adapters. This is a coordinate rotation, not division by true `h`. It does not cover a general complex channel, does not establish an [A]-confirmed observation process, and does not imply equal/independent AWGN after averaging.

## Explicit clocks and window

The three integer scales remain distinct:

| Scale | Contract |
|---|---|
| Absolute sample index `n` | Caller supplies labels for every buffer element and `received_start_sample`. For symbol `f`, the exact window is `n=O+8f+k`, `k=0,…,7`, with explicit `symbol_origin_sample=O`. |
| Absolute symbol index `f` | Caller supplies `target_symbol_index`; it is never inferred from array offsets. |
| Estimator `time_index=i` | Caller explicitly supplies the pre-observation state label paired with `f`. The adapter checks it matches `state.time_index`, then delegates exactly `i→i+1`. It does not convert origins or silently assume `i=f`. |

The causal call means: state at `i` is the state before observing symbol `f`; the complete eight-sample window for `f` arrives; exactly one update runs; the result is available after sample `O+8f+7`. The caller must pair the next state at `i+1` with symbol `f+1` on the next call. The returned forward snapshot is labelled `i+1`; it may be applied only to symbol `f+1` or later. This explicit per-call pairing avoids an implicit conversion between clock origins.

The adapter rejects missing window samples and never pads observations. It validates all buffer labels as contiguous from their declared origin and checks finiteness of the selected window. It does not inspect future sample values. Zero padding remains a forward-prediction alignment policy under ADR-008, not an observation-window policy.

## Estimator and forward integration

`advance_real_one_path_symbol()` performs only:

`explicit received buffer/window → ADR-012 observed mean → advance_reconstruction_estimator_state() → snapshot_full_iq_for_forward()`.

`posterior (M,)`, `predicted_iq (M,2)`, `alpha_prime`, `k_tilde (1,2)`, and `mu0 (1,2)` are caller operands. The caller also supplies absolute sample cutoffs for data used to form posterior and predictions; the adapter rejects a cutoff later than the last sample of current symbol `f`. These are explicit provenance labels, not proof that a caller truthfully reported its inputs. The adapter does not produce or infer operands. The existing step delegates [A](1) arithmetic to unchanged `paper_recursion.py`. The resulting immutable state keeps `fluctuating_iq` and `full_iq` separate; the forward snapshot copies `full_iq` only.

`reconstruction_forward.py` remains unchanged: it uses a coefficient pair constant for an entire frame. The adapter returns a labelled snapshot but does not choose a frame start/count or connect the snapshot to that forward function. Any future integration must schedule a frame only at or after the snapshot's `next_usable_symbol_index` and explicitly reconcile frame/sample labels. No coefficient is applied retroactively to the symbol just observed.

## Causality, posterior operands, and noise

For symbol `f`, only its eight samples and prior history may affect the update. Explicit `predicted_iq` and `posterior` must be produced from data available at the declared cutoff and may not use future received samples. This adapter checks their delegated numeric shape/validity but does not establish operand provenance or calculate either one. Future-data smoothing is not supported.

The arithmetic mean remains a deterministic observation transform. For correlated sample noise with covariance matrix `Σ` over the eight samples, the mean's variance depends on `1ᵀΣ1/64`; no independent AWGN claim, covariance, or noise variance is inserted by this code. Noise covariance for likelihood/statistical claims remains open.

## Readiness and remaining boundary

- **L=1 observed-IQ adapter — READY:** exact profile, path count, zero delay, ZOH, eight samples, absolute labels, complete window and selected-sample finiteness are checked.
- **Causal one-path explicit-posterior step — READY as an isolated adapter:** one completed symbol maps to one delegated state step; old state remains immutable; next snapshot contains `full_iq` and is labelled for future use. Status: **causal one-path explicit-posterior reconstruction step, NOT complete paper-exact receiver**.
- **Autonomous estimator — BLOCKED:** this observation/state adapter does not generate per-candidate predictions or metrics, and the standalone posterior policy is not connected to it. General complex-channel/noise model and candidate/metric provenance remain unspecified. ADR-011 remains proposed for multipath pseudo-observations.
- **B4 — BLOCKED:** ADR-003/004/005 now define isolated reconstruction posterior choices, but their metric vectors are not mapped/clocked to causal symbols; ADR-009 decoder/search/traceback remains proposed. No adaptive decoder or pipeline/CLI connection is added.

ADR-001/002/003/004/005/006/007/008/010/012 are accepted; ADR-009/011 remain proposed. `paper_exact:false`, `receiver_enabled:false`. The separate v7 article file is not present here, so this contract makes no claim of checking that edition. SCI-02/SCI-03/SCI-METRIC-02 and `paper_metric.py` remain unchanged.

## B4b candidate-metric cutoff and operands

For one target symbol `f`, the B4b candidate-metric generator requires an explicit pre-observation state timestamp `i = state.time_index`, separately supplied alongside `f` and the sample origin `O`; it does not infer `i=f`. It snapshots `full_iq` before examining the target observations and creates all 16 one-symbol forward predictions for labels `O+8f` through `O+8f+7`. The prediction data cutoff is `O+8f-1`. After those eight aggregate samples arrive, ADR-012 supplies eight per-sample `(-Im,Re)` values and the project metric sums squared residuals over all 8×2 operands. Metric availability is after sample `O+8f+7`.

This metric path does not use the averaged observed-IQ `(2,)` operand used by the estimator recursion. It accepts a full explicit buffer with contiguous sample labels but selects only the exact target window; samples after that window do not enter the result. `ReconstructionCandidateMetricResult.metrics` is an immutable `(16,)` vector aligned to its explicit `hypothesis_ids`, `output_bits` and `phase_indices` metadata. Default order is the canonical `HYPOTHESES` order shared by B4a; an explicitly requested permutation permutes all row metadata and values together.

The vector can feed B4a's per-edge emission update, but does not choose a sequence of edges or decode information bits. B4c remains separate: posterior-to-coefficient operand alignment and the timing/meaning of posterior and estimator recursion operands have not been approved or integrated.

## M4.7q/B4c single-symbol posterior-to-estimator composition

The isolated B4c entry point explicitly requires either the first-edge initial prior or the preceding-edge posterior. For the first edge it applies only the current metric emission to the initial prior; for later edges it applies the accepted transition and then the current emission. It sends the resulting current-edge posterior and the aligned `(16,2)` candidate predictions to the existing single-beam [A](1) adapter. Candidate IDs, output bits, phase indices, metrics and predictions are validated in canonical `HYPOTHESES` order.

The pre-observation `full_iq` snapshot is shared by B4b's eight-sample predictions and the recursion prediction operand. Each `(16,2)` [A](5) prediction must match all eight repeated B4b ZOH samples. The ADR-012 mean-of-eight observation is extracted only for the estimator recursion. The explicit prediction cutoff is `O+8f-1`, the observation/posterior cutoff is `O+8f+7`, and the next state/snapshot may be used only for `f+1` or later. Estimator index `i` and symbol index `f` remain separate caller-supplied labels.

This establishes only a single-symbol causal project reconstruction step. It does not establish a complete paper-exact receiver, autonomous sequence clocking, decoded bits, or B5/B6 behavior.

## M4.7r/B4d multi-symbol clock and handoff contract

B4d uses B4c's exact absolute sample mapping `n=O+8f+r`, `r=0..7`; therefore an input buffer for requested consecutive absolute symbols `f0..f0+N-1` must start at sample `O+8f0`, provide exact contiguous labels and contain exactly `8N` finite complex values. The runner passes a growing prefix to each B4c call so the step receives no later-symbol samples. Its prediction cutoff is the preceding sample `O+8f-1`; its metric/posterior/update cutoff is the eighth current-symbol sample `O+8f+7`.

Clock mapping is explicit but affine by the accepted one-tick-per-completed-symbol convention: caller supplies initial state tick `i0` and first symbol `f0`, then runner checks `i=i0+k` and `f=f0+k` for every call. No `i=f` equality is inferred. A `new_independent_sequence` declaration applies the ADR-004 prior once at its explicitly declared sequence origin. A `continuation` supplies the posterior and state after the immediately preceding symbol plus its symbol/tick labels; it starts with a transition. A frame/reporting boundary causes no reset.

The runner accepts one contiguous buffer per invocation and does not align frame-local and absolute indices. Split-run continuation is supported when the second buffer starts at the next absolute sample and carries the predecessor posterior/state/clocks. This remains independent of the frame-constant `reconstruction_forward.py` convention.
