# M5h Pilot Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run only the explicitly authorized 120-sequence M5h planning pilot under monitored single-process resource limits, with reproducible checkpoints and a bounded report.

**Architecture:** Preserve both proposed drafts and create a separate approved-for-pilot run config at launch time with source/config/code fingerprints. An external parent supervisor launches one worker, checks wall time and Windows RSS, while the worker validates the authorization guard, resumes only matching checkpoints, runs the existing paired adaptive diagnostic per independent sequence, atomically stores compact run records, and then computes ADR-014 stratum summaries.

**Tech Stack:** Python 3.11+, NumPy SeedSequence/PCG64, existing evaluation APIs, Windows `ctypes` process/memory APIs, JSON atomic replacement, pytest and Ruff.

**Spec:** `NEXT_TASK.md`, `docs/M5_PILOT_PREPARATION_CONTRACT.md`, and the current user M5h-run instruction.

## Global Constraints

- Keep M5g/M5h proposed drafts unchanged; store authorization only in a new immutable run-specific config.
- Candidate remains limited to 4 strata x 30 runs, F=256, and existing B/C parameters.
- Use only pilot data/noise/bootstrap namespaces; never evaluation namespaces.
- Use one decoding worker; no multiprocessing or parameter tuning.
- Keep `paper_exact:false`, `receiver_enabled:false`, ADR-009/011 proposed, and open SCI-02/SCI-03/SCI-METRIC-02 unchanged.
- Do not execute a confirmatory sample size or a sweep.
- Keep received arrays and full coefficient histories out of long-lived aggregate memory/output.

## Review Focus

- An approved config with altered candidate parameters must fail validation before run generation.
- Resume with mismatched config/code fingerprints or duplicate checkpoint IDs must fail closed.
- A timeout/RSS stop during a run must preserve completed checkpoints and mark the current run incomplete.
- A numerical failure must be retained and must block complete-stratum inference.
- Pilot and evaluation/bootstrap child streams must remain disjoint and collision-checked.

---

### Task 1: Approved run config and authorization gate

**Files:** modify `src/hf_tcm/evaluation/m5h_pilot_protocol.py`; create `configs/m5h_pilot_approved_run.json` at runtime; test `tests/test_m5h_pilot_protocol.py`.

Add `approved_for_pilot`, `execution_scope`, and provenance fields without changing the draft. Validate authorization provenance, exact candidate parameter snapshot, source draft hash, code fingerprint, and execution limits. Continue rejecting before SeedSequence derivation when any guard fails.

- [ ] Test authorized scope and parameter drift rejection.
- [ ] Test existing unauthorized draft still invokes no executor.
- [ ] Run focused guard/config tests before any stochastic execution.

### Task 2: Checkpoint/resume and worker execution

**Files:** modify `src/hf_tcm/evaluation/m5h_pilot_protocol.py`; create `src/hf_tcm/evaluation/m5h_pilot_runner.py`; test in `tests/test_m5h_pilot_protocol.py`.

Add exact run-ID skip/resume, per-run success/failure callback, current-run marker, and atomic checkpoint persistence. The worker generates reference bits from each data child seed and calls the actual `run_adaptive_estimator_diagnostic` once per run with ADR-015 noise seed; extract only paired counts, received hash, and compact coefficient/posterior diagnostics. No B/C decoder randomness is permitted.

- [ ] Test atomic checkpoint load, duplicate rejection, fingerprint mismatch rejection, and skipping completed IDs with a spy.
- [ ] Test failed-run checkpoint retention and interrupted-run status without decoder execution.
- [ ] Run focused tests; no stochastic fixture.

### Task 3: External resource supervisor and pilot summary

**Files:** `src/hf_tcm/evaluation/m5h_pilot_runner.py`; tests for resource API failure paths; output under `outputs/m5h_independent_pilot/<run-id>/`.

Run one worker process with a 1800-second deadline, 1.5 GiB monitored RSS stop threshold where Windows APIs permit, 0.25-second monitor interval, and available-memory preflight. Report polling/scheduling limitations and never describe sampled RSS as a hard cap. After runs, calculate pooled rates and paired ADR-014 bootstrap only for complete strata. Compute `s_d` and non-approved `R_approx` only from complete 5 dB pairs.

- [ ] Test unavailable resource monitor degrades explicitly to bounded single-process mode.
- [ ] Test deadline/memory stop is recorded as incomplete and completed checkpoint IDs remain intact.
- [ ] Do not benchmark or run exploratory stochastic pilots in tests.

### Task 4: Execute once, report, and verify

**Files:** create `docs/M5_INDEPENDENT_PILOT_REPORT.md`; update `BUILD_VERIFICATION.md`, `PLAN.md`, `NEXT_TASK.md`, `docs/M4_OPEN_QUESTIONS.md`, and M5 evaluation/bootstrap docs.

Create the approved config and immutable run output, execute exactly 120 registered IDs in fixed gamma/run order, analyze and report failures/warnings/limitations, and run the requested full tests and Ruff commands. Never launch confirmatory R.

- [ ] Verify exact run counts, output/config/code fingerprints, and all seed lineage before analysis.
- [ ] Run `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider`.
- [ ] Run `ruff check src tests` and `ruff format --check src tests`.
- [ ] Update phase status only with verified results; leave confirmatory gate BLOCKED.
