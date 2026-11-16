# M11c Defense Readiness and Demo Release Freeze

## Acceptance status

**DEFENSE_PACKAGE_READY**, with the limits listed below. This package freezes the M11b deterministic demo and makes it easier to launch, rehearse, recover from common failures, and answer committee questions. It is not a new scientific study. The browser rehearsal was automated through Edge DevTools Protocol; no claim is made that a person completed a rehearsal.

## Release freeze

[`DEMO_RELEASE_MANIFEST.md`](DEMO_RELEASE_MANIFEST.md) records the observed Windows/Python/NumPy/tool/browser versions, app and static asset hashes, F=32 fixture and runtime registry fingerprints, selected historical summary hashes, M11b QA baseline, and scientific flags. Hash values were recomputed from current file bytes. The frozen inventory has 459 entries: metadata exposes 201 configuration entries before a run, and explicit F=32 POST loads 459 runtime/trace entries. Selected-symbol values are searchable through a UI overlay sourced from that live trace. No Git revision is stated because `.git` metadata is absent.

The manifest freezes: Python 3.13.13, package `hf-tcm-sim` 0.1.0, NumPy 2.3.3, F=32, 64 fixed bits, 8 samples/symbol, fixed `low_amplitude_a` noise, gain 0.75, no RNG, and both configured receivers on one received buffer. `paper_exact:false` and `receiver_enabled:false` remain explicit.

## Launcher and recovery package

- `start_demo.cmd` is the Windows entry helper; it invokes the small `start_demo.ps1` from the repository root.
- The PowerShell script checks Python and NumPy, checks a busy localhost port, prints the URL, calls the existing module, performs no installation, and leaves Python output/tracebacks visible.
- Direct `.ps1` invocation is blocked by this environment’s execution policy. The `.cmd` wrapper uses a per-process execution-policy bypass and does not change global policy.
- Valid launcher startup was exercised on localhost. Port conflict returned a clear message and exit code 3. A fake Python executable exercised the missing-NumPy message and exit code 2 without installing packages.
- Browser/server/port/POST/missing-dataset/no-internet recovery instructions and safe static fallback are in [`DEMO_FINAL_USER_REHEARSAL.md`](DEMO_FINAL_USER_REHEARSAL.md).

## Browser rehearsal

Edge 156.0.4314.58 was driven at **1366×768** on `127.0.0.1`. The automated sequence explicitly ran F=32, selected symbols 0/15/31, traversed all 16 edge rows, tested table-to-graph and graph-to-selector synchronization, opened posterior tables and estimator history, compared both receivers on the same received hash, searched the runtime Inspector and archived CI provenance, opened M5j/M7b/M8 recovery/M9b/M10b dashboard entries, and traversed all 18 presentation screens. Reset, Inspector access during presentation, and return to the detailed GUI worked without restarting the server.

| Check | Observed result |
|---|---|
| Parameter inventory | 459 entries in the frozen inventory; metadata exposes 201 configuration entries before run, explicit F=32 POST exposes all 459 actual runtime/trace entries |
| Symbol bound and synchronization | `max=31`; indices 0, 15, 31 synchronized with global slider |
| Graph/table | 4 distinct state nodes; 16 table rows and graph paths; all paths distinct; all 16 table selections highlighted the matching path |
| Graph selection | Selecting edge 10 set the canonical edge selector to 10 |
| Runtime Inspector | Search returned actual selected-symbol bits/state/edge/phase, samples, predictions, metrics, posterior, estimator states, Viterbi decision, BER/SER, channel/AWGN configuration, and M9/M10 CI provenance with archived hash |
| Receiver comparison | `historical_frozen_B` and `anch_a085_k025` visible with shared received SHA-256 |
| Presentation | 18/18 screens; requested states/edges/selection order; Reset, Inspector and Return controls worked |
| Layout | document width 1351 px at 1366 px viewport; no horizontal page overflow |
| Browser errors | No JavaScript exceptions, failed requests, or HTTP status errors observed during the rehearsal |
| HTTP release smoke | GET `/`=200, health ready and `receiver_invoked=false`; metadata=28 stages; explicit F=32 POST=32 symbols/256 samples, `rng_used=false`, 2 receiver arms, 459 runtime entries, 64 decoded bits per conditional Viterbi result; invalid bits=400 |
| Freeze hashes | 22 files/fingerprints declared in the manifest checked; zero mismatches |

The archived evidence screenshot from the live browser is [`m11c-rehearsal-m9m10-1366x768.png`](screenshots/m11c-rehearsal-m9m10-1366x768.png). The existing M11b screenshots remain labeled as screenshots, not live execution. Step 17 has vertical content and may require scrolling at 1366×768; this is normal document scrolling and does not cause horizontal overflow.

## Defense content

- [`DEMO_PRESENTATION_SCRIPT.md`](DEMO_PRESENTATION_SCRIPT.md) now follows the requested 18-step order and gives one short Ukrainian speaking line per screen; the full duration is 8:45, with a 5-minute compressed route.
- [`DEMO_DEFENSE_QA.md`](DEMO_DEFENSE_QA.md) answers all 18 committee questions from the implemented reconstruction and archived results.
- [`DEMO_FINAL_USER_REHEARSAL.md`](DEMO_FINAL_USER_REHEARSAL.md) contains startup, exact navigation, Inspector queries, M9/M10, 8–10-minute and 5-minute flows, a 2-minute emergency fallback, and A–F recovery steps.
- [`DEMO_DEFENSE_CHECKLIST.md`](DEMO_DEFENSE_CHECKLIST.md) includes exact runtime field searches and final navigation order.

## Scientific and artifact integrity

The M11c Inspector addition displays values already present in the selected demo trace and saved study metadata. It does not change receiver, encoder, candidate metric, pseudo-likelihood, posterior, estimator, or Viterbi calculations. ADR-002 remains reconstructed; ADR-005 remains a reconstructed pseudo-likelihood; ADR-016 remains evaluation-only. SCI-02, SCI-03, and SCI-METRIC-02 remain open.

M9b DeltaBER is −0.0011328125 with 95% CI [−0.00322265625, 0.00068359375]. M10b P1 DeltaBER is −0.0003125 with 95% CI [−0.00205126953125, 0.0014453125]. Both intervals include zero. M7b remains TRAIN-only, not independent validation. Stage 28 remains PARTIAL BY DESIGN for paired inference from a single fixture.

Selected historical summaries M5j, M7b, M8b recovery, M9b, and M10b were rehashed and match dashboard values. M11b reports 331 entries across its checked historical integrity manifests with zero mismatches; the final M11c full suite includes the existing M5–M10 hash regressions. No historical artifact or integrity manifest was written.

## Verification results

The final commands and outputs are recorded below after M11c final verification:

| Command/check | Result |
|---|---|
| `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-m11c-final-temp -p no:cacheprovider` | PASS — 944 passed in 25.59s |
| `ruff check src tests` | PASS — All checks passed |
| `ruff format --check src tests` | PASS — 162 files already formatted |
| `node --check src/hf_tcm/studio/static/studio.js` | PASS |
| Local HTTP GET / explicit F=32 POST | PASS — details in HTTP release smoke row above |

## Known limits

- The user has not personally rehearsed this package; automated browser interaction is not a human rehearsal.
- Paired inference cannot be created from the single F=32 demonstration. Historical per-symbol estimator fields remain unavailable where archived schemas contain only aggregates.
- This workspace did not disable the physical network during verification. The GUI uses localhost and local files and has no cloud/API dependency; a disconnected-machine rehearsal remains a user-side optional check.
- The M9/M10 evidence screen may require vertical scrolling at 1366×768.

No Monte Carlo, parameter tuning, new ADR, production-mathematics change, historical-artifact change, or M12 work was performed.
