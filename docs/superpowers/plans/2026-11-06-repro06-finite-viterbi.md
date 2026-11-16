# REPRO-06 Finite-Depth Viterbi Implementation Plan

> **Execution:** Native in this session; the user explicitly requested implementation.

**Goal:** Add a real bounded-memory, transition-depth Viterbi decoder with η=20 and integrate it as an opt-in mode for REPRO-04/05 while preserving full-frame defaults.

**Architecture:** A shared streaming four-state core consumes typed 16-edge metric rows, keeps a ring of survivor predecessors bounded by η, emits delayed decisions, and flushes every remaining symbol using only the last available survivor. Existing full-frame receiver algorithms remain the compatibility path; branch metrics and REPRO-05 estimator order are untouched.

**Tech Stack:** Python 3.13, NumPy, pytest, Ruff; no new dependencies.

**Spec:** User request REPRO-06; source constraints in REPRO-01 A(2) and receiver contracts.

## Global Constraints

- η counts trellis transitions; normal decision for symbol `k-19` becomes available after symbol `k`.
- Existing receiver configurations default to `full_frame`; article-oriented convenience config explicitly selects finite depth 20.
- `zero_tail_2` constrains the last two declared transitions to `(0,0)`; no reference or hidden final state is used.
- No transmitter/channel/metric/estimator/posterior/GUI/M5–M10 changes, Monte Carlo, or REPRO-07.
- `paper_exact:false`, `receiver_enabled:false`, open SCI statuses, and unsupported joint multipath remain unchanged.

## Review Focus

- Flush for `F<η`, `F=η`, `F>η`: exact count, actual depth and no duplicate symbols.
- Online survivor decision edge may differ from the canonical edge obtained by replaying emitted input pairs; preserve both decision records and a valid decoded state/edge path.
- Hamming integer and Euclidean float rows must remain unchanged across decoder modes.
- Joint metric/estimator diagnostics must be identical across modes.
- Compact trace output must omit long survivor history without breaking plot/serialization paths.

## Tasks

1. Add independent finite-depth core tests and implement `finite_viterbi.py` streaming/batch APIs.
2. Extend REPRO-04/05 strict configs with opt-in mode, η, termination/tie/trace policies; integrate after branch metrics are frozen.
3. Add CLI overrides, compact/full diagnostics support, and regression/integration tests.
4. Record performance on short, F=256, and existing F=20,000 metric fixtures; verify frozen M5–M10 fingerprints.
5. Write the seven REPRO-06 reports and update PLAN, NEXT_TASK, and BUILD_VERIFICATION only after final checks.

## Verification

- Target REPRO-06/core and both receiver tests.
- Full pytest using a new workspace-local basetemp; preserve ACL-protected directories.
- Ruff check and format on `src tests`.
- Historical hash comparison to `tmp/m11d-integrity-before.json`, requiring all 694 entries unchanged.
