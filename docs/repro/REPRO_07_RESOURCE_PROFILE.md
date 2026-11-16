# REPRO-07 resource profile

The F=256 pilot is sequential and has a 2,400-second wall limit, 60-trial maximum, and 2 GB output cap. The F=20,000 resource check uses one paired trial, a 240-second wall budget, and the same disk cap. A REPRO-06C measurement of roughly 153 seconds for one F=20,000 adaptive decode is only a prior single-run observation, not a runtime guarantee.

Per-trial summary records are small. Selected pilot trials save the receiver observation, decoded/reference bits, estimator means, and metric rows in compressed NPZ; unselected raw traces are not retained. The runner does not create a worker pool. Budget checks occur between atomic trial commits; a currently executing pair completes before the runner checks its wall budget again.

Single observed durations in the final report are measurements of these particular executions, not benchmarks. Peak RSS is not reported unless measured by the host process monitor.
