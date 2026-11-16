# M5i Confirmatory Design Preparation Plan

> **For agentic workers:** execute inline in the current session; this task explicitly requests implementation.

**Goal:** Freeze a pilot-informed, unauthorized confirmatory paired B/C design and a deterministic evaluation-only seed manifest without running stochastic evaluation.

**Architecture:** Add a narrow immutable M5i design validator and deterministic SeedSequence manifest derivation that reuses the reserved M5h evaluation roots and domain codes. Keep execution outside this phase: status is proposed, scope none, authorization false, and an injectable execution guard rejects before any data/noise/decoder callbacks. Store the manifest as planned provenance only.

**Tech Stack:** Python 3.11+, NumPy SeedSequence/PCG64, JSON, pytest, Ruff.

**Spec:** `docs/M5_CONFIRMATORY_DESIGN_CONTRACT.md` (written during this task from the user-fixed design).

## Global Constraints

- No stochastic data, noise, decoder, bootstrap-on-new-data, Monte Carlo, sweep, or tuning execution.
- Preserve M5f/M5h outputs and proposed pilot configs byte-for-byte.
- Do not change M1-M3/B4-B5 math, accepted ADRs, open SCI issues, `paper_exact:false`, or `receiver_enabled:false`.
- The candidate has 100 paired runs at effective discrete gamma_b=5 dB, F=256, R=100, epsilon=0.02.

## Review Focus

- Seed manifest must use only M5h evaluation roots and domain-separated children; test no derived seed overlaps any M5h pilot stream.
- Config must reject unsupported labels, altered frozen policy, malformed run count, or bad sigma calibration.
- Execution denial must happen before any injected callback.
- Failure/missing-output policy must prevent full-design inference and prevent silent retry/exclusion.
- Immutable planned IDs must be exactly 100 and deterministic after JSON round-trip.

## Tasks

1. Add failing tests for config validation, fixed workload/policy, manifest seed isolation, stable serialization, and authorization guard with zero spy calls.
2. Add `m5i_confirmatory_design.py` with immutable validated design, canonical fingerprint, seed derivation/manifest builder, and non-executing denial guard.
3. Add explicit draft config and generated planned-run manifest; verify IDs/seeds by deterministic tests only.
4. Write confirmatory design contract and update pilot/preregistration/evaluation/bootstrap/open-question/build/plan/next-task documentation, preserving historical M5f/M5h evidence.
5. Run the requested full pytest and Ruff commands; do not execute M5j.
