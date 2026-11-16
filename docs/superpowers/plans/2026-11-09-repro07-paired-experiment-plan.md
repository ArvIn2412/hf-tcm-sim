# REPRO-07 Paired Experiment Implementation Plan

> **For agentic workers:** execute inline in this session; the user explicitly requested implementation and verification.

**Goal:** Run a reproducible, resumable paired comparison of the existing REPRO-06C and REPRO-04 receivers, with pooled BER/SER and trial-cluster confidence intervals.

**Architecture:** New modules under `src/hf_tcm/repro/` orchestrate existing APIs without changing receiver mathematics. Immutable JSON trial records and SHA manifests live under `outputs/repro07`; a deterministic bootstrap/statistics module and measured SVG plot adapter consume only completed records.

**Tech Stack:** Python standard library and existing NumPy; no added dependency.

**Spec:** `docs/superpowers/specs/2026-11-09-repro07-paired-experiment-design.md`

## Tasks

1. Write failing unit tests for strict config, domain-separated seed derivation, pooled ratio statistics, and paired bootstrap.
2. Implement experiment schema/statistics/seed planning and pass those tests.
3. Add a real one-pair runner using the current transmitter/channel/receivers/evaluation adapters; verify shared observation hashes and truth isolation.
4. Add atomic trial storage, manifest validation, resume, failure exclusion, budget stops, and CLI; test interrupted/repeated runs.
5. Add actual-result SVG plots and long-frame preset validation/configuration.
6. Run deterministic smoke, the bounded 3 × 20 F=256 pilot, and a resource-bounded long-frame attempt; verify outputs and hashes.
7. Run targeted tests, full pytest, scoped Ruff, historical fingerprints; write the REPRO-07 documents and update PLAN/NEXT_TASK/BUILD_VERIFICATION.

## Review focus

- Same observation hash and same compared payload on both arms.
- Trial/channel realization—not individual bits—is the bootstrap unit.
- Atomic completion and hash-checked skip on resume; no duplicate aggregates.
- Sample-domain noise variance is never labeled physical Eb/N0.
- Failed trials and budget-interrupted trials do not enter statistics.
