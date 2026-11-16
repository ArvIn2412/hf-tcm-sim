# REPRO-09 final report

## Verdict

`REPRO_09_SCIENTIFIC_GUI_PARTIAL`

The existing local studio now has a working scientific view and runs actual REPRO-02 → REPRO-03 → REPRO-06C/REPRO-04 paired single-frame experiments. The GUI also launches real REPRO-07 paired Monte Carlo trials, reports their progress/results, supports stop-after-current-pair and resume, and verifies saved manifests. The full milestone is partial because complete trellis/Viterbi-stage exploration, exact 20-sample detail navigation, REPRO-08 B1 integration, archival REPRO-07/08 browsing, and exhaustive long-frame/keyboard-only browser acceptance remain incomplete.

## Source preflight

The primary v7 article `(4)` exists at `references/Яковів_Гриненко_2026_в7 27-10-26(4).docx`, SHA-256 `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3`. Alternate v7 `(6)` is separately present under `references/alternate_versions/`, SHA-256 `190163b9f123e99648ce9dc2d57cb4fdcc24a8a675001009da41cb0ecf6f9a87`. `references/Раздел_4.doc` SHA-256 is `e877a9272da0e8baa0e4eb21256acf1e2112428d3dbf14472d9b12d3239cfd59`; separately retained `references/supervisor/4.pdf` SHA-256 is `97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904`. Article DOCX XML/text and repository source inventory were checked. The legacy binary DOC was hash-verified but not visually rendered; no chapter-equivalence claim is made. Crosswalk limitations and article/project separation are in [REPRO_08_ARTICLE_CROSSWALK.md](REPRO_08_ARTICLE_CROSSWALK.md).

## Implemented screens and APIs

- **Параметри:** F, information seed, channel profile/noise, static path coefficients, channel seed; explicit launch.
- **Передавач:** bits/pairs, Encoder A state and edge traces, phases, 8PSK constellation and ZOH I/Q window.
- **Канал:** received/transmitted I/Q, delayed path contributions, profile and sample/hash metadata.
- **Спільне приймання:** real REPRO-06C metric rows, estimator data and augmented trellis dimensions.
- **Роздільне приймання:** REPRO-04 B0 hard symbols and Hamming rows.
- **Порівняння:** actual BER/SER/error counts and common observation hash.
- **Monte Carlo:** REPRO-07 runner, completed-pair progress, stop at pair boundary, resume, measured BER plot and paired cluster-CI status.
- **Збережені:** hash-verified one-run and Monte Carlo summaries.

The GUI uses the existing M11 localhost HTTP server, with `/scientific`; Windows launch: `python -m hf_tcm.demo_studio --view scientific`. The previous M11 demo remains at `/`.

## Measured control runs

The real Edge identity run at F=32 and noise 0 returned 64 compared information bits and 0 errors in each receiver. Both receiver outputs recorded the exact same observation SHA-256. The deterministic service test also ran a static two-path `[0,3]` case at 32 symbols and produced 259 received samples; selected fixture produced zero errors for both receivers. A Rician AR(1) two-path service run at F=32/noise variance 0.005 completed with finite BER and paired hashes.

The real Edge Monte Carlo smoke used F=32, one independent paired trial, Rician AR(1) path delays `[0,3]`, and complex sample-domain noise variance `0.005`. It completed 1/1 paired trials and saved a measured point. In this particular trial, Joint BER/SER were 0/0; B0 BER was 0.34375 and pair-SER 0.625. The UI correctly reports `exploratory_too_few_independent_trials`; these values are functionality evidence only, not an algorithm comparison result or a claim of receiver superiority.

## Source/scientific limits

`paper_exact:false` remains. Article-v7 source semantics for the literal metric, edge-to-phase assignment, full physical channel process, and Eb/N0 normalization remain unresolved. GUI noise axis is complex sample-domain variance, not physical Eb/N0. Article's 1.5 dB remains a historical source claim; a single-run GUI does not estimate energy gain. B1 is not presented as a supported GUI receiver. B0 has no multipath compensation and can have a BER floor under fading/ISI.

## Remaining work within REPRO-09

Full path-level trellis views, all 16/68 transition-edge details, dedicated 20-sample zoom, complete receiver-estimator panels, keyboard/screen-reader QA, explicit cancellation of a long single run, and browsing legacy REPRO-07/08 result formats are not implemented or not fully verified. Long F=20,000 GUI run was not launched; the UI only exposes it as an explicit user action and the test suite does not claim this acceptance scenario passed.

## Final verification and status matrix

- **Full regression:** `python -m pytest -q --tb=short --maxfail=1 -p no:cacheprovider` — 1167 passed in 54.75 s. The first full run exposed a routing regression in the legacy `POST /api/demo`; after moving it to its own handler, the isolated legacy endpoint test passed and the full rerun passed.
- **Focused GUI/backend tests:** 6 passed. **Scoped Ruff check and format:** passed on all changed Python implementation/test files. **Node syntax:** passed for the scientific UI, translations, and Edge QA driver.
- **Real browser QA:** the Edge CDP run passed at 1366×768 and 1920×1080, including Identity, shared observation identity, actual charts, and a one-pair Monte Carlo UI smoke. The smoke completed 1/1 pair; it is not a statistical pilot.
- **Saved artifacts:** SHA verification passed for 15 single-run manifests and 2 Monte Carlo experiment manifests. REPRO-06B bundle: 76/76 files and 27 SVGs verified. Screenshots are listed above.
- **Historical fingerprints:** the verifier reports 693/694, with the only changed path `src/hf_tcm/demo_studio.py`. This file now accepts `--view scientific` while preserving the prior default M11 launch. No historical M5–M10 result artifact was changed; the literal 694/694 source-fingerprint criterion is therefore not met.

| Acceptance area | Status | Evidence / limit |
|---|---|---|
| Primary source inventory/crosswalk | `PARTIAL` | Exact filenames and SHA-256 recorded; legacy DOC not visually rendered and source ambiguities remain. |
| GUI launch, real transmitter/channel, Joint/Separate paired run | `READY` | Edge Identity plus API tests; both receiver outputs share observation SHA. |
| Transmitter and channel visualization | `READY` | Actual traces from REPRO-02/03; static `[0,3]` delay frame aligns to 259 received samples at F=32. |
| Receiver metrics/estimates and decoded BER/SER | `PARTIAL` | Real REPRO-06C/04 values shown; detailed step-by-step candidate and estimator panels are incomplete. |
| Viterbi/augmented trellis exploration | `PARTIAL` | State/transition summary is available; full selected-edge/survivor-path inspection is incomplete. |
| Paired single-frame comparison and save/load | `READY` | Same observation hash; manifests and traces re-opened and verified. |
| Monte Carlo GUI | `PARTIAL` | Real REPRO-07 runner, progress, stop-at-pair and resume connected; only one browser trial was executed, so no multi-trial statistical GUI acceptance is claimed. |
| Windows browser QA | `PARTIAL` | Edge passed both required viewports; long-frame, full keyboard/accessibility and long-job cancellation scenarios remain unverified. |

`paper_exact:false` remains. No REPRO-10 work was started.
