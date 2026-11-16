# SCIENTIFIC-EXP-03A — controlled metric comparison design

**Status:** approved design, implementation in progress  
**Date:** 2026-11-11  
**Decision:** use option 2, a shared pilot frontend and equalizer for the metric-isolation experiment. Preserve option 1 as an AWGN identity-frontend control. Keep oracle CSI as a separately labeled diagnostic. Do not run the confirmatory SCIENTIFIC-EXP-03B series in this phase.

## Purpose and scope

This phase adds an isolated experimental path for comparing squared-Euclidean and Hamming branch metrics under the same received samples and the same receiver-side preprocessing. It does not replace or modify the existing adaptive Joint, Separate B0, or static-channel B1 receivers. The existing full-receiver comparison remains a distinct contrast and its results must not be pooled with the metric-isolation results.

The new components are versioned project adapters: a training-symbol schedule, a causal pilot estimator, a common ISI-avoiding/equalizing frontend, constrained finite-depth Viterbi decoding, a paired bounded runner, and a separate Scientific Workspace view. They consume `ReceiverObservation`; evaluator-only channel truth may be read only after both decoders finish to quantify estimation error and residual distortion.

## Common channel observation model

For integer path delays `d_p` in samples, the existing channel produces

`y[n] = sum_p h_p[n] x[n-d_p] + w[n]`,

with zero extension outside the transmitted waveform. The existing transmitter uses rectangular ZOH with `S=8` samples per coded symbol. Let `D=max_p d_p`, with `0 <= D < S`. At local sample positions `r=D,...,S-1` of symbol `k`, every delayed source sample belongs to symbol `k`; hence

`y[kS+r] = g[kS+r] s_k + w[kS+r]`, where `g[n]=sum_p h_p[n]`.

The frontend discards the first `D` samples of each symbol. This is an exact ISI-avoidance operation for the supported integer-delay/ZOH model, not a reconstruction from truth and not a general equalizer for arbitrary pulse shapes or fractional delays. The remaining `L=S-D` samples are combined with the latest causal pilot estimate `g_hat`:

`z_k = sum_{r=D}^{S-1} conj(g_hat) y[kS+r] / (L |g_hat|^2)`.

If no valid causal pilot estimate exists, the run is invalid (except the explicit AWGN identity-frontend control). Deep fades below a frozen denominator threshold are recorded as erasures/failures under a fixed rule, never silently imputed.

For a static channel and an accurate estimate, `E[z_k|s_k] = s_k` and the output noise is circular Gaussian with variance `sigma_c^2/(L |g_hat|^2)`. The pilot estimate is computed from the same `L` clean samples of a known coded pilot symbol as

`g_hat = sum conj(s_p) y_p / (L |s_p|^2)`.

The estimator updates only after the complete pilot symbol is observed. Until then it uses the prior estimate. Pilot positions and coded pilot phases are known from the frozen input-pair schedule, initial encoder state, and the Encoder A transition rule; the estimator never receives actual channel coefficients or `EvaluationTruth`.

In Rician AR(1), this scalar composite-gain estimate is held causally between pilots. The channel is time-varying within and between symbols. The resulting normalized output has pilot staleness, multiplicative gain/phase error, and potentially temporally correlated distortion. These are measured by an evaluator-only audit against channel truth, and reported alongside BER. They are not described as AWGN. The metric experiment is valid as a same-observation comparison under this explicit receiver model, but its result is conditional on the chosen pilot interval and equalizer. A failed tracking diagnostic blocks the claim that the frontend supplies a sufficiently faithful common symbol observation for Rician.

## Pilot schedule and trellis treatment

Pilots are known input pairs inserted into the encoded sequence at a frozen periodic schedule. All pilot symbols count toward transmitted duration and energy; their two input bits per transition are excluded from payload BER/SER denominators and are reported as training overhead. Payload bit rate is reported both as the nominal 2 information bits per coded symbol and as the pilot-adjusted useful-bit fraction.

At the frame start the initial encoder state is known, so initial pilot phases are known. At an interior pilot burst following unknown payload, the first two known input pairs flush the two-bit encoder state. Their output phases are not used to estimate the channel. The third and subsequent pilot phases in the burst are determined by the known pilot sequence and state convergence. A common mask constrains both decoders to the same known input-pair edges at pilot positions. The metric value at a constrained pilot transition is set to zero for each allowed edge so the training waveform does not create different branch-cost evidence for the two decoders. Both algorithms still process the same frame, transition count, trellis, traceback depth, and frame-end policy.

The pilot interval and burst length are design parameters. They must be frozen before confirmatory runs and included in energy, time, payload-rate, and seed manifests. Range-finding runs may choose a pilot interval only; they are excluded from confirmatory inference.

## The two metric arms

For payload symbol `k`, the common frontend yields the same complex `z_k` for both arms. The phase mapping is the existing project ADR-002 mapping: coded triple `(c2,c1,c0)` maps to phase index `4*c2+2*c1+c0`. For each of the 16 canonical Encoder A edges `e`:

* A-E uses `m_E(k,e)=|z_k - s(c(e))|^2`.
* A-H first makes one candidate-independent nearest-phase hard decision `q_hat_k = argmin_q |z_k-s(q)|^2`, maps that phase back through the inverse three-bit labeling to `b_hat_k`, then uses `m_H(k,e)=d_H(b_hat_k,c(e))`.

Tie-breaking for a point exactly equidistant from phase points is fixed to the lowest phase index and tested. Hard slicing occurs once per symbol, never once per candidate edge. The branch-row shape/order is checked against `transition_table()`. At AWGN control, `z_k` is obtained from the direct eight-sample symbol average with no channel equalizer; A-E/A-H share that output.

The Hamming cost discards reliability and the Euclidean cost retains distance. In time-varying fading, equalizer noise variance can differ by symbol and the held-gain mismatch can correlate symbol errors. The primary A-E comparator remains the specified unweighted squared distance on the common normalized `z_k`, because that is the frozen metric contrast. A secondary evaluator diagnostic computes the per-symbol conditional output-noise variance and gain residual; it does not reweight either decoder. Claims are conditional on this metric definition and do not claim that unweighted squared distance is the exact likelihood under time-varying Rician mismatch.

The decoder uses the existing canonical four-state trellis, initial state `(0,0)`, finite-depth `eta=20`, deterministic edge/state tie policy, and the existing frame-end flush semantics. The new constrained decoder must reproduce the existing decoder exactly when no pilot constraints are supplied. Pilot constraints are hard edge masks rather than a large finite penalty. No pilot or channel truth is passed as a metric observation.

## Causal channel estimation and equalizer validity

The practical estimator knows only the public schedule, known pilot phases, public path-delay support, and received samples. It estimates the composite clean-region gain `g=sum(h_p)`; separate path coefficients are not identifiable from the ISI-free tail alone. Therefore the practical frontend does not claim to estimate individual taps. Pilot/equalizer diagnostics, calculated after decoding, include:

* pilot update timestamps and the age of the held estimate;
* composite-gain bias/RMSE against the evaluator-only `sum(h_p)`;
* equalized symbol residual against the transmitted symbol (evaluation only);
* pilot overhead in symbols, samples, bits, and measured transmit energy;
* empirical output noise variance on a dedicated AWGN control;
* Rician per-symbol conditional noise variance, residual gain, lag correlation, and BER by pilot age;
* count and location of deep-fade erasures.

The clean-region theorem guarantees no previous-symbol ISI only for the stated discrete channel and integer delays. Estimation error is not ISI. Rician gain variation inside one symbol is not removed by a held scalar estimate and is reported as residual multiplicative distortion. A diagnostic oracle mode may substitute the evaluator-only composite gain for the estimate to establish an upper-bound frontend control; it is separately named, excluded from practical curves, and never passed to A-E/A-H as a production receive path.

## Separate whole-receiver contrast

The B contrast remains the existing adaptive Joint Euclidean receiver versus Separate B0 Hamming receiver, and B1 only where the public static channel contract supports it. It retains current receiver channel-information asymmetries and adaptive/full-system processing. B results are stored with `contrast_id=whole_receiver`; A results use `contrast_id=metric_isolation`. The GUI and output schema must reject plots or aggregates that mix contrast IDs.

## Experimental execution and inference

This phase permits only deterministic tests and bounded correctness/estimation smoke checks. It does not execute a large BER sweep or confirmatory series. A separate, frozen SCIENTIFIC-EXP-03B protocol specifies pilot schedule, channel grid, energy grid, trial counts, seed domains, stop rules, interpolation, bootstrap cluster unit, runtime/memory budget, and exclusion/failure rules. Pilot/range-finding records use a disjoint seed namespace and cannot enter confirmatory aggregates.

Every paired record stores the same observation SHA-256 for A-E/A-H, common frontend-output hash, pilot-schedule hash, decoder settings, payload/reference and decoded bits, BER/SER/FER counts, energy/overhead, time, channel-profile configuration, and provenance. An independent recount reconstructs all bit/pair/frame counts from saved arrays. Cluster bootstrap resamples independent paired trial IDs, not bits.

## GUI and non-goals

Scientific Workspace gains a distinct “Порівняння метрик” mode for A-E/A-H and keeps “Порівняння способів приймання” for Joint/B0/B1. The screen exposes channel, pilot schedule/estimation mode, frame length, seeds/trials, energy, metrics, estimation diagnostics, and explicit distinction between practical pilot estimates and oracle diagnostics. It must not imply that a smoke run is a BER curve or that an oracle result is practical performance.

This phase does not modify old receiver mathematics, old EXP-01B/02 records, historical fingerprints, article metadata, or `paper_exact:false`; it does not prove article exactness or the cited 1.5 dB result. No SCIENTIFIC-EXP-03B confirmatory execution occurs automatically.

## Acceptance gates

1. Independent mapping and metric tests validate all eight phases and all canonical edges.
2. Shared pilot outputs are byte-identical across A-E/A-H; no evaluator truth is in receiver-call signatures.
3. Causality tests prove samples after time `t` cannot change estimates/outputs at or before `t`.
4. Noiseless AWGN and supported static multipath recover a deterministic payload under both metrics with the same constrained trellis.
5. Rician smoke reports estimation and residual diagnostics; it does not claim tracking adequacy without predeclared tolerance checks.
6. Paired bounded runner writes resumable, integrity-checked records and independently recounts them.
7. GUI allows selecting and running A and B contrasts independently and displays their outputs separately.
8. Full pytest, scoped lint/format, Node, Edge QA, historical 694/694 verification, and EXP-01B/02 integrity checks pass.
9. Frozen 03B protocol and verified audit ZIP are present before marking preparation complete.
