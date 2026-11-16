# M11f supervisor alignment and Signal Explorer

## Goal

Audit the supervisor's Chapter 4 Code 2 source against the v7 article and the
current HF-TCM-SIM implementation, then add a synchronized Signal Explorer to
the existing Demo Studio using only the existing deterministic trace. Preserve
the M11e trace/API contract and all historical experiment artifacts.

## Verified baseline and constraints

- M11f/M11g implementation is absent; M11e is the last verified UI baseline.
- Chapter 4 PDF pages 126–129 provide Code 2's generator matrix, four-register
  layout, 16-state/64-transition table, output ordering, and B labels.
- Existing Studio trace already contains actual bits, encoder states/edges,
  phase indices, 8-sample Tx/gain/noise/Rx arrays, observed I/Q, metrics,
  posterior weights, estimator states, and full-frame conditional Viterbi path.
- Current receiver accepts the four-state/16-edge model and its full-frame
  conditional decoder is not the source's depth-20 decoder.
- No production mathematical kernel, channel module, M5–M10 result, or source
  ambiguity is to be changed. No Monte Carlo is authorized.

## Implementation decisions

- Extend the existing Studio rather than add a second interface.
- Treat the 20-symbol/160-sample viewing window as a visualization only. It
  never changes the full-frame Viterbi invocation or its decoder depth.
- Keep arbitrary sample offset separate from selected symbol. At frame bounds,
  clamp the displayed interval to actual samples; for the F=32 preset, expose
  the full 0–96 start-sample range for a 160-sample window.
- All chart data comes from the latest explicit deterministic trace. Channel
  state posterior is not displayed; 16 weights are identified as project
  candidate-edge posterior weights.
- Existing multipath/Rician/AWGN modules are documented as standalone and not
  integrated into this receiver. M11f will prepare a design/gap report only.

## Tasks and verification

1. **Source and channel audit** — record article versus Chapter 4 coding,
   samples/symbol, eta, Viterbi contracts, module capabilities, and exact
   source-to-code statuses. No code changes in this task.
2. **Window-index contract (TDD)** — add Node tests first for frame bounds,
   first/middle/last windows, single-symbol frames, symbol/sample conversion,
   and safe clamping; run them red before adding the pure window helper.
3. **Signal Explorer UI** — add one selectable large chart view for all-frame
   overview and the 20×8 sample viewport, explicit symbol/sample controls,
   component selection, synchronized trellis selection, help/provenance, axes,
   units, legend, hover values, and window/symbol highlights. Keep exact trace
   and decoder code unchanged.
4. **Browser regression coverage** — extend a separate M11f Edge QA script for
   actual F=32 trace interaction, sample-index alignment, first/middle/last
   viewport, symbol details, candidate metric/posterior chart, trellis/path
   synchronization, and 1366×768/1920×1080 readability. Save new screenshots
   under M11f names; do not overwrite M11e captures.
5. **Reports** — create the four requested M11f reports and update build,
   phase plan, and next task only after verification.
6. **Final verification** — full pytest, Ruff check/format, Node checks,
   real Edge QA at both requested viewports, and read-only comparison against
   the frozen M5–M10 fingerprints.

## Out of scope

Code 2 receiver/decoder integration, new channel simulation, editable physical
channel parameters, estimator/metric changes, Monte Carlo, scientific claims
of paper-exact fidelity, M11g projector/input controls, and M12 work.
