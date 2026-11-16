# M11d real-browser visual and interaction QA

Date: 2026-11-02. Browser: Microsoft Edge 156.0.4314.58 controlled through Chromium DevTools Protocol. Server: `127.0.0.1:18766`. QA entry: `node scripts/qa_m11d_browser.js`. Result: **285/285 checks passed**, 36 actual screenshots; viewports 1366×768 and 1920×1080. The report JSON is `tmp/m11d-browser-qa.json`.

## Coverage

Both viewport passes opened the Simulation Start screen, confirmed GET did not execute a receiver, and ran exactly one explicit deterministic F=32 POST. Each trace had 32 symbols, 64 bits, 256 samples, no RNG, both policies, and the same received-buffer hash. Post-run screenshots were captured after the POST.

The browser checked selected symbols 0/15/31 and formula operands; four distinct states, all 16 canonical IDs and graph paths/table rows; edge selection 0/15; 16 actual metrics and normalized posterior; I/Q plots; estimator pre/update/post values; conditional Viterbi path; shared-received B/anchored comparison; exact Inspector split Core=125, Runtime=258, Technical=76, registry=459 plus 27 selected trace overlays; exact α′ help/source label; mouse and keyboard trigger; focus enters dialog, Tab and Shift+Tab stay inside, Escape and X restore exact opener; ten open/close cycles; receiver change; removed-opener fallback; no console errors. It visited archived charts and checked exact M9/M10 intervals including zero, all 18 presentation screens, JSON/CSV downloads, local-only requests, and responsive layout.

The suite also confirms that the first GET made no POST/receiver call and that the explicit run sends one deterministic POST per viewport. Invalid inputs returning HTTP 400 are exercised by `tests/test_m11a_demo_studio.py` in the full pytest run; they are not sent by the browser rehearsal.

Observed dialog focus after Escape was the original `.help-button` immediately and after two animation frames; the dialog was closed. The race root cause and fix are described in `M11D_GUI_UX_REDESIGN_REPORT.md`.

## Screenshot index

All files below are actual Edge captures. The two `demo-results-post-run` images show the live UI after explicit F=32 POST.

```text
docs/screenshots/m11d-start-1366x768.png
docs/screenshots/m11d-demo-results-post-run-1366x768.png
docs/screenshots/m11d-pipeline-1366x768.png
docs/screenshots/m11d-trellis-1366x768.png
docs/screenshots/m11d-time-trellis-1366x768.png
docs/screenshots/m11d-symbol-1366x768.png
docs/screenshots/m11d-estimator-1366x768.png
docs/screenshots/m11d-decode-1366x768.png
docs/screenshots/m11d-compare-1366x768.png
docs/screenshots/m11d-datasets-1366x768.png
docs/screenshots/m11d-parameters-1366x768.png
docs/screenshots/m11d-help-1366x768.png
docs/screenshots/m11d-presentation-{1,11,13,15,17,18}-1366x768.png
```

The same 18 captures exist for `1920x1080` with the matching names. JSON and CSV downloads completed at both sizes. No clipped page content, horizontal overflow, JavaScript exceptions, failed HTTP requests or external requests were recorded. This is automated browser QA, not a claim that a person performed a live defense rehearsal.
