# SDD ledger — plan: docs/superpowers/plans/2026-11-03-m11g-interactive-simulation-and-projector.md

Workspace: project root. This checkout has no `.git` directory, so no git worktree can be created; user authorized implementation in the current project root. No commit will be made.

Baseline: M11e verified (958 passed, 694/694 historical hashes); M11f subsequently added with 958 passed, Edge 68/68 and same 694 fingerprints. Current source fidelity remains `PAPER_PARTIAL`, `paper_exact:false`, `receiver_enabled:false`.

## Rulings

- Ruling: Implement Code B encoder and trellis preview from Chapter 4 PDF Table 4.2 plus G/Fig. 4.6; disable receiver. The actual source fully enumerates the encoder branches but no compatible complete receiver contract exists. Cost if wrong: the preview may encode a register convention differently; mitigate with all 64 source rows, polynomial checks and zero-reset/state-transition tests.
- Ruling: expose Code 2 `B` as the source-named manipulation parameter, not as an asserted absolute 8PSK phase. Article-v7/ADR-002 absolute phase mapping is a separate unresolved model. Cost if wrong: less direct 8PSK presentation in B mode, but avoids invented phase semantics.
- Ruling: restrict encoder A input to 2–64 even bits and B preview to 2–256 even bits. Existing B4d API caps 64 input bits; increasing this through the receiver would require model/performance review. Cost if wrong: B preview upper bound may be unnecessarily conservative.
- Ruling: A initial state is read-only `(0,0)` and B preview reset is read-only zero. Only source/API-supported initial states can be offered; no decoder math changes.
- Ruling: Table 4.2 transition IDs enumerate input pairs `00,10,01,11`, so `Q=4Y+X0+2X1`; this differs from ordinary binary flattening of `(X0,X1)`. Tests caught and corrected the initial swapped branch-id assumption before UI integration. Cost if wrong: preview labels would disagree with the source row numbers.

## Progress

- Source review: complete. Available Chapter 4 PDF pages visually reviewed (printed pp.126–129, 141); article v7 named file absent, source_paper_2026.docx and M11f article audit available. Separate `Раздел_4.doc` and `4.pdf` absent; `references/Раздел_4.pdf` available.
- Task 1: complete — separate A/B source-to-code audit written; B receiver/phase integration explicitly blocked by source contract gaps.
- Task 2: complete — input parser tests, local file import, supported parameter controls, explicit A POST and isolated B preview implemented.
- Task 3: complete — 8/20/160/full-frame windows, arbitrary sample slider, symbol navigation/playback, runtime charts and synchronized trellis/path verified.
- Task 4: complete — projector controls/theme/sidebar/keyboard, responsive graph layout and dark SVG label contrast verified in Edge at both target viewports.
- Task 5: complete — five M11g reports created; PLAN/NEXT_TASK/BUILD_VERIFICATION updated; pytest 977 passed; Ruff check/format and Node syntax/helper tests passed; Edge QA 106/106; M5-M10 fingerprints 694/694 unchanged.

Final source-alignment verdict is PARTIAL because the separately named `Раздел_4.doc`, `4.pdf`, and article-v7 source file are not present; the available Chapter 4 PDF and project source-paper materials were audited. Code B remains preview-only. No Monte Carlo, production receiver math, or historical output was changed.
