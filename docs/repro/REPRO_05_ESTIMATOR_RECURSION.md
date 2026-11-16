# REPRO-05 — estimator recursion and causality

The paper's A(1) shows a recursion for fluctuating quadrature estimates and a posterior-weighted innovation, but does not fully specify initial values, gain constants, latent-state meanings, or the mapping into the REPRO-03 complex sample convention. The implemented complex adaptation is therefore `adaptive_project_v1`, a documented project reconstruction:

\[
\epsilon_k=\sum_{e=0}^{15}w_{e,k}\,\frac{1}{|W_k|}\sum_{i\in W_k}(y_i-\hat y_{e,i}),
\quad s_{k+1}=\alpha' s_k+\tilde K\epsilon_k,
\quad h_k=h_0+s_k.
\]

Predictions, metrics, and weights for symbol k use only `h_k` (the pre-update estimate). The update is computed after those values and is used at k+1. The JSON config stores initial state, `mu0`, alpha, K, beta, and estimator policy. Under `channel_mode=nominal`, `h0=mu0`. Under explicitly receiver-known static gain, the configured gain is the baseline; the additive state remains the adaptation component.

`frozen` requires `alpha_prime=1` and `k_tilde=0`. `adaptive_project_v1` permits finite alpha/K and starts from the explicit configured complex state. No parameter is fitted from reference bits, `EvaluationTruth`, or true coefficients. Tests hand-calculate the weighted innovation and one-step update, and check that a current candidate prediction equals the pre-update value even when the update is nonzero.

This equation is not labeled exact article A(1): the project innovation is a complex residual average over candidate edges and sample windows, which is a reconstruction choice.
