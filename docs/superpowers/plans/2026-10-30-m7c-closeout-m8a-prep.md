# M7c Closeout and M8a Preparation Plan

> **For agentic workers:** implement this plan task by task; M8a remains an unauthorized design-only phase.

**Goal:** Close the M7 exploratory search from preserved TRAIN records and prepare a guarded, deterministic-testable anchored-adaptation study draft.

**Architecture:** Read M7b checkpoints without mutating them, independently aggregate integer counts, and document why validation is omitted. Add an evaluation-only M8a schema validator and pre-execution guard; use the current B4c sequence API for deterministic anchor invariants in tests, without modifying receiver kernels or creating stochastic observations.

**Tech Stack:** Python 3.11+, NumPy, pytest, JSON, Markdown.

**Spec:** User request M7c-closeout + M8a-prep; `docs/M7_TRAIN_POLICY_SEARCH_REPORT.md`; current reconstruction sequence APIs.

## Global Constraints

- `paper_exact:false`, `receiver_enabled:false`; accepted ADRs and open SCI questions remain unchanged.
- M7b historical records and all M5/M6/M7 outputs are read-only.
- No M8 RNG, data/noise generation, decoder study, Monte Carlo, or parameter search.
- Production receiver mathematics remains unchanged.

## Review Focus

- M7b selection must be recomputed from complete checkpoints, not trusted from summary alone.
- Anchor validation must preserve the specified exact initial coefficient decomposition.
- The unauthorized guard must reject before invoking any supplied RNG/data/receiver callback.
- Anchored and historical profiles must have equal first full estimates and equal first-symbol metrics/posteriors.
- Proposed M8 partitions must use unique namespaces outside M5/M6/M7 roots without deriving child seeds.

### Task 1: M7 Read-Only Closeout

**Files:** Create `docs/M7_EXPLORATORY_STUDY_CLOSEOUT.md`; update `PLAN.md` and `NEXT_TASK.md`.

- [ ] Replay all 40 checkpoints and confirm 9 records each, counts, failures, ranking, and winner.
- [ ] Record status `EXPLORATORY_GRID_COMPLETED; TRAIN_WINNER_FROZEN_B; ADAPTIVE_GAIN_NOT_ESTABLISHED; VALIDATION_NOT_EXECUTED` without editing original M7b artifacts.

### Task 2: M8a Draft and Evaluation Guard

**Files:** Create `configs/m8a_anchored_study_draft.json`, `src/hf_tcm/evaluation/m8a_anchored_study_design.py`, and `tests/test_m8a_anchored_study_design.py`.

- [ ] Validate the exact six anchored policies, two historical controls, sigma scaling, partition roots, and proposed/unauthorized status.
- [ ] Ensure the execution guard blocks before callbacks; it never generates seeds.

### Task 3: Anchor Algebra and Receiver Invariants

**Files:** `tests/test_m8a_anchored_study_design.py`.

- [ ] Verify independent scalar decay/anchor equations and run only fixed deterministic B4c unit fixtures for equal initial metrics, K=0 trajectories, alpha=1 recentering, edge order, and causal cutoffs.

### Task 4: Scientific Documentation and Verification

**Files:** Create `docs/M8_ANCHORED_ADAPTATION_DESIGN.md`; update assumptions, open questions, build verification, and phase plans.

- [ ] Document M7 closeout and proposed M8 partitions, failure/selection policy, seed separation, resource counts, and authorization gates.
- [ ] Run requested pytest and Ruff checks; verify historical hashes before and after.
