# REPRO-06B multipath MLSE design

## Intent

Add an isolated, source-labeled REPRO receiver for Encoder A over the discrete complex-baseband integer-delay channel. It must score each candidate from the actual delayed waveform, decode on the resulting expanded trellis, and support full-frame and the REPRO-06 finite-depth convention. The first verified profile is a receiver-known static channel; unknown time-varying fading remains unavailable unless survivor-specific adaptation is independently established.

## Goals and constraints

- Preserve REPRO-02/03/04/05/06 numerical behavior, existing outputs, ADRs, and historical M5-M10 artifacts.
- Receiver API accepts only `ReceiverObservation` and explicit receiver configuration. Evaluation truth is supplied only to evaluation/plotting after the receiver call.
- Use 8-sample rectangular ZOH, integer sample delays, zero extension, and the REPRO-02 phase map.
- Include every receive sample exactly once, assigning the `D` channel-tail samples to the final trellis transition rather than treating them as another symbol.
- `D=3`: retain one previous phase; use a start sentinel plus the reachable augmented states. The independently derived reachable graph from initial `(0,0)` has 17 nodes and 68 edges (4 first-step edges plus 64 regular edges).
- Limit supported memory to at most two previous symbols (`D <= 16` samples, `q=ceil(D/8)<=2`) and validate the reachable expanded-state/edge cap before running. The unbounded state count is at most `4*8^q`; do not silently truncate delays.
- Unknown Rician multipath must be rejected by configuration until a causal survivor-specific channel estimator is specified and tested. Do not imply static CSI solves unknown fading.
- Preserve `paper_exact:false`, `receiver_enabled:false`; no Monte Carlo or REPRO-07.

## Approaches considered

1. **Extend REPRO-05 in place.** This reuses its output structures but risks changing the validated single-path predictor, estimator, and finite-depth behavior. Rejected for isolation.
2. **Build a separate multipath receiver and expanded-state Viterbi.** This keeps old contracts stable, permits branch predictions conditioned on the minimal symbol history, and allows finite-depth survivor records to retain their actual expanded transition. Recommended and selected for this execution.
3. **Use a memoryless effective gain or feed true channel histories to REPRO-05.** Both omit ISI or leak EvaluationTruth. Rejected as mathematically invalid.

## Model and state design

For sample `n=8k+i`, predict `sum_l h_l*x[n-d_l]`. The current candidate phase supplies samples whose source-symbol index is `k`; the augmented state's phase-history tuple supplies earlier source symbols; negative or beyond-frame source indices map to zero. For `q=ceil(D/8)`, an augmented node is `(encoder_state, previous_q_phase_indices)`, with an explicit initial sentinel containing unavailable phases. The transition selects one canonical Encoder A edge, emits its mapped phase, and shifts that phase into the history. This makes the delayed candidate prediction Markov on the expanded trellis. For `D=3`, one prior phase is sufficient and the old Encoder A state alone is insufficient because its two memory bits do not identify the previous ADR-002 phase.

Each symbol branch cost covers its 8 receive samples. The final transition also includes receive samples `[8F, 8F+D)`; zero extension predicts direct paths as zero there and delayed paths from the final payload/tail symbols where their source indices remain inside the transmitted frame. Thus the `F*8+D` observation is used once without inventing a symbol.

Static-known prediction uses complex gains in receiver config. Costs are either `sum(abs(residual)**2)` or its square root over that branch's complete observation subset, selected explicitly by `metric_profile`. Finite-depth decoding uses the same `eta`-transitions rule and flush semantics as REPRO-06. Decision records retain local expanded transitions; emitted bit decisions from overlapping tracebacks are not falsely reported as one continuous survivor path.

## Non-goals and open work

- No transmitter/channel/old-receiver mathematics changes, no GUI, no hidden-state truth access, no automatic equalizer, and no BER-SNR sweep.
- No adaptive multipath channel estimator in this implementation unless it receives a complete independent test suite. The current plan treats that profile as unsupported and therefore expects `REPRO_06B_MULTIPATH_PARTIAL` overall.
- This is a reconstructed project MLSE profile, not proof of paper-exact fidelity or physical HF propagation.

## Verification shape

Independent short-frame exhaustive enumeration compares full expanded-trellis Viterbi against direct waveform cost minimization. Hand-computed sample and branch-cost fixtures cover delay indexing and final tail. Tests also cover all 16 base edges, graph cardinality, D=0/D=3, arbitrary initial state, ties, full/finite agreement, eta=20 availability/flush, same-observation paired execution, truth isolation, deterministic noise, bounds, output hashes, and a 20,000-symbol channel-only receiver run. Existing suite, Ruff, and historical fingerprint checks remain required.
