# REPRO-09 GUI/backend integration

## Architecture

REPRO-09 extends the existing dependency-free M11 `ThreadingHTTPServer`; it does not create a second server or duplicate scientific algorithms. `/` retains the M11 demo. `/scientific` serves the new Ukrainian workspace.

The single-run adapter is `hf_tcm.studio.scientific`:

```text
ScientificRunConfig
  → TransmitterConfig / run_transmitter (REPRO-02)
  → ChannelConfig / run_channel (REPRO-03)
  → one ReceiverObservation
  → run_adaptive_multipath_receiver (REPRO-06C)
  → run_separate_receiver (REPRO-04 B0)
  → evaluation adapters, after both receivers return
  → NPZ traces + JSON summary + SHA-256 manifest
```

Both receiver calls receive the exact same `ReceiverObservation`; neither receives `ChannelResult` or `EvaluationTruth`. Evaluation truth is stored in a separate `evaluation_truth.npz` only after receiver calls have completed.

The Monte Carlo API wraps REPRO-07 `ExperimentConfig` and `run_paired_experiment`. An optional stop event is checked at paired-trial boundaries. It does not interrupt a receiver midway through a pair or alter receiver calculations. Resume uses the same frozen configuration and REPRO-07's verified completed-trial records.

## HTTP contract

| Method / path | Behavior |
|---|---|
| `GET /scientific` | Serve the scientific workspace; no simulation runs. |
| `POST /api/scientific/run` | Validate config and queue one paired single-frame run. |
| `GET /api/scientific/jobs/{job_id}` | Poll actual job status/result summary. |
| `GET /api/scientific/runs` | List hash-verified saved single runs. |
| `GET /api/scientific/runs/{run_id}` | Verify manifest and load a saved summary without rerunning. |
| `GET /api/scientific/traces?run_id=…&start=…&count=…` | Load a bounded 1–256 symbol trace window from NPZ. |
| `POST /api/scientific/experiments` | Queue a REPRO-07 paired experiment. |
| `POST /api/scientific/jobs/{job_id}/stop` | Request stop after the current paired trial. |
| `GET /api/scientific/experiments` | List manifest-verified saved MC summaries. |
| `GET /api/scientific/experiments/{experiment_id}` | Verify and load the stored MC result. |

The server overrides output roots to `outputs/repro09/` and `outputs/repro09/monte-carlo/`; user-supplied paths are not accepted by HTTP. IDs are restricted to safe filename characters. The job manager runs one scientific task at a time to bound memory and avoid concurrent adaptive receivers.

## Data and equations

The GUI invokes existing APIs only. It does not implement the encoder, channel, demodulation, estimator, Viterbi, or statistics in JavaScript. Browser charts are read-only bindings to persisted trace arrays. Full-precision traces remain in compressed NPZ; only the requested trace window is sent to the browser. Truth and receiver estimates are separate data products.

The single-run saved payload contains transmitter data, received samples, B0 hard/metric diagnostics, Joint branch metrics and estimator history, path contributions, noise, and channel coefficients. `manifest.json` stores SHA-256 for config, summary, trace arrays, and evaluation truth. Static multipath public coefficients are part of the experiment configuration; generated Rician coefficients remain evaluation truth.

## Current supported selection

- Identity, AWGN, static one-path, static multipath, and Rician AR(1) multipath use validated REPRO-03 configs.
- Joint single-run uses REPRO-06C with finite-depth Viterbi, η=20, and the configured public prior/profile. Separate uses original B0, finite-depth η=20.
- REPRO-08 B1 is selectable for supported public-static single runs only; it is not available for time-varying Rician fading or the Monte Carlo GUI. Static-known REPRO-06B is not an additional receiver choice in this workspace.
- Rician/unknown channel estimates are receiver products; exact generator coefficients are never injected into receiver inputs.
- The GUI provides a sample-domain variance grid and correctly avoids presenting physical Eb/N0 or energy-gain estimates.

## REPRO-09B additions (2026-11-10)

- `GET /api/scientific/viterbi?...&survivor_state=N` selects an actual destination-state survivor for a bounded trace window. Omitting it keeps minimum accumulated path metric endpoint selection. The response includes `endpoint_state_id`, predecessor trace, branch-cost rows and real survivor decisions; no transmitter truth is read to construct the trace. The archived long-frame route supports the same selection.
- `GET /api/scientific/samples?...` supplies the independent 20-complex-sample zoom. `GET /api/scientific/traces?...` remains a 20-symbol data window. The UI's canonical shared symbol index drives transmitter, channel, receiver and Viterbi views; local form controls mirror that state.
- Single-run `include_b1` is routed to the existing REPRO-08 `run_channel_aware_hard_receiver` only for public static/identity channel inputs. B1 receives `ReceiverObservation` and explicitly configured taps; time-varying Rician configs are rejected/disabled. The backend checks all receiver observation hashes before marking the run paired.
- The GUI continues to call REPRO-07 `run_paired_experiment` for Monte Carlo. Browser acceptance exercised stop-at-pair, persisted incomplete checkpoint, resume with the same frozen config, and completed 10/10 trials (2 variance points × 5 independent pairs). Confidence intervals use the runner's paired trial-cluster bootstrap. This small pilot is exploratory; the GUI does not present it as confirmatory evidence. MC currently compares Joint with B0, not B1.
- The lazy F=20,000 archive loader verifies REPRO-08 and REPRO-06C manifests and reads only the requested Viterbi window. It keeps their distinct source observations separate (`same_observation=false`); archive I/Q payload is unavailable, so the UI does not fabricate a joined waveform/trace.
- New launcher, verified with automatic browser open: `python -m hf_tcm.repro.scientific_studio --port 18769`. `src/hf_tcm/demo_studio.py` remains the historical demo entry point and no longer handles the scientific view flag.
- The scientific launcher passes `default_view="scientific"` to the shared server. Consequently both `/` and `/scientific` resolve to the workspace when using this launcher; `make_server()` still defaults to the legacy M11 demo root for the historical launcher.
