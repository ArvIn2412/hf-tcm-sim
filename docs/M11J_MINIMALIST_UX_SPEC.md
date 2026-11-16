# M11j Minimalist Simulation Studio UX Specification

## Intent

Replace the current dense Demo Studio dashboard with six clear learning views for supervised classroom and thesis-defense demonstrations. Preserve the existing deterministic Python/API run as the only source of runtime values; navigation and inspection must not trigger it.

## Goals

- Open on **Моделювання**, with parameters grouped by input, encoder, channel, receiver, and analysis.
- Provide six compact Ukrainian navigation items: Моделювання, Етапи сигналу, Відліки сигналу, Приховані стани, Декодування, Результати.
- Show one principal chart per view, with at most one supporting chart in the focused presentation.
- Keep exact values, formulas, help, archive access, CSV/JSON export, and advanced details available on demand.
- Share selected run, encoder, receiver, symbol, window, stage, and display mode across views.
- Clearly distinguish model-derived data from derived visualization, conceptual stages, and unavailable RF/channel behavior.
- Support projector layout at 1366×768 and 1920×1080 without small-chart dashboards.

## Non-goals and constraints

- No production math, backend receiver, encoder, channel, historical M5–M10 artifacts, or ADR changes.
- No Monte Carlo, new statistical evidence, physical RF chain, passband/carrier/filter simulation, or fabricated channel hidden-state trace.
- Encoder B remains a trellis preview and cannot run a receiver.
- `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN remain.

## Approaches

1. **Extend the current single-page application with six focused views (selected).** Reuse the existing `app.trace`, API POST, chart adapters, sample-window state, and archive metadata. Move existing panels into a compact information architecture and add thin presentation adapters. This preserves numeric provenance and avoids a second execution lifecycle.
2. Build six separate HTML routes. This would create additional server routing, duplicate view initialization, and require explicit persistence of run state across navigation. It does not improve the single local application enough to justify that risk.
3. Replace the Demo Studio frontend wholesale. This would discard tested controls and chart/trellis adapters and make regression review larger without changing the backend contract.

## Interaction and state

- Initial view is the existing interactive simulation form, reorganized into five parameter groups. Run remains an explicit POST. Parameter edits mark the current trace stale; stale values remain inspectable but are visibly labeled and cannot be presented as current. A subsequent successful POST replaces the one active run result and creates a new local run ID.
- Views share the active trace and UI selections. Navigation only changes presentation. Sample index and window start update the stage, symbol, TCM edge, and decoded path markers without another receiver call.
- The Simulation view retains encoder A controls, current supported estimator controls, input presets/file import, and B preview with receiver disabled. Unsupported physical parameters are explained as unavailable, without decorative controls.
- Signal stages use the existing actual trace arrays and ten-step signal pipeline: information bits, encoded bits, TCM transition, 8PSK symbol, complex baseband, rectangular ZOH, gain-applied samples, noise, received samples, and observed I/Q. Each reports provenance/status. RF labels refer to complex-envelope model input/output only.
- Samples view combines a whole-frame overview, one large selected signal chart, and a collapsed exact-value table. Full frame, 20×8 (160 samples), and 20-sample detail reuse the existing window calculator. Short frames show available samples without padding.
- Hidden States separates TCM encoder states from channel latent states. Channel state view uses an explicit unavailable explanation unless actual trace fields exist; no posterior or transitions are invented.
- Decoding has Metrics, Estimation, and Viterbi tabs, each with one principal chart. B mode shows receiver unavailable.
- Results separates one-run demonstration counts from read-only M5–M10 archive results. Single-fixture BER/SER has no comparative-performance interpretation.
- Projector mode collapses navigation, enlarges the active chart and summary values, retains scientific caveats, and supports previous/next and fullscreen.

## Presentation rules

- Default Simple mode contains structured cards, not raw JSON. Large raw details remain inside collapsed Advanced disclosure or existing explicit export/download controls.
- Each view has a title, short Ukrainian explanation, primary chart (or factual unavailable state), key values, formula, contextual `?`, Previous/Next, and optional advanced details.
- Status labels are `ACTUAL IMPLEMENTED`, `DERIVED VISUALIZATION`, `CONCEPTUAL ONLY`, or `UNAVAILABLE`.
- Preserve accessible labels, keyboard focus, graph legends/axes, existing projector trellis overview/detail, and all existing transitions.

## Acceptance

Full pytest, Ruff check and format, Node tests/syntax, and real Edge QA at 1366×768/1920×1080 must verify initial Simulation view, edit/STALE/explicit POST lifecycle, six-view navigation without new POST, stage chart provenance, sample-window boundaries and short frames, TCM/channel separation, decoding/archive views, no raw JSON in Simple mode, projector controls, and unchanged M5–M10 fingerprints.
