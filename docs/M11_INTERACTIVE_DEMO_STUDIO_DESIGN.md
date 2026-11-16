# M11a Interactive Demo Studio Design

## Scope

Build a locally hosted browser interface for inspecting existing reconstructed
receiver behavior and a deterministic demonstration. The interface is an
evaluation and presentation tool. It does not activate the receiver, change
production mathematics, modify historical data, or run stochastic experiments.

## Architecture

- A Python standard-library HTTP server binds only to `127.0.0.1`.
- A small evaluation-side trace collector calls the existing B4d conditional
  sequence API once per selected policy and the existing conditional Viterbi
  decoder through that API. It records available raw and derived operands.
- Static HTML, CSS, and JavaScript render navigation, tables, plots, trellis,
  comparison, and Ukrainian defense-presentation mode. No external CDN or
  runtime package is required.
- A parameter registry is assembled from the exact demo/run configuration,
  accepted constants and decisions, receiver state, and dataset metadata;
  the browser receives provenance and availability with each value.
- Historical artifacts are opened read-only. Missing per-symbol information
  is represented as unavailable, never synthesized from aggregate summaries.

## Trace lifecycle

Changing a form value updates pending controls only. The receiver is called
only after the user presses “Виконати демонстрацію”. The default fixture uses
explicit information bits and explicit deterministic complex noise values.
No random generator is constructed. B4d history supplies pre/post estimator
states, observations, predictions, metrics, posterior, innovation and clocks;
the conditional decoder supplies frozen metrics, decoded path, survivor
metrics and predecessor IDs. Transmitter, channel and reference comparison
fields are evaluation-side provenance, not receiver operands.

## Views

1. Full pipeline with 28 clickable stage blocks, formula/input/output,
   parameters, clock, provenance, and explicit missing-data state.
2. Parameter registry with subsystem groups, search, exact values, units,
   default/source/assumption/editability/constraints/explanation.
3. Symbol inspector with exact 8-sample window and 16 canonical hypotheses.
4. Four-state/16-edge graph and time-expanded trellis with edge table and
   synchronized selected/decoded-path highlighting.
5. Recursive estimator with coefficient components and trajectories.
6. Explicit-action deterministic demo and B-versus-anchored comparison.
7. Exact tables and JSON/CSV export of available actual/derived values.
8. Dataset coverage matrix and experiment dashboard for M5–M10.
9. Ukrainian thesis-defense presentation mode.

## Scientific display invariants

Every screen displays `RECONSTRUCTED MODEL`, `paper_exact:false`, and
`receiver_enabled:false`. ADR-002 mapping and ADR-005 pseudo-likelihood remain
project reconstruction choices; author mapping and innovation semantics stay
unresolved. A deterministic demonstration is prominently marked as not
scientific evidence. Viterbi metrics are conditional on the frozen causal
metric sequence; the UI does not represent them as forward-backward HMM
inference.

## Verification strategy

- Test trace collection against actual API result fields and explicit clocks.
- Test independent scalar conventions for bit/encoder/phase/sample windows.
- Test conditional decoder path and survivor shapes and ensure a single decode
  per policy.
- Test parameter provenance and dataset coverage against loaded artifacts.
- Test HTTP launch, key routes, deterministic rerun, and no RNG construction.
- Test that pending GUI edits do not invoke the trace collector until explicit
  action.
- Run the full pytest suite and Ruff; do not modify historical output files.

## Implemented local interface

The M11a implementation is available through `python -m hf_tcm.demo_studio`.
It uses only the Python standard library for the localhost HTTP server and
static HTML/CSS/JavaScript. The browser offers pipeline, parameter, symbol,
trellis, estimator, deterministic demo, comparison, exact tables, archived
dashboard/coverage, and Ukrainian presentation views. Startup and GET routes
do not call the receiver. An explicit POST from the demo button invokes the
evaluation-only trace collector.

The current collector retains actual B4d pre/post state, 16 candidate metric
rows, posterior/innovation operands, 8-sample predictions, clocks/cutoffs, and
the conditional Viterbi result. It separately marks transmitter, deterministic
noise, channel, and reference-comparison data as evaluation-side. The exact
demo BER/SER is a single-fixture count; inferential paired statistics are
unavailable. Historical dataset coverage remains schema-specific rather than
being inferred from aggregate results.

## Known data boundary

The deterministic demo is the full-coverage inspection source. Historical
datasets expose different trace depths: M5j is aggregate-only for per-symbol
estimator history; M6b/M6g/M6h contain deterministic diagnostics but not a full
transmitter/channel sample record; M7b/M8b/M9b/M10b expose saved evaluation
records with their own schemas. The UI will report each field's coverage from
the corresponding artifact rather than filling gaps.
