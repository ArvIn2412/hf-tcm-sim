# M11b Demo Studio Release Hardening Implementation Plan

> **For agentic workers:** use inline execution; keep changes within M11b.

**Goal:** Harden the existing localhost studio for a deterministic 32-symbol defense demo, auditable stage/parameter coverage, synchronized inspection, and documented release QA.

**Architecture:** Extend the current standard-library HTTP service, evaluation-side deterministic trace collector, and dependency-free HTML/CSS/JavaScript frontend. Keep receiver, encoder, metrics, estimator, Viterbi mathematics, and historical output artifacts read-only.

**Tech Stack:** Python 3.11+, NumPy already used by the project, standard-library HTTP server, browser-native JavaScript and SVG, pytest, Ruff, Node.

**Spec:** `docs/M11_INTERACTIVE_DEMO_STUDIO_DESIGN.md` and the user's M11b acceptance request.

## Global Constraints

- Preserve `paper_exact:false`, `receiver_enabled:false`, ADR-002 reconstructed, ADR-005 reconstructed, ADR-016 evaluation-only, and open SCI-02/SCI-03/SCI-METRIC-02.
- No internet, cloud API, RNG, Monte Carlo, new ADR, production mathematics change, or historical artifact mutation.
- Demo execution remains explicit POST only; fixtures are bounded to 64 bits / 32 symbols.
- Browser screenshots count only when captured from an actual browser instance.

## Review Focus

- Final-symbol stage must not fabricate a next prediction; cover in stage audit and boundary tests.
- Shared B/anchored traces must use identical immutable received samples; cover in F=32 test.
- UI controls must synchronize trace values and edge selection; cover DOM interaction hooks plus real browser if available.
- Historical values and artifacts remain exact/read-only; cover assertions and final hash audit.
- Missing historical files remain visible as unavailable; cover dashboard availability tests.

---

### Task 1: Trace and coverage contracts

**Files:** `src/hf_tcm/evaluation/m11a_demo_studio.py`, `tests/test_m11a_demo_studio.py`.

- [ ] Add a tested stage-coverage audit that checks actual trace-backed values for each of the 28 stage renderers and reports stage 28 as `PARTIAL_BY_DESIGN`.
- [ ] Add the fixed F=32 defense request while preserving the existing 4-symbol default smoke request.
- [ ] Verify the targeted tests fail before implementation and pass after.

### Task 2: Interactive frontend hardening

**Files:** `src/hf_tcm/studio/static/index.html`, `src/hf_tcm/studio/static/studio.js`, `src/hf_tcm/studio/static/studio.css`, `tests/test_m11a_demo_studio.py`.

- [ ] Add 18 defense steps and Previous/Next/Reset/Return controls; keep Inspector navigation available.
- [ ] Add visible 4/32-symbol named presets and fixed F=32 deterministic selection.
- [ ] Make stage content refresh on symbol/arm changes, explicitly label formula/explanation/provenance/indices, and show final-symbol unavailability.
- [ ] Make all 16 graph edges individually selectable with parallel-edge routing and table synchronization.
- [ ] Verify frontend syntax and static interaction contracts.

### Task 3: Release evidence and documentation

**Files:** `docs/M11B_DEMO_RELEASE_QA_REPORT.md`, `docs/DEMO_DEFENSE_CHECKLIST.md`, `docs/DEMO_PRESENTATION_SCRIPT.md`, `docs/DEMO_PARAMETER_COVERAGE.md`, `docs/M11_INTERACTIVE_DEMO_STUDIO_REPORT.md`, `docs/BUILD_VERIFICATION.md`, `PLAN.md`, `NEXT_TASK.md`.

- [ ] Record the generated full parameter inventory and stage-by-stage renderer audit, including unavailable data and source provenance.
- [ ] Run required tests, Ruff, Node syntax, HTTP and deterministic POST smoke, browser automation if available, and historical integrity checks.
- [ ] Update phase documents with only verified results and stop at M11b.
