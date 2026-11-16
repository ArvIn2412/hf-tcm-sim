# REPRO-09 functional verification

## Automated checks

`tests/repro/test_scientific_workspace.py` exercises:

- strict configuration validation;
- real Identity and static-multipath transmitter/channel/receiver pipelines;
- matching Joint/Separate observation hashes;
- payload-sized BER comparison and saved NPZ traces;
- manifest verification and trace-window parsing;
- actual Rician AR(1) two-path processing without receiver truth input;
- HTTP page load, asynchronous launch, job polling, saved-run load, and trace retrieval;
- an interrupted REPRO-07 run followed by resume, with one completed trial record and verified output manifest.

The reference channel/receiver code remains the source of numerical results. Tests do not substitute static plot fixtures.

## Real Edge QA

Script: `scripts/qa_repro09_scientific.js`.

It drives the local app through Edge's DevTools Protocol at 1366×768 and 1920×1080. It checks the Ukrainian scientific page, no receiver run on initial GET, no horizontal overflow, an actual noiseless Identity run, hash pairing, data-bound transmitter view, and a real F=32 / one-trial REPRO-07 GUI experiment. Screenshots are:

- `docs/screenshots/repro09-scientific-identity-1366x768.png`
- `docs/screenshots/repro09-scientific-workspace-1920x1080.png`

The Monte Carlo browser scenario is a one-trial functionality smoke, not scientific evidence. Its UI correctly reports that the bootstrap interval is unavailable with fewer than two independent trials.

## Known coverage limits

Browser acceptance has not exhaustively exercised F=20,000, user interruption during a long adaptive pair, opening older REPRO-07/08 formats, or screen-reader/keyboard-only operation. The GUI currently gives truthful status for the unsupported or unverified paths; these limits prevent a REPRO-09 READY verdict.
