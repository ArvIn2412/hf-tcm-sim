# REPRO-03 implementation plan

## Scope and decisions

Implement a project-defined, discrete complex-baseband channel in the isolated `hf_tcm.repro` package. Input is an actual REPRO-02 `TransmitterResult`; no M5-M11 code is reused or altered. Equation structure follows the REPRO-01 multi-ray requirement `y[n]=Σ_l h_l[n]x[n-d_l]`; physical delays are nonnegative integer samples only, out-of-frame input is zero, and output includes a declared delayed tail. The source does not provide physical path/SNR parameters, so example channel values are explicitly project reconstruction settings.

Use existing Rician arithmetic only through its documented helper contract (unit average diffuse power, K ratio, static or explicitly approximate stationary AR(1)); use independent PCG64 streams per path and a separate sample-domain complex AWGN stream. Do not call the old multipath wrapper because it accepts one shared RNG and has its own output alignment. Do not implement source A(9)-(10) as complex AWGN; leave correlated passband quadrature disturbance unavailable pending its time/carrier mapping. Expose no Eb/N0 conversion in this phase.

Represent `ReceiverObservation` as received samples plus timing and a deliberately small public-profile record. Keep coefficients, generated noise, per-path contributions/delays, and transmitter truth in a separate `EvaluationTruth`. Persist observation and truth in separate NPZ files and hash observation arrays as a shared future receiver input.

## Implementation steps (TDD)

1. Add strict config/path validation and tests for profiles, units, seeds, delay and noise semantics.
2. Add independent scalar reference tests for zero-extension, complex gain and two-path sample alignment; then implement path contributions.
3. Add Rician component/power/correlation/reproducibility tests and independent noise-stream tests; then build isolated per-path seed streams.
4. Add AWGN mean/variance/quadrature/correlation tests and zero-noise exactness; then implement explicit complex variance convention.
5. Add truth-separation and observation-hash tests; then construct immutable result contracts.
6. Add serialization round trip/hash validation and channel-only CLI tests, including strict `outputs/repro03/` output boundary.
7. Add actual-data SVG plot tests, then 20,000-symbol reference execution and array-storage/time measurement.
8. Run targeted tests, complete pytest, Ruff check/format, and 694 historical fingerprint verification; only then update PLAN/NEXT_TASK/BUILD_VERIFICATION.

## Explicit non-goals

No receiver, BER/SER, Monte Carlo, Eb/N0 calibration, fractional-delay interpolation, RF carrier, GUI integration, or M5-M11 changes. Correlated quadrature noise from A(9)-(10) remains unimplemented in this complex-envelope channel until the source-to-baseband transformation is defined.
