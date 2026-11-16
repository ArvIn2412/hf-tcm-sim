# M5g — proposed preregistered B/C study design

**Status:** preregistered reconstructed_offline statistical experiment design,
**NOT new performance evidence**, **NOT paper-exact receiver**, **NOT
reproduction of paper results**. This is a proposed design record, not an
authorization to run a pilot or confirmatory study. No stochastic experiment,
SNR sweep, or parameter tuning was run in M5g.

## Scope and evidence boundary

The proposed scope is the accepted reconstructed profile only: L=1, positive
real channel gain, zero delay, normalized 8PSK, rectangular ZOH at 8
samples/symbol, ADR-012 observed IQ, ADR-013 conditional Viterbi, and ADR-015
independent circular complex sample AWGN. Report only `effective discrete
gamma_b = 4*a*a/sigma_squared`; it is not physical HF Eb/N0. Keep
`paper_exact:false`, `receiver_enabled:false`, SCI-02, SCI-03, and SCI-METRIC-02
open. ADR-009 and ADR-011 remain proposed.

The only existing paired evidence is M5f's exploratory sample: 12 independent
sequences, F=32, 768 bits and 384 coded symbols; a=0.75, sigma_squared=0.08,
beta=0.7; common mismatched estimate (0.42, 0.91); C used alpha_prime=0.85,
K_tilde=(0.35,-0.2), mu0=(0,0). Raw records confirm B=0/768 bit and 0/384
symbol errors, C=189/768 and 181/384, DeltaBER=+0.24609375 and
DeltaSER=+0.4713541666666667. Adaptive C was worse in every observed pair.
The sample was small, B had zero observed errors, and the bootstrap emitted
`too_few_independent_runs`, `rare_error_count`,
`degenerate_bootstrap_distribution`, and `bootstrap_interval_unreliable`.
This is not a population-level conclusion and does not justify changing the
fixed C policy to improve the next result.

## Research questions and estimands

**Primary confirmatory question (RQ1):** at the prespecified 5 dB effective
discrete gamma stratum and the fixed M5f B/C policies below, does adaptive C
have a different pooled information-bit BER from frozen B on paired runs?
The primary estimand is `DeltaBER = pooled BER_C - pooled BER_B`; negative
values favor C in observed errors. The proposed primary stratum is a design
choice pending user approval, not a value selected from new evaluation data.

**Secondary descriptive questions:**

- RQ2: how do point estimates and paired intervals vary over the proposed
  effective-gamma grid?
- RQ3: how do they vary over prespecified initial mismatch scenarios?
- RQ4: how do trajectories and error counts vary in one-factor sensitivity
  diagnostics for alpha_prime, K_tilde, and the shared beta?
- RQ5: how often do finite coefficient-error trajectories grow, and how often
  do numerical failures occur?

`DeltaSER = pooled SER_C - pooled SER_B` is a secondary outcome. Coefficient
trajectory, posterior entropy, error counts, and failure classifications are
diagnostics; they do not replace the primary estimand. No relative BER ratio
is reported when B has zero errors, and no gain in dB is derived from BER.

## Proposed effective-gamma strata

Hold `a=0.75` fixed and set `sigma_squared=4*a*a/gamma_b_eff`. The grid is
log-spaced to cover four discrete operating levels; it is proposed before any
new data and is not evidence that both modes will produce errors at every
point.

| effective discrete gamma_b_dB | linear gamma_b | a | sigma_squared | Rationale and limit |
|---:|---:|---:|---:|---|
| 0 | 1.000000 | 0.75 | 2.250000 | Low reference level; may yield many errors or unstable estimates; no count guarantee. |
| 5 | 3.162278 | 0.75 | 0.7115124735 | Proposed primary reference stratum; selected as the second point of a fixed log grid, not from evaluation outcomes. |
| 10 | 10.000000 | 0.75 | 0.225000 | Mid/high diagnostic level; one pointwise secondary contrast only. |
| 15 | 31.622777 | 0.75 | 0.0711512474 | Upper level; may have zero errors in one or both modes, making error-rate inference weak. |

All labels are `effective discrete gamma_b` (or `_dB`), never physical
Eb/N0. A separate pilot may describe error prevalence, but pilot runs must
have different IDs and data/noise/bootstrap streams and must never enter the
confirmatory records. The proposed pilot uses F=256 and 30 independent
sequences at each grid point as an operational variance-calibration batch;
30 is not a power calculation or a sufficient sample claim. No pilot was run.

## Fixed policy and sensitivity boundary

For the proposed primary comparison, freeze the M5f policies before the
study:

| Operand | B: frozen | C: adaptive |
|---|---|---|
| Initial fluctuating/full IQ | `(0.42, 0.91)` | Same exact state as B |
| alpha_prime | `1.0` | `0.85` |
| K_tilde | `(0,0)` | `(0.35,-0.2)` |
| mu0 | `(0,0)` | `(0,0)` |
| beta | `0.7` | Shared `0.7` |

These are fixed project settings for the proposed comparison, not article-derived
values and not a claim that C is stable or optimal. B/C must also share the
same bits, single generated received buffer, channel/noise realization,
absolute labels, initial state and termination policy. Only the coefficient
update policy differs. Neither receiver gets reference bits or ChannelTruth;
true `a` is limited to evaluation-side signal generation and post-decode
diagnostics.

RQ3's proposed sensitivity scenarios at a=0.75 are `(0.42,0.91)` (historical
M5f), `(0.60,0.90)` (smaller symmetric mismatch), and `(0.30,1.20)` (larger
symmetric mismatch). They are candidate design levels, not validated or
accepted settings. RQ4 sensitivity is one factor at a time around the fixed
M5f C policy: alpha_prime `{0.50,0.85,1.00}`; K_tilde scale
`{0.5,1.0,1.5}` applied to `(0.35,-0.2)`; beta `{0.35,0.70,1.40}`. These
diagnostics are exploratory, separately seeded and excluded from the primary
contrast. Do not choose a setting from evaluation BER. A separate approval is
required before any sensitivity runs; no multiplicity-adjusted global claim
is proposed here.

## Pilot, sample-size rule, and stopping

The sample-size gate is **BLOCKED**: M5f's 12 clusters do not estimate the
between-sequence variability precisely enough to justify confirmatory `R`,
and zero B errors make a normal-approximation variance estimate especially
fragile. The proposed pilot is independent of evaluation: 30 complete F=256
sequences per gamma, with distinct fixed data/noise seeds, identical paired
B/C execution within run, and no reuse in evaluation. It estimates paired
sequence-level variation, not bit-independent variation.

Before pilot launch, the user/researcher must approve a practical target
half-width `h` for the primary absolute DeltaBER interval and a compute budget.
For equal fixed F, calculate a planning estimate from the SD `s_d` of the
pilot's per-sequence paired BER differences:
`R0 = ceil((t_(0.975, Rpilot-1) * s_d / h)^2)`. Use at least 20 clusters only
as the ADR-014 warning-heuristic floor, not as adequate sample size. Validate
the planned count against cluster-bootstrap interval-width simulations over
the independent pilot records; this is a precision-planning exercise, not
evaluation inference. If pilot counts/variance are degenerate or the target
cannot be met within the approved compute budget, leave confirmatory testing
blocked and revise the design in a separately approved version. Do not
silently substitute a variance floor or select a gamma from favorable pilot
effects.

Once `R` is fixed, register it, F, all seeds and the analysis before evaluation
starts. Run exactly R independent sequences per stratum. No optional stopping
or early stopping based on Delta sign, BER, CI inclusion of zero, or apparent
benefit. Stop only at the registered count or a predeclared data-quality / hard
resource limit; incomplete runs remain failure records and cannot be silently
deleted. A target precision or final R is not claimed until the pilot and
resource limit are approved.

## RNG, pairing, and records

Use distinct SeedSequence master roots for pilot data, pilot noise, evaluation
data, evaluation noise, and bootstrap. Record the full child spawn keys and
derived generator seeds. Ensure no pilot/evaluation run ID or stream lineage
is reused. Bootstrap randomness is independent of data/noise generation.
Within every run, one reference bitstream and one received array feed both B
and C. Preserve raw integer counts, per-run pair deltas, received identity,
coefficient trajectories, posterior entropy, initial/final mismatch,
absolute sample/symbol/estimator labels, and provenance. Evaluation-only
truth comparisons never feed back into a receiver.

## Accepted bootstrap and multiplicity

Apply ADR-014 unchanged: cluster is one complete independent TCM sequence;
resample the same run indices for B and C; pool raw integer counts in each
replicate; use 2000 replicates, explicit bootstrap seed, two-sided 95%
percentile intervals, and `numpy.quantile(method="linear")`. Preserve all
warning flags. A `[0,0]` interval is not proof of zero true BER/SER; an interval
including zero is not evidence of equivalence.

Only the 5 dB primary DeltaBER is confirmatory in this proposed design. The
primary DeltaSER and other gamma/mismatch/parameter results are secondary,
descriptive pointwise estimates and intervals. They do not confirm a curve-
wide advantage. Any familywise or simultaneous inference across secondary
contrasts needs a separately approved multiplicity policy; none is silently
adopted here.

## Trajectory and failure policy

For every run retain the per-symbol coefficient trajectory, pre/post estimate
norms, update-increment norms, posterior entropy, initial/final evaluation-only
coefficient error, BER/SER, and failure classification. Report separately:

- **Numerical failure:** non-finite state/metric or an exception; retain the
  run ID, last valid state/time, exception class and diagnostic. Do not impute
  zero errors or delete the run. Report failure counts separately from BER/SER.
- **Finite coefficient-error growth:** flag when the maximum or final
  evaluation-only coefficient error exceeds the initial mismatch; this is a
  descriptive flag, not automatic exclusion or proof of instability.
- **Decoding errors:** valid decoded output with nonzero reference mismatch;
  count normally in BER/SER, however large.
- **Analysis/data failure:** malformed or unpaired record; preserve an audit
  record and do not treat it as a valid pair. Any exclusion rule must be
  specified before seeing outcomes and accompanied by counts/reasons.

Numerically valid but poor runs remain in their registered denominator.
Receiver exceptions are not silently removed; if an output is unavailable,
report the failure endpoint and mark rate estimands with missing receiver
outputs as blocked rather than inventing a rate.

## Readiness gates and next decision

| Gate | Status |
|---|---|
| ADR-014 bootstrap implementation/policy | READY; accepted, exploratory intervals only |
| M5f paired execution and raw records | READY as prior diagnostic evidence; C performed worse in that sample |
| Proposed protocol and non-executable JSON draft | READY for review; not approved for execution |
| Gamma grid / primary contrast / candidate C policy | PROPOSED; user approval required |
| Pilot/evaluation seed namespace | PROPOSED; must be frozen before pilot |
| Pilot and confirmatory sample size | BLOCKED pending target half-width, compute budget, and independent pilot variability |
| Multiplicity for secondary contrasts | BLOCKED pending a future policy if inferential claims are desired |
| Physical HF Eb/N0, M2 adaptive-CSI parity, paper result reproduction | BLOCKED |

The minimum next decision is approval or revision of the proposed grid and
5 dB primary stratum, fixed M5f B/C policies, F=256 pilot length, 30-run-per-
stratum variance pilot, and target absolute DeltaBER half-width/compute budget.
No new ADR is proposed or accepted by M5g. Accepted ADRs remain
001/002/003/004/005/006/007/008/010/012/013/014/015; proposed ADRs remain
009/011. Preserve `paper_exact:false` and `receiver_enabled:false`.

## M5h-prep addendum — validated candidate, still unauthorized

`docs/M5_PILOT_PREPARATION_CONTRACT.md` and
`configs/m5h_pilot_draft.json` convert the M5g proposal into a strictly
validated candidate with explicit origins, derived per-stratum ADR-015
variances, separate pilot/evaluation data/noise/bootstrap namespaces, unique
run provenance, and an execution guard. This is preparation only: the candidate
remains `design_status="proposed"`, `execution_authorized=false`; no pilot,
new BER/SER evidence, sweep, tuning, or performance claim was produced.

For later planning, the initial approximation may be reported as
`R_approx=ceil((1.96*s_d/epsilon)^2)` using the pilot standard deviation of
paired sequence-level differences at 5 dB. It is a normal approximation and
does not guarantee percentile cluster-bootstrap precision. The M5g t-based
formula was a prior candidate; neither approximation approves `R`. The
candidate `epsilon=0.02` and compute budget remain unresolved, and numerical
failure interpretation keeps confirmatory inference BLOCKED. See the M5h
contract for exact seed derivation and workload.


## M5h-run execution record (pilot only)

The user later explicitly authorized one bounded independent planning pilot. Its immutable approval snapshot and all records are in `outputs/m5h_independent_pilot/`; the full results and resource accounting are in `M5_INDEPENDENT_PILOT_REPORT.md`. This records execution of the separate pilot only. It does not change the M5g proposed preregistration into an executed or confirmatory experiment, and pilot records remain excluded from confirmatory evaluation. M5g/M5h proposed draft files, M5f historical artifacts, ADR states, and `execution_authorized=false` in the drafts are unchanged. Confirmatory sample-size and execution gates remain BLOCKED pending explicit scientific decisions and separate authorization.


## M5i pilot-informed confirmatory design candidate

`docs/M5_CONFIRMATORY_DESIGN_CONTRACT.md` and `configs/m5i_confirmatory_design_draft.json` specify one candidate primary condition at effective discrete gamma_b=5 dB, F=256, and recommended R=100 paired sequences. The pilot checkpoint audit independently reproduced the 30-run primary `s_d=0.053093594133490844` and normal-approximation `R_approx=28`; this informed the operational R recommendation without tuning receiver parameters. The target 95% DeltaBER CI half-width is epsilon=0.02, not a stopping rule and not guaranteed by R=100.

A separate deterministic manifest lists 100 planned M5j IDs and reserved M5h evaluation-namespace seed provenance. It generated no data, noise, decoder output, or bootstrap records. M5i remains `proposed_confirmatory`, `execution_authorized=false`, `execution_scope=none`. M5g remains a proposal; M5f and M5h remain separate historical experiments. M5j requires a new immutable run-specific approval; no existing pilot authorization carries forward.
