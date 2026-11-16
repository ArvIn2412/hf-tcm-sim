# M5k — post-confirmatory scientific audit

**Status:** post-confirmatory scientific audit and read-only estimator diagnostics, **NOT new performance evidence**, **NOT a paper-exact receiver**. No M5j/M5h rerun, new receiver observation, Monte Carlo sample, sweep, or parameter search was launched. `paper_exact:false` and `receiver_enabled:false` remain unchanged.

## 1. M5j execution completeness

The approved M5j run config is `configs/m5j_confirmatory_approved_run.json`: `design_status=approved_confirmatory`, `execution_authorized=true`, and `execution_scope=m5j_confirmatory_only`. The planned evaluation manifest has 100 ordered IDs, separate evaluation data/noise/bootstrap roots, and the frozen seed derivation. The M5j record partition is evaluation; no M5h pilot seeds or records are included.

All `run-001` through `run-100` checkpoints exist and match the manifest order. Audit results:

| Check | Result |
|---|---:|
| Unique planned and completed run IDs | 100 / 100 |
| Complete paired B/C records | 100 / 100 |
| Unique received hashes, shared within each B/C pair | 100; all paired hashes match |
| Numerical/runtime decoder failures | 0 |
| Total information bits, each receiver | 51,200 |
| Total coded symbols, each receiver | 25,600 |
| Decoded symbols, B and C | 25,600 each |
| Evaluation seeds match approved manifest | Yes |
| Pilot/evaluation separation | Confirmed |

The saved `independent_verification.json` agrees on IDs, received hashes, seed provenance, paired hashes, decoder symbol totals, and pooled counts. `summary.json` reports `complete`, 100 valid records, 0 failure records, and 0 not-completed records.

## 2. Historical artifact integrity

SHA-256 values were recorded before the audit and the same outputs were hashed after read-only audit and tests. No M5f, M5h, or M5j historical output changed.

| Artifact set | Before/after SHA-256 |
|---|---|
| Approved M5j run config | `8a9cb4c2d42a0b7014a40d5b83b9da13e7d1a65fe2fa3a68e1d90d5a53607840` |
| Planned M5i evaluation manifest | `6b63e12f6463680af603944a43e576afa15e08b1b84155273fbbbc42c4fb5b15` |
| M5j summary | `a2fc4e86d1c5dbddbc7254fba16a4a20a32bbd87db3576eaecc83cc8ca0cc2c6` |
| M5j independent verification | `c40c82e906d6e5c2e4d5aa5fefcf61c571e963d2bf085a560ac6f4354898e305` |
| Ordered set of 100 M5j checkpoint name/hash pairs | `4947265547217a76de785bdbd68577b581a8fd079e1d6b17dc459f6a9fb05992` |
| Entire M5j output tree (102 files) | `a14f2e59725d060d4114bc34f48c0d130e5be8716716b2f7efaa6e68585fa600` |
| Entire M5h output tree (128 files) | `81ccf68090c2e64a0ddc90b25033cd73e073cfaaa93c5522ccf6e02105d38dc7` |
| M5f saved records | `93d5993cbad256eaf4363118c4b3a44b01fb14da82ca9450520213eda4dfc2e6` |
| M5f config / report | `cca939a2ea1e0e8668f2197c709d3b210c0cf0fb735f1d15b2f9d6128f8cde8e` / `da8038f373aca4c43f24821d46b3d0dbda4b630878ffc266e17e8457a899f7c1` |

Original M5j runner fingerprint remains recorded in the approved config as `ebb588d63c73e80372b568ef8ea10df95882fba3f8f13d4da6fcd0e9e6f2e930`. The runner source changed after M5j only to fix summary printing; its current SHA-256 is `b651db32e44a603c7d1ac527b7de434f45571a6c1b963bf7f1fd9b47daf77360`, so it differs from M5j runtime provenance. The approved config and all historical output bytes were not rewritten.

## 3. Independent raw-count verification

The audit read each checkpoint's integer `b_counts` and `c_counts`, summed those counts independently, and compared the results with both saved JSON summaries. No receiver function was called.

| Receiver | Bit errors / bits | Pooled BER | Symbol errors / symbols | Pooled SER |
|---|---:|---:|---:|---:|
| Frozen B | 1,079 / 51,200 | 0.02107421875 | 1,003 / 25,600 | 0.0391796875 |
| Adaptive C | 19,793 / 51,200 | 0.38658203125 | 17,956 / 25,600 | 0.70140625 |
| C − B | — | **0.3655078125** | — | **0.6622265625** |

**AUDIT DISCREPANCY — float serialization only:** direct binary-float subtraction of the two BER values is represented as `0.36550781250000003` in `summary.json` and the API; the count-derived decimal is `0.3655078125`. This is a ~`3e-17` representation difference, not a count, pooling, or scientific discrepancy. Saved and replayed confidence bounds likewise differ only in their last floating-point bits; all six match within `2e-16`. No substantive audit discrepancy was found.

## 4. ADR-014 bootstrap audit — read-only statistics

The bootstrap was independently recomputed from the 100 saved paired integer-count clusters. This replay generated only resampling indices and statistics, **not receiver observations, bits, noise, or decoder outputs**.

| Contract element | Audit result |
|---|---|
| Cluster unit | One complete independent F=256 coded sequence per run |
| Paired index reuse | Same ordered resample index vector applied to B and C |
| Replicates / confidence | 2,000 / two-sided 95% percentile |
| Pooling | Raw integer errors and denominators pooled per replicate |
| Seed / generator | `3940591365597190145` / NumPy `PCG64` |
| Quantile method | `numpy.quantile(method="linear")` |
| Exclusions / stopping | No post hoc exclusions; fixed `R=100` |
| Warnings | None |

| Metric | Recomputed 95% percentile CI |
|---|---:|
| BER_B | [0.017265625, 0.02498193359375] |
| BER_C | [0.37710888671875, 0.395900390625] |
| DeltaBER | [0.35548681640625, 0.37578173828125] |
| SER_B | [0.032734375, 0.045705078125] |
| SER_C | [0.6882421875, 0.7135244140625] |
| DeltaSER | [0.6474599609375, 0.6771494140625] |

The primary interval half-width is `0.0101474609375`, below the declared `epsilon=0.02` target. The target was not a stopping or extension rule. Bootstrap inference assumes independent clusters across the independently seeded sequences; within-sequence dependence is retained by resampling whole sequences.

## 5. Confirmatory interpretation

For the **predefined B/C policies** under the one fixed ADR-015 `L=1` discrete-AWGN profile, adaptive C had higher pooled BER than frozen B in the independent M5j sample: `DeltaBER = BER_C − BER_B = +0.3655078125`; its primary 95% paired cluster-bootstrap interval `[0.35548681640625, 0.37578173828125]` excludes zero. The declared precision target was reached. The secondary `DeltaSER` was `+0.6622265625`, with 95% interval `[0.6474599609375, 0.6771494140625]`.

This supports a limited statement about this fixed paired contrast under ADR-014's assumptions. It does not establish universal adaptive inferiority, B optimality, failure of a paper method, general HF performance, a physical `Eb/N0` gain/loss, general multipath behavior, or that recurrence [A](1) is mathematically incorrect. The result is not evidence for conditions beyond the declared profile.

Keep these concepts separate:

- **Mathematical implementation correctness:** implementation and tests can establish the code's algebra and invariants; they do not identify a source ambiguity's intended meaning.
- **Reconstruction assumptions:** ADR-002/005/012/013/015 define project choices, not source-author confirmation.
- **Estimator stability:** finite saved trajectories establish only finite values on these 100 runs, not convergence or stability in general.
- **Fixed-policy performance:** the observed paired contrast is estimable for the frozen policies/profile and sample under ADR-014.
- **Source-paper scientific fidelity:** not established; `paper_exact:false`, with open SCI questions and unaccepted ADR-009/011.

## 6. Estimator/root-cause hypotheses

All “tests” below are existing deterministic equation/API tests; they constrain implementation behavior but do not validate scientific fidelity or prove causal attribution. A proposed control is for a separately reviewed future diagnostic with new seeds where applicable. Do not use reference bits or true `a` to steer the recursion.

| Hypothesis | Possible mathematical mismatch | Invariant to check | Existing tests/evidence that constrain it | Missing evidence | Independent control test | Status |
|---|---|---|---|---|---|---|
| **H1. Fixed `alpha_prime` / `K_tilde` configuration is unfavorable** | The retained-state coefficient and signed quadrature correction may have poor scale for the mismatch/noise/sequence regime. Values `0.85`, `(0.35,-0.2)` are explicit project settings, not source-derived stability guarantees. | Hand-computed update equals `alpha_prime * previous + K_tilde * posterior_weighted_innovation`; zero correction (`K=0`) reduces to retention only; inputs remain finite. | `test_paper_recursion.py`, `test_reconstruction_posterior_estimator_step.py`; frozen operands are pinned in config and M5j. | No independent stability analysis or source-author parameter rationale; M5j did not store full innovation/state history. | Derive one alternative from a prior source/math review, freeze it before any new seeds, then inspect a short per-symbol diagnostic trace; do not sweep or select by BER. | **UNRESOLVED** |
| **H2. ADR-012 observed-IQ convention differs from [A](5) prediction** | The mapping `(-Im(y), Re(y))` and exactly-eight-sample mean may not represent the author's complex/IQ orientation or observation statistic. | For every 8-sample window, observed coordinates equal the explicitly declared transform; prediction and observation use the same quadrature order and sample cutoff. | `test_iq_prediction.py`, `test_reconstruction_candidate_metrics.py`, `test_reconstruction_posterior_estimator_step.py` validate declared convention and fixtures. | No source-author confirmation that ADR-012 is the intended symbol/sample bridge; no source-faithful end-to-end convention. | Independent hand calculations over all 8 phases and nontrivial complex samples, plus a source-convention decision before receiver comparison. | **UNRESOLVED** |
| **H3. Innovation semantics in [A](1) are reconstructed incorrectly** | The equation may intend a different residual, timing, averaging, or posterior-index convention than the implemented posterior-weighted `Y−Uhat_h`. | Compute every residual, posterior weighted sum, and next coefficient independently for a hand fixture; confirm posterior weights align with the same canonical hypotheses and current symbol. | `test_paper_recursion.py`, `test_reconstruction_posterior_estimator_step.py`; code documents the exact implemented operands. | The printed equation/source does not settle all index, timing, and observation conventions; no author confirmation. | Use a hand-constructed posterior with unequal weights and independent scalar residuals; compare algebra term by term, then separately review source interpretation. | **UNRESOLVED** |
| **H4. Correction direction, scale, or sign is adverse** | Componentwise `K_tilde` signs/magnitudes may amplify error in one coordinate or combine with a sign-convention mismatch. | Compare each signed component against direct calculation; test sign reversal and zero-gain cases; verify `full = fluctuating + mu0`. | `test_paper_recursion.py`, step/state tests cover explicit coefficient update and decomposition; M5j `mu0=(0,0)`. | No authoritative source-derived M5j correction coefficient or direction; checkpoints omit per-symbol residuals needed to attribute trajectories. | Deterministic synthetic cases with known residual vectors and both signed gains; record values only, no decoded performance selection. | **UNRESOLVED** |
| **H5. Posterior-weighted operand interacts poorly with 16 edge hypotheses** | Posterior mass over project-local edge hypotheses could be misaligned with phase labels, transitions, or the estimator residual operand. | The 16 weights are nonnegative and sum to one; row ID, edge, output bits, phase, prediction, metric, and residual share canonical order. | `test_reconstruction_candidate_metrics.py`, `test_reconstruction_posterior_estimator_step.py`, `test_reconstruction_conditional_decode.py` check ordering, normalization, mappings, and likelihood flow. | Source `theta`/edge correspondence and author posterior/likelihood remain open; no saved per-symbol posterior in M5j. | Independently enumerate all 16 edge residual terms for a fixed fixture and compare posterior-weighted sum and transition update to the API. | **UNRESOLVED** |
| **H6. Later branch metrics depend on earlier estimator updates** | The current symbol's posterior/update changes the pre-state used for symbol `f+1`, which can change later candidate costs and the final conditional path. | `state(f+1) = post_state(f)`; metric `f` uses pre-state `f`; changing unavailable future samples cannot change prior metrics/state. | `test_reconstruction_posterior_estimator_sequence.py`, `test_reconstruction_conditional_decode.py`, and adaptive diagnostic causality tests exercise sequencing and cutoffs. | M5j checkpoints do not retain per-symbol pre/post states or candidate metrics to quantify which updates changed which selected path. | With new seeds, store the actual per-symbol metric/state trace and separately recompute a test-only frozen-state control; do not feed reference bits or true gain to recursion. | **SUPPORTED as an implementation dependency; contribution to the M5j BER contrast UNRESOLVED** |
| **H7. Frame-constant forward model differs from the per-symbol adaptive receiver** | `reconstruction_forward.py` holds coefficients constant over a frame, while B4d can update them each symbol; the waveform/metric model may therefore differ from the recursive receiver trajectory. | For an explicitly declared frame, candidate predictions use the same coefficient snapshot for every sample; for adaptive B4d, only the next symbol uses a just-completed post-state. | `test_reconstruction_paired_monte_carlo.py`, adaptive sequence tests and `test_reconstruction_candidate_metrics.py` validate the implemented per-symbol composition; M4 docs record the open schedule gap. | No source-defined frame scheduling rule that maps [A](5) to the per-symbol recursion; M5j history does not contain prediction snapshots. | After source schedule review, create a deterministic bridge test comparing frame-frozen and per-symbol predictions under declared identical inputs, without re-decoding historical M5j metrics. | **SUPPORTED as a model-schedule difference; causal contribution UNRESOLVED** |
| **H8. ADR-005 pseudo-likelihood differs from source-faithful likelihood** | Posterior emission `exp(-beta * F_rx)` uses a reconstructed squared-residual metric whose relation to source [A](2) is not settled. | For any declared likelihood, row probabilities normalize and obey its stated residual/scale; never silently substitute one likelihood for another. | `test_reconstruction_posterior_estimator_step.py`, candidate metric and posterior tests validate ADR-005's implementation and normalization. | SCI-METRIC-02 remains open; source equation's missing/unclear square and likelihood scale are not resolved. | Obtain an independently reviewed source reading, then add a hand-derived likelihood fixture; any alternate performance comparison needs its own frozen protocol and authorization. | **SUPPORTED as an explicit ADR-005 reconstruction choice; causal contribution UNRESOLVED** |

No H1–H8 causal mechanism is established by M5j. H6–H8 identify existing implementation/model differences that could matter, but their contribution to the result is unmeasured. No tuning was performed and no parameter is recommended from these outcomes.

## 7. Read-only coefficient diagnostics and history availability

Available in M5j checkpoints:

- Initial full-IQ estimate `[0.42, 0.91]` for all 100 runs. The approved design also records the identical initial fluctuating estimate; the checkpoint does not separately store that initial field.
- Final full-IQ and fluctuating-IQ values; because fixed `mu0=(0,0)`, their saved values are identical on all runs.
- 25,600 full-IQ increment norms, one per symbol, pooled across runs: minimum `0.0011519989244`, median `0.1733958345`, maximum `0.5307475518`.
- All 100 `finite_coefficient_trajectory` flags are true.
- Evaluation-only final coefficient-error norm: mean `1.0933054668`, median `1.1073315266`, maximum `1.6477646003`. This diagnostic was recorded after decoding and did not enter estimator updates.
- Per-run B/C decoded error counts and decoded symbol totals.

Across the 100 final full-IQ states, component means are `(0.0002324491, -0.0047189956)` and component ranges are `[-0.6369456371, 0.5482927199]` and `[-0.4153344494, 0.4730906790]`.

**HISTORY UNAVAILABLE:** M5j does not save per-symbol pre/post states, innovations, posterior vectors/normalization values, observed IQ operands, candidate metrics, or exact update operands. Increment norms do not recover those missing values. No such histories were inferred from final states, and no historical branch metrics were recomputed using final coefficients. A future isolated diagnostic would need a separate protocol, fresh seeds, and explicit per-symbol logging; it must not alter M5j or constitute another confirmatory sample.

## 8. Causality and metric lifecycle audit

The inspected code and deterministic tests establish the current implementation lifecycle:

1. Symbol `f` samples are the exact 8-sample window `[O+8f, O+8f+7]`. Sample, symbol, and estimator clocks are explicit and need not share a numeric origin.
2. Candidate predictions/metrics use the pre-observation full-IQ estimator state; the prediction cutoff is `O+8f−1`. The metric becomes available after the last current-symbol sample `O+8f+7`.
3. The first edge uses the ADR-004 prior supported at initial memory state `(0,0)` without a transition. Continuations use the immediately preceding posterior, then the transition, then the current emission.
4. The current row's posterior is formed from that row's actual metrics and is the posterior supplied to [A](1). The update consumes only operands available by the end of symbol `f`.
5. The post-state for `f` is labelled for use at `f+1`; sequence code sends only the observed sample prefix through the current symbol into the current update.
6. The canonical 16-hypothesis order is checked across candidate rows, posterior, phase mapping, and decoder inputs.
7. B5b consumes the completed frozen `(F,16)` metric history once after the sequence; it does not re-decode each prefix or rebuild past metrics from a final estimate.

These are implementation-causality properties, supported by the named step, sequence, candidate, conditional-decode, and IQ-prediction tests. They do not show that ADR-012/005 or the reconstructed posterior is the scientifically correct source model.

## 9. Scientific limitations retained

- One fixed effective discrete `gamma_b=5 dB` point only.
- One L=1, real channel gain `a=0.75`, zero delay.
- Independent sample-level circular complex AWGN under ADR-015.
- `reconstructed_offline`, not paper-exact; ADR-005 pseudo-likelihood.
- Conditional full Viterbi over a frozen causal metric history; not joint channel/decoder inference.
- Fixed mismatched initial estimate `(0.42,0.91)` and fixed update coefficients/policies.
- No tuning or evaluation adaptation.
- Cluster-bootstrap inference assumes independence across sequence clusters.
- No physical radio-energy calibration or physical HF `Eb/N0` interpretation.
- No correlated AR(1), multipath, or complex fading evaluation.
- `U0` versus `U**` correspondence remains unresolved.
- SCI-02, SCI-03, and SCI-METRIC-02 remain open; ADR-009/011 remain proposed.

## 10. Future independent diagnostic options

These are options for a separately designed and authorized question; **none is launched by M5k**.

1. **Fresh-seed trace capture:** use a separately frozen diagnostic seed set and the existing fixed B/C policies to persist per-symbol pre/post states, observed IQ, posterior sums, candidate metrics, update operands/increments, cutoffs, and decoded error counts. Treat as estimator diagnostics, not new confirmatory performance evidence.
2. **Deterministic algebra controls:** independent hand calculations for nonuniform posterior weights, sign/component corrections, `mu0` decomposition, and zero-gain/zero-innovation cases. These need no receiver observations and can resolve implementation invariants, not source meaning.
3. **Model correspondence tests:** after scientific review, independently test ADR-012 IQ mapping and frame/per-symbol scheduling with hand-derived fixtures; record any changed assumption as a separate decision before performance work.
4. **Likelihood/source review:** resolve SCI-METRIC-02 from primary source evidence before proposing any source-faithful likelihood. A comparison would need a separately frozen protocol and must not overwrite historical results.

Do not rank parameter variants by BER or tune C from M5j. A future fixed-profile confirmatory comparison, if desired, requires a new research question, new seeds, immutable protocol, and explicit authorization.

## 11. Gates

| Gate | Status |
|---|---|
| M5j execution completeness, paired provenance, stored-count replay | **READY** |
| ADR-014 bootstrap replay and `epsilon=0.02` precision target | **READY / MET** |
| Narrow fixed-profile confirmatory statement | **READY**, under stated assumptions only |
| M5j final summary printing regression | **READY**, tested with synthetic complete/incomplete summaries |
| Estimator per-symbol mechanism attribution | **BLOCKED — HISTORY UNAVAILABLE** |
| Source-paper fidelity, generalization, physical HF/multipath claim | **BLOCKED / out of scope** |
| New performance experiment, parameter tuning, or receiver activation | **NOT AUTHORIZED** |

No new ADR is needed for this audit: no scientific assumption or accepted ADR was changed. Keep accepted ADRs 001/002/003/004/005/006/007/008/010/012/013/014/015, proposed ADR-009/011, and the open SCI questions unchanged.

## Verification record

- The specifically requested `python -m pytest -q --basetemp .pytest-m4-7b-temp -p no:cacheprovider` could not use the existing ACL-restricted basetemp (19 setup errors, 709 tests passed); repeating outside the sandbox found the same Windows `Access denied` condition. No operation was made on that inaccessible directory.
- The same full suite passed using the new workspace-local basetemp: `python -m pytest -q --basetemp .pytest-m5k-temp -p no:cacheprovider` — **728 passed in 4.75s**.
- `ruff check src tests` — **All checks passed**.
- `ruff format --check src tests` — **120 files already formatted**.
- M5k's new regression tests use only synthetic summaries and saved checkpoint counts; they block the runner's receiver call and diagnostic execution. The full repository suite also contains pre-existing deterministic seeded unit fixtures for the M5e/f composition; these are not a new M5k/M5j evaluation sample and did not modify historical artifacts.

## M6a follow-up — causal trace tooling, not a reanalysis of M5j

M6a adds `evaluation/reconstruction_causal_trace.py`, which copies actual B4d/B4c per-symbol rows from a caller-provided deterministic sample buffer, compares frozen B with adaptive C, freezes each mode's exact metric history, then calls B5b once. It generates no sample/noise and takes no reference bits or channel truth. The independent deterministic fixture observes post-state divergence at symbol 5 and first candidate-metric divergence at symbol 6 under its explicit fixed inputs. This shows the implemented next-symbol dependency only.

**M5j historical per-symbol trace remains unavailable.** M6a does not reconstruct old states/metrics from final estimates, does not change the fixed M5j conclusion or numerical results, and supplies no new performance evidence. H1–H5 remain unresolved. H6 is supported as an implementation dependency only; H7/H8 are supported as documented model distinctions only. Their contribution to M5j's errors remains unresolved. Full field provenance and status matrix are in `M6_CAUSAL_ESTIMATOR_TRACE_CONTRACT.md`. No new ADR is needed; open SCI-02, SCI-03, SCI-METRIC-02, `paper_exact:false`, and `receiver_enabled:false` remain unchanged.

## M6b-prep protocol note

A separate proposed M6b protocol is frozen in `M6_FRESH_TRACE_DIAGNOSTIC_PROTOCOL.md`, with the H1-H8 measurement/refutation matrix in `M6_ROOT_CAUSE_TEST_MATRIX.md`. It plans three fresh-seed sequences of F=32 under the historical fixed M5j B/C policies, with paired received input. The draft remains proposed, unauthorized, and scope `none`. Preparation generated no RNG streams, data/noise, receiver output, or performance evidence. H1-H5 remain unresolved; H6 is supported only as an implementation dependency; H7/H8 remain documented model distinctions with causal contribution unresolved. The M5j historical trace remains unavailable. No open SCI question or ADR status changed; separate M6b-run authorization is required.

## M6b-run readout

Three authorized paired fresh-seed causal traces completed under a separate
approved M6b snapshot; M5j/M5h were not rerun and no M5 historical bytes were
changed. The recorded per-run adaptive diagnostic BER/SER values are not a new
performance claim and do not alter M5j's fixed-policy conclusion. All three
runs show an implementation-level update-to-next-metric dependency; no H1-H8
scientific root cause was established. M5j historical per-symbol trace remains
unavailable. SCI-02, SCI-03, SCI-METRIC-02, proposed ADR-009/011,
`paper_exact:false`, and `receiver_enabled:false` remain unchanged. Full
results and limitations are in `M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md`.
