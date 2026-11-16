# M11d scientific gaps and correction record

No production math or evidence was changed. These source ambiguities remain open.

## SCI-METRIC-02 — [A](2) residual metric

The article's p.4 equation image was visually inspected: it does not explicitly show a squared norm/residual, while production uses accumulated squared residuals. Do not infer a typographical error. For a fixed symbol and candidates, squaring a nonnegative Euclidean distance preserves ordering. Across accumulated path costs, it need not: path residuals `[0,3]` and `[2,2]` sum to 3 versus 4, while squared totals are 9 versus 8. Thus Viterbi path ordering may differ. Under ADR-005, `exp(-βF)` also changes concentration; changed posterior weights change the weighted innovation and later recursive states/predictions. BER/SER from prior runs must not be reinterpreted or recomputed under this UX task. SCI-METRIC-02 remains OPEN; ADR-005 remains reconstructed pseudo-likelihood.

## Phase increment / absolute phase correction

Article p.5 defines Δφ=π/4 as an increment in the phase expression. This does not establish an absolute initial phase φ₀=π/4. ADR-002's absolute edge-to-phase mapping remains a project reconstruction. New UI/help uses “phase increment Δφ” for the article statement and labels the absolute mapping reconstructed. The older wording in `docs/MATHEMATICAL_MODEL.md` is preserved and followed by an explicit correction note.

## Other open items

- No complete source-author-confirmed mapping of all 16 project edges to phase labels was found; ADR-002 remains reconstructed.
- Project innovation indexing, μ₀ anchor, prior/transition rule and posterior contract are not fully specified by [A]; SCI-02/SCI-03 remain open.
- Project conditional Viterbi initialization/termination/tie conventions are not fully established by the source.
- Demo channel is fixed gain plus explicit deterministic noise. It is not a physical HF channel experiment and is not independent performance evidence.
- M9/M10 archived intervals include zero. No established anchored superiority claim is presented.

See the item-by-item locations and implementation/test/GUI mapping in `M11D_SOURCE_FIDELITY_AUDIT.md`.
