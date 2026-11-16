# M7 exploratory policy-study closeout

**Closeout status:** `EXPLORATORY_GRID_COMPLETED; TRAIN_WINNER_FROZEN_B;
ADAPTIVE_GAIN_NOT_ESTABLISHED; VALIDATION_NOT_EXECUTED`.

This closes M7's exploratory nine-policy TRAIN search. The historical M7b
artifacts retain their original status, `TRAIN_SELECTED_NOT_VALIDATED`; no
checkpoint, config, seed, count, ranking, or selected-policy record was
rewritten. This closeout is not independent validation, confirmatory evidence,
or a source-faithful receiver result.

## M7a design and M7b execution

M7a preregistered nine fixed `alpha_prime`/`K_scale` candidates, 40 TRAIN
sequences, one common received realization per sequence, raw-count BER/SER
pooling, deterministic tie-breaks, failure eligibility, and isolated future
partitions. M7b had separate explicit TRAIN-only authorization and used the
M7a candidate order and TRAIN seed derivation. It completed exactly 40 runs,
40 unique received hashes, nine policy records per run, and 360 decoder
passes. Each policy had 40 complete valid records, with zero numerical or
decoder failures. Each candidate denominator was 20,480 information bits and
10,240 coded symbols.

This closeout independently read the 40 saved sequence checkpoints. It
recounted bit errors from each saved reference/decoded information-bit pair,
recounted symbol errors from each saved transmitted/decoded symbol-index
pair, pooled integer counts, and re-applied the frozen ranking rule. It did
not call a receiver, decoder, generator, or RNG.

## Fixed TRAIN ranking

| Rank | Candidate | Bit errors / bits | Pooled BER | Symbol errors / symbols | Pooled SER | Failures | Eligible |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `a100_k000` | 478 / 20,480 | 0.023339843750 | 441 / 10,240 | 0.043066406250 | 0 | yes |
| 2 | `a095_k000` | 1,903 / 20,480 | 0.092919921875 | 1,559 / 10,240 | 0.152246093750 | 0 | yes |
| 3 | `a100_k050` | 3,050 / 20,480 | 0.148925781250 | 2,333 / 10,240 | 0.227832031250 | 0 | yes |
| 4 | `a100_k100` | 4,831 / 20,480 | 0.235888671875 | 3,835 / 10,240 | 0.374511718750 | 0 | yes |
| 5 | `a085_k000` | 4,871 / 20,480 | 0.237841796875 | 4,006 / 10,240 | 0.391210937500 | 0 | yes |
| 6 | `a095_k100` | 7,357 / 20,480 | 0.359228515625 | 6,799 / 10,240 | 0.663964843750 | 0 | yes |
| 7 | `a095_k050` | 7,575 / 20,480 | 0.369873046875 | 6,791 / 10,240 | 0.663183593750 | 0 | yes |
| 8 | `a085_k100` | 8,093 / 20,480 | 0.395166015625 | 7,339 / 10,240 | 0.716699218750 | 0 | yes |
| 9 | `a085_k050` | 8,545 / 20,480 | 0.417236328125 | 7,502 / 10,240 | 0.732617187500 | 0 | yes |

The frozen TRAIN winner was `a100_k000`, `alpha_prime=1.0`,
`K_tilde=(0,0)`. The exact ordering, numerators, denominators, failures,
and winner are available in the [M7b report](M7_TRAIN_POLICY_SEARCH_REPORT.md)
and immutable [checkpoint namespace](../outputs/m7b_train/m7_reconstructed_estimator_policy_study_v1/).

The supported exploratory statement is:

> No tested adaptive policy outperformed frozen B by pooled TRAIN BER within
> this predefined nine-policy grid.

This is limited to the selected sample and fixed reconstructed profile. The
minimum is selection-biased. It does not establish adaptive inferiority in
general, an optimality result for B, or confirmatory superiority.

## Why no validation was run

The original validation contrast would compare the TRAIN-selected policy with
frozen B. Since the selected policy is B itself, the contrast would be B
versus B and would not address whether adaptation improves on B. The second
ranked candidate was not promoted after seeing TRAIN results. No validation
or final seeds were derived or used. M7 is closed rather than repurposed into
a same-policy exercise; any later study needs a new protocol, independent
partitions, and explicit authorization.

## Integrity and scientific boundary

The original M7b artifacts remain `TRAIN_SELECTED_NOT_VALIDATED`. Its output
integrity manifest still verifies every listed file; the M7a draft and M7b
approved config hashes remain respectively
`6b5cffdd9c4f47241bf7d54ff5d58c93d65bc2759a35557e07e3a1f38dae841f` and
`7b29eaed0166765193b3f8bc16eae760826e1469a97025577573730113c87595`.
Historical M5f/M5h/M5j/M6b/M6g/M6h tree hashes match the pre-M7b baseline
recorded in the approved config.

M7 concerned one `reconstructed_offline` profile: L=1, real gain 0.75, zero
delay, normalized 8PSK, rectangular 8-sample ZOH, ADR-005 pseudo-likelihood,
ADR-012 observed-IQ, ADR-013 conditional full Viterbi, and 5 dB effective
discrete ADR-015 AWGN. This is not physical HF `Eb/N0`. The M7b outcome does
not prove the historical M5j error mechanism. Source edge-to-phase mapping,
quadrature, innovation, and likelihood fidelity remain unresolved.

## M8 motivation

M7 motivates a distinct hypothesis about the parameterization of the
reconstructed estimator: with `mu0=(0,0)` and `K_tilde=(0,0)`, the fluctuating
state decays geometrically when `alpha_prime<1`. M8 proposes a nonzero
receiver-side anchor while retaining the same initial full estimate. This is
a new project reconstruction variant, not a source-derived repair or
guaranteed improvement. Its design is in
[`M8_ANCHORED_ADAPTATION_DESIGN.md`](M8_ANCHORED_ADAPTATION_DESIGN.md); no M8
observations or random streams were created during M8a. The later authorized
M8b attempt is documented in
[`M8_ANCHORED_TRAIN_REPORT.md`](M8_ANCHORED_TRAIN_REPORT.md): it is incomplete,
produced no decoder outputs or policy ranking, and did not run VALIDATION or
FINAL.
