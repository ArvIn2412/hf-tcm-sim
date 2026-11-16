# M11c Defense Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze a verifiable M11b demo release and prepare a safe, repeatable Ukrainian defense rehearsal package.

**Architecture:** Preserve the standard-library localhost GUI and its deterministic F=32 POST flow. Add only a small Windows launcher if it can keep startup errors visible; place release hashes, rehearsal procedures, recovery guidance, and scientific FAQ in documentation.

**Tech Stack:** Python 3.11+ / current project Python, standard-library HTTP server, existing NumPy receiver dependencies, PowerShell launcher, Markdown release documentation, Edge DevTools Protocol for browser QA.

**Spec:** User request M11c in this conversation; M11b acceptance reports and M11a architecture.

## Global Constraints

- Do not run Monte Carlo, tune parameters, accept ADRs, or change receiver / encoder / metric / estimator / Viterbi mathematics.
- Preserve historical M5-M10 artifacts and integrity manifests unchanged.
- Preserve `paper_exact:false`, `receiver_enabled:false`, reconstructed ADR-002/ADR-005, evaluation-only ADR-016, and open SCI-02 / SCI-03 / SCI-METRIC-02.
- Keep the demo explicit-action only, deterministic, F=32, 8 samples/symbol, and localhost-only.
- Do not install dependencies or hide Python tracebacks; do not delete ACL-restricted pytest folders or start M12.

## Review Focus

- Hash drift between manifest, fixture, source, and frozen M11b baseline: compute SHA-256 from live canonical inputs and document hash scope.
- Launcher masks startup errors or binds externally: use existing `python -m hf_tcm.demo_studio`, explicit loopback host, and visible process output.
- FAQ overstates reconstructed science: derive answers from code, ADRs, and saved M9/M10 intervals only.
- Rehearsal navigation assumes absent UI routes: verify controls and view names against current HTML/JS before documenting.
- Browser automation is mistaken for a human rehearsal: label it as automated browser rehearsal and make no human-performance claim.

## File Structure

- Create `start_demo.ps1`: minimal root-relative launcher, dependency preflight, port conflict message, visible Python output.
- Create `docs/DEMO_RELEASE_MANIFEST.md`: environment, entrypoint, source/static hashes, fixture and historical hashes, M11b baseline and scientific flags.
- Create `docs/M11C_DEFENSE_READINESS_REPORT.md`: acceptance and verification report.
- Create `docs/DEMO_FINAL_USER_REHEARSAL.md`: exact 2/5/8–10 minute demo flows and recovery runbook.
- Create `docs/DEMO_DEFENSE_QA.md`: short, scientifically bounded answers to 18 committee questions.
- Update `docs/DEMO_PRESENTATION_SCRIPT.md`, `docs/DEMO_DEFENSE_CHECKLIST.md`, `docs/BUILD_VERIFICATION.md`, `PLAN.md`, and `NEXT_TASK.md` for M11c only.
- Modify presentation step wording only if the existing UI labels materially conflict with the requested 18-step order; do not change computation behavior.

## Tasks

### Task 1: Capture immutable release baseline

- [ ] Read the exact M11a/M11b, parameter, checklist, presentation, build, plan, and next-task documents.
- [ ] Query installed Python/package/browser versions and live metadata; capture F=32 bits/noise/receive hashes, runtime registry hash/count, source/static hashes, and selected historical artifact hashes without writing to historical paths.
- [ ] Write the release manifest with explicit scope and no invented Git commit ID.
- [ ] Independently recalculate every listed SHA-256 and assert expected M11b invariants.

### Task 2: Launcher and rehearsal documentation

- [ ] Add a PowerShell launcher that checks Python/NumPy, detects the selected local port, prints the URL, starts the existing module, and leaves tracebacks visible; no auto-install.
- [ ] Verify the launcher with an available port, a deliberate port conflict, and a missing-dependency simulation that does not alter the environment.
- [ ] Prepare committee FAQ answers from implementation and archived evidence; include explicit uncertainty boundaries.
- [ ] Prepare 2-minute fallback, 5-minute compressed script, 8–10 minute full script, and recovery instructions for browser/server/port/POST/data/internet failures.
- [ ] Update checklist and current presentation wording only as necessary to match the requested order.

### Task 3: Browser rehearsal and final verification

- [ ] Run the local server and repeat the specified browser sequence at 1366x768 through all 18 presentation steps; inspect console, HTTP status, overflow, disabled controls, graph overlap, and visible numeric values.
- [ ] Verify metadata counts, explicit F=32 POST, final symbol bound, same-received comparison, and the exact 459-entry runtime inventory.
- [ ] Recheck historical manifests read-only; make no historical writes.
- [ ] Run the requested pytest, Ruff, Node, and HTTP checks; record exact output and limits.
- [ ] Update PLAN/NEXT_TASK after evidence; stop at M11c.

## Plan self-review

- All user sections map to one of the three tasks: manifest; launcher/rehearsal/FAQ; browser and verification. Mathematical behavior is explicitly out of scope.
- The manifest distinguishes source hashes, deterministic fixture hashes, and historical hashes; no revision ID is inferred because the workspace has no Git metadata.
- Browser automation evidence will be called automated rehearsal, not a human rehearsal.
