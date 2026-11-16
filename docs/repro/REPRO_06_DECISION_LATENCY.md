# REPRO-06 — decision latency and frame flush

Indices are zero-based TCM transition indices. `η` counts transitions, not states, a GUI window, channel memory, or tail length.

| Frame condition | Ordinary decisions | Flush decisions | Depth used by symbol `i` at flush |
|---|---|---|---|
| `F < η` | None | All `F` | `F-i` |
| `F = η` | Symbol 0 at availability `η-1` | Symbols `1 … η-1` | `η-i` |
| `F > η` | Symbols `0 … F-η`, each at `i+η-1` | Symbols `F-η+1 … F-1` | `F-i` |

For the normal η=20 decision, `decision_available_at = symbol_index + 19`; latency is 19 subsequent symbols. Flush decisions become available at `F-1` and report their actual remaining depth, not an assumed 20. With `F=1`, the only output flushes at depth 1. There are no duplicate or omitted decision indices.

For an unterminated frame, the last available minimum-metric survivor is used. No reference bits or true final state enter endpoint selection. With declared `zero_tail_2`, the final two input pairs are constrained to `(0,0)` and `(0,0)` is the public terminal-state constraint. Receivers continue to remove the four termination information bits only under that explicit policy.
