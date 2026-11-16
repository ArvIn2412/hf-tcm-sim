# M11j Minimalist Simulation Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure Demo Studio into six minimalist, trace-backed Ukrainian views with explicit run/stale state and a projector-friendly single-chart presentation.

**Architecture:** Keep the existing single-page app, API POST, `app.trace`, chart renderer, Signal Explorer, and archive metadata. Add a lightweight UX router/view shell in `studio_ux.js`, organize the simulation form in existing HTML, and derive all displayed values from the active trace or read-only archive metadata.

**Tech Stack:** Existing vanilla JavaScript, HTML, CSS, Python HTTP server/API, pytest, Ruff, Node tests, Microsoft Edge QA.

**Spec:** `docs/M11J_MINIMALIST_UX_SPEC.md`

## Global Constraints

- Do not change production encoder, modulation, receiver, metric, estimator, Viterbi, backend model, or accepted ADRs.
- Do not change M5–M10 data or run Monte Carlo/new performance studies.
- Keep `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN.
- Use existing deterministic trace data; do not synthesize RF, channel latent state, or unavailable values.
- Keep Encoder B preview-only with receiver execution disabled.

## Review Focus

- Changed configuration with an old trace: test that it is visibly `STALE` and retained data is not labeled current.
- A failed or repeated explicit POST: test active run ID/data are replaced only on successful POST.
- Short signal frames: test window clamps to available samples and does not pad.
- Encoder B and channel-state view: test no receiver/HMM output appears.
- Simple mode: test it contains no raw JSON outside collapsed advanced details/exports.

## Planned files

- Modify `src/hf_tcm/studio/static/index.html`: six primary nav items, grouped Simulation controls, and focused view shells while preserving existing panel IDs/API hooks.
- Modify `src/hf_tcm/studio/static/studio_ux.js`: shared run/UI state, six-view navigation, status-aware stage adapters, sample/decode/results tabs, stale lifecycle, and previous/next routing.
- Modify `src/hf_tcm/studio/static/studio_ux.css`: compact sidebar, one-chart views, responsive/projector layout, collapsed advanced data, accessible focus and status treatments.
- Add `tests/test_m11j_minimalist_navigation.js` (or extend current Node UI helper tests) for pure stage mapping, navigation order, stale/current labels, and sample window boundaries.
- Add `scripts/qa_m11j_minimalist_studio.js`: actual Edge POST, six-view routing/state synchronization, stale behavior, chart/status/help, samples, channel unavailable, decode/archive, projector, screenshots.
- Create `docs/M11J_MINIMALIST_UX_REPORT.md`, `docs/M11J_BROWSER_QA_REPORT.md`; update `PLAN.md`, `NEXT_TASK.md`, `docs/BUILD_VERIFICATION.md` after verification.

## Task 1: Freeze baseline and add failing interaction checks

**Interfaces:** retain `app.trace` and current server endpoints; do not add backend endpoints.

- [ ] Capture current M5–M10 baseline fingerprints from the existing integrity manifest.
- [ ] Add failing Node/Edge checks for 6-view labels/order, Simulation initial view, stage status mapping, explicit run and stale state.
- [ ] Add failing checks for samples, channel-hidden-state unavailable state, decode tabs, archive, and no JSON in Simple mode.
- [ ] Run only the new checks to confirm the expected failures before implementation.

## Task 2: Build the six-view information architecture

**Files:** `index.html`, `studio_ux.js`, `studio_ux.css`.

- [ ] Replace primary navigation with Simulation, Signal Stages, Signal Samples, Hidden States, Decoding, Results.
- [ ] Reuse existing panels/IDs and route them without remounting or clearing `app.trace`.
- [ ] Make Simulation the initial active view and group current supported controls into Information, Encoder, Channel, Receiver, and Analysis sections.
- [ ] Add previous/next actions and contextual help on each main view.
- [ ] Verify navigation never issues `/api/demo` or `/api/encoder-b-preview` requests.

## Task 3: Add run identity, stale marking, and structured Simulation summary

**Files:** `studio_ux.js`, `index.html`, Node/Edge checks.

- [ ] Track one active `runId`, encoder, config snapshot, selected receiver, selected symbol, sample-window start, stage, and display mode.
- [ ] Mark the current trace `STALE` on any simulation-affecting edit; keep it visibly stale until a successful explicit POST replaces it.
- [ ] On successful A POST, set new run ID/config snapshot, show “Симуляцію завершено” and “Переглянути сигнал”.
- [ ] On GET/navigation/edit, assert no receiver invocation; B remains preview-only.
- [ ] Keep raw full-trace/JSON details collapsed by default; preserve explicit JSON/CSV exports.

## Task 4: Implement focused signal-stage and sample views

**Files:** `studio_ux.js`, `index.html`, `studio_ux.css`, Node/Edge checks.

- [ ] Add ten-stage subnavigation and map stages to existing actual trace arrays or explicit status categories.
- [ ] Render one principal trace-backed chart and compact values/formula/source for the selected stage.
- [ ] Label transmitter/receiver as complex-envelope model stages; mark RF hardware-only stages conceptual/unavailable.
- [ ] Consolidate frame overview + main sample chart + collapsed exact-values table into Signal Samples.
- [ ] Preserve Full Frame, 20×8, 20-sample detail, absolute index, Tx/Noise/Rx, I/Q, symbol highlight, and trellis jump.
- [ ] Test F=32 first/middle/last, F<20, and no padding; keep the viewing window separate from Viterbi depth.

## Task 5: Implement Hidden States, Decoding, and Results views

**Files:** `studio_ux.js`, `index.html`, `studio_ux.css`, Node/Edge checks.

- [ ] Split TCM code states from channel latent states. Show actual A 4-state/16-edge or B 16-state/64-edge preview according to selected encoder.
- [ ] For channel latent states, render actual model fields only; otherwise show the explicit unavailable message.
- [ ] Add Metrics, Estimation, Viterbi tabs with one primary chart each, actual F=32 A values, and unavailable B receiver state.
- [ ] Add current-demo error positions/counts and separate read-only M5–M10 archive summaries with TRAIN/EVALUATION and CI caveats.
- [ ] Ensure Simple mode never expands raw JSON; archive details are advanced/collapsed.

## Task 6: Projector layout, accessibility, and screenshots

**Files:** `studio_ux.css`, `studio_ux.js`, Edge QA script.

- [ ] Collapse sidebar in projector mode; size active chart >=500px on desktop, enlarge title/legend/summary, retain scientific caveat and Previous/Next/fullscreen.
- [ ] Verify keyboard interaction, help dialogs, trellis overview/detail, and no page-level horizontal overflow at 1366×768 and 1920×1080.
- [ ] Capture actual Edge screenshots for Simulation, signal stage, samples, hidden states, decoding, results, and projector mode.

## Task 7: Verification, reports, and baseline preservation

- [ ] Run full `python -m pytest -q`, Ruff check/format, Node tests/syntax, and real Edge QA.
- [ ] Recompute/compare all M5–M10 historical fingerprints; require exact match.
- [ ] Write final M11j reports with actual statuses/limitations, update PLAN/NEXT_TASK/BUILD_VERIFICATION, and stop without starting M12.

