# M5h pilot preparation implementation plan

## Scope

Prepare a validated, reproducible M5g pilot candidate while keeping execution
unauthorized. Preserve M5f artifacts, ADR statuses, receiver behavior, and all
mathematical kernels. Add an evaluation-only schema, deterministic stream
provenance, and an execution guard which runs before any injected decoder
callback.

## Files

- `src/hf_tcm/evaluation/m5h_pilot_protocol.py`: strict draft validation,
  derived candidate quantities, seed namespace derivation, and guarded pilot
  orchestration with retained failure records.
- `configs/m5h_pilot_draft.json`: explicit candidate configuration and
  embedded validated inactive receiver profile.
- `tests/test_m5h_pilot_protocol.py`: parsing, derivation, gate, provenance,
  contract, and failure retention tests; no stochastic receiver invocation.
- `docs/M5_PILOT_PREPARATION_CONTRACT.md`: complete operational/statistical
  preparation contract, gates, limitations, and workload.
- Existing M5 design/evaluation/bootstrap/open-question/build/phase documents:
  update preparation status without changing historical M5f evidence.

## Sequence

1. Add failing tests for explicit config validation, candidate calculations,
   hierarchical seed separation, unique provenance, and blocked execution.
2. Implement only the evaluation-side protocol and pass the focused tests.
3. Add the explicit JSON draft and verify parse/round-trip without invoking any
   stochastic data/noise/decoder path.
4. Update protocol and phase documentation with candidate vs approved values,
   failure handling, sample-size procedure, resource counts, and gates.
5. Run the user-requested pytest and Ruff commands; record exact results and
   leave confirmation blocked until the required decisions are approved.

## Safety boundary

The checked-in draft remains `design_status="proposed"` and
`execution_authorized=false`. No pilot, Monte Carlo, sweep, tuning, benchmark,
or new BER/SER evidence is produced in this phase.
