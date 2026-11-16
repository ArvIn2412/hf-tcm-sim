# REPRO-08 implementation plan

Design: `docs/superpowers/specs/2026-11-09-repro08-research-design.md`.

## Constraints

- Reuse REPRO-02 transmitter, REPRO-03 channel, REPRO-04 B0, REPRO-06C joint and REPRO-07 storage/bootstrap; do not modify their mathematical behavior.
- New receiver/profile, experiment configs and all generated evidence belong to REPRO-08 and `outputs/repro08/`.
- Do not call noise variance Eb/N0. Retain `paper_exact:false`, `receiver_enabled:false`, historical REPRO-07 records, and M5-M10 fingerprints.
- Write failing tests before new B1 or statistics behavior; do not begin Phase B until Phase A controls are checked.

## Tasks

### 1. Lock source crosswalk and immutable baselines

- Hash available article manuscripts and channel notes; record version uncertainty and visually checked page/equation references.
- Snapshot REPRO-07 config/result manifest hashes; verify historic fingerprints.
- Tests: source paths/hash register and REPRO-07 config immutability check.

### 2. Validate Phase A signal controls

- Reuse existing paired trial and actual observation construction for identity/noise, static gain/phase, public static multipath, unknown-static, slow fading, and Rician AR(1).
- Add a same-bits/same-fading scaled-noise diagnostic to separate the noise contribution from ISI/phase mismatch; label cross-level common-noise dependence.
- Record hard phase decisions, phase error counts, decoded bit errors, and sample hashes in REPRO-08 output only.
- Tests: identity/AWGN mapping, hard phase mapping, explicit static phase mismatch, delay-3 ZOH indexing, and count denominators.
- Gate: if transmitter mapping/timing or AWGN scaling fails an independent check, stop statistical work and patch only that isolated defect with tests.

### 3. Implement channel-aware hard B1 for public static taps

- Create a new isolated receiver using the same `ReceiverObservation` contract, public static taps, zero-extension history, candidate phase waveforms with decision-feedback ISI, hard phase decisions, existing inverse-label contract, and existing finite-depth Hamming Viterbi.
- Restrict and validate supported delays; do not accept hidden truth or time-varying channel claims.
- Tests: hand-computed complex taps, phase rotation recovery with public CSI, delay-3 prediction, boundary/tail indexing, all eight phases, metric/Hamming hand fixtures, η=20 output length, truth isolation.

### 4. Define REPRO-08 paired runner and energy convention

- Define strict config with receiver arms A/B0/B1, noise grid or discrete normalized `gamma_b,dB`, channel profile, seed plan, trials, resource caps, and output paths.
- Reuse established modules for actual transmitter/channel/A/B0; pass one observation to B1 and hash-check all arms.
- Aggregate BER, information-pair SER, phase SER separately; ratio-of-sums and paired cluster bootstrap by trial.
- Tests: energy normalization independent calculation, paired hashes, seed separation, unequal lengths, bootstrap fixtures, failed/incomplete trial handling, resume/integrity.

### 5. Phase B bounded pilots and plots

- Run at least three fixed noise levels and 20 independent paired trials per point, F=256, eta=20, only for Phase A validated profiles.
- Run main adaptive-joint versus original B0 Rician comparison; run A/B1 public-known static profile only if its control passes. State that A/B1 does not identify an adaptive-fading metric-only effect.
- Plot actual BER/SER, CIs, paired differences, floor diagnostics, runtime and selected-trial traces with axis conventions in labels.

### 6. Bounded long-frame check and final verification

- Prepare a reproducible F=20,000 config and execute only within explicit wall/disk budget; checkpoint completed pairs and mark incomplete if needed.
- Run targeted independent tests, full pytest, scoped Ruff check/format, manifests, historical fingerprints, and plot XML/SVG validation.
- Write all required REPRO-08 reports and update PLAN/NEXT_TASK/BUILD_VERIFICATION from actual results only.

## Review focus

- Static phase offset outside the nominal detector: test B0's expected mismatch and B1's configured compensation.
- Delay tail off-by-one: test final symbol and extra channel samples separately.
- Sample energy vs physical Eb/N0: independent algebra test and explicit unit label.
- Noise scaled by 40 with same channel: verify B0 floor tracks channel impairment more than noise in this fixture.
- Bootstrap with sparse/zero errors: preserve ratio-of-sums and report limitations.
