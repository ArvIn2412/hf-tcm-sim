# M11a Interactive Demo Studio implementation report

## Scope and launch

M11a adds a local, dependency-free browser studio for `reconstructed_offline`.
It is an evaluation and presentation interface; it does not enable the receiver,
modify receiver mathematics, create random observations, or rewrite historical
artifacts. The page always labels the model as reconstructed and displays
`paper_exact:false` and `receiver_enabled:false`.

Launch from the repository root:

```powershell
python -m hf_tcm.demo_studio
```

The server binds to localhost. Startup and GET requests expose metadata only;
the existing B4d sequence API and conditional Viterbi run only after the user
presses **Виконати демонстрацію**. Bits, waveform, deterministic noise, and
reference comparison stay on the evaluation side.

## Implemented views

- 28 clickable end-to-end stages with formula, previous/next navigation,
  current symbol/tick/sample indices, provenance, and separate input/output
  values.
- Searchable 14-group parameter registry sourced from approved run configs,
  receiver constants/state, accepted decisions, and dataset artifact metadata.
  Entries show symbol, exact value, unit, default, source, assumption,
  read-only/demo-editable status, constraints, and explanation tooltip.
- Per-symbol inspector with encoder transition, phase, all eight Tx/channel/noise/
  Rx samples, observed I/Q, pre/post estimator states, all 16 predictions,
  metrics, posterior weights, innovation, update components, next-symbol state,
  Viterbi output, and reference error flags.
- Sample-level component plot and exact-value tables including all 16 edges,
  their phase predictions across eight samples, metrics, posterior weights,
  sample-level channel values, estimator state, decoded path, and errors.
- Four-state transition graph, time-expanded trellis with zoom and horizontal
  navigation, and a synchronized 16-edge detail table. The displayed survivor
  and decoded path are from the actual conditional Viterbi API; no
  forward-backward HMM inference is claimed.
- Recursive estimator trajectories and a same-received frozen B versus
  anchored comparison with selectable symbol and hypothesis.
- M5–M10 read-only result dashboard and stage-by-dataset availability matrix.
- Ukrainian thesis-defense step mode with previous/next controls and access to
  the complete parameter view.
- JSON and CSV export of available deterministic demo values only.

The deterministic demo offers four explicit bit patterns, 1/2/4/8/16/32
symbol lengths (the UI exposes 4/8/16/32), frozen B or anchored mode, editable
demo-only `alpha_prime`, `K_tilde`, and `beta`, and three fixed deterministic
noise fixtures. Editing controls does not call the receiver. There is no RNG.

## Pipeline stage disposition

| Stage | Disposition | Data available in deterministic demo |
|---|---|---|
| 01 Information bits | IMPLEMENTED | Explicit evaluation input |
| 02 Grouping into 2-bit inputs | IMPLEMENTED | Exact pairs |
| 03 Encoder state before transition | IMPLEMENTED | Exact M1 state |
| 04 TCM transition selection | IMPLEMENTED | Canonical selected edge |
| 05 Three encoded output bits | IMPLEMENTED | Exact M1 output |
| 06 ADR-002 edge-to-phase mapping | IMPLEMENTED | Reconstructed phase index |
| 07 8PSK symbol generation | IMPLEMENTED | Normalized constellation symbol |
| 08 Rectangular ZOH waveform | IMPLEMENTED | Eight exact complex samples |
| 09 Channel gain application | IMPLEMENTED | Gain-applied samples |
| 10 AWGN contribution | IMPLEMENTED | Explicit deterministic noise samples |
| 11 Received complex samples | IMPLEMENTED | Eight exact complex samples |
| 12 ADR-012 observed-IQ transform | IMPLEMENTED | Eight sample transforms and symbol observation |
| 13 Initial estimator state | IMPLEMENTED | Policy-specific `s0`, `mu0`, and `full0` |
| 14 Full estimator state | IMPLEMENTED | Actual B4d pre-update state |
| 15 Sixteen edge predictions | IMPLEMENTED | 16 × 8 × 2 phase predictions and symbol IQ values |
| 16 Sixteen candidate metrics | IMPLEMENTED | Actual B4d metric row |
| 17 Pseudo-likelihood calculation | IMPLEMENTED | ADR-005 likelihood row and beta |
| 18 Sixteen posterior weights | IMPLEMENTED | Actual posterior and normalization check |
| 19 Posterior-weighted innovation | IMPLEMENTED | Actual operands and derived innovation |
| 20 Recursive coefficient update | IMPLEMENTED | Alpha, correction, and post-state components |
| 21 Next-symbol prediction | IMPLEMENTED | Next row's predictions; unavailable after final symbol |
| 22 Frozen metric sequence | IMPLEMENTED | Actual per-symbol metrics passed to decoder |
| 23 Viterbi dynamic programming | IMPLEMENTED | Actual survivor metrics/predecessors |
| 24 Survivor path / traceback | IMPLEMENTED | Actual conditional Viterbi path/state path |
| 25 Decoded information bits | IMPLEMENTED | Actual conditional Viterbi output |
| 26 Reference comparison | IMPLEMENTED | Evaluation-side bit/symbol flags |
| 27 Bit errors / symbol errors | IMPLEMENTED | Existing raw integer count functions |
| 28 BER / SER / paired statistics | PARTIAL | Single-fixture BER/SER; inferential paired statistics unavailable by design |

Stage 28 remains partial: one deterministic demo is not an independent sample
and cannot produce a paired confidence interval. Historical data availability
is separately reported per dataset; in particular, M5j per-symbol estimator
history is unavailable and aggregate results are not expanded into traces.

## Data provenance and scientific boundary

The demo collector uses actual existing encoder, B4d sequence, metric,
posterior, and conditional Viterbi APIs. It stores actual trace fields beside
explicitly identified evaluation-side derivations. The receiver is never given
reference bits, `ChannelTruth`, or a true channel gain parameter. Clock origins
come from the existing M5i/B4d resolver; sample windows and prediction/metric
cutoffs are retained per symbol.

ADR-002 mapping and ADR-005 pseudo-likelihood remain project reconstruction
choices. Author edge mapping and innovation/correction semantics remain
unresolved; SCI-METRIC-02 remains open. The 16 project posterior weights are
not presented as a confirmed author HMM. No BER performance claim is made.

## Verification

The targeted M11a tests cover complete trace shape, shared initial predictions/
metrics/posterior, canonical 16-edge ordering, eight-sample windows, causal
cutoffs, receiver input isolation, invalid-input rejection, direct conditional
API/Viterbi equivalence, HTTP metadata/POST behavior, and no receiver call on
startup/GET. A live localhost smoke returned 28 stages, four states, and 16
edges; an explicit deterministic POST produced two four-symbol traces and one
Viterbi call per arm. Node syntax checking is used for the browser JavaScript. The full
pytest and Ruff results are recorded in `docs/BUILD_VERIFICATION.md` after the
final verification run.

No historical artifact is an output target of this feature. The project has no
Git metadata in this workspace, so no commit revision is available as a source
fingerprint.

M11b release hardening, actual browser interaction checks, full stage/parameter
coverage, screenshots, and defense materials are documented in
[`M11B_DEMO_RELEASE_QA_REPORT.md`](M11B_DEMO_RELEASE_QA_REPORT.md),
[`DEMO_PARAMETER_COVERAGE.md`](DEMO_PARAMETER_COVERAGE.md),
[`DEMO_DEFENSE_CHECKLIST.md`](DEMO_DEFENSE_CHECKLIST.md), and
[`DEMO_PRESENTATION_SCRIPT.md`](DEMO_PRESENTATION_SCRIPT.md).
