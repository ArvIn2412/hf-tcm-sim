# REPRO-06C implementation plan

## Files and boundaries

- Add `adaptive_multipath_config.py`: strict public profile/prior/path/decoder config; no truth data.
- Add `survivor_channel_estimator.py`: immutable complex mean/covariance state, AR(1) prediction, complex measurement update, delayed symbol regressor builder.
- Add `adaptive_multipath_receiver.py`: per-expanded-node survivor bank, dynamic branch scoring, winner-only filter update, full/eta traceback and result dataclasses.
- Add `adaptive_multipath_io.py`, `adaptive_multipath_plots.py`, `adaptive_multipath_cli.py`: NPZ/JSON hashes, actual-data SVGs, explicit run/validate-only CLI.
- Add configs under `configs/repro06c/` and a deterministic paired reference runner under `scripts/`.
- Add estimator and receiver tests under `tests/repro/`.
- Create the seven required REPRO-06C docs and update PLAN/NEXT_TASK/BUILD_VERIFICATION after verification.

## Tasks (TDD order)

1. **Config and profile boundaries.** Write failing tests for unknown-static and Rician public-prior parsing, delay `[0,3]`, eta/full modes, rho bounds, finite numeric input, and refusal of known truth fields. Implement only the dataclasses/JSON conversion.
2. **Regressor and estimator scalar math.** First test delayed `X[n,l]`, D=3 start/history/tail, manual one/two complex Kalman/RLS steps, conjugation, Hermitian covariance, rank deficiency, and deterministic replay. Implement sample-level prediction/update primitives.
3. **Per-survivor adaptive decoder.** First test that each node starts from an independent filter state, branch rows use pre-update means, only each destination's winning edge is updated, ties are canonical, and metrics match a hand oracle. Implement winner-only state transfer.
4. **Finite-depth/full traceback.** First test exhaustive F≤4 path cost under fixed-coefficient state, exact decision records, eta=20 latency, flush depths, and ring bound. Implement streaming ring plus full reference mode without touching REPRO-06B.
5. **Receiver API/evaluation isolation.** Test `ReceiverObservation` only, truth-sidecar changes not affecting decisions, tail length, same observation hash as REPRO-04, BER/SER post-decode only, and repeatability. Implement `run_adaptive_multipath_receiver` and result contract.
6. **Artifacts, CLI, plots, profiles.** Test validation-only no execution, serialization and manifests, actual-data SVG count/XML, unknown-static/slow-Rician/Rician scenarios at F=32/256. Implement CLI, output configs, plots, and deterministic integration runner.
7. **Reference-size and final verification.** Run F=20000 finite-depth profile, record timing/array memory/output hashes; execute target/full pytest, Ruff, historical 694 fingerprints, and manifest verification. Only then update status rows and final docs.

## Interfaces

`run_adaptive_multipath_receiver(observation: ReceiverObservation, config: AdaptiveMultipathReceiverConfig) -> AdaptiveMultipathReceiverResult` is the new API. It never accepts `ChannelResult`. `AdaptivePathConfig` gives sample delay plus either explicit unknown-static prior or public Rician power/K/LOS settings. `AdaptiveMultipathReceiverConfig` carries rho, observation-noise variance, metric profile, eta/full decoder policy, frame symbols, initial TCM state and trace level. All arrays in result are numeric; complex arrays serialize to NPZ, JSON stores shape/dtype/hash/config/summary only.

## Review focus

- The complex model is `x.T @ h`; the estimator uses `z=conj(x)` and `zᴴ h`. Tests must fail if conjugation is reversed.
- AR(1) transition is sample-level; first sample uses stationary prior directly, later samples apply rho/Q once per sample, including all three channel-tail samples.
- Branch metrics are frozen before any measurement update for that symbol; only winning predecessor per destination receives updates.
- A node estimator bank remains state-indexed and is copied on winner transfer; no shared mutable covariance arrays.
- Finite decision records can be local to overlapping windows; do not misrepresent the stitched bit stream as a single continuous survivor.
- Full-frame F=20000 is not required; finite eta=20 F=20000 is.
- Rician generator seeds/coefficients/truth never enter the receiver config or function.
