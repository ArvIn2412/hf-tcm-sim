# REPRO-06 — REPRO-05 Euclidean integration

`JointReceiverConfig` receives the same finite-depth settings and preserves full-frame defaults. For finite mode, the receiver first completes its existing causal loop: pre-update estimate → predictions → selected Euclidean or squared-Euclidean rows → pseudo-posterior → innovation → next-symbol state. Only then does Viterbi consume those frozen rows. No estimator update is moved, repeated, or conditioned on finite-decoder decisions.

The full-frame `metric_rows`, `posterior_weights`, `estimator_pre`, `estimator_post`, `innovation`, and candidate predictions are identical between full-frame and finite-depth configs given the same observation and estimator settings. The Viterbi uses float costs and the explicitly stored metric profile. Delayed multipath remains rejected because the predictor still has no survivor-specific ISI history.

The result stores selected local survivor decision records, actual traceback mode/depth, the output path re-encoded from emitted information pairs, and bounded-buffer diagnostics. It never receives EvaluationTruth.
