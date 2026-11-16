# M11d UX/accessibility closeout

Date: 2026-11-02. This report records the verified presentation-layer repair over the M11c GUI. Receiver, encoder, estimator, metric, trellis and Viterbi mathematics were not changed.

## Changes and verified behavior

- The help dialog stores the actual opener, traps Tab/Shift+Tab, closes on Escape or the close button, and returns focus to the opener. Root cause of the earlier focus test failure: the explicit close path restored the opener, then the dialog `close` event restored a second time and replaced focus with the Inspector search fallback. The close listener now restores only if focus remains inside the closed dialog or on `body`; modal-local trapping owns Tab.
- Edge focus capture: before close the active element was `#help-close`, the saved trigger was one connected `.help-button`; immediately after Escape and after two animation frames, `document.activeElement` was that same help trigger and the dialog was closed.
- Parameter Inspector retains the 459 registry rows (Core 125, Runtime 258, Technical 76). Its 27 selected-symbol trace values are displayed as an additional live snapshot, not counted as registry rows. Help shows exact JSON numeric values and source-fidelity labels.
- `viewUX` now scopes breadcrumbs and explanations to the active view. The duplicate-ID lookup had populated the first hidden view, leaving the landing copy blank.
- The estimator formula card shows operands and results from the current trace. The decode screen shows the actual conditional Viterbi trace. These are display fixes; neither recomputes the algorithms.
- `docs/MATHEMATICAL_MODEL.md` carries a correction note: article Δφ=π/4 is an increment and does not establish absolute φ0=π/4.

## Browser acceptance

Real Microsoft Edge 156.0.4314.58, localhost `127.0.0.1:18766`, DevTools Protocol. `node scripts/qa_m11d_browser.js`: **285 checks passed, 36 actual screenshots**, at 1366×768 and 1920×1080. The run included explicit deterministic F=32 POST, symbols 0/15/31, graph/edge selection, exact 459/27 inventory separation, formula operand checks, all 18 presentation screens, modal keyboard/mouse cycles, archives, and completed JSON/CSV downloads. Zero console errors, failed requests, external requests, or horizontal overflow. Screenshot index and details: [M11d visual QA](M11D_VISUAL_QA_REPORT.md).

The automated rehearsal is not a claim of a human rehearsal. Screenshots are real browser captures after the deterministic POST, not generated images.

## Release boundary

`paper_exact:false`, `receiver_enabled:false`; ADR-002 remains reconstructed, ADR-005 remains a reconstructed pseudo-likelihood, ADR-016 remains evaluation-only. SCI-02, SCI-03 and SCI-METRIC-02 remain open. A single deterministic fixture is not independent performance evidence. Source fidelity is reported separately in [the source audit](M11D_SOURCE_FIDELITY_AUDIT.md).

The preserved M11c manifest file has SHA-256 `e76b4d3acd011cba2e655a8d859997023c36f5a34be12f543d819772633cfc67`. It remains a historical freeze: its source fingerprints are not rewritten to match subsequent M11d UX changes.

## Final verdicts

- `GUI_UX_READY` — mandatory modal, interactive, viewport and quality gates passed.
- `SOURCE_AUDIT_COMPLETE` — source-to-assumption-to-code-to-test-to-GUI review and correction records are complete; unresolved science remains explicit.
- `PAPER_PARTIAL` — source supports some structures, while metric, mapping, innovation and model semantics prevent an exact-reproduction claim.
