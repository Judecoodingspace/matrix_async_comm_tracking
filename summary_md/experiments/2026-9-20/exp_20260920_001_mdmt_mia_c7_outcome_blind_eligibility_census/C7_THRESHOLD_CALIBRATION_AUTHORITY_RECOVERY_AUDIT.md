# C7 Threshold Calibration Authority Recovery Audit

```text
DOCUMENT_ROLE = C7_THRESHOLD_CALIBRATION_AUTHORITY_RECOVERY_AUDIT
AUDIT_MODE = READ_ONLY_OUTCOME_BLIND_PRE_C7_AUTHORITY_RECOVERY_AUDIT
CONTRACT_CONTENT_AUTHORITY_COMMIT = 131bc41d22f919be24f63ae5f963ba94538daa19
CONTRACT_SHA256 = 044fe9d3538704bace3faa692ddb24d8bff9b0dd0541ed8ac145dbeaed897ec9
APPROVAL_RECORD_COMMIT = 6a8a802828731f20fcfa55a88c8419ca7a72926c
INPUT_AUDIT_SHA256 = d0074016e6a311b04e53c245e43f954f6c7fba764f5e0275555ed8eb6b4ad302
PRE_CENSUS_SPEC_SHA256 = f120a75088910524b1c268bc7258f8386800ed1c1d1caf015c342f22ca5b5797
```

## Search method and scope

The audit searched current tracked files and all reachable Git history for C4,
C5, and C6 measurement/report/result paths and for stale, first-service,
denominator, opportunity, queue pressure, unfinished service, completion,
suppression, coexistence, count, ratio, and rate fields. It examined C5
authorization/qualification governance, C4 contracts and implementation
evidence, C6's frozen temporal forensic report/CSV, and the first historical
appearance of the four cited C5 numbers. It did not run code or reconstruct a
new scientific quantity from raw traces.

## Historical artifact provenance

| Stage | Artifact | First introduced / frozen commit | Authority type | Result |
| --- | --- | --- | --- | --- |
| C4 | `COMMUNICATION_C4_U1_U2_WORKLOAD_DERIVATION.md` | `24778f49ec9c913aadf95199343b12a75fd4078d` | Original outcome-blind workload derivation | Capacity only; wrong threshold dimension |
| C4 | C4 qualification contracts/runtime evidence | C4 governance history | Original service semantics | No pre-defined aggregate binding/noncompletion-window metric |
| C5 | C5 Contract, plan, qualifications, and run-003/run-004 authorizations | C5 history through `09747e7de973b8a08f0cd08c97e3649fc2b8496b` | Original semantic/authorization governance | Defines metrics but contains no tracked scientific aggregate result |
| C6 | `C6_TEMPORAL_COEXISTENCE_READ_ONLY_AUDIT.md` and CSV | `af98328b4bb7779afa7750e1a2cc3836b5df9f23` | Frozen pre-C7 non-outcome forensic measurement | Direct epoch/support counts; limited structural context |
| C6/C7 | `C6_C7_DECISION_INPUTS.md` | `e752f251e8619c88824237c48e9a392012b609c6` | Later post-hoc explanatory summary | Secondary only; not calibration authority |

## Historical C5 aggregate investigation

```text
C5_3836_1145_AUTHORITY_STATUS = SECONDARY_ONLY
```

- `0.298488` and `0.181975` have no pre-C7 Git-history occurrence. Their first
  tracked occurrence is the later C7 governance text that quotes them as
  unverified historical discussion values.
- `3836` and `1145` first occur in reachable tracked C6-stage material, notably
  commit `284807b3ce8c0ee90de5af6509af27121a49edbd`, in C6 generated-source,
  MVE, and raw-ledger-related artifacts rather than a C5 original aggregate
  report.
- C5 run authorizations enumerate permitted metric names and frozen cells but
  contain no run aggregate values. No tracked C5 scientific-result root or
  authoritative C5 aggregate report was recovered.

Therefore the cited numbers have no verified original C5 numerator,
denominator, unit, or frozen source identity for calibration. They are
`EXCLUDE_NO_AUTHORITY` and cannot enter any distribution.

## Threshold calibration authority recovery table

| Candidate ID | Stage | Artifact / commit | Historical definition and unit | D_count | D_den | D_global | D_cond | Final status | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| CA-01 | C4 | U1/U2 derivation / `24778f49` | `W_comm`, bytes/frame, 25 workload pairs | No | No | No | No | `EXCLUDE_WRONG_DIMENSION` | Bytes/frame is neither a structural-event count nor a conditional denominator/rate. |
| CA-02 | C4 | C4 runtime/service evidence | Per-packet service states and finalization | No | No | No | No | `EXCLUDE_RETROSPECTIVE_QUANTITY` | Binding/noncompletion windows were not historically defined/saved as an aggregate measurement. Raw service traces do not authorize a new retrospective event definition. |
| CA-03 | C5 | C5 Contract/plan | Checked first-service packets and whole-packet non-applicability definitions | No | Definition only | No | Definition only | `INCLUDE_FOR_DEFINITION_ONLY` | Definitions are authoritative; an original aggregate/distribution is absent. |
| CA-04 | C5 | cited `3836/1145/0.298488/0.181975` | Claimed checked/non-applicable aggregates and ratios | No | No | No | No | `EXCLUDE_NO_AUTHORITY` | No original C5 aggregate artifact, definitions, or immutable source recovered. |
| CA-05 | C6 | forensic CSV / `af98328b` | `suppression_epochs` per sealed trajectory: `[699,699,359,299]` | Yes | Yes | No | No | `INCLUDE` for count and denominator only | It is an already-defined discrete recurring stale/suppression structural event and stale-present support unit; it is not C7 eligibility or a completion flip. |
| CA-06 | C6 | forensic CSV / `af98328b` | `suppression_epochs / frame_count`: `[699/700,699/700,359/360,299/300]` | No | No | Candidate | No | `CANDIDATE_MECHANICAL_DERIVATION_REQUIRES_REVIEW` | Both primitive columns exist, but a historical global-frequency measurement was not recorded; direct division requires separate acceptance before inclusion. |
| CA-07 | C6 | forensic report / `af98328b` | strict recipient coexistence counts, all zero | No | No | No | No | `EXCLUDE_DEFINITION_MISMATCH` | It is a negative C6 coexistence observation, not a historically defined C7-compatible conditional completion-flip frequency. |
| CA-08 | C6 | post-hoc C6→C7 input note / `e752f251` | explanatory C5/C6 trajectory discussion | No | No | No | No | `EXCLUDE_INCOMPLETE_PROVENANCE` | Later secondary explanation; not original calibration authority. |

## Distribution-level decision

### D_count

```text
D_COUNT_AUTHORITY_STATUS = RECOVERED
D_COUNT_MEMBERS = [699, 699, 359, 299]
D_COUNT_MEMBER_COUNT = 4
PROVISIONAL_Q20_COUNT = 335
PROVISIONAL_T_COUNT = 335
```

The members are direct, already-defined C6 `suppression_epochs` counts per
sealed trajectory. `Q20=335` follows the frozen linear P20 operator and the
provisional count threshold is `ceil(335)=335`. This is a read-only mechanical
derivation, not a change to the C7 Specification.

### D_den

```text
D_DEN_AUTHORITY_STATUS = RECOVERED
D_DEN_MEMBERS = [699, 699, 359, 299]
D_DEN_MEMBER_COUNT = 4
PROVISIONAL_Q20_DEN = 335
PROVISIONAL_T_DEN = 335
```

Each suppression epoch is a historically recorded stale/suppressible
antecedent support window. It is compatible only with denominator-support scale,
not with C7 eligibility results.

### D_global

```text
D_GLOBAL_AUTHORITY_STATUS = PARTIALLY_RECOVERED
D_GLOBAL_MEMBER_COUNT = 0
PROVISIONAL_Q20_GLOBAL = NOT_COMPUTED
PROVISIONAL_T_GLOBAL = NOT_COMPUTED
```

The forensic CSV contains direct epoch and frame-count columns; their ratios
would be `[699/700,699/700,359/360,299/300]` and a mechanical P20 would be
`997/1000`. However that ratio was not an existing frozen historical
measurement. It is preserved only as `CANDIDATE_MECHANICAL_DERIVATION_REQUIRES_REVIEW`, not included in `D_global`.

### D_cond

```text
D_COND_AUTHORITY_STATUS = NOT_RECOVERABLE_FROM_EXISTING_PRE_C7_AUTHORITY
D_COND_MEMBER_COUNT = 0
PROVISIONAL_Q20_COND = NOT_COMPUTED
PROVISIONAL_T_COND = NOT_COMPUTED
```

No recovered artifact defines an authoritative, compatible communication-side
antecedent-to-consequent frequency for C7's stale-present → eligible
redistribution opportunity relation. C5's possible rate lacks recovered
authority; C6 coexistence counts do not define a completion-flip frequency.

## Final determination

```text
THRESHOLD_CALIBRATION_AUTHORITY_RECOVERED = PARTIAL
FROZEN_CALIBRATION_ARCHITECTURE_INSTANTIABLE = NO
FROZEN_THRESHOLD_CALIBRATION_ARCHITECTURE_IS_NOT_INSTANTIABLE_WITH_EXISTING_PRE_C7_AUTHORITY = YES
```

The remaining block is not a missing grid or unimplemented schema. It is the
absence of a lawful `D_cond` authority and the non-final status of `D_global`.
The only safe next governance action is:

```text
NARROW_CORRECTIVE_SPECIFICATION_DECISION_REQUIRED
```

Its scope is limited to outcome-blind threshold-calibration authority and
derivation. It must not alter C7 semantics, pairs, capacity grid, eligibility,
selection, or use C7/tracking/treatment outcomes.

## Self-audit seal

```text
C7_OUTCOME_READ = NO
TRACKING_OUTCOME_READ = NO
C6_FORMAL_OUTCOME_VALUES_READ = NO
C7_CENSUS_EXECUTED = NO
C4_RERUN = NO
C5_RERUN = NO
C6_RERUN = NO
NEW_HISTORICAL_SCIENTIFIC_QUANTITY_CREATED = NO
SPECIFICATION_MODIFIED = NO
IMPLEMENTATION_STARTED = NO
THRESHOLD_HAND_TUNED = NO
```
