# M5b — single-path BER/SER smoke experiment

**Result:** isolated reproducible single-path BER/SER smoke experiment,
**NOT validated performance comparison**, **NOT reproduction of paper results**.
This report records deterministic control runs only. It does not claim noise
robustness, an SNR point, a BER gain, or statistical sufficiency.

## Experimental scope and input provenance

Runs use `reconstructed_offline`, L=1, a real scalar channel gain, zero delay,
rectangular ZOH at 8 samples/symbol, ADR-012 observed-IQ, ADR-005's explicit
`beta`, and ADR-013 conditional full Viterbi. Each run has its own required
`run_id`, explicit reference bits, gain, perturbation array/provenance, sample
origin, first absolute symbol, initial estimator clock, configuration, receiver
mode, segment partition if applicable, and initial CSI provenance.

The transmit-side reference bits are encoded from M1 state `(0,0)`. M1 output
triples are mapped by ADR-002 `assumed_natural_binary`, modulated by the M1
8PSK mapper, and expanded by the existing rectangular 8-sample waveform helper.
The evaluation-side control generator multiplies those complex baseband samples
by explicit real `a`, then adds the exact supplied complex perturbation array.
Perturbations are deterministic operands, not AWGN, AR(1), or any calibrated
noise model. No RNG is used.

All reported controls use `O=23`, first absolute symbol `f=5`, initial
estimator `time_index=41`; sample labels start at `O+8f=63`. The tested
configuration supplies `beta=0.7`, `alpha_prime=1.0`, `K_tilde=[[0,0]]`,
`mu0=[[0,0]]`, and initial fluctuating/full I/Q estimates `[[a,a]]`. The latter
are explicitly labelled **oracle-initialized control experiment**. This checks
correct-model integration with a fixed initial estimate; it is not an available
truth input or default initialization procedure for the receiver.

Reference bit sequences are supplied explicitly and retained only in the
evaluation record. The deterministic test sequence rule is
`bit[j]=(3*j + floor(j/2) + 1) mod 2`; an additional F=4 variant flips every
other position to verify a second independent input pattern. The receiver
decoder calls receive only generated `received`, configuration-derived
receiver operands, and explicit clocks/partition. Neither reference bits,
transmitted phases, `a`, nor `ChannelTruth` is passed to B5c/B5d.

## Noiseless correct-model controls

Each row represents one distinct run ID in the test/control set. For every row,
the decoder returned the reference information bits and selected a valid M1
edge path. The frozen B4b path cost was zero.

| Run ID | `a` | `F` | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|---:|---:|
| `clean-a075-F1` | 0.75 | 1 | 0 / 2 | 0 | 0 / 1 | 0 |
| `clean-a075-F2` | 0.75 | 2 | 0 / 4 | 0 | 0 / 2 | 0 |
| `clean-a075-F4` | 0.75 | 4 | 0 / 8 | 0 | 0 / 4 | 0 |
| `clean-a075-F6` | 0.75 | 6 | 0 / 12 | 0 | 0 / 6 | 0 |
| `clean-a2-F1` | 2.0 | 1 | 0 / 2 | 0 | 0 / 1 | 0 |
| `clean-a2-F2` | 2.0 | 2 | 0 / 4 | 0 | 0 / 2 | 0 |
| `clean-a2-F4` | 2.0 | 4 | 0 / 8 | 0 | 0 / 4 | 0 |
| `clean-a2-F6` | 2.0 | 6 | 0 / 12 | 0 | 0 / 6 | 0 |

An additional F=4 control used a different explicit input sequence and also
decoded with zero bit and coded-symbol errors. These are finite noiseless
integration checks, not evidence of adaptivity or general performance.

## Explicit perturbation controls

The first three cases use F=2, `a=0.75`, and one nonzero sample perturbation
`0.035 + 0.012j` at offsets 0, 5, and 15 respectively. Each produced 0/4 bit
errors and 0/2 coded-symbol errors in these particular runs. A fourth
deterministic stress operand adds `10 + 10j` to each of the 16 samples of an
F=2 run; it produced 3/4 bit errors and 2/2 symbol errors. That operand is not
assigned a noise distribution or SNR. The zero perturbation case exactly
reproduces the corresponding clean received array.

## Monolithic and segmented processing

For the same F=6, `a=2.0`, reference sequence, received samples, initial
estimator state and configuration, B5c monolithic processing and B5d partition
`(1,2,3)` returned identical received arrays, candidate metrics, decoded edge
path, decoded information bits, final posterior, final estimator state, and
BER/SER counts. Both had zero errors in this noiseless control. Segmentation is
another processing mode for the same reconstructed receiver; it is not a
second baseline algorithm and it does not reset the independent sequence.

## Small pooled-count check

Two deterministic runs demonstrate unequal-length pooling:

| Run ID | `F` | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|---:|
| `perturbed-length-2` | 2 | 3 / 4 | 0.75 | 2 / 2 | 1.0 |
| `clean-length-6` | 6 | 0 / 12 | 0 | 0 / 6 | 0 |
| **Pooled** | **8** | **3 / 16** | **0.1875** | **2 / 8** | **0.25** |

The unweighted means of the two run rates would instead be BER 0.375 and SER
0.5. The aggregator retains both run records and calculates the pooled ratios
from summed raw counts. This two-run arithmetic check is not a Monte Carlo
estimate, uncertainty interval, or performance claim.

## Gates and scientific status

| Gate | Status | Reason |
|---|---|---|
| Explicit noiseless and perturbation received-to-bits composition | READY | Reproducible inputs; M1/M3 waveform helper, B5c/B5d and M5a composition tested. |
| M5a raw per-run and pooled count evaluation | READY | Exact lengths, retained records, pooled ratios verified. |
| Monolithic/segmented equivalence for tested operands | READY | Identical metrics, states, posteriors, paths, bits and error counts. |
| Matched M2 baseline | BLOCKED | M2 symbol-rate observation, noise scaling, channel/CSI and B5 sample-domain operands are not matched. |
| SNR calibration / Monte Carlo | BLOCKED | Shared sample-energy and noise/covariance calibration has not been approved. |
| Confidence intervals | BLOCKED | ADR-014 remains proposed and unaccepted; no bootstrap is run. |
| General complex fading, multipath, frame integration | BLOCKED | Outside the accepted M5b control scope. |
| Paper result or 1.5 dB claim | BLOCKED | This smoke experiment is not a source-faithful reproduction or comparison. |

ADR-001/002/003/004/005/006/007/008/010/012/013 remain accepted;
ADR-009/011/014 remain proposed. No ADR is accepted by M5b. SCI-02, SCI-03 and
SCI-METRIC-02 remain open. `paper_exact:false` and `receiver_enabled:false`
remain unchanged.

## M5c calibration audit follow-up

The smoke perturbation arrays remain deterministic operands and have no AWGN,
AR(1), variance, or SNR interpretation. The M5c audit in
`M5_NOISE_BASELINE_CALIBRATION_AUDIT.md` confirms that M1 symbols have unit
magnitude and M3 repeats each sample eight times without energy normalization.
M2 AWGN remains a separate symbol-rate API. For the explicit `n=8` AR(1)
noise-generator case, the eight-sample mean complex variance is approximately
`0.018307879788` from the API's zero initial state under its independent
unit-normal innovations; this is a conditional derivation, not the M5b noise
model or an SNR point.

The M5b oracle-initialized controls remain labelled as such. M5c added only
deterministic sample-domain diagnostics. M5d subsequently accepted a narrow
discrete-AWGN oracle-CSI matched control and added a paired M2/B5 harness; see
`M5_MATCHED_M2_B5_EXPERIMENT_REPORT.md`. This does not establish physical HF
Eb/N0, adaptive CSI parity, BER gain, or paper reproduction. ADR-014 remains
proposed; SNR sweeps and confidence intervals remain blocked.
