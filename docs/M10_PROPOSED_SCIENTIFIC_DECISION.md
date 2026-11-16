# ADR-016 — controlled piecewise real-gain evaluation extension

**Status:** ACCEPTED for evaluation-side experiments only.  
**Decision date:** 2026-10-30.  
**Decision provenance:** explicit user authorization in the M10 scientific-
decision gate and M10b evaluation instruction.  
**Decision fingerprint:** recorded in the adjacent `.sha256` sidecar.

## Decision

Accept the experimental channel profile
`controlled_piecewise_real_gain_v1`, scoped only to evaluation-side channel
generation and analysis. For 256 symbols, eight samples per symbol, and
`n=0..2047`, define

```text
y[n] = a[floor(n/8)] * x[n] + w[n]
```

where `x[n]` is the unchanged normalized 8PSK rectangular-ZOH waveform,
`a[f]` is deterministic, real, positive, and constant over each symbol, and
`w[n]` follows the accepted independent circular complex AWGN convention.
This is a zero-delay, memoryless `L=1` evaluation extension. It does not add
multipath, AR(1), complex fading, or physical HF propagation assumptions.

## Frozen profiles

The frame has 256 symbols. The gain change is at symbol 128, sample 1024.
Let `a_nominal=0.75`, `a_low=0.60`, and
`a_high=sqrt(2*(0.75**2)-(0.60**2))=sqrt(0.765)`.

| Profile | Symbols 0–127 | Symbols 128–255 |
|---|---:|---:|
| P0 CONSTANT | 0.75 | 0.75 |
| P1 HIGH_TO_LOW | `sqrt(0.765)` | 0.60 |
| P2 LOW_TO_HIGH | 0.60 | `sqrt(0.765)` |

Every profile has frame-average squared gain 0.5625. This does not imply equal
per-symbol SNR. P1 and P2 have the same gain histogram in opposite order; P0
has a different gain distribution, so P1/P0 is not a pure transition-count
contrast.

## Noise, pairing, and receiver boundary

Keep `sigma_squared=0.7115124735378853` and component variances
`sigma_squared/2` for every profile. Do not normalize received samples or
couple noise power to gain. The nominal effective 5 dB reference applies at
gain 0.75; local effective gamma varies with `a[f]`. No physical HF Eb/N0
claim follows.

Within a future paired run, share information bits, coded symbols, normalized
waveform, and one complex noise vector across P0/P1/P2. The receiver sees only
the current profile's received samples and its pre-fixed receiver
configuration. The gain schedule, switch index, true per-symbol gain,
ChannelTruth, correct path, and reference bits are evaluation-side data and
must not be receiver inputs. The switch does not trigger an oracle reset.

The design's future independent cluster is one complete run containing all
three profiles and both receiver policies. Its specified primary is
P1's paired pooled raw-count DeltaBER; secondary profile and SER contrasts
remain descriptive unless a multiplicity rule is separately accepted.

## Compatibility and limits

This decision leaves ADR-015's noise mathematics unchanged and does not alter
ADR-002/005/012/013/014, the receiver, estimator, metric, or decoder. It does
not establish source fidelity: author edge-to-phase mapping and source
equation semantics remain unresolved. Historical `reconstructed_offline`
continues to mean its constant-gain profile. `paper_exact:false` and
`receiver_enabled:false` remain.

Acceptance is not production channel integration, a new receiver mode, or
authorization for a particular run. A separate run-specific M10b approved
snapshot and explicit execution authorization remain required. No future
physical-channel generalization is approved by ADR-016.
