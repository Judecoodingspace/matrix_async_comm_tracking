# C7 Pre-Census Input Evidence Audit

```text
DOCUMENT_ROLE = C7_PRE_CENSUS_INPUT_EVIDENCE_AUDIT
AUDIT_MODE = READ_ONLY_PRE_CENSUS_INPUT_EVIDENCE_AUDIT
CONTRACT_CONTENT_AUTHORITY_COMMIT = 131bc41d22f919be24f63ae5f963ba94538daa19
CONTRACT_SHA256 = 044fe9d3538704bace3faa692ddb24d8bff9b0dd0541ed8ac145dbeaed897ec9
APPROVAL_RECORD_COMMIT = 6a8a802828731f20fcfa55a88c8419ca7a72926c
TRACKING_OUTCOME_READ = NO
C7_OUTCOME_READ = NO
```

## Verified usable evidence

| Evidence | Authority | Role | Status |
| --- | --- | --- | --- |
| C7 Contract | frozen Contract commit | Defines C7 semantics, scope, validity, and qualification structure | `INCLUDE` |
| C4 U1/U2 workload derivation | `24778f49ec9c913aadf95199343b12a75fd4078d` | Defines the 25-pair outcome-blind `W_comm` population and the C4 P20/P50/P80 anchors | `INCLUDE` |
| C4 runtime and implementation evidence | tracked runtime and C4 implementation evidence | FIFO, frame budget, logical-packet and identity facts | `INCLUDE` |
| C5 Contract and implementation plan | tracked C5 governance | TRUE-first-service and fail-closed measurement conventions | `INCLUDE_FOR_SEMANTICS_ONLY` |
| C6 temporal forensic report and CSV | `af98328b4bb7779afa7750e1a2cc3836b5df9f23` | Non-outcome structural limitation and observability facts | `INCLUDE_FOR_CONTEXT_ONLY` |

## Excluded evidence

| Evidence | Reason |
| --- | --- |
| C5 aggregate values reported historically as `3836`, `1145`, `0.298488`, and `0.181975` | No independently authoritative, safe pre-C7 C5 aggregate artifact was located. Their later/C6 appearances are not calibration authority. |
| C6 Formal per-cell execution outputs and all C7 outputs | They may reveal later-stage results or capacity-selection information; `DO_NOT_READ`. |
| Tracking metrics and treatment outcomes | Explicit outcome firewall. |

## Audit conclusions

1. The frozen C4 capacities are mechanically derived workload-percentile anchors,
   not engineering lower or upper bounds. They do not themselves determine a
   C7 grid; the later frozen SD-C7-01 does so.
2. The runtime has packet IDs, sequence numbers, per-event service state,
   remaining bytes, frame budget, FIFO order, and conservation fields. C7 still
   requires an extended evidence record for event-local stale proof, residual
   linkage, recipient serviceability, binding loss, and conditional flip.
3. C5 stale opportunity is not C7 eligible redistribution opportunity. C6's
   no-recipient-coexistence result is diagnostic context, not a rate threshold
   and not evidence that redistribution is impossible.
4. A valid observed zero is distinct from missing evidence. Missing identity,
   predicate, conservation, linkage, recipient, or flip evidence must fail
   closed as `CELL_INVALID`; it must not be coerced to zero.

```text
CAPACITY_GRID_EVIDENCE_CLASS = C
C5_AGGREGATE_CALIBRATION_AUTHORITY = NOT_ESTABLISHED
VALIDITY_GATE_SEPARATE_FROM_QUALIFICATION = SUPPORTED
READY_TO_DRAFT_PRE_CENSUS_SPECIFICATION = YES
```
