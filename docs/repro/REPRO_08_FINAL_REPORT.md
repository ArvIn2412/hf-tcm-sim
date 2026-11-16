# REPRO-08 final report

## Verdict

- Overall: **REPRO_08_SCIENTIFIC_REPRODUCTION_PARTIAL**.
- ARTICLE_CROSSWALK: **ARTICLE_CROSSWALK_PARTIAL** (requested v7 source file absent; source equations/parameters remain unresolved).
- RECEIVER_BASELINE: **RECEIVER_BASELINE_VERIFIED** for the tested project implementations and immutable REPRO-07 counts.
- SNR_NORMALIZATION: **SNR_NORMALIZATION_PARTIAL** (dimensionless discrete convention validated; physical Eb/N0 unavailable).
- PAIRED_MONTE_CARLO: **PAIRED_MONTE_CARLO_PARTIAL** (real completed bounded pilots; no confirmatory/article grid).
- BER_SER_CURVES: **BER_SER_CURVES_PARTIAL** (actual pilot points and plots exist for explicitly project-defined profiles).
- ENERGY_GAIN: **ENERGY_GAIN_NOT_ESTIMABLE**.
- ARTICLE_REPRODUCTION: **INSUFFICIENT_DATA**.
- TRUTH_ISOLATION: **TRUTH_ISOLATION_READY** for tested receiver contracts, including B1.

## Answers to the research questions

1. **Why was REPRO-07 B0 BER about 0.145?** It was a high hard-phase-decision error regime: phase SER was about 0.29-0.30. B0 uses a nominal phase reference and does not estimate time-varying complex gain or cancel the delayed `[0,3]` multipath. A static 0.9 rad phase-rotation control independently makes all hard phase-symbol decisions wrong. The evidence supports channel/phase/ISI mismatch and hard-decision propagation as the explanation class; it does not identify a unique quantitative causal split.
2. **Implementation/method errors?** The baseline audit found a method mismatch for using B0 as a competitive receiver on the REPRO-07 Rician multipath channel: B0 lacks channel awareness. Identity/noiseless and nominal AWGN controls pass; hard decision errors precede Hamming Viterbi in the failure controls. No confirmed implementation defect in REPRO-04 was established. B0 was not altered.
3. **Which algorithms are compared?** Three labels are kept separate: A Joint adaptive REPRO-06C; B0 original REPRO-04; B1 new public-static-tap hard/decision-feedback front end followed by Hamming eta=20. Static Phase B has both a REPRO-06B known-static Euclidean control and an exploratory follow-up replaying the same observations through REPRO-06C adaptive PSP with public static prior against B1. The latter is a static public-channel comparison, not unknown Rician fading or article reproduction.
4. **Is the baseline fair?** Paired observations are fair (same hash). The Rician A/B0 comparison is a comparison of complete algorithms under a mismatch that B0 cannot compensate, not a metric-only comparison. Static known-CSI REPRO-06B vs B1 is the controlled common-channel-information comparison. B1 does not support unknown time-varying fading.
5. **Horizontal-axis meaning?** `gamma_b,d = 10log10((8 A^2 / 2)/sigma_c^2)`, a discrete ZOH energy-per-information-bit to complex per-sample noise-variance ratio. It is explicitly not physical Eb/N0.
6. **Measured results?** Frozen REPRO-07 and new static pilot values appear in `REPRO_08_STATISTICAL_RESULTS.md`. New static pilot v2 completed 60/60 paired trials; B0 BER was 0.01797, 0.04697, 0.11973; B1 was 0.000391, 0.005664, 0.048145; known-static Euclidean arm observed zero errors at all three points.
7. **Uncertainty?** REPRO-07 intervals are trial-cluster bootstrap intervals from 20 trials per point. Static v2 uses 5,000 trial-cluster resamples and 20 trials per point. Zero-error known-CSI bootstrap intervals degenerate and do not provide valid rare-event upper bounds. These are bounded pilots.
8. **Energy gain?** Not estimable: no physical Eb/N0 axis and no prespecified article-consistent decoded BER target. The article's p*=0.05 is not assumed to be decoded payload BER.
9. **Are 1.5 dB confirmed?** No. It remains a historical article claim only.
10. **Source fidelity?** Rate 2/3, 8PSK, phase increment pi/4, 8 samples/signal element, eta=20, and the printed formulas/claim are documented from available article pages. Exact v7 is absent; phase mapping, A(2) metric norm/square, N* unit/denominator, p* event, channel stochastic parameters, SNR normalization, and traceback indexing include project reconstructions or unresolved choices.
11. **Remaining limitations?** No exact v7 source; no established physical Eb/N0; B1 limited to sub-symbol public static taps and previous hard-symbol decision feedback; no adaptive B1 for unknown fading; no confirmatory long-frame series; no article-level gain determination. Historical fidelity flags are unchanged and `paper_exact:false`.

## Verification and integrity

REPRO-08 contains new target tests for B1 and discrete energy; all pilot observations have matching receiver hashes. A bounded F=20,000 Rician pair completed in 147.804 s under a 300 s budget. Full pytest, scoped Ruff/format, manifests, and the historical M5-M10 verifier are recorded in `docs/BUILD_VERIFICATION.md` after final verification.

REPRO-09 was not started.
