# REPRO-07 Paired Experiment Design

Build an isolated runner around the existing REPRO-02 transmitter, REPRO-03 channel, REPRO-04 Hamming receiver, and REPRO-06C adaptive multipath receiver. Each trial creates one transmitter and one channel realization, passes the same `ReceiverObservation` to both arms, and evaluates both only afterward. The experiment runner owns seed derivation, immutable per-trial checkpoint records, resume validation, ratio-of-sums aggregates, paired trial-cluster bootstrap intervals, resource limits, and measured-data SVG plots.

The initial executable pilot is a project-defined two-path Rician AR(1) sample-domain AWGN experiment: three explicitly recorded complex-noise variances, at least 20 independent paired trials per point, F=256, and eta=20. It is exploratory. It is not a physical Eb/N0 curve or a paper-exact reproduction. Article-oriented mode is accepted only when it uses parameters already verified in REPRO-01; unspecified channel/noise values remain user/project extensions.

Non-goals: changing transmitter/channel/receiver mathematics, running a long-frame grid automatically, Monte Carlo beyond the bounded pilot, GUI work, or claiming algorithmic superiority.

Implementation uses one strict JSON config, domain-separated deterministic seeds per grid point/trial/stream, serialized sequential execution, atomic completed-trial records, hash validation before resume, and no raw per-trial arrays in summary-only mode. Failed/incomplete trials are excluded from aggregation. BER/SER use pooled integer counts; uncertainty resamples whole paired trials and recomputes ratios of sums.
