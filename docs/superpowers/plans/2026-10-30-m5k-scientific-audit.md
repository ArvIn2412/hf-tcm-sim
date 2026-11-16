# M5k Scientific Audit Plan

> **For agentic workers:** Use this plan inline; do not launch receiver runs or Monte Carlo.

**Goal:** Independently audit saved M5j results and diagnostics, document scientific limits, and repair only final summary reporting.

**Architecture:** Read immutable M5j checkpoints and approved provenance, replay count aggregation and ADR-014 bootstrap from stored paired counts, inspect existing API/tests, and keep receiver execution out of M5k. Fix the runner's final print and worker exit status behind synthetic-summary regression tests.

**Tech Stack:** Python 3.11+, pytest, Ruff, existing NumPy count/bootstrap APIs, Markdown reports.

**Spec:** User-provided M5k request; `AGENTS.md`; M5j design and bootstrap contracts.

## Global Constraints

- Preserve M5f/M5h/M5j historical bytes and original M5j fingerprints.
- Do not run receiver, generate new signal/noise observations, tune parameters, or launch a new Monte Carlo.
- Keep `paper_exact:false`, `receiver_enabled:false`, ADR status and open SCI questions unchanged.
- Change only the M5j final summary/reporting path in runtime code.
- Run the exact user-requested pytest and Ruff commands before updating `PLAN.md`.

## Review Focus

- Confirm run IDs, seeds, paired received hashes, denominators, and counts against manifest/checkpoints.
- Reproduce six intervals from stored count clusters using ADR-014's same-index policy and explicit seed.
- Ensure stored-history tests never call any receiver/noise-generation API.
- Ensure completion exit status and printed count-field names follow the saved summary schema.
- Keep root-cause hypotheses explicitly unresolved unless existing evidence supports only the implementation fact.

## Tasks

### Task 1: Establish baseline and audit saved M5j

- [x] Read phase, contracts, reports, and actual APIs.
- [x] Record pre-audit hashes for M5j, M5h, M5f artifacts.
- [x] Independently aggregate integer counts and replay bootstrap without receiver execution.
- [x] Summarize available and unavailable estimator history and audit gates.

### Task 2: Fix final summary reporting

- [x] Add a synthetic completed/incomplete summary regression test and observe the current `KeyError`.
- [x] Print `failure_record_count` and derive worker exit status from consistent run-record counts.
- [x] Verify the isolated regression and full suite.

### Task 3: Lock read-only audit behavior

- [x] Add stored-count replay/bootstrap reproducibility, run-ID, artifact-integrity, and no-receiver-execution tests.
- [x] Update requested M5k and protocol/history/build docs with bounded conclusions and gates.
- [x] Recheck artifact hashes, run requested pytest/Ruff commands, then update PLAN/NEXT_TASK.
