# M11e Final GUI Patch and Scientific Baseline Freeze — Implementation Plan

**Goal:** Correct M11d GUI data binding and numeric presentation, record the current scientific baseline, and verify the release without altering mathematics or M5–M10 artifacts.

**Architecture:** Keep the changes in the presentation layer and verification/documentation. Add a real browser regression around the existing localhost server's deterministic F=32 POST; test frozen environment metadata separately from demo configuration invariants.

**Tech Stack:** Python 3.13.13 / pytest, standard-library HTTP server, JavaScript, Node, Microsoft Edge CDP, Ruff.

**Spec:** M11e request in the user message; `docs/DEMO_RELEASE_MANIFEST.md`; `docs/M11D_SOURCE_FIDELITY_AUDIT.md`.

## Global Constraints

- Preserve `paper_exact:false`, `receiver_enabled:false`, and open SCI-02, SCI-03, SCI-METRIC-02.
- Do not modify encoder, mapping, 8PSK math, receiver, estimator, metric, posterior, Viterbi, M5–M10 artifacts, or historical manifests.
- Do not run Monte Carlo or reinterpret stored results.
- Do not claim cross-environment reproduction of mathematical results.

## Review Focus

- Missing/moved `channel_gain` displays a localized fallback; actual F=32 POST value must render from the response schema.
- Count values stay integers; all other numeric display retains round-trip precision.
- Simple mode labels are Ukrainian while technical/scientific names and exact numeric strings remain available in scientific mode.
- Frozen environment metadata remains immutable and is not compared to the running environment.
- Historical fingerprints, four states, sixteen edges, Inspector/help, and all 18 defense steps remain intact.

## Tasks

### Task 1: Regression coverage and portability separation

**Files:** Modify `scripts/qa_m11d_browser.js` only if an M11e copy cannot preserve M11d evidence; otherwise add `scripts/qa_m11e_browser.js`. Add a focused test under `tests/` for immutable release metadata and demo configuration invariants.

- [x] Add a browser assertion for live gain after actual F=32 POST, numeric formatting, missing/nonfinite display values, and Ukrainian labels.
- [x] Add a separate configuration/metadata portability test that never compares the current Python/NumPy versions to frozen experiment metadata and never runs receiver mathematics.
- [x] Run focused tests and verify each new regression detects the pre-patch behavior.

### Task 2: Presentation-only correction

**Files:** `src/hf_tcm/studio/static/studio_ux.js`.

- [x] Read gain from `trace.input.channel_gain`; show `Недоступно` for missing/nonfinite values.
- [x] Format integer counts as integers and use round-trip-safe numbers for rates, coefficients, metrics, and posterior values.
- [x] Localize confusing Simple-mode labels while keeping scientific names and full precision.
- [x] Run focused regression checks; do not change simulation or receiver code.

### Task 3: Freeze report and release verification

**Files:** Create `docs/M11E_FINAL_PATCH_REPORT.md`; update `PLAN.md`, `NEXT_TASK.md`, `docs/BUILD_VERIFICATION.md`.

- [x] Run full pytest, Ruff check/format, Node syntax checks, real Edge QA, deterministic F=32 POST, and read-only M5–M10 fingerprint comparison.
- [x] Record exact commands, outcomes, limitations, scientific status, and whether the frozen manifest remains unchanged.
- [x] Issue READY only if all requested checks complete and pass; otherwise report PARTIAL with the exact blockers.
