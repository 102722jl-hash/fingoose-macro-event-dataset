# FinGoose Ten-Event Timeline FAST_CANDIDATE

release_tier=FAST_CANDIDATE
formal_ready=false
production_dataset_modified=false
scope=timeline_and_source_reconciliation

## Reconciled Counts

- Events: 10
- Timeline nodes: 50
- Verified existing nodes: 42
- Pending evidence nodes: 8
- Promotable milestones: 18
- Workbook episodes: 37
- Accepted supplemental candidates: 25
- Rejected supplemental candidates: 2
- Pending supplemental candidates: 23
- Hard failures: 0

Ten supplemental records were downgraded because their local snapshots do not 
independently reproduce both exact timestamps. Five production-backed targets were 
restored from immutable v2 milestones; five candidate-only targets remain pending.

event-02-M01 remains pending because its Kremlin candidate and EIA precondition fact 
are semantically different records.

This directory remains an isolated research workbook and does not replace production v2.
