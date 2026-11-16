# M6c — independent source-equation and quadrature-convention audit

**Classification:** source/algebra audit; no performance experiment, no new
receiver observations, no M6b/M5 rerun, no tuning, and no decoder change.
`paper_exact:false` and `receiver_enabled:false` remain in force. Scope stays
`reconstructed_offline`, `L=1`, real `a>0`, zero delay, normalized 8PSK,
rectangular ZOH 8 samples/symbol, and accepted ADR-005/012/013/014/015.

## 1. Source availability and exact transcriptions

The local [A] source is available as `references/source_paper_2026.docx`; the
equations were visually audited against `references/key_pages/page-4.png` and
`page-5.png`. The equation scans show printed page numbers 4 and 5. No attempt
was made to infer missing definitions from [B] or [C]. In the transcriptions
below, typesetting is normalized to readable subscripts/superscripts; the
mathematical signs, summation range, and equation numbers follow the scans.

[A](1), printed p. 4, gives the fluctuating and full coefficient estimates:

\[
\widetilde{\mu}_{j,i+1}^{*(l)}=\alpha'\widetilde{\mu}_{j,i}^{*(l)}+
\widetilde K_{\mu,j}^{(l)}\sum_{\alpha=1}^{m}
P_{i+1}^{(l)}\!\left(\theta_{i+1}^{(l),\alpha}\mid
\bar\mu_{i+1}^{0(l)}\right)
\left[U_{j,i+1}^{(l)}-U_{j,i+1}^{0(l)}\!\left(
b_{i+1}^{(l)}(\theta_{i+1}^{(l),\alpha})\right)\right],
\qquad
\mu_{j,i+1}^{*(l)}=\widetilde{\mu}_{j,i+1}^{*(l)}+\mu_{j0}^{(l)},
\quad j=1,2,\quad l=1,\ldots,L.
\]

The page text calls `P` the a-posteriori probabilities of the discrete
parameter states and defines `M=2^(ν+k)` for their total count. The printed
paragraph calls `α′`, `K̃`, and other coefficients known, but does not give
their numeric values or an independent initialization rule on this page.
The exact semantic relationship between the displayed conditioning term and
the implementation's explicitly supplied posterior remains a reconstruction
question beyond the algebraic update.

[A](5), printed p. 5, gives the two passband quadratures (with
`Δφ=π/4` stated immediately above):

\[
 U_{s,i}^{(l)}=\mu_{1,i}^{(l)}[-\sin(b_i^{(l)}\Delta\phi)],\qquad
 U_{c,i}^{(l)}=\mu_{2,i}^{(l)}[\cos(b_i^{(l)}\Delta\phi)].
\]

The same page's [A](4) writes the passband as a sine component plus a cosine
component. [A](6) defines `μ1`/`μ2` from amplitude, delay, phase, and channel
quadrature components. It does not define a complex-baseband sample convention
equivalent to ADR-012.

## 2. Definition and provenance matrix

| Quantity | Source category | Source definition / indices / dimension | Project operand and status |
|---|---|---|---|
| `j` | SOURCE_EXPLICIT | Quadrature component index, `j=1,2`, [A](1), p. 4 | Last-axis I/Q-like component in `paper_recursion.py`; project order `(first,second)`. Source's `s,c` labels in [A](5) suggest sine/cosine components, but do not prove ADR-012 axes. |
| `l`, `L` | SOURCE_EXPLICIT | Path/ray index, `l=1,…,L`, [A](1), p. 4; path language appears in p. 4–5 | Project profile fixes `L=1`. Delay is zero by reconstruction profile, not by the source equation. |
| `i`, `i+1` | SOURCE_AMBIGUOUS | Adjacent recursion labels in [A](1), p. 4 | Estimator integer clock is explicit in B4d. Equality to symbol index is only a caller-supplied schedule; no global source clock/sample interpretation follows from this equation alone. |
| `α′` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Named known coefficient multiplying the previous fluctuating estimate in [A](1), p. 4; no numeric value or range given there | `alpha_prime` scalar. Dimensionless for a dimensionally consistent same-unit coefficient recursion; numerical value and admissibility are reconstruction choices. |
| `K̃_{μ,j}^{(l)}` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Named quasi-stationary cumulant multiplying the posterior-weighted residual in [A](1), p. 4; no value, sign, or construction is defined there | `k_tilde[...,j]`; applied componentwise. Exact source construction/value unavailable. Do not substitute [B](16)–(19) without source authorization. |
| `P_{i+1}^{(l)}(…)` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | A-posteriori probability over discrete parameter states; `α=1,…,m` in the sum, [A](1), p. 4; `m` is the stated discrete-state count | B4c posterior vector is length 16 under ADR-002/003/004/005. Whether the source's `m` and `θ` set equal this project edge set is not established. `q` intermediate transition distribution is unavailable from B4c. |
| `U_{j,i+1}^{(l)}` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Observed quadrature operand in the residual in [A](1), with passband quadratures described by [A](4)/(5), p. 5 | B4c `observed_iq` is the ADR-012 mean of `(-Im,Re)` over eight samples. Source does not define that complex-to-I/Q reduction, mean, sample clock, or ZOH convention. |
| `U^0_{j,i+1}(b(θ))` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Predicted quadrature depending on previous coefficient estimates and discrete parameter, as explained below [A](1), p. 4 | B4c prediction operand `(16,2)` is generated from pre-state full I/Q and project phase indices via `iq_prediction.py`; the source-to-edge and source-to-phase identification is unavailable. |
| `μ̃`, `μ*`, `μ0` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Fluctuating, full, and regular coefficient components; full is fluctuating plus regular, [A](1), p. 4 | `fluctuating_iq`, `full_iq`, and explicit `mu0`. Their decomposition matches the printed identity. Source units/normalization and initial values are not fully specified in the equation legend. |
| `b_i^(l)` | SOURCE_EXPLICIT / SOURCE_AMBIGUOUS | Discrete 8PSK parameter; [A](5), p. 5, says it takes values 0…7 and `Δφ=π/4` | Project `phase_index` is 0…7 from ADR-002 natural-binary output labeling. No source table proves `b↔(c2,c1,c0)` or `b↔edge_id`. |
| `μ1`, `μ2` | SOURCE_EXPLICIT | Defined by [A](6), p. 5, from amplitude/delay and channel coefficient quadratures | Project full estimate pair is passed explicitly. Equating the project pair to the source quantities over a whole frame/symbol is a reconstruction assumption. |
| `Δφ` | SOURCE_EXPLICIT | `π/4`, [A](5), p. 5 | Same numerical angular step as the project's eight phase indices. This does not establish origin or labeling. |
| Physical units, complex-envelope convention, sample-time origin | UNAVAILABLE | Not defined by [A](1)/(5) on audited pages | No physical Eb/N0 or complex I/Q convention is inferred. ADR-012 remains project-only. |

## 3. Independent [A](5) audit

Manual values were formed from scalar trigonometry, not from
`iq_prediction.py`. For `μ1=2`, `μ2=4`, and `b=0,…,7`, the oracle is:

| `b` | `U_s=-μ1 sin(bπ/4)` | `U_c=μ2 cos(bπ/4)` |
|---:|---:|---:|
| 0 | 0 | 4 |
| 1 | `-√2` | `2√2` |
| 2 | -2 | 0 |
| 3 | `-√2` | `-2√2` |
| 4 | 0 | -4 |
| 5 | `√2` | `-2√2` |
| 6 | 2 | 0 |
| 7 | `√2` | `2√2` |

The new deterministic tests also check unequal (`3,5`), equal negative
(`-2,-2`), and zero/negative (`0,-3`) coefficients. The code returns the
source's first-then-second order and matches the formula and all sign
boundaries within explicit `1e-14` tolerance. **Verdict: ALGEBRA_MATCH for
the isolated [A](5) transform.** This does not establish the project mapping
from edge/hypothesis to `b`.

## 4. ADR-012 and complex quadrature convention

For the selected mathematical representation `y=a exp(jθ)`, direct expansion
gives `Re(y)=a cos θ` and `Im(y)=a sin θ`. ADR-012 maps one sample to
`(-Im(y),Re(y))`, hence `(-a sin θ,a cos θ)`. This equals the [A](5)
two-component expression under the additional identification `μ1=μ2=a` and
`bπ/4=θ`. Eight-angle hand checks and a literal eight-sample ADR-012 mean test
pass. The implementation's observation code takes `(-imaginary,real)` and
then averages the eight samples; candidate predictions use the ordered
quadrature pair returned by `iq_prediction.py`.

This is an algebraic identity under the selected `θ`, coefficient, and
complex-number convention. It does **not** show that [A] uses this complex
envelope, this time origin, sample interpretation, ZOH waveform, or the
ADR-012 mean. Real/imag axes and component signs are internally explicit;
their author correspondence remains unresolved. **Verdict: ALGEBRA_MATCH
within ADR-012; SOURCE_UNRESOLVED for source equivalence.** No ADR was changed.

## 5. Canonical 16-edge / 8-phase mapping

The following is the project's M1 enumeration and ADR-002 assumed-natural-
binary mapping only. IDs are local row indices, not author `θ` labels. `b`
shown is the phase index the reconstruction uses in [A](5).

| edge ID | source state | input pair | output `(c2,c1,c0)` | next state | project `b` | mapping provenance |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 00 | 00 | 000 | 00 | 0 | M1 + ADR-002 |
| 1 | 00 | 01 | 010 | 10 | 2 | M1 + ADR-002 |
| 2 | 00 | 10 | 100 | 00 | 4 | M1 + ADR-002 |
| 3 | 00 | 11 | 110 | 10 | 6 | M1 + ADR-002 |
| 4 | 01 | 00 | 010 | 00 | 2 | M1 + ADR-002 |
| 5 | 01 | 01 | 000 | 10 | 0 | M1 + ADR-002 |
| 6 | 01 | 10 | 110 | 00 | 6 | M1 + ADR-002 |
| 7 | 01 | 11 | 100 | 10 | 4 | M1 + ADR-002 |
| 8 | 10 | 00 | 001 | 01 | 1 | M1 + ADR-002 |
| 9 | 10 | 01 | 011 | 11 | 3 | M1 + ADR-002 |
| 10 | 10 | 10 | 101 | 01 | 5 | M1 + ADR-002 |
| 11 | 10 | 11 | 111 | 11 | 7 | M1 + ADR-002 |
| 12 | 11 | 00 | 011 | 01 | 3 | M1 + ADR-002 |
| 13 | 11 | 01 | 001 | 11 | 1 | M1 + ADR-002 |
| 14 | 11 | 10 | 111 | 01 | 7 | M1 + ADR-002 |
| 15 | 11 | 11 | 101 | 11 | 5 | M1 + ADR-002 |

The test independently hard-codes the state/input/output/next-state/phase
table and verifies the implementation's canonical order. Source [A], p. 5,
defines the range and use of `b` but does not give this edge table. Nor does
it explicitly equate the project's four encoder memory states with the
source's discrete state parameter set (`M=2^(ν+k)`). **Verdict:
RECONSTRUCTION_ONLY for this table; SOURCE_UNRESOLVED for author mapping.**

## 6. One-step [A](1) and innovation identity

The numeric manual fixture uses
`previous=[0.4,-0.3]`, `α′=0.6`, `K̃=[0.25,-0.5]`,
`μ0=[0.1,0.2]`, `Y=[1.2,-0.4]`. Of 16 explicitly indexed predictions,
`U⁰_0=[0.2,-0.3]`, `U⁰_1=[0.6,0.1]`; posterior weights are `0.25,0.75`
on those entries and zero elsewhere. A scalar loop gives

`innovation = Σ_h p_h(Y-U⁰_h) = [0.7,-0.4]`;
`new fluctuating = α′ previous + K̃ ⊙ innovation = [0.415,0.02]`;
`new full = new fluctuating + μ0 = [0.515,0.22]`.

The independently calculated values match the actual
`update_quadrature_estimates()` result componentwise. Posterior sum is one;
the test checks component order, sign, coefficient scaling, alpha placement,
and full/fluctuating decomposition. The production function applies the
posterior once inside the sum, `K̃` once after the sum, `α′` only to the prior
fluctuating state, and adds `μ0` only to form the full state. It does not
normalize posterior; it validates the supplied row.

For normalized weights `p_h` and a hypothesis-independent observation `Y`,
`Σ_h p_h(Y-U⁰_h) = Y Σ_h p_h - Σ_h p_h U⁰_h = Y-Σ_h p_h U⁰_h`.
The 16-entry scalar-loop test checks this identity with unequal normalized
weights. The actual update API takes the posterior vector and the
`observed_iq` / `predicted_iq` arrays and forms the weighted residual itself;
M6b's named weighted innovation is therefore a **derived diagnostic**, not
an exported raw B4c field. The API sums over all supplied hypotheses (16 in
B4d); the `q` transition-predicted distribution is unavailable from B4c, and
no extra posterior update was performed. No double posterior weighting is
present in the inspected update path.

**Verdict:** ALGEBRA_MATCH for the actual project one-step operands and the
printed [A](1) residual/update structure. SOURCE_UNRESOLVED for whether the
project posterior, prediction operands, clock, and 16-edge index set have the
same meanings as the paper's `P`, `U⁰`, `i`, and `m`.

## 7. Root-cause hypotheses H1–H8

| Hypothesis | M6c evidence | Status after M6c |
|---|---|---|
| H1 — fixed `α′/K̃` policy | One-step arithmetic is correct for explicit operands. No tuning, stability criterion, or M5j per-symbol inputs were examined. | **UNRESOLVED** |
| H2 — ADR-012 vs [A](5) convention | Complex identity holds under chosen `y=a exp(jθ)` / `θ=bπ/4`; source complex-envelope, time origin, and sample convention are not stated by (3)–(6). | **UNRESOLVED**; convention-specific algebra matches |
| H3 — innovation semantics | Source residual is observed minus predicted; project kernel applies the same posterior-weighted residual. Meaning/provenance of source posterior and prediction remains uncertain. | **UNRESOLVED**; implementation algebra matches |
| H4 — correction direction/sign/scale | Signed componentwise update agrees with direct scalar oracle; source gives no numeric or sign/stability prescription for `K̃` or `α′`. | **UNRESOLVED** |
| H5 — posterior weighting / 16 hypotheses | Project's 16 local rows and ADR-002 phase values independently enumerated; paper's `m`/`θ` mapping is not established. | **UNRESOLVED** |
| H6 — update affects later metrics | M6a/M6b establish the implementation dependency: post-state at symbol `f` can feed candidate metrics at `f+1`. M6c does not attribute historical errors. | **SUPPORTED as implementation dependency; M5j causal contribution UNRESOLVED** |
| H7 — frame-constant vs symbol-adaptive models | Documented project schedule distinction only; not a source-equation result. | **SUPPORTED as a model distinction; contribution UNRESOLVED** |
| H8 — ADR-005 pseudo-likelihood vs source likelihood | ADR-005 is explicitly project pseudo-likelihood; this audit did not derive a source-faithful likelihood. | **SUPPORTED as a model distinction; contribution UNRESOLVED** |

No causal root cause or explanation of M5j errors is established. Historical
M5j per-symbol states remain unavailable. Deterministic algebra fixtures do
not re-interpret M5j results.

## 8. Verdicts, gates, and next research decision

| Audit item | Verdict |
|---|---|
| [A](1) printed residual/update algebra vs `paper_recursion.py` explicit operands | ALGEBRA_MATCH for project operands; source semantics partly unresolved |
| [A](5) signs, coefficient/component order, eight angles | ALGEBRA_MATCH |
| ADR-012 `(-Im,Re)` vs `y=a exp(jθ)` | ALGEBRA_MATCH under selected convention; SOURCE_UNRESOLVED as author convention |
| Canonical edge IDs to phase index | RECONSTRUCTION_ONLY under M1/ADR-002 |
| Author `θ`/edge/phase mapping | SOURCE_UNRESOLVED |
| Physical units, source sample clock, complex-baseband equivalence | UNAVAILABLE |
| Receiver or performance correctness | NOT_TESTED by this audit |

`SCI-02`, `SCI-03`, `SCI-METRIC-02` remain OPEN. No ADR is accepted or
changed. If an author-faithful edge/phase interpretation is required, the
smallest next action is a source clarification or a higher-resolution
authoritative mapping/table for `b_i^(l)` and `θ`; do not infer it from [C]
or natural-binary labeling. If source clarification is unavailable, retain
the reconstructed-only gate and do not change receiver behavior.

## 9. Verification and scope

The new tests use only fixed mathematical vectors, explicit complex values,
and current deterministic APIs. They contain no RNG/noise/bit generation,
receiver sequence execution, BER/SER experiment, or output-writing behavior.
Full test/Ruff results and historical hash checks are recorded in
`docs/BUILD_VERIFICATION.md` after final verification.

## M6d source-evidence follow-up

The M6d full-source ledger at `M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md` now
records the source identity/hash, readable scan coverage, source locators, and
the distinction between explicit, derivable, ambiguous, project-only, external,
and unavailable evidence. It additionally records the page-6 encoder/trellis
figures: they show two labeled inputs, three labeled outputs and four numbered
trellis nodes, but do not establish a complete edge/output-to-`b` mapping.
The source does define `b` as 0…7 and its additive phase increment as
`bπ/4`; the source does not thereby identify encoder output bits with that
integer or define a complex-I/Q convention.

M6d also clarifies that [A](1) describes `U⁰` through previous coefficient
estimates and the discrete parameter, while [A](2) uses `U**` for the
decoder-metric prediction. Their descriptions differ; no identity between
them is inferred. The M6c project-algebra verdict remains valid for explicit
operands, but source operand equivalence remains open. No M6j result,
receiver behavior, ADR, or scientific gate changed. See the M6d ledger and
author-clarification package for the exact boundary and unanswered questions.
