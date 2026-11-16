# M8a anchored reconstructed adaptation design

**Status:** proposed and unauthorized. M8a produced no random streams,
received observations, stochastic experiments, decoder results, or performance
evidence. Its target outcome is an independently proposed research design,
not an optimized receiver, validation result, or paper-exact implementation.
The frozen draft is
[`m8a_anchored_study_draft.json`](../configs/m8a_anchored_study_draft.json),
SHA-256 `0740500746cfc340207d3b30a9e9cc62209e620c6a108926b1623cd7e46d960c`.

## 1. Research question and motivation

M7's fixed nine-policy TRAIN grid selected frozen B. That exploratory result
does not establish that adaptation is generally harmful, but it motivates a
specific reconstructed-model question: does the zero reference `mu0=(0,0)`
cause the current no-correction recursion to shrink its full coefficient
estimate toward zero when `alpha_prime<1`? M8 proposes a receiver-side
nominal anchor equal to the already-used initial estimate and asks whether a
small fixed set of anchored policies behaves differently on independent
sequences.

M7b already informed this hypothesis. Its runs and checkpoints are not M8
training observations; M5j is not M8 validation. M8 is a subsequent,
hypothesis-generating project study. It neither waits for nor asserts an
author definition of `mu0`.

## 2. Exact reconstructed recursion and decay derivation

Let `s_n` denote the fluctuating I/Q coefficient vector after `n` updates,
`mu0` the regular/anchor vector, and `full_n=s_n+mu0`. The implemented
reconstructed recursion is

```text
s_(n+1) = alpha_prime * s_n + K_tilde elementwise eps_n
full_n  = s_n + mu0
```

For `K_tilde=(0,0)`, repeated substitution gives

```text
s_n    = alpha_prime^n * s_0
full_n = mu0 + alpha_prime^n * (full_0 - mu0)
```

Consequences for the fixed cases:

1. **Zero anchor.** If `mu0=(0,0)`, `full_0=(0.42,0.91)`, and
   `K_tilde=(0,0)`, then `full_n=alpha_prime^n*full_0`. For
   `0 <= alpha_prime < 1` this tends to zero. This is an exact property of
   the stated recursion, not an empirical fit.
2. **Anchor at initial estimate.** If `mu0=full_0=(0.42,0.91)`, then
   `s_0=(0,0)` and with `K_tilde=(0,0)`, `full_n=mu0` for every allowed
   `alpha_prime`.
3. **Unit alpha.** For arbitrary `K_tilde`, rewrite the full-state update as
   `full_(n+1)=alpha_prime*full_n+(1-alpha_prime)*mu0+
   K_tilde elementwise eps_n`. At `alpha_prime=1`,
   `full_(n+1)=full_n+K_tilde elementwise eps_n`; with identical initial
   full state and identical innovations, changing the anchor does not change
   the full-state trajectory.
4. **Subunit alpha with correction.** For `alpha_prime<1` and nonzero
   `K_tilde`, the full-state update contains `(1-alpha_prime)*mu0`. The anchor
   therefore has a nontrivial direct effect and may also alter future
   predictions, posterior, and innovations in closed loop.

The first two claims are algebraic. They do not establish stochastic
stability, boundedness under feedback, coefficient accuracy, or BER benefit.

## 3. Profile and anchor interpretation

The proposed `anchored_reconstructed_offline` profile inherits the accepted
reconstruction: L=1, real channel gain `a=0.75`, zero delay, normalized 8PSK,
rectangular ZOH at 8 samples/symbol, ADR-002 mapping, ADR-005 pseudo-likelihood,
ADR-012 observed I/Q, ADR-013 conditional full Viterbi, and the ADR-015
independent circular complex AWGN profile at effective discrete
`gamma_b=5 dB`. Here `sigma_squared=0.7115124735378853`; this is not physical HF
`Eb/N0`.

The proposed anchor is `mu0=(0.42,0.91)`, with initial fluctuating state
`s0=(0,0)` and full estimate `(0.42,0.91)`. Historical reconstruction uses
`mu0=(0,0)`, `s0=(0.42,0.91)`, and the same full estimate. Thus initial
predictions, candidate metrics, and posterior are expected to agree when
other inputs are identical. The anchor is a fixed receiver-side nominal
initial estimate. It is not the channel truth `a=0.75`, oracle CSI, or a
source-paper recommendation. True channel gain remains unavailable to the
receiver and may be used only in evaluation-side coefficient-error
diagnostics after receiver execution.

The existing B4c sequence API accepts the initial `ReconstructionEstimatorState`
and `mu0` as separate operands. Deterministic tests confirm it can represent
the two initial decompositions without changing a kernel. The forward
prediction snapshot uses the supplied initial full estimate; the update
continues to compute `full=s+mu0`. No production API or receiver mode is
changed by M8a.

## 4. Deterministic mathematical checks

M8a adds no random fixture. Tests use explicitly defined finite received
samples only for the production B4c lifecycle checks, and independent scalar
arithmetic for expected recursion values. They verify:

- `full_0=s_0+mu0` and identical initial full estimates for both profiles;
- identical initial 16 predictions, local metric row, and posterior;
- geometric decay for zero anchor and `alpha_prime=0.95/0.85` with `K=0`;
- constant full estimate for anchor-equals-initial and `K=0`;
- anchor invariance of the full-state trajectory at `alpha_prime=1` for
  equal inputs and innovations;
- the permitted anchor-dependent update term at subunit alpha with nonzero K;
- pre-observation metric formation, 16-edge order, and per-symbol cutoffs;
- no receiver inputs for reference bits, `ChannelTruth`, or true gain;
- unauthorized guard rejection before any RNG/data/receiver callback.

The tests audit existing reconstructed semantics. They do not establish
source-equation intent or full stochastic behavior.

## 5. Fixed eight-arm candidate design

All arms share `beta=0.7` and initial full I/Q `(0.42,0.91)`. The six new
anchored candidates use `mu0=(0.42,0.91)` and initial fluctuating state
`(0,0)`. `K_tilde=K_scale*(0.35,-0.2)`.

| Candidate | alpha_prime | K_scale | K_tilde | Role / anchor |
|---|---:|---:|---|---|
| `anch_a100_k025` | 1.00 | 0.25 | (0.0875, -0.05) | New anchored candidate |
| `anch_a100_k050` | 1.00 | 0.50 | (0.175, -0.1) | New anchored candidate |
| `anch_a095_k025` | 0.95 | 0.25 | (0.0875, -0.05) | New anchored candidate |
| `anch_a095_k050` | 0.95 | 0.50 | (0.175, -0.1) | New anchored candidate |
| `anch_a085_k025` | 0.85 | 0.25 | (0.0875, -0.05) | New anchored candidate |
| `anch_a085_k050` | 0.85 | 0.50 | (0.175, -0.1) | New anchored candidate |
| `historical_frozen_B` | 1.00 | 0.00 | (0, 0) | Historical B control, zero anchor |
| `historical_combined_C` | 0.85 | 1.00 | (0.35, -0.2) | Historical C control, zero anchor |

These are proposed finite candidate values, not optimized parameters. The six
anchored arms are a new project variant; none is attributed to the authors.

## 6. Future partitions and seed separation

The candidate TRAIN design has 40 new independent sequences, F=256 symbols
(512 information bits), and eight decoder calls per sequence. All eight arms
share one transmitted sequence and one received realization within each run.
If the TRAIN-selected candidate is anchored and separately authorized,
VALIDATION has 40 new sequences with two arms (frozen B and the single frozen
anchored candidate), 80 decoder passes, 20,480 policy-symbol passes, and
81,920 unique received samples. Validation is not run if B wins TRAIN.
TRAIN, VALIDATION, and future FINAL each have separate proposed data, noise,
bootstrap, and experiment-metadata namespaces. Proposed roots are recorded
in `configs/m8a_anchored_study_draft.json` and are distinct from M5/M6/M7
roots. They are labels in a draft, not generated seeds or initialized RNG
streams.

The derivation rule is:

```text
SeedSequence(master_seed,
             spawn_key=(1295337521, partition_code,
                        zero_based_run_index, stream_code))
  -> uint64 child seed -> PCG64
```

Proposed partition codes are TRAIN=801, VALIDATION=802, future FINAL=803;
stream codes are data=11, noise=23, bootstrap=37, metadata=41. Run IDs use
`m8_anchored_reconstructed_adaptation_v1:<partition>:run-NNN`, with displayed
indices 001–040 for TRAIN/VALIDATION. Future FINAL sample size, run range, and
inferential design remain for separate approval. No child seeds are derived
in M8a.

## 7. Selection, failure, and validation policy

Among candidates with 40 complete valid paired records, TRAIN selects the
minimum pooled raw-count BER. Ties break by lower pooled SER, lower absolute
K scale, alpha closer to 1.0, then lexicographic candidate ID. Frozen B may
win. If B wins, do not promote the runner-up and do not run a B-versus-B
adaptive validation; close the exploratory result.

Invalid or incomplete candidates are ineligible; do not pool only successful
runs. Retain finite high-error trajectories and all failures. Do not impute
zero or maximum errors, replace seeds, or silently exclude records. An
incomplete frozen B blocks paired selection. Validation, if a non-B anchored
candidate is selected and separately authorized, compares only that frozen
candidate with frozen B on 40 new sequences and cannot reselect. A future
FINAL requires a separately approved independent confirmatory design.

M8 training minima are selection-biased descriptive statistics. Coefficient
error, computed only after receiver execution, is a diagnostic and is not a
selection criterion. No gain in physical dB or BER curves is in scope.

## 8. M8b TRAIN execution record

M8b was explicitly authorized for TRAIN only. Its approved snapshot preserved
the eight M8a arms and profile, but the attempt is
`TRAIN_INCOMPLETE_OR_BLOCKED`: 40 TRAIN bit/noise inputs were generated and
checkpointed, while all 320 policy records failed before decoder invocation
with `KeyError: 'clock_origins'`. The M8a JSON does not define that object.
There are no valid decoder outputs, raw error counts, eligible candidates,
ranking, or selected policy. No missing result was imputed as zero.

The output records 40 unique run IDs and received hashes, zero decoder calls,
and explicit failures for all eight arms in every run. Validation and FINAL
were not executed. The M8b namespace and approved snapshot are separate from
M7b and earlier evidence. Historical M5f/M5h/M5j/M6b/M6g/M6h/M7b artifacts and
the M8a draft/checksum matched the pre-run baseline.

The runner's clock lookup has since been corrected to record sample and
estimator origins from the accepted receiver configuration and symbol origin
zero for a new independent sequence. That source revision differs from the
M8b execution fingerprint; the original approved snapshot cannot authorize a
resume. No attempt was repeated, no seed was replaced, and no M8c validation
is available because there is no TRAIN-selected candidate. See
[`M8_ANCHORED_TRAIN_REPORT.md`](M8_ANCHORED_TRAIN_REPORT.md). Any retry requires
a separately frozen and explicitly authorized M8b run snapshot.

## 9. Workload, guards, and limitations

Candidate TRAIN workload was 40 sequences × 8 arms = 320 unique decoder
passes, 81,920 policy-symbol passes, and 81,920 unique received complex
samples. The attempted M8b run generated 81,920 received samples but invoked
zero decoders because every arm failed before receiver entry. The failed
attempt's actual resource readings are in
[`M8_ANCHORED_TRAIN_REPORT.md`](M8_ANCHORED_TRAIN_REPORT.md).

`configs/m8a_anchored_study_draft.json` is
`proposed / false / none`. Its evaluation-only validator checks the exact
profile, anchor decomposition, eight arm definitions, partition counts,
seed separation, selection/failure rules, and resource counts. The guard
blocks before RNG/data/noise/receiver callbacks. An M8b approved snapshot was
created for the attempted TRAIN run; its source fingerprint no longer matches
the post-failure corrected runner, so it cannot authorize a resume. There is
no automatic TRAIN→VALIDATION→FINAL transition.

The study remains limited to a single fixed effective discrete gamma point,
L=1 real channel, zero delay, and the stated reconstruction conventions.
Author edge-to-phase mapping, quadrature and innovation semantics, and
SCI-02/SCI-03/SCI-METRIC-02 remain unresolved. M7b is not reused for training;
M5j is not validation. `paper_exact:false`, `receiver_enabled:false`; no ADR
was accepted.

## 10. Next minimal step

M8c is blocked because M8b produced no eligible TRAIN-selected policy. Any
corrected M8b attempt requires a new explicit TRAIN-only authorization,
run-specific config/runtime fingerprints, a separate output namespace, and a
decision about whether the exact fixed TRAIN IDs/seeds may be replayed to
reconstruct the incomplete attempt. Do not promote an unobserved runner-up.
If a later complete M8b selects an anchored arm, M8c still requires its own
independent VALIDATION design and authorization; FINAL remains separate.

## M8b technical recovery outcome

A later, separately authorized technical recovery replayed the exact same M8a
TRAIN IDs, seeds, and received buffers in a separate namespace after fixing
the orchestration-only `clock_origins` lookup. All 40 received hashes matched
the immutable failed attempt before decoding; 320 records and 320 decoder
calls completed. Frozen B ranked first, so the result remains
`TRAIN_SELECTED_NOT_VALIDATED`; no validation or final evaluation was run.
This same-seed recovery is not an independent replication sample. Details and
raw-count ranking are in
[`M8_TRAIN_RECOVERY_REPORT.md`](M8_TRAIN_RECOVERY_REPORT.md). The anchored
policy hypothesis was not selected on this TRAIN partition; do not promote a
runner-up or start M8c from these exploratory results.

### M8c closeout and M9a proposal

M8's recovered exploratory TRAIN is closed with historical frozen B as the
winner. The post-hoc runner-up contrast is recorded separately and does not
change M8's winner or status. No M8 validation was run. M9a proposes a
separately fixed comparison of `anch_a085_k025` and frozen B on a new
constant-gain partition; it remains unauthorized and generated no streams or
samples. See [`M9_FIXED_POLICY_COMPARISON_DESIGN.md`](M9_FIXED_POLICY_COMPARISON_DESIGN.md)
and [`M9_VARIABLE_CHANNEL_RESEARCH_NOTE.md`](M9_VARIABLE_CHANNEL_RESEARCH_NOTE.md).
