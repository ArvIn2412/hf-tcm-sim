# M10b statistical protocol and execution record

**Status:** the design below was frozen by the M10a draft and executed under
the separate approved M10b run snapshot. See
`M10_VARIABLE_GAIN_EVALUATION_REPORT.md` for results, provenance, and audit
details.

## Paired design

The proposed study has 100 independent run clusters, each with 256 symbols.
For each run, generate one information sequence, encode once, build one
waveform, and generate one AWGN vector. Apply the same bits, waveform, and
underlying noise to each gain profile P0/P1/P2. For each profile, decode the
profile-specific received buffer once with frozen B and once with
`anch_a085_k025`.

Expected workload: 100 run clusters, 3 profiles, 2 policies, 300
profile-specific received buffers, 600 policy records and decoder calls,
614,400 received complex samples, and 153,600 policy-symbol passes. The
independent cluster is the complete run containing all profiles and policies;
300 profile buffers are not 300 independent observations.

## Estimands

The single primary contrast is

```text
DeltaBER_P1 = BER(anchor, P1_HIGH_TO_LOW) - BER(B, P1_HIGH_TO_LOW)
```

Positive values mean higher BER for the anchored policy. Descriptive
secondary contrasts are DeltaBER for P0 and P2, DeltaSER for all three
profiles, `DeltaBER_P1-DeltaBER_P0`, and `DeltaBER_P2-DeltaBER_P1`. They do not
receive confirmatory claims without a separately specified multiplicity
policy. Coefficient errors, coefficient changes, and before/after-switch
segment counts are descriptive diagnostics only.

## Bootstrap

Use ADR-014 paired cluster bootstrap with 100 full-run clusters and 2,000
resamples. Each replicate draws 100 run indices with replacement and applies
those same indices across B/anchor and all three profiles. Pool raw integer
counts within each resample and report 95% percentile intervals using
`numpy.quantile(method="linear")`. Do not resample bits, symbols, or profile
rows independently. The primary interval is for DeltaBER_P1; any other
interval is descriptive.

## Failure and stopping rules

Complete joint-profile inference requires all planned paired outputs. Record
missing or invalid outputs and block full-design inference; do not impute them
as zero, substitute a seed, or replace a run. Preserve valid high-error
outputs. There is no data-dependent stopping. A numerical failure is reported
as an integrity outcome, not silently turned into an error count. No
equivalence or noninferiority claim is allowed without a justified margin
fixed before independent observations.

## Frozen RNG and run provenance

No M10 RNG was initialized in M10a. The frozen draft specified domain-separated
`SeedSequence(master_seed, spawn_key=(1295337521,1001,run_index,stream_code))`
and PCG64, where run index is 0..99 and stream codes are data 11, noise 23,
bootstrap 37, and metadata 41. Proposed roots are data 2027030101, noise
2027030102, bootstrap 2027030103, and metadata 2027030104. Planned IDs are
`m10_controlled_piecewise_gain_v1:evaluation:run-001` through `run-100` in
ascending order. The separate approved M10b snapshot materialized the exact
child-seed manifest, and the verified run used only these M10 roots. They are
distinct from M5–M9 roots and observations.

## Resources and authorization

The approved execution was single-process with 600 policy decodes, one atomic
checkpoint per run, a 900-second wall-clock budget, and periodic 1.5 GiB RSS
monitoring. RSS polling was not a hard OS memory limit. Observed resource use
is reported in `M10_VARIABLE_GAIN_EVALUATION_REPORT.md`.

## Execution result

The independent recount verified all 100 clusters, 300 profile-specific
received buffers, 600 records, and 600 decoder calls. The predefined P1
DeltaBER point estimate was -0.0003125 and its 95% paired cluster interval
was [-0.00205126953125, 0.0014453125], which includes zero. No equivalence,
noninferiority, physical HF, or paper-exact claim follows.
