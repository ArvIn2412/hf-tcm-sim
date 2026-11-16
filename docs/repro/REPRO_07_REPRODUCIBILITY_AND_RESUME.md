# REPRO-07 reproducibility, checkpoints, and resume

Each completed paired trial is stored at `outputs/repro07/<experiment_id>/point_NN/trial_NNNN/trial.json`. The record is written atomically only after both arms and evaluation complete. Optional selected-trial arrays are compressed to NPZ and hashed before the trial record commit. A record binds to the frozen full experiment-config hash and has its own canonical JSON SHA-256.

On resume, completed trial records are hash-checked and skipped; changed experiment configuration or corrupted records are rejected. Failed attempts are kept separately and excluded from aggregates. A partial trial is not committed. Completed trial records are not overwritten. Summary and manifest hashes are rebuilt from verified records, and `verify_experiment()` checks safe relative paths and every manifest digest.

The bounded runner is sequential. Wall-time, trial-count, and disk limits are checked between trial commits; an individual receiver pair is not asynchronously interrupted. A stop produces `incomplete` with committed pairs available for resume. The pilot rerun used resume and retained 60 unique completed trial IDs; it did not rerun their receivers or add duplicate aggregates.

Environment metadata records Python and NumPy versions. Raw diagnostic traces are stored only for selected trial IDs; ordinary trials retain counts, error positions, timing, seeds, and hashes.
