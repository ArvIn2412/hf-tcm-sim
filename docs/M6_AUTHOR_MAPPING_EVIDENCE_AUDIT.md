# M6d — source-evidence audit of author mapping and estimator semantics

**Result:** source clarification dossier, **NOT author-confirmed mapping unless
direct authoritative evidence exists**, **NOT paper-exact implementation**.
This is a source review only. No Monte Carlo, receiver evaluation, tuning, or
new received observations were created. `paper_exact:false` and
`receiver_enabled:false` remain unchanged.

## 1. Source inventory, version, and coverage

| Material | Local identity / version | Evidence reviewed |
|---|---|---|
| [A] original article | `references/source_paper_2026.docx`; authors/title are present in the document; no independent journal/version identifier is recorded in the repository metadata. Local DOCX SHA-256: `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8`; document core modified timestamp 2026-10-26T06:49:00Z. | Full DOCX text/structure was inspected. The equation objects are embedded Office media and are not all represented in extractable paragraph text. Available page scans pp. 4–7 were visually inspected, including Figures 2–3 and equations (1)–(10) where shown. Scans p. 1–3 are absent; visual-only formula/figure content on those pages is **SOURCE_UNAVAILABLE** in this audit. |
| [A] scan p. 4 | `references/key_pages/page-4.png`, SHA-256 `9badaf252cf49f39966ac1df95cfa4abf8ce588c8914a5fc5b363e290b9a89ee` | Equations (1)–(2), legend, estimator and metric prose. |
| [A] scan p. 5 | `references/key_pages/page-5.png`, SHA-256 `1cf330cf21eee47035fc2b6dba57c9e34a8b6150d55106b06c1f8a85b27aa791` | Equations (3)–(6), 8PSK passband/quadrature definitions, generator matrix. |
| [A] scan p. 6 | `references/key_pages/page-6.png`, SHA-256 `571b196c7496e5de2ded8923ff10168c7b2f0fe13ecb278f602ae946abc16053` | Figures 2–3, simulation-parameter bullets, error-rate equation (7), additive disturbance equation (8). |
| [A] scan p. 7 | `references/key_pages/page-7.png`, SHA-256 `404ea3a6a6728771e360f70b064e13af6dc7eac0c4c5df0a8e56f41dbd28bc3e` | Equations (9)–(10), definition of `n`, reported 1.5 dB statement and conclusions. |
| [B] | `references/Автореферат_1-1.pdf`, 18 pages | Existing source audit locates recursion (15) at printed p. 10 (PDF p. 12), posterior discussion and (20) at printed p. 11 (PDF p. 13). It is **EXTERNAL_REFERENCE_ONLY** for claims about [B]. |
| [C] | `references/Раздел_4.pdf`, 42 pages | Existing source audit locates encoder generator/diagram at printed p. 126 (PDF p. 18) and table 4.1 at printed p. 127 (PDF p. 19). It is **EXTERNAL_REFERENCE_ONLY** for claims about [C]. |

The separate filename `Яковів_Гриненко_2026_в3_24_10_2026.docx` is also in
the references folder, but is not treated as [A] unless its document role and
version are established; it is not silently substituted for the supplied
`source_paper_2026.docx`. No author response, email, or external clarification
was available or recorded.

## 2. Evidence hierarchy and source findings

The machine-readable ledger is
[`configs/m6d_source_evidence_matrix.json`](../configs/m6d_source_evidence_matrix.json).
It uses only `SOURCE_EXPLICIT`, `SOURCE_DERIVABLE`, `SOURCE_AMBIGUOUS`,
`RECONSTRUCTION_ASSUMPTION`, `EXTERNAL_REFERENCE_ONLY`, and `UNAVAILABLE`.
It contains no `AUTHOR_CONFIRMED` claims and no author response records.

| Question / source locator | Evidence status | What the source establishes | Boundary |
|---|---|---|---|
| [A](3), printed p. 5; definition immediately below | SOURCE_EXPLICIT | `b(t_i)` is the discrete 8PSK signal parameter, values 0…7; the passband argument includes `b(t_i)Δφ`, with `Δφ=π/4`. | `b` is not explicitly defined as encoder output integer, edge ID, or a particular bit-label conversion. The absolute phase also contains carrier term `ω₀t_i` and `ψ(t_i)`. |
| [A](5), printed p. 5 | SOURCE_EXPLICIT | `U_s=μ_1[-sin(bΔφ)]`; `U_c=μ_2[cos(bΔφ)]`. Together with [A](3), the b-dependent phase increment is `bπ/4`. | The source names sine/cosine components; it does not define complex-baseband I/Q, `(-Im,Re)`, or a universal I/Q axis order. |
| [A](4), printed p. 5 | SOURCE_EXPLICIT | Received passband expression is a sum of `U_s sin(ω₀t_i)` and `U_c cos(ω₀t_i)` plus disturbance. | No complex-envelope transformation or baseband phase origin is supplied there. |
| [A](6), printed p. 5 | SOURCE_EXPLICIT | `μ_1`/`μ_2` depend on amplitude, delay, phase, and sine/cosine channel-coefficient components. | It does not prescribe the fixed M5j coefficients, normalized project gain, or estimator initialization. |
| [A], Figure 2, printed p. 6 | SOURCE_EXPLICIT | Diagram labels inputs `X₀`, `X₁`, outputs `C₂`, `C₁`, `C₀`, and shows a two-stage memory path with taps. The generator matrix is also printed at the bottom of p. 5. | It does not supply a complete table from `(state,input pair)` to output tuple and `b`, or a bit-order declaration for mapping the tuple to 8PSK. |
| [A], Figure 3, printed p. 6 | SOURCE_AMBIGUOUS | The drawing shows four numbered trellis nodes and branch labels. | There is no adequate legend establishing that the edge labels are `b`, no complete 16-transition listing, and no mapping from its state labels to the project’s `(u1[k−1],u1[k−2])`. The drawing cannot support a unique edge-to-b table. |
| [A], simulation bullets, printed p. 6; [A](10), printed p. 7 | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | The simulation says 8 samples per signal element; [A](10) defines `n` as the number of samples over the signal-element duration `T`. | It does not explicitly equate “signal element” to the project symbol, define ZOH, `O+8f…O+8f+7`, absolute sample origin, or B4d estimator tick. |
| [A](1), printed p. 4 and legend | SOURCE_EXPLICIT | The formal update uses `α′` on the previous fluctuating coefficient, a posterior-weighted sum of observed-minus-predicted quadrature residuals multiplied by `K̃`, and adds regular `μ₀` to form the full coefficient. The text calls `P` a-posteriori probabilities and `M=2^(ν+k)`. | Source does not give the M5j fixed numerical coefficients or prove that the project’s 16 ADR-002/003/004/005 hypotheses are its `θ` states. Exact update algebra for explicit operands was independently checked in M6c; operand equivalence is a separate question. |
| [A](1) vs [A](2), printed p. 4 and explanatory text | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | [A](1) uses `U⁰` as the predictor operand, described as depending on prior coefficient estimates and the discrete state. [A](2) uses `U**` in the decoder metric and describes it through estimated channel coefficients supplied to Viterbi and possible discrete states. | The notation and explanatory roles are distinct. The audited source does not establish a general identity, conversion, or same-time evaluation rule between `U⁰` and `U**`; do not collapse them into one project operand. |
| Gray/natural-binary, differential encoding, explicit offset/permutation, bit order | UNAVAILABLE in the reviewed readable evidence | No directly verifiable definition/table for these conventions was located in the readable p. 4–7 scans or the extracted source text relevant to coding/labeling. | Because p. 1–3 visual-only content is not available as page scans and the embedded equation objects are not all text-extractable, this is not a universal claim that no version of [A] contains such information. Request the author’s explicit definition. |

### Explicitly separated source and reconstruction facts

- `b∈{0,…,7}` and its phase contribution `bπ/4` are source-defined/derivable.
- `edge_id=0…15`, M1 state/input order, output bit order `(c2,c1,c0)`, and
  `b=4c2+2c1+c0` are project M1/ADR-002 conventions only.
- The complex identity `(-Im(ae^{jθ}),Re(ae^{jθ}))=(-a sinθ,a cosθ)` is true
  under the selected complex convention. It does not establish the source’s
  demodulator quadratures or their sample-time interpretation.
- [C] table 4.1 uses an integer expression for its own labels; this is
  **EXTERNAL_REFERENCE_ONLY** and does not establish [A]’s mapping. Existing
  M4 review records a discrepancy between that table and [C]’s diagram/generator.
- [B](15) has a structurally similar recursion; it does not transfer [B]
  posterior, coefficient, or scheduling conventions into [A].

## 3. Project’s 16 reconstructed transitions

These values are obtained from the actual `HYPOTHESES`/M1 trellis API and
ADR-002 assumed-natural-binary conversion. Every row is explicitly marked
`project reconstructed; source mapping unresolved`; no row is author-confirmed.

| edge_id | source_state | input_pair | next_state | encoder_output_bits `(c2,c1,c0)` | project_phase_index / project `b` | source evidence / mapping status |
|---:|:---:|:---:|:---:|:---:|---:|---|
| 0 | 00 | 00 | 00 | 000 | 0 | unavailable / project reconstructed |
| 1 | 00 | 01 | 10 | 010 | 2 | unavailable / project reconstructed |
| 2 | 00 | 10 | 00 | 100 | 4 | unavailable / project reconstructed |
| 3 | 00 | 11 | 10 | 110 | 6 | unavailable / project reconstructed |
| 4 | 01 | 00 | 00 | 010 | 2 | unavailable / project reconstructed |
| 5 | 01 | 01 | 10 | 000 | 0 | unavailable / project reconstructed |
| 6 | 01 | 10 | 00 | 110 | 6 | unavailable / project reconstructed |
| 7 | 01 | 11 | 10 | 100 | 4 | unavailable / project reconstructed |
| 8 | 10 | 00 | 01 | 001 | 1 | unavailable / project reconstructed |
| 9 | 10 | 01 | 11 | 011 | 3 | unavailable / project reconstructed |
| 10 | 10 | 10 | 01 | 101 | 5 | unavailable / project reconstructed |
| 11 | 10 | 11 | 11 | 111 | 7 | unavailable / project reconstructed |
| 12 | 11 | 00 | 01 | 011 | 3 | unavailable / project reconstructed |
| 13 | 11 | 01 | 11 | 001 | 1 | unavailable / project reconstructed |
| 14 | 11 | 10 | 01 | 111 | 7 | unavailable / project reconstructed |
| 15 | 11 | 11 | 11 | 101 | 5 | unavailable / project reconstructed |

Two mappings must remain distinct:

1. **Encoder output/trellis edge → `b`:** no unique author mapping is
   identified. Verdict: `AUTHOR_MAPPING_NOT_IDENTIFIABLE_FROM_AVAILABLE_SOURCE_EVIDENCE`.
2. **Known `b` → b-dependent phase increment:** source equations (3)/(5) give
   `bΔφ=bπ/4`, derivable. They do not identify the entire passband/complex
   phase because `ω₀t_i` and `ψ(t_i)` are also present.

Possible unresolved degrees of freedom include a permutation of the eight
labels, phase origin/offset, sign or traversal convention, bit order, and
state-label association. These are examples of information not identified;
they are not claims about what the authors actually implemented. Verdict is
limited to available source evidence and is **not** a claim that the method is
intrinsically unidentifiable.

## 4. Quadrature and time evidence ledger

| Item | [A] evidence | Project convention | Verdict |
|---|---|---|---|
| First/second component names | [A](4)/(5), p. 5: `U_s` and `U_c`; received expression lists sine then cosine. | Stored as two ordered project components, first then second. | Component roles/signs are source-explicit; mapping to axes named I/Q is not. |
| Sine sign | [A](5), p. 5: leading negative inside `[-sin(bΔφ)]`. | `iq_prediction.py` first component is `-μ1 sin`. | `ALGEBRA_MATCH`; no physical axis attribution. |
| Cosine sign | [A](5), p. 5: positive `cos(bΔφ)`. | `iq_prediction.py` second component is `+μ2 cos`. | `ALGEBRA_MATCH`; no physical axis attribution. |
| Complex representation | No `y=I+jQ` equivalence or Hilbert/quadrature demodulator convention appears in the inspected p. 4–7 scans. | `y=a exp(jθ)` and ADR-012 `(-Im,Re)`. | `SOURCE_UNRESOLVED`; project-only convention. |
| Phase reference/carrier | [A](3), p. 5, includes `ω₀t_i`, `bΔφ`, and `ψ(t_i)`; [A](6) includes delay and phase terms. | Zero-delay, real-gain, normalized 8PSK profile. | Source has carrier/channel phase terms; no source basis for equating absolute phase to `bπ/4` alone. |
| Continuous time vs sample | Equations (3)/(4) use `t_i`; p. 7 defines `n` via duration `T`. | Absolute sample/symbol/estimator origins are explicit reconstruction clocks. | Source does not define project’s sample labels, origins, or equality `estimator_tick=symbol_index`. |
| Sampling / ZOH | p. 6 specifies 8 samples per signal element. It does not specify rectangular ZOH on audited text/figures. | ADR-008 rectangular timebase; ADR-012 8-sample mean and causal cutoff. | Sample count source-explicit; pulse shape, symbol equivalence, and mean are reconstruction assumptions. |
| Forecast/update order | [A](1) uses index `i+1` and prior coefficient estimate in its predictor; exact sample cutoff is not given. | B4d predicts from pre-state, observes eight samples, updates after the window, exposes post-state only to next symbol. | Project causality is an implementation contract; source timing equivalence remains unresolved. |

## 5. A(1) operand verdict

| Operand | What [A] states | Project status |
|---|---|---|
| `α′` | Multiplies previous fluctuating estimate; called known coefficient. No fixed value/range in audited equation legend. | `alpha_prime` supplied by fixed reconstructed policy. Algebra placement matched M6c oracle; value is not author-confirmed. |
| `K̃` | Multiplies posterior-weighted residual; described as quasi-stationary cumulants. Numerical construction, sign policy, or fixed value is not fully specified on p. 4. | `k_tilde` componentwise operand; project policy only. |
| `μ₀`, fluctuating/full estimates | Full estimate equals fluctuating plus regular term, [A](1), p. 4. | `mu0`, `fluctuating_iq`, `full_iq` satisfy this decomposition. Initial values and units remain reconstruction choices. |
| Observation `U` | Quadrature observation in [A](1); passband roles `U_s/U_c` appear in [A](4)/(5). | B4c uses ADR-012 eight-sample `(-Im,Re)` mean. Source equivalence unresolved. |
| Prediction `U⁰` | Depends on previous channel-coefficient estimates and the specific discrete parameter, per legend below [A](1). | B4c predictions derive from pre-state full I/Q and the project 16-edge / ADR-002 phase mapping. Only the algebraic update structure matches; operand identity does not follow. |
| Posterior weights `P` | A-posteriori probabilities over discrete parameter states, with sum index `α=1…m`; `M=2^(ν+k)`. | B4c posterior is length 16 under ADR-003/004/005. Source state count/ordering and posterior construction are not demonstrated to match. |
| Innovation | The bracketed residual is explicitly observation minus prediction, summed with posterior weights. | `paper_recursion.py` forms that residual and weights once for explicit operands. M6b weighted innovation is derived read-only; B4c does not export a raw innovation field. |
| `U⁰` vs `U**` | [A](1) and its legend use `U⁰`; [A](2) and its legend use `U**` in a metric/path context. | Project B4c predictions and B4b metric predictions are related in implementation, but are not author-certified as either source object or as identical. | **SOURCE_AMBIGUOUS**; author clarification requested. |

Thus M6c supports (1) formal update arithmetic for explicit operands. It does
not establish (2) that project operands are source-intended operands or (3)
that the reconstructed policy is scientifically identical to [A].

## 6. H1–H8 status after source review

| Hypothesis | New source evidence | Status |
|---|---|---|
| H1 — fixed policy parameters/coefficient behavior | [A](1) calls coefficients known but the audited pages do not give the fixed M5j policy numbers or stability criterion. No tuning or performance inference. | **UNRESOLVED** |
| H2 — quadrature convention | [A](4)/(5) fixes passband sine/cosine components and signs; it does not equate them to ADR-012 complex-baseband axes. | **UNRESOLVED**; formula signs explicit, complex convention unresolved |
| H3 — innovation semantics | [A](1) explicitly has posterior-weighted observed-minus-predicted residual. Whether B4c posterior and operands have identical source semantics is unknown. | **UNRESOLVED**; project algebra match does not settle operand identity |
| H4 — correction sign/scale | Sign/placement of the displayed residual/update is explicit; numeric `K̃` construction and intended coefficient behavior are not. | **UNRESOLVED** |
| H5 — 16-edge hypothesis mapping | Figures 2–3 show a code structure and trellis but no adequate complete edge-to-b legend/table. | **UNRESOLVED** |
| H6 — update affects later metrics | M6a/M6b established the implementation dependency. Source review does not change its scope. | **SUPPORTED as implementation dependency; M5j causal contribution UNRESOLVED** |
| H7 — frame-constant vs per-symbol model | Project forward/receiver schedules differ; source schedule interpretation is not established by this audit. | **SUPPORTED as project model distinction; contribution UNRESOLVED** |
| H8 — pseudo-likelihood distinction | ADR-005 is project pseudo-likelihood; no source-faithful likelihood was established by this source review. | **SUPPORTED as distinction; contribution UNRESOLVED** |

No M5j root cause follows from a missing source table. M5j remains the fixed
reconstructed B/C contrast `DeltaBER=+0.3655078125` and is not reinterpreted.

## 7. Gates and scientific boundary

| Gate | Status |
|---|---|
| [A] p. 4–7 readable evidence and equation/figure locators | READY for reviewed scans; p. 1–3 visual-only details **SOURCE_UNAVAILABLE** |
| Source `b` range and b-dependent phase increment | READY: `b=0…7`, increment `bπ/4` |
| Author edge/output-bit → `b` mapping | **BLOCKED — AUTHOR_MAPPING_NOT_IDENTIFIABLE_FROM_AVAILABLE_SOURCE_EVIDENCE** |
| Author complex I/Q ↔ ADR-012 convention | **BLOCKED / SOURCE_UNRESOLVED** |
| Author sample origin, symbol relation, and update cutoff | **BLOCKED / SOURCE_UNRESOLVED** |
| A(1) explicit algebra vs project kernel | READY for explicit operands (M6c); source operand equivalence still blocked |
| Author response | **NONE recorded** |
| `paper_exact:false`, `receiver_enabled:false` | Preserved |

No ADR is accepted. Existing ADR-002, ADR-005, ADR-012, ADR-013, ADR-014,
ADR-015 and all open questions remain unchanged. Any source-aligned
implementation requires a separate scientific decision and branch after an
authoritative response; this dossier does not authorize that work.
