# M6 H1–H8 causal diagnostic test matrix

**Preparation only.** M6b-prep does not change any H1–H8 status and runs no
fresh-seed trace. This matrix distinguishes an observable trace, an
implementation invariant, and evidence sufficient to establish a causal
explanation. M5j historical per-symbol history remains unavailable.

| Hypothesis | Measurable fields / assumption | Deterministic invariant already available | What could refute the proposed mechanism | Still unavailable / status |
|---|---|---|---|---|
| **H1 — alpha-prime / K-tilde configuration** | Per-symbol `alpha_prime`, signed `k_tilde`, weighted innovation, fluctuating increment. Assumes these fixed reconstructed coefficients are the update policy under study. | Independent one-step [A](1) oracle; exact pre/post delta and frozen C operands. | With frozen coefficients and explicit nonzero innovations, a hand-derived component correction disagrees with trace increments, or the alleged correction component remains zero when its operands imply otherwise. This refutes an implementation-level claim only; it does not show the M5j parameter choice was scientifically good/bad. | No source-derived stability/optimality criterion; no M5j per-symbol innovations. **UNRESOLVED** |
| **H2 — ADR-012 observed-IQ vs [A](5)** | Eight-sample labels, observed-IQ mean, predicted I/Q per hypothesis, exact phase indices. Assumes ADR-012's `(-Im,Re)` reduction corresponds to the source's observation convention. | Hand-reduced literal complex window, independent [A](5) component formula, prediction from pre-state. | A hand-computed ADR-012 mean or [A](5) prediction differs from the implementation for literal operands. That would refute implementation consistency, not settle the source convention. | No independently confirmed source convention or M5j raw sample history. **UNRESOLVED** |
| **H3 — innovation semantics in [A](1)** | Posterior, observed mean, predicted I/Q, explicitly derived `sum_h p[h]*(observed-predicted[h])`. Assumes project recurrence uses the displayed weighted residual. | Independent manual recursion oracle on explicit operands; innovation provenance explicitly says derived, not a raw B4c field. | The actual update delta fails the explicit project equation when independently calculated operands and coefficients are used. | Source indexing/semantic interpretation remains open (SCI-03); M5j operands/history unavailable. **UNRESOLVED** |
| **H4 — correction direction, scale, or sign** | Signed K-tilde, I/Q innovation components, fluctuating/full increments and mu0. | Fixed residual vectors with positive/negative components can be compared against hand-multiplied corrections; decomposition `full=fluctuating+mu0`. | Trace increments contradict direct componentwise arithmetic for the supplied signs and values. This does not establish which signs/source convention authors intended. | No authoritative source-derived M5j correction operands or per-symbol trajectory. **UNRESOLVED** |
| **H5 — posterior-weighted operand / 16 edge hypotheses** | Canonical edge IDs, phase indices, posterior input/output, predicted I/Q, candidate rows, innovation. | Independent enumeration of the 16 hypotheses; normalization, first-edge ADR-004 prior, one continuation transition; keep edge IDs distinct from phases. | An independently enumerated posterior-weighted operand or edge-to-phase map differs from trace while the fixed project conventions are held constant. | Source correspondence of the author's estimator hypotheses to the project-local 16 edges remains unverified. **UNRESOLVED** |
| **H6 — earlier updates affect later metrics** | `post_state(f)`, `pre_state(f+1)`, candidate rows and posterior rows. Assumes the actual adaptive state feeds later B4d rows. | M6a deterministic pair verifies row f uses pre-state and first update affects f+1; future-sample perturbation leaves earlier rows unchanged. | Later candidate metrics remain invariant under a controlled change to the preceding post-state when the next-symbol pre-state is otherwise changed; this would contradict the claimed code dependency. | M5j contribution to BER/path remains unavailable without M5j histories or separately authorized traces/ablation. **SUPPORTED as implementation dependency; M5j causal contribution UNRESOLVED** |
| **H7 — frame-constant forward model vs per-symbol adaptive receiver** | Per-symbol pre/post coefficients and schedule; would need frame-constant comparison policy. Assumes the forward and adaptive coefficient time bases may differ scientifically. | Trace confirms per-symbol state timing; deterministic hand schedule comparison can establish a code-level difference without BER. | Evidence that the compared production forward path actually consumes the same per-symbol state at the same causal timestamps would refute the asserted implementation mismatch for that path. | Source scheduler semantics and performance contribution; no frame-constant control in M6b-prep. **SUPPORTED as a documented model distinction; contribution UNRESOLVED** |
| **H8 — ADR-005 pseudo-likelihood vs source-faithful likelihood** | Candidate metric rows and resulting posterior; assumes the project's squared-residual pseudo-likelihood may differ from source intent. | Independently check the implemented metric-to-likelihood mapping for hand-set rows; this only checks ADR-005 consistency. | A source-derived literal likelihood and ADR-005 produce identical weights/posteriors for the relevant operands, which would refute a numerical likelihood difference for those operands, not generally. | SCI-METRIC-02/source-faithful likelihood unresolved; no source-faithful control implemented. **SUPPORTED as a documented distinction; contribution UNRESOLVED** |

At M6b-prep close, the three fresh-seed traces were prospective. The later
authorized M6b-run addendum records their observed trajectories. They do not by
themselves refute/confirm source meaning, estimate general performance, or
establish root cause. Any ablation or model-convention change needs a separate
frozen question and authorization.

## M6b-run observed evidence (status update; no status inflation)

Exactly three authorized fresh-seed sequences produced paired B/C traces. In
all three, C's post-state first diverged at symbol 0, and pre-state, metric-row,
and posterior divergences first occurred at symbol 1. First final path
divergences occurred at symbols 17, 11, and 10, respectively. This supports
H6 as an implementation dependency and still does not isolate an error cause.

H1-H5 remain **UNRESOLVED** despite finite changing C trajectories and
observed coefficient-error growth. H6 is **SUPPORTED as implementation
dependency; decoded-error contribution UNRESOLVED**. H7 and H8 remain
**SUPPORTED as documented model distinctions; contributions UNRESOLVED**.
M5j historical per-symbol history remains unavailable. The diagnostic output
is not a performance result and does not establish scientific root cause; see
`M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md` for controlled next-test proposals.

## M6c source-equation audit update

The local [A] scans (printed pp. 4–5) are available. Independent tests match
the explicit [A](5) sine/cosine signs and printed [A](1) weighted
residual/update algebra for supplied project operands. The ADR-012 complex
identity is confirmed only under the selected `y=a exp(jθ)` convention. A
literal M1/ADR-002 table verifies the project's 16 edge IDs and phase indices;
the source does not provide a checked `θ/edge ↔ b` mapping. No H1–H5 status is
promoted based on these algebra-only checks. H6 remains supported as an
implementation dependency, not as M5j error attribution; H7/H8 remain model
distinctions whose contribution is unresolved. Full evidence, limits, and
status rationale are in `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md`.

## M6d source-evidence clarification

The available [A] scans show the source definition `b∈0…7`, additive phase
increment `bπ/4`, passband `U_s/U_c` signs, and a two-input/three-output
encoder drawing plus four-node trellis (locators in
`M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md`). They do not provide an adequately
legended table mapping each of the 16 project transitions/output tuples to
`b`. ADR-002 remains only a project assumption. The complex I/Q convention and
sample/time cutoffs are likewise not identified by the passband equations or
the “8 samples per signal element” statement.

For H3, [A](1) explicitly prints the posterior-weighted observed-minus-
predicted residual; whether B4c's operands/posterior are source-equivalent
remains open. For H4, update signs are explicit but numeric `K̃` behavior is
not. The source describes `U⁰` in [A](1) and `U**` in [A](2) in distinct
contexts without stating their identity. H1–H5 therefore remain
**UNRESOLVED**. H6 stays supported only as an implementation dependency; H7
and H8 remain project-model distinctions with contribution unresolved. No
M5j error attribution or root cause is added. Full evidence status and
locators: `M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md`.

## M6e deterministic intervention update

An evaluation-only one-step intervention holds the next observed-IQ window,
ADR-002 canonical 16-edge ordering, beta, and ADR-005 metric fixed and changes
only the estimator state through one explicit [A](1) update. An independent
scalar oracle verifies the update, [A](5) prediction differences, all 16
local squared-residual metric differences, and a separate fixed-prior
posterior response. Signed innovations move the metric row in either
direction; zero innovation may still change coefficients through the
`alpha_prime` forgetting term. The frozen `alpha=1, K_tilde=0` control leaves
the next row unchanged.

This supports H6 as an implementation dependency from update to next
predictions, candidate metrics, and the specified one-step posterior
sensitivity. H1–H5 remain **UNRESOLVED**: these fixtures do not test parameter
quality, source quadrature convention, author innovation semantics, source
correction scale, or author edge labeling. H6's contribution to M5j errors
remains unresolved; H7/H8 remain documented model distinctions with
unresolved contributions. No decoder, historical metric row, M5j record, or
M6b trace was changed or replayed. Details are in
`M6_UPDATE_INTERVENTION_AUDIT.md`.

## M6f deterministic factorial ablation

A two-symbol four-arm test (B frozen, A alpha-only, K correction-only, C
combined) uses the actual B4d sequence API on one explicit deterministic
16-sample buffer. At symbol 0, the 16 metrics, posterior, and weighted
innovation are shared. The independent scalar first-update factorial identity
`C−A−K+B=0` passes within `1e-12`. At symbol 1, changed states produce changed
predictions and ADR-005 metrics; the squared-residual interaction is verified
as `2*8*Σ(d_alpha*d_K)` and is nonzero for this fixture. Actual continuation
posteriors are normalized and match an independent scalar transition /
likelihood oracle. B4d does not export intermediate `q`; the separately
derived `p*T` is labeled an audit value, not a raw operand. A uniform
common-prior sensitivity is reported separately from the actual posterior.

This further supports H6 as a deterministic implementation dependency through
second-symbol metrics and posterior for this fixture. H1–H5 remain
**UNRESOLVED**; the ablation does not establish parameter quality, source
semantics, or author mapping. H6's contribution to historical M5j BER remains
unresolved; H7/H8 contributions also remain unresolved. No decoder, BER, or
performance comparison was made. See
`M6_FACTORIAL_UPDATE_ABLATION_REPORT.md`.

## M6g deterministic multistep feedback audit

The eight-symbol fixture shows that CLOSED_LOOP arms use their own posterior
and derived innovation at every step. COMMON_OPERAND freezes the complete
eight-value innovation stream from B before replay; each arm's own posterior
is diagnostic only in the replay update. B and A match across the two regimes
for all rows. K/C first diverge in post-state after symbol f=1, with metric
and posterior contrasts first appearing at f=2. Factorial state, metric, and
posterior interactions accumulate under both regimes; the common-epsilon
control shows that recursive alpha/K composition alone can produce state
interaction, while CLOSED_LOOP adds arm-specific posterior-weighted feedback.

H1 is **SUPPORTED** for deterministic effects of these fixed policy terms,
but historical M5j contribution remains unresolved. H6 is **SUPPORTED** as
implementation dependency update -> next metrics -> posterior -> later
innovation on this fixture; historical BER causation remains unresolved.
H2-H5 remain **UNRESOLVED** at source-semantic level. H7/H8 contributions
remain **UNRESOLVED**. No decoder, BER, parameter search, or receiver-kernel
change occurred. See `M6_MULTISTEP_POSTERIOR_FEEDBACK_AUDIT.md`.

## M6h deterministic posterior-weight intervention

M6h reads the exact M6g fixture and B/A/K/C traces. It establishes a
same-state algebraic contrast between own posterior weights and same-symbol
frozen-B weights, plus a distinct multistep replay that keeps each arm's own
posterior history while clamping only the correction weights. B/A states,
metrics, and posteriors remain invariant across CLOSED_LOOP,
POSTERIOR_CLAMP, and COMMON_OPERAND; K/C show fixture-specific state, metric,
and posterior contrasts. This refines the project-level posterior-weight
sensitivity observable under H5 and the implementation feedback dependency
under H6. It does not identify author mapping, prove a general mechanism, or
attribute M5j BER. H2-H5 source semantics remain unresolved; H7/H8 model
contributions remain unresolved. Full equations, per-symbol values, and
artifact provenance are in `M6_POSTERIOR_CLAMP_ABLATION_REPORT.md`.

## M7a synthesis boundary

The M6a-M6h findings are consolidated in `M6_MECHANISM_SYNTHESIS.md` to
motivate a proposed independent reconstructed-policy study. They support
testing a compact alpha/K grid; they do not provide an optimum, establish
universal instability, or identify M5j's cause. M7a does not change H1-H8
status: H1 local/multistep effects are supported for tested fixtures, H5
project weight sensitivity is supported while author mapping is unresolved,
and H6 implementation dependency is supported while M5j contribution is
unresolved. H2-H4 remain source-unresolved, and H7/H8 contributions remain
unresolved. The nine-policy grid is not executed in M7a.
