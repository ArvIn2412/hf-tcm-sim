# REPRO-06C design — survivor-specific adaptive multipath

## Intent and scope

Add a new adaptive Encoder A receiver beside, not inside, REPRO-06B's known-static MLSE. It receives `ReceiverObservation` and a public configuration, performs ISI-aware Euclidean branch scoring on the existing augmented trellis, keeps a separate channel-estimator state for every live expanded-state survivor, and supports full-frame plus finite-depth eta decoding. It must never access `EvaluationTruth`, transmitter bits, or channel realizations.

## Existing behavior and constraints

REPRO-06B uses 8PSK, 8 ZOH samples/symbol, delay-derived phase history, `[0,3]` reference delays, and a generic expanded Viterbi. Its static-known path predictor and branch metrics remain unchanged. REPRO-03 Rician AR(1) coefficients are generated at every receive sample: the diffuse part follows `g[n]=rho*g[n-1]+sqrt(1-rho^2)*v[n]`, with stationary `CN(0,1)` initialization at sample zero and a fixed LOS mean. REPRO-03's public observation excludes actual coefficients/noise/truth.

## Approaches considered

1. **One global channel estimator.** Lowest compute cost, but competing delayed symbol histories need different regressors and residuals; a global update violates survivor conditioning. Rejected.
2. **Per-survivor state-conditioned RLS/Kalman bank.** Keep one coefficient mean/covariance per reachable expanded node, score all outgoing transitions from that node's pre-update state, choose one predecessor per destination, then update only the winning branch and install its post-update state. This matches the requested survivor-specific processing and bounds filter state by reachable nodes. **Selected.**
3. **Particle/list path bank or exhaustive joint channel/path search.** Could retain more hypotheses but grows rapidly and changes the decoder contract/complexity. Deferred.

## Mathematical convention selected

Use complex observation model `y[n]=x[n]^T h[n]+w[n]`, where `x_l[n]=x[n-d_l]`. Store `h` as a column and set `z=conj(x)`, giving `y=z^H h+w`. For each branch, use its predecessor's prior mean trajectory and delayed transmitted regressors to compute `sum_n |y[n]-x[n]^T h_prior[n]|^2` (or the explicit Euclidean-root profile). Do not use current-symbol observations to form any branch metric.

After the winning incoming edge is selected for a destination node, update a copy of its source estimator state sample-by-sample using that edge's regressors. Complex Kalman/RLS update:

`h_pred = m + rho*(h-m)`; `P_pred = rho^2 P + Q`; `e = y - zᴴ h_pred`; `S = zᴴ P_pred z + R`; `g = P_pred z/S`; `h_post = h_pred + g e`; `P_post = P_pred - g zᴴ P_pred`.

For Rician AR(1), public `m_l=sqrt(P_l K_l/(K_l+1))*exp(j phi_l)`, stationary diffuse covariance `P_l/(K_l+1)`, and `Q_l=(1-rho^2)P_l/(K_l+1)`. These describe a public prior/model, not a realization. For unknown static CSI set `rho=1`, `Q=0`, public configured prior, and a configurable forgetting factor; no true gain is used. Covariance is Hermitianized and singular/zero-information updates are skipped only when the innovation is within tolerance; otherwise they fail with diagnostics.

The AR(1) dynamics are applied sample-by-sample exactly as REPRO-03 defines them. Branch likelihood uses the causal predicted mean only; it does not fold estimator covariance into a Gaussian branch likelihood. Survivor processing is therefore a project-defined approximate joint search, not exact global ML over channel trajectories and not a reconstruction of article A(1).

## Boundary, trellis, and decoder rules

Reuse REPRO-06B's augmented nodes/edges. Each node's live survivor owns one `h,P` pair. For delay `[0,3]`, the graph remains 17 states/68 transitions. Each symbol owns its eight receive samples; the last transition also owns the three zero-extension tail samples. The filter processes each sample once for each destination survivor's selected branch; no extra symbol is created. Finite-depth decisions use an eta-sized predecessor ring and report regular latency plus actual flush depth. Output arrays scale with frame length; the live survivor bank and ring scale with `S*L^2 + eta*S*L^2`, not all competing full paths.

## Profiles

- Existing known-static REPRO-06B remains `known_public_static`.
- New unknown-static CSI uses `psp_unknown_static_rls_v1`.
- New sample-level Rician AR(1) uses `psp_rician_ar1_kalman_v1`, with named `slow_fading_rician_ar1` and `rician_ar1` modes and explicit public per-path power/K/LOS phase/correlation.

No pilots or payload changes are introduced. Evaluation references and `EvaluationTruth` are accepted only by post-decode evaluation/plot adapters.

## Acceptance gates and limitations

Independent hand-computed complex updates, rank-deficient regressors, branch-before-update causality, survivor state isolation, small-frame exhaustive/local equations, D=3 channel prediction/tail, eta=20 latency/flush, truth isolation, deterministic slow/fast AR(1) integrations, same-observation Hamming comparison, and F=20000 finite-depth execution are required. No BER-vs-SNR study is allowed. Rician/AR(1) remains an REPRO-03 approximation, not paper-exact HF propagation. Flags remain `paper_exact:false`, `receiver_enabled:false`; SCI issues remain unchanged.
