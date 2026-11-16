# REPRO-05 — Euclidean metrics

The implementation keeps two selectable profiles distinct:

\[
d_E(e,k)=\sqrt{\sum_{i\in W_k}|y_i-\hat y_{e,i}|^2},\qquad
d_{E2}(e,k)=\sum_{i\in W_k}|y_i-\hat y_{e,i}|^2.
\]

`metric_profile` is either `euclidean` or `squared_euclidean`; the reproducible default is the REPRO-01 project choice `squared_euclidean`. `W_k` is the configured sample subset of symbol k (8 samples at offset zero, otherwise the declared suffix). The branch row has shape `(F,16)`, with canonical REPRO-02 edge ordering. The Viterbi path cost is the sum of the selected branch values under the same selected profile.

The source's A(2) does not visibly settle square, modulus/norm, or its aggregation semantics. Therefore neither implementation is represented as an author-confirmed exact transcription. A squared residual is a project interpretation. Euclidean and squared-Euclidean path ordering need not be assumed equivalent after accumulation and must be treated as separate configurations.

The numerical kernel rejects non-finite operands/results and negative/non-supported settings. It scales residuals before squaring to reduce intermediate overflow; if the requested squared result itself is outside float64 range, it rejects the result. Independent hand fixtures check values 3 and 2.25 for squared distances and their square roots for distances.
