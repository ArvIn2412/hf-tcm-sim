# REPRO-05 — posterior weights and causal order

For each step, the 16 raw branch metrics are transformed with the explicitly configured nonnegative `beta`:

\[
w_{e,k}=\frac{\exp[-\beta(m_{e,k}-m_{min,k})]}{\sum_q\exp[-\beta(m_{q,k}-m_{min,k})]}.
\]

Subtracting the minimum is a stable log-sum-exp-equivalent normalization for the flat project prior. The weights are finite, nonnegative, sum to one within floating-point tolerance, and preserve all 16 edge entries. Extreme underflow to exact zero for negligible candidates is allowed; a degenerate denominator is rejected.

These are **soft edge pseudo-posterior weights**. The implementation does not perform HMM forward-backward marginalization, state transition priors, or Baum-Welch, and it does not call them exact hidden-channel or TCM-state posteriors.

The processing order for every symbol is: pre-update estimate → candidate waveforms → raw metrics → normalized weights → posterior-weighted residual innovation → post-update estimate. The update affects only the next symbol. The Viterbi consumes the branch metric matrix directly and does not consume hard phase decisions or the pseudo-posterior as a substitute cost.
