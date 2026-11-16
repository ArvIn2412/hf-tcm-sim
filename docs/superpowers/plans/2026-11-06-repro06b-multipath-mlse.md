# REPRO-06B Multipath ISI-Aware Joint Receiver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a truth-isolated static-known multipath MLSE receiver with exact integer-delay ISI prediction and finite-depth Viterbi; document adaptive fading as unavailable unless independently verified.

**Architecture:** Add a standalone `hf_tcm.repro.multipath_*` API and an expanded trellis whose node stores Encoder A state plus the minimum prior phase history implied by `ceil(D/8)`. Reuse the REPRO-06 latency/flush convention in a generic graph decoder, keeping the existing 4-state Viterbi and REPRO-05 single-path receiver behavior unchanged.

**Tech Stack:** Python 3.11+, NumPy, pytest, standard-library JSON/hash/SVG output.

**Spec:** `docs/superpowers/specs/2026-11-06-repro06b-multipath-mlse-design.md`

## Global Constraints

- Do not change REPRO-02/03/04/05/06 mathematics, M5-M10 artifacts, accepted ADRs, or GUI.
- Receiver input is only `ReceiverObservation` plus validated public receiver configuration; never pass `EvaluationTruth`.
- Use 8 samples/symbol, integer sample delays, zero extension, ADR-002 project mapping, and the same complex-baseband convention as REPRO-03.
- `D<=16`, `ceil(D/8)<=2`, and expanded graph caps must be validated; no delay rounding/truncation.
- No Monte Carlo, BER-vs-SNR sweep, `paper_exact:true`, or REPRO-07.
- Store new run products only in `outputs/repro06b/`; do not delete ACL-protected temporary directories.

## Review Focus

- A `D=3` delay crosses only the first three samples of a symbol block; test those indices against a manual scalar predictor.
- `D=3` needs previous phase history beyond Encoder A state; test augmented state connectivity and 17-node/68-edge graph.
- Final `D` samples are delayed channel observations, not an extra symbol; test their contributions and exact one-time accounting.
- Finite decisions can come from different survivor paths; test local decision provenance separately from re-encoded output-state history.
- Time-varying channel coefficients are truth-only; test that the adaptive profile is rejected and no truth-bearing object can enter the API.

---

### Task 1: Public static channel config and reachable augmented trellis

**Files:** create `src/hf_tcm/repro/multipath_receiver_config.py`, `src/hf_tcm/repro/augmented_trellis.py`, `tests/repro/test_augmented_trellis.py`.

**Interfaces:** `MultipathReceiverConfig`; `build_augmented_trellis(initial_state, delays_samples, *, max_nodes=256, max_edges=2048) -> AugmentedTrellis`. Each transition records stable expanded edge id, base edge id, source/target augmented node ids, input pair, and phase index.

- [ ] Test D=0 graph, D=3 reachable node/edge counts (17/68), state/history transition invariants, all 16 base edges, arbitrary initial state, and D>16/state-cap rejection.
- [ ] Run focused tests; observe missing API failures.
- [ ] Implement deterministic BFS ordering from canonical Encoder A edge order; only `known_static` estimator/channel mode is enabled.
- [ ] Run focused tests and Ruff on changed files.

### Task 2: Independent waveform predictor and ISI branch rows

**Files:** create `src/hf_tcm/repro/isi_predictor.py`, `src/hf_tcm/repro/isi_metrics.py`, `tests/repro/test_isi_predictor.py`.

**Interfaces:** `predict_transition_samples(transition, trellis, symbol_index, frame_symbols, config, sample_indices) -> complex128[]`; `build_branch_metric_row(observation, symbol_index, trellis, config) -> float64[E]`.

- [ ] Add manual expected-value tests for D=0, one complex path, D=3 first/middle/final blocks and the three-sample tail, known seeded noise, phase-history dependence, and both Euclidean profiles.
- [ ] Run focused tests and verify expected red failures.
- [ ] Implement exact source-sample indexing with zero extension; no true channel arrays.
- [ ] Verify each receive observation index is scored once and only final row includes the D tail samples.

### Task 3: Generic expanded-state full/finite Viterbi

**Files:** create `src/hf_tcm/repro/expanded_viterbi.py`, `tests/repro/test_expanded_viterbi.py`.

**Interfaces:** `ExpandedViterbiDecoder(trellis, config)` with `consume_metric_row(row)`, `flush()`, `result()`; batch wrapper accepts `(F,E)` float costs. Results retain actual local expanded-edge decisions and a separately re-encoded bit/state output.

- [ ] Test direct exhaustive enumeration agreement for short frames, ties, initial state, zero-tail endpoint, eta=1/2/20, F<eta/F=eta/F>eta, full-frame, streaming/batch agreement, flush depth/latency, and max ring rows `min(F,eta)`.
- [ ] Run focused tests to verify failures before implementation.
- [ ] Implement strict-improvement canonical ties and a deque of target-predecessor rows capped at eta.
- [ ] Verify no full survivor history is retained in compact streaming mode.

### Task 4: Static-known multipath receiver orchestration and truth isolation

**Files:** create `src/hf_tcm/repro/multipath_joint_receiver.py`, `tests/repro/test_multipath_joint_receiver.py`.

**Interfaces:** `run_multipath_joint_receiver(observation: ReceiverObservation, config: MultipathReceiverConfig) -> MultipathJointReceiverResult`. It processes F 8-sample blocks plus D final tail samples, computes E expanded branch costs, and decodes those costs.

- [ ] Test only ReceiverObservation accepted, no EvaluationTruth fields, exact observation/config hashes, finite/full modes, static gains/no noise and with configured AWGN, and unsupported Rician/adaptive config rejection.
- [ ] Test transmitter -> REPRO-03 constant channel -> multipath receiver; separately run REPRO-04 on the same observation and assert equal observation SHA-256.
- [ ] Implement per-row predictor/metric/decode orchestration; do not change REPRO-05.
- [ ] Verify metrics identical across decoder modes and estimator/truth inputs are absent.

### Task 5: Exhaustive verification, plots, CLI and reproducible artifacts

**Files:** create `multipath_receiver_cli.py`, `multipath_receiver_io.py`, `multipath_plot_adapter.py`, tests, and new JSON config fixtures under `configs/repro06b/`; only write runs under `outputs/repro06b/`.

- [ ] Test CLI validate-only, NPZ serialization round-trip, manifest hashes, deterministic repeat, actual-data metric/tail plots, and optional evaluation-only comparison.
- [ ] Add an independent exhaustive direct waveform cost oracle for small F; do not call production predictor or Viterbi in the oracle.
- [ ] Run F=32 and F=256 measurements, then the 20,000-symbol D=3 reference if resource use is bounded; report single-run timing rather than benchmark claims.
- [ ] Verify top-level output manifest and every file hash.

### Task 6: Reports and complete verification

**Files:** create all eight requested REPRO-06B reports; update `PLAN.md`, `NEXT_TASK.md`, and `docs/BUILD_VERIFICATION.md` after verification only.

- [ ] Document exact model, 17/68 D=3 expanded graph, supported delay/memory limits, tail policy, metric profiles, eta decision latency, static-only status, adaptive blocker, truth separation, and performance limitations.
- [ ] Run targeted tests, full pytest, `ruff check src tests`, and `ruff format --check src tests`.
- [ ] Recompute 694 M5-M10 fingerprint comparison; require 694 matches, zero missing/changed.
- [ ] Confirm scientific flags unchanged and no Monte Carlo/REPRO-07.
