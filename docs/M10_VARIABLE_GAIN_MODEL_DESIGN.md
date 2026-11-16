# M10 controlled real-gain variation model

**Status:** accepted evaluation-only model under ADR-016 (2026-10-30);
M10b completed under a separate approved run snapshot. The adapter does not
integrate a production channel or receiver mode.

## Research question

M9 did not resolve the direction of the fixed-policy BER difference under a
constant gain. M10 asked whether the paired BER difference between
frozen B and the unchanged `anch_a085_k025` policy differs under a controlled
within-frame real-gain change. Adaptive improvement is not presumed.

This channel is an accepted project experimental extension, not a physical HF fading
model and not a source-aligned profile. The historical receiver remains
`paper_exact:false`, `receiver_enabled:false`; author edge-to-phase mapping is
still source-unresolved.

## Model and fixed noise

For `n=0..2047` and `f=floor(n/8)`, the accepted evaluation-side channel is

```text
y[n] = a[f] * x[n] + w[n]
```

`x[n]` is the same normalized 8PSK rectangular-ZOH waveform for all profiles.
`w[n]` is one independent circular complex AWGN realization shared across
profiles within a run. Gain is real, positive, zero-delay, memoryless, and
applied at the transmitter/channel side. No gain schedule, switch position,
true gain, or ChannelTruth is passed to the receiver. Receiver policies use
only profile-specific received samples and their own state histories. No
oracle reset occurs at the switch and no received-signal normalization is
applied.

The noise variance remains `sigma_squared=0.7115124735378853` for all
profiles; real and imaginary component variances are each
`sigma_squared/2`. The 5 dB effective discrete reference applies to nominal
gain 0.75 only. Local `gamma_b[f]=4*a[f]^2/sigma_squared` varies with gain;
the whole frame is not described as physical HF Eb/N0=5 dB.

## Exact profiles

`F=256`, switch after symbol 127, new gain at symbol 128, and sample switch
index `128*8=1024`.

| Profile | Symbols 0–127 | Symbols 128–255 |
|---|---:|---:|
| P0 CONSTANT | 0.75 | 0.75 |
| P1 HIGH_TO_LOW | `sqrt(0.765)=0.8746427842267951` | 0.60 |
| P2 LOW_TO_HIGH | 0.60 | `sqrt(0.765)=0.8746427842267951` |

The high gain is defined by `2*(0.75**2)-(0.60**2)=0.765`. Thus each profile
has frame-average `a^2=0.75^2=0.5625`. Equal frame-average `a^2` does not imply
equal per-symbol SNR. P1/P2 have the same gain histogram in a different order.
P0 comparisons also change the gain distribution, not only transition count.
This design does not isolate every causal aspect of nonstationarity.

## Deterministic implementation boundary

`evaluation/controlled_piecewise_real_gain.py` accepts explicit waveform,
noise, and gain schedule arrays and computes the channel equation. It does not
create an RNG, generate a waveform, call a receiver, or expose channel truth.
Its tests compare the implementation with independent scalar arithmetic,
check all three schedules and the exact sample-1024 boundary, verify a
zero-noise oracle and P0 constant-gain expression, and run the two fixed
receiver policies on deterministic inputs to verify the receiver sees only
received samples and causal clocks.

The switch occurs on a symbol boundary, so no symbol receives two gains. The
model has no delay, channel memory, multipath, or complex fading. Existing
constant-gain contracts are unchanged.

## Fixed policies

| Policy | alpha_prime | K_tilde | mu0 | Initial fluctuating IQ | Initial full IQ | beta |
|---|---:|---|---|---|---|---:|
| `historical_frozen_B` | 1.00 | (0, 0) | (0, 0) | (0.42, 0.91) | (0.42, 0.91) | 0.7 |
| `anch_a085_k025` | 0.85 | (0.0875, -0.05) | (0.42, 0.91) | (0, 0) | (0.42, 0.91) | 0.7 |

No reset or parameter change is made at the switch. M10b would remain a
conditional full-frame Viterbi evaluation. Its estimator updates are causal,
but full-frame traceback can use metrics from the whole frame. Any
pre-/post-switch error counts would therefore be descriptive full-frame
segment diagnostics, not online prefix-decoder or latency measurements.

## Accepted decision and execution record

ADR-016 accepts only the evaluation-side gain generator. The M10a draft
remains unchanged with its original proposed/unauthorized status. M10b used a
separate approved snapshot and completed 100 run clusters, 300 profile
buffers, and 600 fixed-policy decodes. Its independently recounted primary
P1 interval includes zero. No receiver mathematics or production channel
behavior changed. See `M10_VARIABLE_GAIN_EVALUATION_REPORT.md` for hashes,
counts, bootstrap, and the transparent correction of the runner's initial
seed-state audit comparison.

The machine-readable draft remains `proposed / false / none`; its SHA-256 is
`80ec2ea30e04bfeb02508380b94f29bb08140a1906fa61816d137ed56798066f` and the
adjacent `.sha256` sidecar matches the draft bytes.
