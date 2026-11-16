# SCIENTIFIC-EXP-03B — preregistered execution amendment v1.1

**Frozen before any SCIENTIFIC-EXP-03B trial.** The parent design remains unchanged at `SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md` (SHA-256 `a378bde3140e9b62f6599e5d046fb659565876e63a08d040ed0803040a2c85fa`). This amendment resolves execution and precision details; it does not modify a transmitter, channel, receiver, decoder, or the parent energy grid.

## Why an amendment is needed

The parent v1 document is deliberately non-executable: it says 100 metric trials per point, has no system-contrast grid, and its 03A runner rejects `confirmatory`. The requested 03B includes both an isolated A-E/A-H metric contrast and a separate full Joint/B0/B1 system contrast, a noise-sweep control, long-run checkpointing, and explicit precision criteria. v1.1 therefore fixes those additions before data collection. The parent and all 03A pilot records stay immutable and will not be pooled into confirmation.

## Confirmatory designs

### A — isolated metric effect

- Two decoder arms: Euclidean A-E and Hamming A-H. Each pair uses one information sequence, channel/fading realization, complex AWGN realization, `ReceiverObservation`, pilot schedule, causal pilot frontend output, allowed-edge mask, Encoder A trellis, initial state and finite-depth traceback `η=20`. Only the branch-cost construction differs.
- F=1024 symbols; primary pilot cadence 32, preamble 4, burst 4. Rician cadence 8 is a separately analyzed sensitivity arm with its own pilot overhead. AWGN direct control remains a distinct no-pilot/no-equalizer control.
- All 38 energy cells from the parent grid are retained exactly. A second noise-at-fixed-amplitude sweep uses the same offsets. For each matched scenario/cell/trial across the two sweep methods, information/fading/noise seed streams are identical; the AWGN realization is consequently scaled by the channel implementation rather than treated as a new independent pair. The two sweep curves are not pooled.
- 300 independent trial clusters per cell and sweep. This yields at least 537,600 payload bits per primary cadence-32 cell (300 × 896 × 2), and approximately 307,200 at cadence 8 (300 × 512 × 2). The AWGN-direct cell has 614,400 bits. At BER 0.001 the corresponding expected counts are about 538, 307 and 614; actual counts decide estimability.
- Fixed complex variance `σ²_c=0.05` for amplitude sweep; fixed nominal amplitude `A=1` for noise sweep. The plotted abscissa is measured `γ_b,d=10log10(E_b,d/σ²_c)`, with total transmitted energy including pilots divided by useful payload information bits. This remains a discrete project convention, not calibrated physical Eb/N0.

### B — complete receiver systems

- Independently generated confirmatory series; its outputs are never mixed with A.
- F=256; 100 independent frames per measured energy point, using the full receiver grid in `configs/SCIENTIFIC_EXP_03B_PROTOCOL.json`: AWGN and static [0,3] use 0…14 dB in 0.5 dB steps; Rician AR(1) uses 0…24 dB in 1 dB steps.
- AWGN arms are Joint/B0. Static arms are Joint/B0/B1 with B1 receiving the public nominal static taps. Rician arms are Joint/B0; B1 is unavailable. These are full-system contrasts, not isolated metric effects.
- Fixed complex variance `0.05`, amplitude selected from the measured discrete energy grid, and separate root-seed domains from A, preflight, SCI-EXP-01B/02 and all 03A pilots.

## Precision and stopping rules

- All planned points and the full frozen sample count are completed; positive early outcomes never stop a sweep.
- A metric target crossing is reportable only if both arms have measured adjacent brackets, at least 200 bit errors per arm at each bracket, no extrapolation, and at least 95% valid paired-cluster bootstrap crossings. A target with a zero-error bracket is unresolved, not assigned BER zero as a probability.
- A system target uses the same 200-error and 95%-valid-crossing requirements. The bootstrap resamples whole independent frame clusters, not bits.
- Required-energy uncertainty is computed by 5,000 paired cluster-bootstrap replicates with log10(BER)-versus-measured-energy interpolation as primary. Linear-BER interpolation is a sensitivity analysis. Report the crossing fraction and the full measured bracket.
- At targets 0.05, 0.01 and exploratory 0.001, report BER confidence intervals at every energy point; the precision flags are those fixed in the JSON protocol (`half-width` limits for BER and gain). A failed precision gate yields `INSUFFICIENT_PRECISION` or `NOT_ESTIMABLE`; there is no outcome-driven grid edit or unregistered extension.
- Runtime is not a stop condition. The runner checks a minimum 1 GiB free-disk reserve before each complete trial, has a 40,000-record ceiling, writes a durable per-pair checkpoint, and only stops at a complete paired trial on an explicit interruption or resource guard. RAM warnings are recorded; they do not alter BER inclusion.

## Preflight (excluded from inference)

- A: for each of five metric scenarios and each of two sweeps, run 10 trials at the middle frozen energy point (100 frames total).
- B: for each channel, run 10 frames at three fixed energy points (low, middle, high) (90 frames total).
- Preflight roots 830091–830098 are reserved only for feasibility; no preflight record can enter a confirmatory manifest. It checks F=1024/F=256 runtime, RSS, saved bytes, exact resume behavior, seed separation and the new Windows/OneDrive atomic retry path.
- The energy grids are not selected or narrowed from preflight outcomes.

## Outcome and provenance rules

- Seed streams follow `[root_seed, 0x03B, scenario_id, point_index, trial_index, stream_id]`; A uses stream IDs 0/1/2 for information/fading/noise, with the same seed tuple across matched amplitude/noise sweeps. B uses distinct scenario IDs 11/12/13.
- Each record stores root and derived seeds, full configuration and protocol SHA-256, trial ID, arrays SHA-256, observations hash, common frontend hash for A, counts, energies, raw wall time and process CPU time. No timer anomaly removes an error record.
- Resume verifies protocol/config hashes and every completed payload SHA before skipping it. Trial IDs are unique. Output paths are new `outputs/scientific_exp03b/` trees; historical EXP-01B/02 files are read-only.
- `EvaluationTruth` is not passed to any decoder or pilot frontend. It is only available to post-decode evaluator diagnostics.

## Source record

Primary article SHA-256: `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3`; alternate article: `190163b9f123e99648ce9dc2d57cb4fdcc24a8a675001009da41cb0ecf6f9a87`; `Раздел_4.doc`: `e877a9272da0e8baa0e4eb21256acf1e2112428d3dbf14472d9b12d3239cfd59`. The project continues to record `paper_exact:false`; the measured gamma is not physical Eb/N0, and the article's 1.5 dB is a comparison value only.

## Planned data volume

- A: 38 cells × 2 sweep methods × 300 = **22,800 paired trials**.
- B: 83 cells × 100 = **8,300 paired full-system frames**.
- Maximum confirmatory total: **31,100 trials**, plus 190 feasibility-only preflight frames.
- Before committing to these counts, preflight must measure runtime and disk consumption. A resource failure must leave a resumable partial run; it cannot be replaced with estimated or synthetic records.

**Execution status at freeze: NOT STARTED.**
