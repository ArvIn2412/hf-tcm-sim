# REPRO-05 joint receiver design

## Intent

Add a second isolated Encoder A receiver which scores each of the 16 TCM edges directly against the received complex samples, recursively updates a channel estimate causally, and runs a float-metric four-state Viterbi. It must consume the same typed `ReceiverObservation` as REPRO-04 and cannot access channel truth or transmitter references.

## Goals and non-goals

- Implement both distance profiles, explicitly named Euclidean and squared Euclidean; default to the REPRO-01 project reconstruction `squared_euclidean`.
- Use REPRO-02 Encoder A and the reconstructed ADR-002 phase table.
- Record per-symbol 16 candidate sample predictions, pre-update estimator state, metrics, posterior weights, innovation, post-update estimate, and Viterbi evidence.
- Include frozen nominal and adaptive posterior-weighted single-path estimator profiles.
- Provide finite reference runs, independent tests, serialization/CLI, SVG traces, and a fair same-observation integration fixture with REPRO-04.
- Do not implement article-exact A(1)/(2), passband channel recovery, HMM forward-backward, time-varying channel equalization, multipath ISI inference, eta=20 traceback, or BER/SNR Monte Carlo.

## Approaches considered

1. **One shared causal channel estimate per symbol (chosen).** Form all edge predictions from the current pre-update estimate; calculate costs and a soft edge distribution; update one estimate from the posterior-weighted mean residual; then continue. This matches the requested REPRO architecture, gives tractable O(F·16·8) work and makes causality auditable. Its estimator and flat 16-edge pseudo-prior are explicitly project reconstructions.
2. **Survivor-specific estimator banks.** Carry separate channel states for trellis paths and merge/select them during Viterbi. This can model path/estimator coupling more fully but changes the inference state and grows memory/runtime; it requires a distinct validated algorithm contract and is out of REPRO-05 scope.
3. **Hard or post-Viterbi adaptation.** Demodulate first or update from decoded symbols. This removes the defining soft joint branch scoring or introduces future-decision feedback into earlier metric rows, so it is rejected.

## Mathematical project profile

For symbol k, phase label b(e) follows the versioned ADR-002 project table. For declared memoryless single-path complex gain `h_k=mu0+s_k`, transmit sample hypothesis `x_e[i]=A exp(j(phi0+b(e)π/4))` is held for the selected ZOH sample range, and `yhat_e[i]=h_k x_e[i]`. The metric row is either `sqrt(sum_i |y[i]-yhat_e[i]|²)` or the project-default `sum_i |y[i]-yhat_e[i]|²`.

The soft edge weights are the stable normalized values proportional to `exp(-beta*m_e)` under an explicit flat project prior. Define the per-symbol complex innovation `epsilon_k = sum_e w_e * mean_i(y[i]-yhat_e[i])`. Adaptive reconstruction: `s[k+1]=alpha_prime*s[k]+k_tilde*epsilon_k`; `h[k+1]=mu0+s[k+1]`. All 8 samples and posterior are from the same symbol; only the pre-update estimate contributes to that symbol's metric. This is not a literal source-transcribed complex equation: source A(1) updates real quadrature coefficients using source-defined-but-unidentified latent states; REPRO-05 specifies a complex single-path project adapter and records units/parameters.

Conditional Viterbi sums selected branch costs across the Encoder A trellis. It uses full-frame traceback, configured initial state, free final state or explicit `zero_tail_2`; no eta=20 claim.

## Channel and data boundaries

- Supported: identity and explicit receiver-known static complex coefficient; adaptive single-path complex gain with no genie CSI.
- Single-path Rician is an estimator smoke/diagnostic profile; no perfect-recovery guarantee.
- Public profiles whose ID declares multipath are rejected with `MULTIPATH_JOINT_RECEIVER_PARTIAL`. A symbol-local predictor cannot model delayed ISI; do not mask that mismatch.
- Only exact `ReceiverObservation` is accepted. A public profile ID, received buffer, public timing and declared config are receiver-visible. Evaluation truth is separate.
- `paper_exact:false`, `receiver_enabled:false`; mapping is reconstructed; A(2) is selected project interpretation; SCI-02/SCI-03/SCI-METRIC-02 remain open.

## Persistence and verification

Use a strict versioned config, compressed NPZ arrays, JSON summary/manifest with source/mapping/profile IDs and SHA-256, `outputs/repro05/`, and read-only plots from actual result arrays. Tests include independent scalar metric/recursion/Viterbi oracles, causality, extreme softmax, truth isolation, multipath rejection, same-observation REPRO-04 pairing, and deterministic end-to-end identity.
