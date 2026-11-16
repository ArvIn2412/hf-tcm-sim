# REPRO-02 Transmitter Implementation Plan

> Native execution follows the user's explicit REPRO-02 implementation request.

**Goal:** Build a reproducible, isolated Encoder A → reconstructed 8PSK → rectangular ZOH transmitter with traceable outputs, serialization, plots, and CLI.

**Architecture:** New code lives in src/hf_tcm/repro/ and consumes the REPRO-01 source vectors. It uses a versioned ADR-002 mapping profile, direct complex-baseband symbols, and immutable NumPy arrays; no channel or receiver is called. The production encoder and M5–M11 code remain unchanged.

**Tech Stack:** Python >=3.11, NumPy, standard-library JSON/hashlib/argparse, existing matplotlib dependency only if already installed; no new dependencies.

**Spec:** docs/repro/REPRO_01_*.md and REPRO-02 user request.

## Global constraints

- Keep paper_exact false and receiver_enabled false.
- Δφ = π/4; source-aligned sample count is 8 per TCM symbol.
- ADR-002/natural-binary output triple mapping remains explicitly reconstructed.
- Do not add RF carrier, pulse shaping, channel, receiver, BER/SER, or Monte Carlo.
- Do not modify M5–M11 code/artifacts or accepted ADR.
- No silent padding, truncation, or normalization.

## Review focus

1. Manual bit order/length and no silent tails — config/source tests.
2. Every REPRO edge ID agrees with independent vectors — exhaustive oracle tests.
3. Nonzero initial state and zero-tail policy — multi-step encoder tests.
4. Phase origin/amplitude are explicit, mapping fingerprint stable — mapping/modulator tests.
5. Large frame keeps exact F, 3F, 8F shapes and metadata — 20,000-symbol end-to-end test.

## File map

- src/hf_tcm/repro/config.py: strict transmitter configuration.
- source_bits.py: manual, deterministic, and seeded PCG64 bit sources.
- encoder.py: independent Encoder A transition loop and termination metadata.
- labeling.py: versioned ADR-002 edge mapping and fingerprint.
- modulator.py: complex 8PSK mapping.
- waveform.py: rectangular ZOH and sample indices.
- transmitter.py: immutable aggregate result and run_transmitter.
- serialization.py: explicit JSON summary plus NPZ numeric arrays and hashes.
- plots.py: read-only source-backed transmitter plots.
- __main__.py: JSON-config CLI.
- configs/: minimal, deterministic example, and N*=20000 transmitter-only profile.
- tests/repro/: validation, independent vectors, mapping, modulation, ZOH, end-to-end, serialization, CLI and large frame.
- outputs/repro02/: reference run summary, manifest, arrays and figures.
- docs/repro/REPRO_02_*.md: implementation and verification reports.

## TDD tasks

### 1. Configuration and source bits
- Write failing tests for malformed binary strings, even grouping, max frame, pattern modes, and PCG64 repeatability/state metadata.
- Implement frozen config and isolated source generation; run focused tests.

### 2. Encoder and edge identity
- Write failing exhaustive tests from the 16 REPRO-01 JSON vectors plus independent formula oracle.
- Implement immutable result, state/input edge-ID convention, initial state, no-tail and two-zero-pair termination.
- Test multi-step patterns, state coverage, final state and encoded lengths.

### 3. Mapping, modulation, sampling
- Test all edge mapping values/fingerprint, 8 phases, explicit φ0/amplitude, unit symbol energy when amplitude=1, and ZOH sample/index boundaries.
- Implement named mapping, complex symbols, and sample metadata.

### 4. Aggregate transmitter, serialization and CLI
- Add failing end-to-end fixture tests, JSON config strictness, explicit complex serialization/round trip, deterministic output hashes and CLI no-implicit-run behavior.
- Implement run_transmitter, immutable result schema, manifest and CLI.

### 5. Plots, performance and integration checks
- Test plot adapters consume result arrays only and emit required files/axis metadata.
- Run a 20,000-symbol transmitter-only measurement and preserve real arrays, manifest and plots under outputs/repro02/.
- Run focused suite, full pytest command, Ruff src/tests, verify frozen fingerprints, and finish required documentation.

## Execution note

The user requested execution now. This plan records the implementation contract; proceed task-by-task with RED → GREEN checks. Do not run REPRO-03.
