# M10 controlled variable-gain evaluation report

**Status:** `M10_EVALUATION_COMPLETE_VERIFIED`  
**Classification:** controlled evaluation of two fixed policies on three
synthetic real-gain profiles; not physical HF performance, not a paper-exact
receiver, and not an optimized policy.

## Gate A: accepted model

The explicit M10 instruction accepted **ADR-016** on 2026-10-30 for
evaluation-side use only. The model is
`controlled_piecewise_real_gain_v1`:

```text
y[n] = a[floor(n/8)] * x[n] + w[n]
```

It uses `L=1`, zero delay, deterministic real positive per-symbol gain,
normalized 8PSK rectangular ZOH at 8 samples/symbol, and independent circular
complex AWGN. The extension adds no multipath, AR(1), complex fading, physical
HF propagation claim, production channel integration, or receiver mode. It
leaves ADR-015's noise mathematics and all receiver mathematics unchanged.
The author mapping and source semantics remain unresolved.

The accepted decision document SHA-256 is
`1dee34b2f608c2abea03c332135cbc67a5726326378b06ba2a7bc117763dd178`; the
machine-readable decision SHA-256 is
`63f36a948c8147f76872e4d00e953e7eba50fff9338dcb6a141e4c82a65b9bb4`.
Both have adjacent sidecars.

## Frozen protocol and provenance

The unchanged M10a draft hash is
`80ec2ea30e04bfeb02508380b94f29bb08140a1906fa61816d137ed56798066f`.
The separate M10b approved config hash is
`a43c5109f58ce8aab75f8c8bac6d8daab648932351bdd6be70942484b4d88b84`.
The runtime source fingerprint is
`918a4ad3538c84536f092a80f318a0e3df1c87518667ae2bd0edfc380439b661`.
Python was 3.13.13, NumPy 2.3.3, on Windows 11. Git revision was unavailable
because the workspace did not expose Git metadata. The approved config and
output manifest record the full source and environment fingerprints.

The real deterministic integration preflight passed before experimental RNG
initialization. It exercised the actual orchestrator and receiver on a fixed
non-experimental fixture for all six policy/profile pairs, compared each
result with direct receiver API calls, checked clocks and causal cutoffs, and
counted smoke decodes separately from the 600 experimental decodes. The M8b
`clock_origins` regression is covered: M10a has no such field, and clock
origins resolve from the accepted M5i configuration plus B4d's fresh-sequence
contract. There were 14 Viterbi invocations in this deterministic gate:
six orchestrator calls, six direct API comparison calls, and two auxiliary
causal-cutoff checks. These are not part of the 600 experimental calls.

The two receiver policies were frozen:

| Policy | `alpha_prime` | `K_tilde` | `mu0` | Initial fluctuating state | Initial full IQ | `beta` |
|---|---:|---|---|---|---|---:|
| `historical_frozen_B` | 1.00 | (0, 0) | (0, 0) | (0.42, 0.91) | (0.42, 0.91) | 0.7 |
| `anch_a085_k025` | 0.85 | (0.0875, -0.05) | (0.42, 0.91) | (0, 0) | (0.42, 0.91) | 0.7 |

All policies used the same initial full estimate, mapping, likelihood,
observation rule, conditional Viterbi decoder, and zero sample/symbol/tick
origins. Receiver arguments contained no gain schedule, switch index,
ChannelTruth, reference bits, true gain, or correct path.

The three channel schedules were exactly P0 constant 0.75, P1
`sqrt(0.765)` then 0.60, and P2 0.60 then `sqrt(0.765)`, switching at symbol
128/sample 1024. The independent identity
`(0.60² + 0.765)/2 = 0.5625 = 0.75²` holds. Equal frame-average gain-squared
does not mean equal instantaneous SNR. P1/P2 share gain values in opposite
order; P0 has a different gain distribution, so P1/P0 is not a pure isolated
switching contrast.

Noise variance was fixed at `sigma_squared=0.7115124735378853` for all
profiles (component variances `sigma_squared/2`); it was not scaled with gain.
The 5 dB effective discrete reference applies only at gain 0.75, not as a
physical HF Eb/N0 for the variable-gain frame.

## Execution and pairing

The execution used the frozen M10 roots and
`SeedSequence(master, spawn_key=(1295337521,1001,run_index,stream_code))`,
deriving uint64 child seeds before PCG64 initialization. Roots were data
2027030101, noise 2027030102, bootstrap 2027030103, metadata 2027030104;
stream codes were 11/23/37/41. Run IDs were
`m10_controlled_piecewise_gain_v1:evaluation:run-001` through `run-100`, in
ascending zero-based index order. No M5–M9 stream or observation was used.
The bootstrap stream used spawn key `[1295337521,1001,0,37]`, derived seed
`15448463198817961909`.

Each run generated bits, one M1 encoded sequence, one normalized waveform and
one AWGN realization. The same waveform/noise pair formed P0/P1/P2 buffers;
each buffer was shared by B and anchored. The run-cluster bootstrap retained
that cross-profile and cross-policy pairing.

| Quantity | Observed |
|---|---:|
| Independent run clusters | 100 / 100 |
| Profile-specific received buffers | 300 / 300 |
| Policy records | 600 / 600 |
| Experimental decoder invocations | 600 / 600 |
| Unique received hashes | 300 |
| Numerical/decoder failures | 0 |
| Bit denominator per policy/profile | 51,200 |
| Symbol denominator per policy/profile | 25,600 |

## Raw counts and rates

| Profile | Policy | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---|---:|---:|---:|---:|
| P0 CONSTANT | Frozen B | 1202 / 51200 | 0.0234765625 | 1107 / 25600 | 0.0432421875 |
| P0 CONSTANT | Anchored | 1180 / 51200 | 0.0230468750 | 1106 / 25600 | 0.0432031250 |
| P1 HIGH_TO_LOW | Frozen B | 4136 / 51200 | 0.0807812500 | 3679 / 25600 | 0.1437109375 |
| P1 HIGH_TO_LOW | Anchored | 4120 / 51200 | 0.0804687500 | 3660 / 25600 | 0.1429687500 |
| P2 LOW_TO_HIGH | Frozen B | 4205 / 51200 | 0.0821289063 | 3777 / 25600 | 0.1475390625 |
| P2 LOW_TO_HIGH | Anchored | 4208 / 51200 | 0.0821875000 | 3780 / 25600 | 0.1476562500 |

### Primary contrast

The predefined P1 estimate is `DeltaBER_P1 = -16 / 51200 = -0.0003125`.
Its ADR-014 95% paired full-run cluster percentile interval is
`[-0.00205126953125, 0.0014453125]`. It includes zero, so this design does
not resolve the direction of the P1 BER difference.

### Secondary descriptive contrasts

| Contrast | Pooled difference | 95% paired cluster interval (descriptive) |
|---|---:|---:|
| DeltaBER P0 | -22 / 51200 = -0.0004296875 | [-0.0024609375, 0.00154296875] |
| DeltaBER P2 | +3 / 51200 = +0.00005859375 | [-0.00214892578125, 0.00224609375] |
| DeltaSER P0 | -1 / 25600 = -0.0000390625 | [-0.0036728515625, 0.0035546875] |
| DeltaSER P1 | -19 / 25600 = -0.0007421875 | [-0.0037900390625, 0.0022275390625] |
| DeltaSER P2 | +3 / 25600 = +0.0001171875 | [-0.0031640625, 0.00359375] |
| DeltaBER P1 − DeltaBER P0 | +6 / 51200 = +0.0001171875 | [-0.00255859375, 0.00285205078125] |
| DeltaBER P2 − DeltaBER P1 | +19 / 51200 = +0.00037109375 | [-0.00232421875, 0.00316455078125] |

The bootstrap used 2,000 resamples, each resampling 100 complete run indices
with replacement and applying the same indices to all six profile/policy
outcomes. It used the 95% percentile interval and
`numpy.quantile(method="linear")`. The shared resample-index SHA-256 is
`8acba20e62aaa186c754ba333eb75bb5909ce1da9ce362646091fb06be8c2e9c`.
Secondary intervals are descriptive; there is no additional confirmatory
claim or multiplicity adjustment.

## Switch-segment and coefficient diagnostics

The pre/post switch bit and symbol counts below use the two half-frame
segments of the **full-frame conditional Viterbi traceback**. They are
descriptive segment outcomes, not online prefix decoding or real-time
tracking measures.

| Profile | Policy | Pre-switch bit / symbol errors (25,600 bits; 12,800 symbols) | Post-switch bit / symbol errors |
|---|---|---:|---:|
| P0 | B | 563 / 528 | 639 / 579 |
| P0 | Anchored | 591 / 565 | 589 / 541 |
| P1 | B | 39 / 35 | 4097 / 3644 |
| P1 | Anchored | 31 / 29 | 4089 / 3631 |
| P2 | B | 4149 / 3720 | 56 / 57 |
| P2 | Anchored | 4160 / 3730 | 48 / 50 |

Mean final full-IQ coefficient norms were approximately 1.00225 for frozen B;
for the anchored policy they were 0.99680 (P0), 0.99826 (P1), and 0.99591
(P2). Largest observed anchored final norm was 1.07208 (P2). The receiver API
does not expose full per-symbol coefficient histories in these result
records; no tracking threshold was defined or inferred.

## Independent verification and technical note

The execution runner's first independent-verification pass marked the run
failed because its comparison expected the planned seed metadata's
`initialized=false` flag to remain false in checkpoints. The runner correctly
recorded `initialized=true` for the data/noise streams it had actually used.
This was an audit-field comparison defect, not a changed seed or input.
The initial verification and initial summary are preserved as
`runner_initial_verification.json` and `runner_initial_summary.json`.

A separate read-only recount then checked all 100 ordered run IDs and exact
seed derivations; regenerated and matched the bits, waveform and AWGN from
those seeds; rebuilt all three received buffers; verified 300 received
hashes, 600 policy records and 600 decoder calls; checked the fixed policy
parameters and canonical M1 paths; and recounted raw errors from saved
decoded arrays. It passed with zero failures. It also independently computed
the paired cluster bootstrap. Its code fingerprint is recorded in
`independent_recount.json`. The output integrity manifest covers the
checkpoints, initial-verifier evidence, independent recount and final summary.

The runner's evaluation wall time was 296.58 seconds. Bootstrap time was
0.17 seconds. Periodic RSS sampling observed a peak of 48,910,336 bytes; this
was a monitor, not an OS-enforced cap. All 100 run clusters completed within
the 900-second budget.

Historical M5f/M5h/M5j/M6b/M6g/M6h/M7b/M8/M9 artifacts and the M10a draft
matched their pre-run fingerprints. The M10a draft hash remained unchanged.
No receiver or estimator mathematics changed, and no validation, final,
additional experiment, or other RNG partition ran.

## Interpretation and limits

For the predefined P1 HIGH_TO_LOW comparison, anchored has a slightly lower
pooled BER point estimate, but its 95% interval crosses zero. The result does
not establish lower BER, equivalence, noninferiority, optimality, or
generalized adaptive superiority. P0/P2 and SER results are secondary
descriptive contrasts. The three synthetic schedules do not represent
physical HF propagation. P1/P0 also changes the gain distribution, not only
temporal order. The result cannot resolve historical M5j error causation,
author mapping/likelihood semantics, multipath, or variable physical channel
behavior. `paper_exact:false`, `receiver_enabled:false`, and open SCI-02,
SCI-03, SCI-METRIC-02 remain unchanged.

**Next gate:** any further channel/profile research requires a separately
specified model and explicit authorization. No M11 experiment is started by
this closeout.
