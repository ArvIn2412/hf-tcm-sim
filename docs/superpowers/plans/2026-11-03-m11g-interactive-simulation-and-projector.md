# M11g implementation plan — interactive simulation and projector

## Context and source decisions

M11f Signal Explorer is present and is the UI base. Code 2 is defined in the available Chapter 4 PDF: printed pp. 126–129 include the rate-2/3 generator matrix, Fig. 4.6, zero initial registers, and all 64 state/input/output/B rows in Table 4.2. Its state order is register cells `(1,3,2,4)`, input `(X0,X1)`, output `(C2,C1,C0)`. Implement a separate encoder and trellis, conforming to the equation and source table. Do not merge with encoder A.

Code 2 does not have an integrated receiver/decoder contract compatible with the existing 4-state conditional decoder. The source calls the last output `B` (manipulation parameter); the GUI may display it as such and must not silently promote it to an absolute article-v7 phase label. Show a source-fidelity warning and disable receiver execution for Code B.

## Scope boundaries

- A remains the M11a/M11f rate-2/3 encoder and deterministic trace path.
- Code A arbitrary input is bounded by the existing API: 2–64 even bits; no hidden padding/truncation. A initial state is canonical `(0,0)` and read-only because the receiver API fixes it.
- Code B encoder preview accepts an explicit binary input up to a configured safe limit of 256 even bits and starts at source-defined all-zero state. Receiver is unavailable.
- Editable receiver fields are only existing alpha-prime, K-tilde, beta and deterministic noise fixture. `mu0`, physical gain/noise/SNR, channel parameters, samples/symbol and decoder depth remain read-only/unavailable in the current simulator.
- The Signal Explorer adds sample zoom and navigation, preserving M11f 20×8 view and full-frame Viterbi semantics.
- Projector mode is a presentation-only layer over actual runtime data; it does not alter simulation or scientific caveats.

## Tasks

### Task 1 — Code 2 implementation and preview endpoint

1. Add tests for the 16×4 source table, output order/B value, inferred shift-register next state, zero reset, invalid input/state, and 16 states/64 unique transitions.
2. Run those tests and confirm RED before implementation.
3. Add `coding/encoder_b.py` with typed state, branch, step, encode and trellis APIs; implement parity equations from the printed G and table-defined `(C2,C1,C0)` order. Add a preview-only POST route with strict bounds and `receiver_invoked:false` response.
4. Add API validation tests; verify GET never calls encoder/receiver and invalid POST has no side effects.

### Task 2 — Simulation input helpers and UI

1. Test a browser-independent helper for manual bit normalization, strict TXT/CSV parsing, even grouping, min/max limits, derived symbol/sample counts and error text.
2. Add a first-screen configuration form with templates, textarea, local TXT/CSV import, encoder selection, compatible receiver policy, and reset to verified F=32 preset.
3. A selection POSTs actual user bits to the existing demo route only after Start. B selection displays its verified encoder preview only after preview action and keeps receiver button disabled. No auto-run on GET or input change.
4. Present the actual bits, encoded bits, state sequence, symbol/sample counts and phase/B parameter values with source labels.

### Task 3 — Signal Explorer controls and comparison

1. Extend M11f window UI with drag handle, one-symbol movement, select/jump, current-symbol zoom, 20-sample zoom, entire-frame reset, and play/pause navigation.
2. Test exact sample/symbol bounds, including F=32 offsets 0–96 by 8, last/short frame, zoom, and clamping.
3. Keep each selected receiver arm synchronized with actual trace. Compare only same-codec compatible receiver policies; label BER/SER as one-frame values.

### Task 4 — Projector mode

Add explicit projector toggle, fullscreen, collapse/restore sidebar, dark/light themes, large readable graphs and labels, previous/next/play/pause/reset/parameters actions, keyboard navigation, and optional presenter notes hidden by default. Preserve caveats and existing full-frame Viterbi disclaimer. Test both target viewports and graph overflow.

### Task 5 — Documentation and final verification

Create the five requested M11g reports; update BUILD_VERIFICATION, PLAN, NEXT_TASK. Run full pytest, Ruff check/format, Node syntax/unit checks, real Edge QA at 1366×768 and 1920×1080, actual deterministic F=32 POST, Code B preview, upload/validation scenarios, all three signal windows and historic M5–M10 fingerprints. Do not run Monte Carlo or alter historical artifacts.

## Review focus

- Encoder B row/state/input/output ordering matches Table 4.2, not an assumed flattening order.
- B output is shown as source `B` manipulation parameter unless source proves phase semantics.
- No B receiver/Viterbi output is fabricated; controls remain disabled.
- Imported files never strip unexpected characters or silently pad/truncate.
- Input edits and configuration changes never invoke POST automatically.
- Projector transforms preserve source warnings and viewport paths without clipping.
- M11f signal window remains visual navigation, not decoder depth.
