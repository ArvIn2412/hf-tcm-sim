# M11b Demo Release QA Report

## Acceptance verdict

**DEMO_READY**, with stage 28 marked **PARTIAL BY DESIGN** for inferential statistics. The local UI and its required interactions were exercised in Microsoft Edge using Chromium DevTools Protocol. Actual screenshots at both requested viewports are saved under `docs/screenshots/`.

## Implemented and verified

- Preserved the existing standard-library localhost server and launch entrypoint.
- Added an explicit fixed F=32 defense preset: 64 fixed bits, exact per-policy initial states, approved anchored alpha/K/mu0/beta, 8 samples/symbol, fixed deterministic noise, zero RNG, and the same immutable 256-sample receive buffer for both receivers.
- Preserved the 4-symbol request as a fast regression fixture and added a named F=4 smoke preset.
- Added an automated source-backed rendering audit for all 28 stages; browser inspection clicked all 28 details with a real F=32 trace.
- Added the exact per-stage raw/derived provenance to live stage metadata; a real-browser stage detail check confirmed it renders from the stage catalog after restarting the updated server.
- Expanded the grouped Inspector to exact value, type, unit, allowed range, default, source, description, and read-only/demo-editable status. Unspecified ranges and defaults are not invented.
- Added all 18 Ukrainian defense steps, Previous/Next/Reset/Return controls, and live M9/M10 evidence sourced from archived metadata.
- Made every graph edge separately selectable and routed all 16 paths distinctly, including parallel/self-loop transitions. Graph, edge table, and selector synchronize.
- Confirmed selected-symbol controls at f=0,1,15,16,30,31. Tx/noise/Rx windows, observed IQ, predictions, metrics, posterior, estimator states, path, and error rows follow the selected symbol. Final-symbol next prediction is explicitly unavailable.
- Confirmed M9 DeltaBER −0.0011328125 and CI [−0.00322265625, 0.00068359375]. Confirmed M10 P1 DeltaBER −0.0003125 and CI [−0.00205126953125, 0.0014453125]. Both include zero; no significant-improvement claim is shown.
- Historical M5-M10 sources remain read-only. M5j per-symbol estimator history remains unavailable; aggregate records are not expanded into fabricated traces. M7b remains TRAIN_SELECTED_NOT_VALIDATED, not independent validation.
- Preserved `paper_exact:false`, `receiver_enabled:false`, reconstructed ADR-002, reconstructed ADR-005, evaluation-only ADR-016, and open SCI-02 / SCI-03 / SCI-METRIC-02.

## Browser QA

Viewport checks: 1366×768 and 1920×1080. Verified page load and GET metadata, explicit Run Demo action, F=32/256-sample trace, synchronized symbol controls, all 28 stage details, graph paths and edge table, parameter search, M5-M10 dashboard, presentation controls, and zero JavaScript console errors. Screenshots were recaptured from the actual Edge page after the provenance update.

Screenshots:

- `docs/screenshots/m11b-edge-1366x768.png`
- `docs/screenshots/m11b-edge-1920x1080.png`

## Offline and local-only checks

- Server binds only to `127.0.0.1`, `localhost`, or `::1`; launcher exposes `127.0.0.1`/`localhost`.
- No remote URLs, cloud APIs, or analytics references are used by the frontend.
- GET metadata/static routes do not call the receiver; only explicit POST `/api/demo` does.
- POST validates a JSON object, body size 1–8192 bytes, valid bit pattern, maximum 64 bits/32 symbols, finite numeric inputs, beta > 0, two K coordinates, and a known deterministic noise fixture.
- Missing archived data remains `UNAVAILABLE` with source notes and no synthesized trace.

## Stage and parameter audit

See [DEMO_PARAMETER_COVERAGE.md](DEMO_PARAMETER_COVERAGE.md) for all 28 stage rows and the full searchable 459-entry registry snapshot generated from the F=32 trace.

## Scientific and implementation boundary

No production receiver, encoder, metric, estimator, or Viterbi mathematics changed. No RNG or Monte Carlo was run. No new ADR was accepted. Paired confidence inference for one deterministic fixture remains unavailable by design.

## Known limitation

Stage 28 provides single-fixture BER/SER only. Correct paired inference requires archived independent study clusters. Historical per-symbol fields are unavailable where original saved schemas contain only aggregates.

## Final verification results

- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11b-final-temp -p no:cacheprovider`: 942 passed in 26.30s.
- `ruff check src tests`: all checks passed.
- `ruff format --check src tests`: 162 files already formatted.
- `node --check src/hf_tcm/studio/static/studio.js`: passed.
- HTTP health/metadata smoke: 28 stages, four states, 16 edges; GET reported `receiver_invoked:false`.
- Explicit F=32 POST: 32 symbols, 256 samples, `rng_used:false`, shared receive buffer, and two 32-edge conditional Viterbi paths.
- Historical M6b/M7b/M8 recovery/M9b/M10b manifests: 331 entries, zero mismatches. The full suite passed existing M5 hash regression tests.
