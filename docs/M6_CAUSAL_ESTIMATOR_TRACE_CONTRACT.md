# M6a — causal estimator trace contract

**Status:** isolated causal estimator trace diagnostics, **NOT new performance evidence**, **NOT established root cause**, **NOT paper-exact joint receiver**. `paper_exact:false` and `receiver_enabled:false` are unchanged. No M5j/M5h rerun, new random sample, Monte Carlo, parameter search, or receiver-mathematics change occurred.

## 1. Trace source and provenance

`hf_tcm.evaluation.reconstruction_causal_trace.run_reconstruction_causal_trace_pair()` accepts one already supplied complex sample vector, its absolute sample labels, clock origins, a shared initial `ReconstructionEstimatorState`, beta, and the explicit adaptive update schedule. The API has no reference-bit or channel-truth operand and generates no samples/noise. It invokes the actual B4d `run_reconstruction_posterior_estimator_sequence(..., include_history=True)` once for each of B and C, copies the resulting B4c rows, freezes those exact local metric rows, then invokes B5b exactly once per mode.

The contract is fixed to the accepted `reconstructed_offline`, L=1, zero-delay, normalized 8PSK, rectangular ZOH 8sps, ADR-012 observed-IQ and ADR-005 pseudo-likelihood profile. The frozen mode uses the existing B policy (`alpha_prime=1`, zero `K_tilde`, zero `mu0`); adaptive mode uses caller-specified fixed diagnostic coefficients. B/C share samples/hash, initial state, beta, and all clock origins. The implementation is instrumentation and orchestration in `evaluation/`; it does not edit B4/B5 kernels.

## 2. Per-symbol clocks and causal flow

For symbol `f` with symbol origin `O`, the trace copies window `[O+8f, O+8f+7]`; prediction cutoff is `O+8f-1`; observation/posterior cutoff is `O+8f+7`. Symbol index and estimator tick are stored separately, and the adapter requires each clock to advance by one per completed symbol without equating their origins. A processing segment index/local position is reporting metadata only; continuation passes the current state and posterior across segment boundaries.

Candidate metrics and sample predictions come from B4c's actual row computed with the pre-observation state. The current row posterior is copied from the same B4c result. The estimator update consumes the current row's observed-IQ mean, posterior, and 16 predictions, and returns the post-state available only to the next symbol. The trace does not recompute posterior or metrics. After all segments, the immutable `(F,16)` rows are passed to one conditional Viterbi decode per mode.

First row provenance is `first_edge` with the ADR-004 initial edge prior and no transition. Each later row is `later_edge` with the immediately preceding posterior and the ADR-003 transition plus current metric likelihood. B4c does not return the intermediate transition-predicted distribution `q`; the trace explicitly leaves `transition_predicted_posterior=None` rather than invoking another update. The trace stores the canonical 16 hypothesis IDs and separately the B4c phase indices; an edge ID is not a transmitted 8PSK phase.

## 3. Captured and unavailable values

| Value | Trace status and source |
|---|---|
| Pre/post fluctuating and full I/Q state | Copied from actual immutable B4c state handoff |
| `mu0`, `alpha_prime`, `K_tilde` | Exact explicit per-step operands supplied to B4d |
| Observed I/Q | Actual B4c eight-sample arithmetic-mean operand; compact summary, not raw samples |
| Predicted I/Q `(16,2)` and per-sample prediction `(16,8,2)` | Actual B4c result and candidate-metric row |
| Candidate metric `(16,)`, edge mode, phase index, sample/cutoff labels | Actual B4c candidate result |
| Posterior input and posterior after observation | Prior/posterior actually supplied to and returned by B4c; posterior sum is recorded |
| Weighted innovation `(2,)` | Read-only algebraic derivation from the actual posterior, observed mean, and predicted I/Q; marked `derived_from_actual_B4c_posterior_observation_prediction`, not a returned B4c field |
| Transition-predicted posterior `q` | **UNAVAILABLE** from B4c output; recorded as `None`; no second posterior call |
| Raw observed eight complex samples in the row | Not duplicated in trace; exact window labels plus copied B4c observed mean are retained |
| M5j historical per-symbol state/metric trajectory | **HISTORY UNAVAILABLE**; not reconstructed from final estimates |

All trace arrays are defensive immutable copies with fixed dtype/shape and finite-value checks. The metric matrix, decoder result, decoded bits/path, best conditional cost, and structural path-validity flag are retained after the one final B5b call.

## 4. B/C comparison and deterministic observations

`compare_reconstruction_causal_traces()` compares pre/post states, posterior vectors, metric rows, coefficient increments, and final-path edges using explicit `rtol`/`atol`. It reports the earliest post-update estimator-state divergence and earliest candidate-metric divergence as descriptive labels only; neither is a causal attribution of bit errors.

`summarize_reconstruction_causal_trace_pair()` provides a compact
JSON-compatible view with per-symbol coefficient estimates, update norms,
posterior sums, metric-row equality, decoded edges, and final decoded bits/path
and validity. It omits the full 16-row metric/prediction histories; callers
retain the immutable trace object when full detail is needed.

The deterministic six-symbol explicit complex fixture (symbol origin 63, first symbol 5, estimator tick 41, beta 0.7, fixed mismatched initial pair `[0.42,0.91]`, alpha 0.85, `K_tilde=(0.35,-0.2)`, zero `mu0`) uses the frozen M5j B/C policy coefficients and gives first post-state divergence at symbol 5 and first candidate-metric divergence at symbol 6. The current symbol's B/C metric row is equal before either update; the first update affects the next row. In this fixture, later posterior rows differ from symbol 6 while the decoded edge paths first differ at symbols 9 and 10. This illustrates that metric divergence and final-path divergence are distinct observations; neither identifies bit-error cause. These deterministic trace observations are not M5j data and are not performance evidence. Tests also exercise F=1,2,4,6 at deterministic noiseless real gains 0.75 and 2.0, with an explicit literal complex perturbation for F>=2; no RNG is used.

Monolithic and segment partitions preserve the tested trace states, posterior, frozen metric rows, decoded path, and one-decode lifecycle. Segment labels may differ because they are partition metadata; estimator/posterior state is not reset at a segment boundary.

## 5. Independent mathematical checks

The focused tests use a manual [A](1) oracle formed directly from the recorded posterior-weighted residual, then independently check the expected pre/post fluctuating estimate and `full_iq = fluctuating_iq + mu0`. A separate posterior oracle enumerates ADR-004 support from M1 current states, applies shifted `exp(-beta*metric)` weights, and for continuation enumerates structurally allowed successors from the 16 `HYPOTHESES`; it does not call the production posterior-update helper as its oracle. Tests check normalization, first-edge/no-transition, one continuation transition, canonical order, the eight-sample clock mapping, no update-before-metric, next-symbol-only state use, frozen B invariance, actual nonzero C correction, trace immutability, finite values, same received digest, and absence of reference/truth receiver inputs.

## 6. H1–H8 diagnostic status

| Hypothesis | New trace observable / independent invariant | Deterministic evidence and limitation | Status |
|---|---|---|---|
| H1 alpha-prime / `K_tilde` configuration | Per-symbol operands, posterior-weighted innovation, signed coefficient increment; independent [A](1) oracle | The selected deterministic schedule updates according to the explicit algebra; no stability criterion or source-derived optimum is known, and this does not identify M5j cause | **UNRESOLVED** |
| H2 ADR-012 observed-IQ vs [A](5) | Eight-sample window labels, observed mean, per-hypothesis prediction, and hand mapping checks | Clock and I/Q arithmetic invariants hold for reconstructed profile; source convention and its M5j contribution remain unverified | **UNRESOLVED** |
| H3 [A](1) innovation semantics | Actual operands and independently calculated weighted residual | Algebraic implementation matches the explicit project equation; paper notation/source semantics remain open (SCI-03) | **UNRESOLVED** |
| H4 correction direction/scale/sign | Signed `K_tilde`, innovation, component increments, and full/fluctuating decomposition | Deterministic nonzero update agrees with explicit operands; no authoritative source-derived coefficient direction or M5j trajectory is available | **UNRESOLVED** |
| H5 posterior estimator operand / 16 edge hypotheses | Canonical edge ordering, posterior inputs/outputs, predictions, phases, metric rows | Internal mapping/order and normalization invariants hold; source correspondence of estimator hypotheses is unverified | **UNRESOLVED** |
| H6 later metrics depend on prior updates | `post_state(f)` equals `pre_state(f+1)`; row `f` invariant to its own post-update and future samples | Deterministic pair first differs in state after symbol 5 and in candidate metric at symbol 6; confirms implementation dependency only, not M5j error contribution | **SUPPORTED as implementation dependency; M5j causal contribution UNRESOLVED** |
| H7 frame-constant forward vs per-symbol adaptive model | Trace exposes per-symbol coefficient/state schedule | This is a documented model/scheduling distinction; no frame-constant control or source scheduling proof was run here | **SUPPORTED as a distinction; performance contribution UNRESOLVED** |
| H8 ADR-005 pseudo-likelihood vs source-faithful likelihood | Actual metric rows/posterior are traceable under ADR-005 | Trace confirms which reconstruction likelihood was used, not source-faithful likelihood or which likelihood is scientifically intended (SCI-METRIC-02) | **SUPPORTED as a distinction; performance contribution UNRESOLVED** |

No hypothesis among H1–H5 is proved by a changing coefficient trajectory. No M5j bit errors are reinterpreted from this fixture.

### Independent controls still needed

The M6a tests are controls of implementation invariants, not source-model
validation. The smallest follow-up for each unresolved mechanism would be:

- **H1:** a predeclared finite-state algebra fixture with fixed nonzero
  innovations and the already frozen M5j coefficients; report componentwise
  increments and boundedness only. No alternate coefficients or BER ranking.
- **H2:** hand-map one literal complex 8-sample symbol through the ADR-012
  observed-IQ reduction and [A](5) prediction, then compare each component
  against an independently transcribed source convention. Source convention
  remains a prerequisite.
- **H3:** a source-review control that transcribes the [A](1) indices/signs
  independently, paired with a hand calculation from explicit operands. The
  current oracle verifies project algebra only.
- **H4:** two fixed residual vectors with positive/negative I and Q components;
  calculate expected signed corrections on paper and compare componentwise.
  This checks implementation response, not author-intended coefficient choice.
- **H5:** enumerate all 16 edge hypotheses independently, check the
  posterior-weighted estimator sum and separately verify edge-to-phase mapping;
  a source-derived correspondence is still needed.
- **H6:** already controlled by the M6a same-row B/C comparison and future
  sample perturbation test. To estimate contribution in new data would require
  a separately frozen trace capture and an explicitly specified ablation.
- **H7:** compare hand-specified frame-constant and per-symbol schedules on the
  same deterministic symbols, with no BER scoring; source timing semantics
  must be decided before interpreting either as faithful.
- **H8:** after SCI-METRIC-02 is resolved from the source, independently
  implement a literal likelihood oracle and compare its posterior on hand-set
  rows. No source-faithful likelihood exists in this M6a scope.

Only the deterministic implementation checks described above ran in M6a. No
new-seed or model-correspondence control was executed.

## 7. Scientific boundary, gates, and next step

This work makes no BER/SER, SNR, or performance claim. It does not change or resolve ADR-005/012/013/014/015, accept ADR-009/011, or resolve SCI-02, SCI-03, or SCI-METRIC-02. `paper_exact:false`; `receiver_enabled:false`.

| Gate | Status |
|---|---|
| Deterministic B4d per-symbol causal trace | **READY** |
| Independent [A](1), posterior, clock, and state-handoff checks | **READY** |
| Frozen/adaptive paired fixture and segmented continuation | **READY** |
| M5j historical per-symbol mechanism attribution | **BLOCKED — HISTORY UNAVAILABLE** |
| Source-paper fidelity and physical/general channel conclusions | **BLOCKED / out of scope** |
| New-seed diagnostic capture | **BLOCKED; M6b-prep protocol exists but remains proposed and unauthorized** |

Minimal next step (M6b): review the trace contract and H1–H8 evidence, then decide whether to authorize a small fresh-seed diagnostic capture with the same fixed policy and a frozen trace schema. It must not tune parameters or be treated as confirmatory performance evidence. Do not launch it automatically. No new ADR is required for M6a.

### M6b-prep status

The proposed protocol and H1-H8 test matrix are now recorded in
`M6_FRESH_TRACE_DIAGNOSTIC_PROTOCOL.md` and `M6_ROOT_CAUSE_TEST_MATRIX.md`.
The candidate fixes three fresh-seed sequences, F=32, and the historical M5j
fixed B/C policies. No RNG streams, samples, receiver calls, or output records
were created. The draft remains `design_status="proposed"`,
`execution_authorized=false`, and `execution_scope="none"`; the validator
blocks execution before callbacks under that state.

M6b-run requires a separate explicit authorization, any resource limits the
user wants fixed, and a distinct runtime fingerprint. M6b-prep supplies no new
BER/SER or root-cause claim and requires no new ADR.

## M6b-run follow-up

The authorized M6b run copied actual B4d rows for three fresh sequences and
validated 192 B/C rows, exact paired hashes, 8-sample windows/cutoffs, prior and
continuation labels, canonical edge ordering, posterior normalization,
pre/post handoff, frozen metric history, and one final decode per mode. In all
runs C post-state first diverged at symbol 0 and next-symbol pre-state/metrics
at symbol 1. B5b path divergence began later (symbols 17, 11, and 10). These
observations verify the implemented dependency but do not establish that it
caused decoded errors.

The three sequences are diagnostic only and do not modify M5j's numerical
claim. M5j per-symbol history remains unavailable. See
`M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md` for run values, H1-H8 status, and limits.

## M6e one-step state intervention boundary

`evaluation/reconstruction_update_intervention.py` adds a deterministic
evaluation-side comparison after one explicit estimator update. It applies
the existing [A](1) kernel to supplied current-symbol operands, then holds the
next eight-sample observed-IQ window, ADR-002 canonical hypotheses, beta, and
ADR-005 metric fixed while calculating before/after next-symbol prediction,
metric, and fixed-prior first-edge posterior rows. The derived weighted
innovation is labeled as a scalar sum from its operands; it is not an exported
raw B4c field.

This adapter does not accept a receiver sequence, reference data, channel
truth, or RNG. It does not decode, feed the changed posterior back into a
second update, or rewrite frozen metric history. Its deterministic evidence
supports implementation dependencies only through the one-step posterior
sensitivity. It does not establish full-path or M5j BER causality, source
semantics, or author mapping. See `M6_UPDATE_INTERVENTION_AUDIT.md`.

## M6f two-symbol factorial boundary

`evaluation/reconstruction_factorial_ablation.py` runs exactly two symbols
for the fixed B/A/K/C update arms through the existing B4d sequence API, using
one explicit complex receive buffer shared across all arms. It verifies shared
first-symbol metrics/posterior/innovation, the single-update alpha/correction
state decomposition, then compares second-symbol predictions, 16 ADR-005
metric rows, actual continuation posteriors, and a separate uniform-common-
prior metric sensitivity. The intermediate continuation `q` is not exported
in sequence history; any `p*T` vector is explicitly marked as an independent
derived audit value.

The actual second-symbol carried pre-state is the prior symbol's B4d
`next_state` propagated by the sequence API; the sequence history does not
persist a duplicate pre-state field. Manual scalar predictions and metrics
verify that carry-forward. No decoder runs and no frozen row is overwritten.
The factorial result establishes only deterministic code dependencies for
this fixture. It does not establish M5j error causality, source fidelity, or a
performance claim; see `M6_FACTORIAL_UPDATE_ABLATION_REPORT.md`.

## M6c source-equation clarification

The equation audit now transcribes [A](1) and [A](5) from the available local
scans. The implementation's explicit [A](1)-shaped operand arithmetic and
[A](5) transform match independent deterministic scalar oracles. M6b's
posterior-weighted innovation remains a derived value: the update API receives
posterior, observed I/Q, and predicted I/Q and sums one weighted residual over
its supplied hypothesis axis; it does not export a separately named raw
innovation. The posterior transition intermediate `q` is unavailable.

The project-local edge/phase table is verified under M1 and ADR-002 only.
Neither that table nor the ADR-012 complex convention is attributed to [A].
See `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md`; SCI-02, SCI-03, and SCI-METRIC-02
remain open and no receiver mathematics changed.

## M6g deterministic multistep feedback trace

`reconstruction_multistep_feedback_audit.py` records eight immutable
rows per arm in two explicitly distinct regimes. CLOSED_LOOP rows are copied
from the B4d sequence history, including current metrics, posterior, predicted
I/Q, observed-IQ operand, and next estimator state. Posterior-weighted
innovation is independently derived from those B4d operands because the API
does not export a named raw innovation.

COMMON_OPERAND first freezes all eight innovations from the completed B
closed-loop path, then runs an evaluation-only replay. It uses each arm's own
candidate metrics and posterior for diagnostics, but applies the frozen B
innovation to the scalar [A](1) state control. The replay's own innovation
does not enter its state update. Raw transition q remains unavailable;
continuation q values are separately derived and labelled. The two regimes
share the same exact sample windows, clocks, 16-edge order, beta, prior and
posterior transition semantics. This audit adds no decoder path, source
mapping claim, or receiver mode.

## M6h posterior-weight intervention

The M6h evaluation adapter reads the fixed M6g complex128 fixture and saved
B/A/K/C trace. For same-state contrasts, it holds an arm's pre-state,
predictions, observation, and symbol fixed while substituting `p_B[f]` for
only the posterior weights in the innovation. It then evaluates an isolated
one-step counterfactual post-state without feeding it into M6g history.

For the separate multistep POSTERIOR_CLAMP replay, each arm retains its own
state, candidates, local metrics, posterior transition history, and own
posterior diagnostic. Only the correction update receives the same-symbol
frozen B posterior. This does not substitute the complete B innovation used
by M6g COMMON_OPERAND. Raw transition `q` remains unavailable; any derived
`p*T` is provenance-labeled. Absolute windows and prediction/observation
cutoffs follow the existing 8-sample causal contract. M6h is evaluation-only,
does not invoke a decoder or compute BER/SER, and does not establish M5j error
causation. Details and hashes are in
`M6_POSTERIOR_CLAMP_ABLATION_REPORT.md`.
