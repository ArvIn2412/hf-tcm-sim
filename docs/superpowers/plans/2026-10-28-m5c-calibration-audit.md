# M5c Calibration Audit Implementation Plan

> **For agentic workers:** execute the tasks in order. The user supplied the execution request and exact scope.

**Goal:** Establish sample-energy/noise calibration facts and matched-baseline readiness without running an SNR experiment.

**Architecture:** Add pure `evaluation.signal_diagnostics` helpers for measured discrete quantities and explicit covariance arithmetic; document the source/API audit and draft ADR-015 while preserving current policies.

**Tech Stack:** Python 3.11+, NumPy, pytest, Ruff, Markdown.

**Spec:** User request M5c in this conversation.

## Global Constraints

- Preserve `paper_exact:false`, `receiver_enabled:false`, accepted ADR-001/002/003/004/005/006/007/008/010/012/013 and proposed ADR-009/011/014.
- Do not change M1-M3, receiver behavior, `paper_recursion.py`, `paper_metric.py`, or `reconstruction_forward.py`.
- Do not run SNR sweeps, Monte Carlo batches, confidence intervals, or matched M2 comparison.
- Leave SCI-02, SCI-03, and SCI-METRIC-02 open.

## Review Focus

- Symbol-rate versus 8-sample discrete energy: tested with exact unit-magnitude 8PSK and ZOH blocks.
- Complex versus per-quadrature noise power: tested with deterministic complex operands.
- Correlated mean variance: tested through explicitly supplied diagonal and non-diagonal covariance matrices.
- Invalid/non-finite inputs and input mutation: rejected/preserved by focused utility tests.
- Source-data truth boundary: utilities accept only numeric arrays and contain no receiver/truth API.

### Task 1: Pure sample-domain diagnostics

**Files:** Create `src/hf_tcm/evaluation/signal_diagnostics.py`; create `tests/test_signal_diagnostics.py`.

- [ ] Write tests for finite complex sample energy, exact 8-sample block sums, sample mean/power, independent/correlated covariance formulas, invalid shapes/non-finite values, and input immutability.
- [ ] Run the focused tests and confirm expected missing API failures.
- [ ] Implement only measured discrete diagnostics and covariance arithmetic; require explicit block size and covariance.
- [ ] Run focused tests, then Ruff on changed Python files.

### Task 2: Calibration and comparison audit

**Files:** Create `docs/M5_NOISE_BASELINE_CALIBRATION_AUDIT.md`; update `docs/M5_EVALUATION_PROTOCOL.md`, `docs/M5_SMOKE_EXPERIMENT_REPORT.md`, `docs/M4_OPEN_QUESTIONS.md`, `docs/ASSUMPTIONS_AND_DECISIONS.md`, and `docs/M4_7_IMPLEMENTATION_DECISIONS.md`.

- [ ] Record actual M1 constellation/ZOH, M2 AWGN/metrics, M3 channel/noise APIs, exact n=8 AR(1) covariance implications, matched observation candidate, CSI matrix, and proposed ADR-015 options.
- [ ] Keep every unresolved calibration/baseline choice visibly BLOCKED and preserve all ADR/SCI statuses.

### Task 3: Verification and phase status

**Files:** Update `docs/BUILD_VERIFICATION.md`, `PLAN.md`, and `NEXT_TASK.md` after verification.

- [ ] Run the exact requested pytest, Ruff check, and Ruff format commands.
- [ ] Record actual results and mark M5c complete as an audit only; leave future SNR and matched-baseline gates blocked pending user policy.
