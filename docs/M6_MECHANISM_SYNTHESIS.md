# M6 mechanism synthesis for the proposed M7 policy study

**Classification:** synthesis of deterministic reconstructed-model audits and
the saved M5j fixed-policy confirmatory result. This is not a new performance
analysis, an author-confirmed receiver, or proof of the cause of M5j errors.
No historical result, ADR, or open SCI status is changed. The project remains
`paper_exact:false`, `receiver_enabled:false`.

## Scope and evidence classes

M6a added causal B4d trace instrumentation and checked clock/window ordering.
M6b ran exactly three separately authorized fresh-seed diagnostic sequences;
it was a trace diagnostic, not a performance study. M6c/M6d audited the
available source evidence and algebra; M6e-M6h used deterministic controls
and interventions. Their conclusions concern only the stated
`reconstructed_offline`, L=1 profile with ADR-002/005/012/013 conventions.

## A. Algebraic identities

- The project implementation of the printed [A](1)-shaped update agrees
  with independent scalar-loop arithmetic for explicitly supplied operands.
  This verifies implementation algebra, not that the reconstruction chose
  the author's intended operands or indexing.
- The isolated [A](5) transform agrees with independent eight-angle
  trigonometric values. The ADR-012 `(-Im, Re)` representation agrees under
  the selected `y=a exp(j theta)` convention; the source's phase origin,
  quadrature order, and edge-to-phase labeling remain unconfirmed.
- For one common first-symbol innovation, the B/A/K/C update terms decompose
  additively into alpha decay and K correction. Squared-residual metrics have
  a quadratic interaction term; posterior normalization is nonlinear, so
  neither metric nor posterior factorial contrasts are required to add.
- The production API does not export a raw continuation `q` or a named raw
  innovation. The audit derives `p*T` and posterior-weighted residuals only
  with explicit provenance labels.

## B. Deterministic interventions

- M6e holds the next observation and candidate set fixed and checks the
  one-step update -> prediction -> ADR-005 metric -> fixed-prior posterior
  sensitivity.
- M6f separates direct alpha and K terms on a fixed two-symbol fixture. Its
  squared-residual interaction is a property of the implemented metric and
  that fixture, not a BER comparison.
- M6h compares own posterior weights with same-symbol frozen-B weights on an
  identical state/prediction/observation, then carries a weights-only clamp
  through eight symbols while retaining each arm's own posterior history.
  The M6h `B` posterior is not a correct-edge oracle. B/A trajectories remain
  invariant; K/C show fixture-specific contrasts. This is distinct from
  M6g's full common-innovation replay.

## C. Multistep closed-loop dependencies

M6a/M6b/M6g/M6h verify the implementation lifecycle: metrics for `f` use
pre-state `f`; the observed window and posterior for `f` become available at
its cutoff; the update's post-state can affect `f+1`. On M6g's fixed
64-sample buffer, K/C separate between CLOSED_LOOP and COMMON_OPERAND after
the first shared update; later metrics/posteriors differ. M6h further
separates same-state weight contrasts from trajectory contrasts. These are
computational dependencies and deterministic counterfactuals, not proof that
the dependency caused any particular decoded error.

## D. Posterior-weight and coefficient diagnostics

M6b's three authorized F=32 B/C trace diagnostics saved per-symbol states,
posterior, metrics, and evaluation-only coefficient errors. The latter were
computed after decoding relative to the reconstructed `(a,a)` target and
never entered recursion:

| Run | Mode | Initial coefficient-error norm | Final norm | Finite trajectory |
|---|---|---:|---:|---|
| 001 | B | 0.366742 | 0.366742 | yes |
| 001 | C | 0.366742 | 1.493646 | yes |
| 002 | B | 0.366742 | 0.366742 | yes |
| 002 | C | 0.366742 | 0.771920 | yes |
| 003 | B | 0.366742 | 0.366742 | yes |
| 003 | C | 0.366742 | 1.431735 | yes |

This records finite coefficient-error growth for those three M6b diagnostic
sequences; it does not establish general instability or explain BER. M6g/M6h
trajectories are additional deterministic fixture-specific diagnostics.

## E. Historical M5j result

M5j remains the only confirmatory performance result in this evidence chain:
for its preregistered B/C policies at one effective discrete `gamma_b=5 dB`
ADR-015 point, pooled `DeltaBER=C-B=+0.3655078125` with 95% paired-cluster
percentile CI `[0.35548681640625, 0.37578173828125]`. This is a narrow fixed
reconstructed-profile contrast. **M5j per-symbol estimator histories are
unavailable.** M6b/M6g/M6h observations cannot reconstruct or causally
attribute those historical errors; M6 traces must not be used to rewrite the
M5j result or select policies using M5j outcomes.

## F. Source alignment and H1-H8 status

| Hypothesis | Synthesis status and provenance |
|---|---|
| H1 alpha/K policy behavior | **SUPPORTED** as local/multistep effects for tested fixed reconstructed fixtures (M6b, M6f-M6h); policy quality and optimality unresolved. |
| H2 ADR-012 quadrature vs source | **UNRESOLVED**; M6c algebra only confirms consistency under the selected convention, M6d found no author confirmation. |
| H3 source innovation semantics | **UNRESOLVED**; project operand algebra was checked, source semantics were not settled. |
| H4 source correction direction/scale | **UNRESOLVED**; project arithmetic is verified, source operand interpretation is not. |
| H5 project posterior-weight sensitivity / author edge map | **SUPPORTED** for measured project-level sensitivity in M6h; author edge-to-phase mapping remains **SOURCE_UNRESOLVED**. |
| H6 update-to-later-metric feedback | **SUPPORTED** as implementation dependency by M6a-M6h; causal contribution to M5j BER remains **UNRESOLVED**. |
| H7 frame-constant vs per-symbol model | Model-timebase distinction documented; contribution to M5j errors **UNRESOLVED**. |
| H8 ADR-005 vs source-faithful likelihood | Likelihood distinction documented; source intent and contribution **UNRESOLVED**. |

SCI-02, SCI-03, and SCI-METRIC-02 remain open. Source uncertainty does not
block an explicitly reconstructed policy study, but no candidate policy may
be described as source-faithful. There is no universal adaptive-inferiority,
physical HF Eb/N0, multipath, or paper-method-failure conclusion.
