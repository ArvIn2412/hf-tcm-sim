# SCIENTIFIC-EXP-03A implementation plan

## Constraints

- Do not change historical Joint/B0/B1 algorithms, EXP-01B/02 records, or their manifests.
- Add the controlled frontend, metric decoders, runner, and GUI as separate versioned project modules/adapters.
- Preserve `paper_exact:false`; do not claim the article's 1.5 dB.
- No full confirmatory series. Only deterministic tests and bounded validation smoke runs.
- A/H must consume the same observation, frontend array, pilot constraints, trellis, eta=20, traceback, and evaluator mask.

## Work sequence

1. Freeze this design and derive exact interfaces from existing transmitter/channel/decoder contracts.
2. Add failing independent tests for phase/triple inverse mapping, hard-slicer tie handling, direct Euclidean/Hamming edge rows, and hard-constrained Viterbi equivalence with the existing no-constraint decoder.
3. Implement a new controlled metric decoder with hard edge masks, eta=20, the canonical state/edge order, common flush semantics, and a full trace suitable for auditing.
4. Add a pilot schedule builder. Validate fixed frame length, known-pair masks, phase-known positions after state flushing, initial-state handling, pilot overhead, and no payload/seed overlap.
5. Add a receiver-facing pilot frontend that accepts only `ReceiverObservation`, public delay support, pilot schedule, and declared noise variance. Select the ISI-free tail, estimate composite gain only on completed known pilot symbols, hold estimates causally, apply the common combiner, and produce immutable z/variance/update traces.
6. Add independent tests for static/noiseless reconstruction, exact clean-region indexing, sample-level causal noninterference, no truth in signatures/data structures, AWGN output noise scaling, pilot accounting, and Rician diagnostic behavior.
7. Add a paired bounded metric-isolation runner that builds a seeded transmitter with inserted known pilot pairs, calls one channel once, feeds one observation to one frontend, then sends identical output/constraints to A-E and A-H. Persist trial arrays, hashes, metrics, energy and runtime atomically; support stop/resume without duplicate trial IDs; independently recount saved records. Keep existing whole-receiver contrast in separate result namespace/labels.
8. Add only separately scoped browser UI controls/results for “Порівняння метрик” while retaining the existing Joint/B0/B1 screen. Validate request bounds, result provenance, status, and separation of contrast IDs.
9. Run bounded deterministic controls: AWGN no-equalizer; static [0,3] pilot/equalizer; Rician AR(1) pilot/equalizer; pilot/ISI/noise diagnostics. These are engineering validation records, not performance estimates or pilots used in 03B grid selection unless expressly identified as separate range-finding.
10. Freeze the independent 03B confirmatory protocol using existing EXP-01B/02 timing as planning priors plus measured 03A smoke runtime; specify pilot interval, grid-selection pilot, seed domains, sample-size/resource rule, stopping, exclusion, bootstrap and interpolation before any main trial.
11. Write the five 03A/03B reports, update only PLAN/NEXT_TASK after verification, run full tests/lints/Node/Edge, verify historical fingerprints and EXP-01B/02 integrity.
12. Build `HF_TCM_SIM_SCIENTIFIC_EXP_03A_PREPARATION_AUDIT.zip` with code, tests, smoke records, screenshots, reports, README, SHA-256 manifest; reopen and verify all archive entries and hashes.

## Acceptance evidence

- Mathematical unit tests plus direct scalar calculations independent of production helpers.
- Paired smoke trial shows identical observation/front-end hashes for A-E/A-H.
- Pilot frontend causality and information isolation checks pass.
- A/E and A/H both decode the same noiseless supported controls after pilot constraints.
- Static multipath clean-region residual ISI is zero within floating-point tolerance by construction; Rician mismatch/noise diagnostics are reported, not concealed.
- Resume test produces no duplicate pair/trial IDs.
- Edge screenshots and click/submit tests at 1366x768 and 1920x1080.
- Full pytest and scoped Ruff/Node; historical 694/694 and EXP-01B/02 verification unchanged.
- ZIP test, complete SHA-256 manifest recount, no excluded directories/secrets, no confirmatory output.
