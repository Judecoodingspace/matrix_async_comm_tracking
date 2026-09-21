# C7 Pre-Census Specification Corrective Revision 1

```text
DOCUMENT_ROLE = C7_PRE_CENSUS_SPECIFICATION_CORRECTIVE_REVISION
CORRECTIVE_REVISION = 1
REVISION_TRIGGER = FROZEN_HISTORICAL_CALIBRATION_ARCHITECTURE_NOT_FULLY_INSTANTIABLE_FROM_EXISTING_LAWFUL_PRE_C7_AUTHORITY
RECOVERY_AUDIT_AUTHORITY = C7_THRESHOLD_CALIBRATION_AUTHORITY_RECOVERY_AUDIT.md
RECOVERY_AUDIT_COMMIT = 86cc2ca38a0ad6bdca3dfe3046132289cc071497
RECOVERY_AUDIT_SHA256 = 95064461a4bab68d1c38e2b941f94dd9f3a928df2c10697ce54563ef0fba4d78
SUPERSEDED_THRESHOLD_ARCHITECTURE = HISTORICAL_P20_THRESHOLD_ARCHITECTURE
SUPERSEDED_PRE_CENSUS_SPEC_SHA256 = f120a75088910524b1c268bc7258f8386800ed1c1d1caf015c342f22ca5b5797
SUPERSESSION_AUTHORITY = CSD_C7_01_THROUGH_CSD_C7_08
SPEC_STATUS = READY_FOR_INDEPENDENT_CORRECTIVE_AUDIT
```

## Revision trigger and authority

The Recovery Audit found that `D_count` and `D_den` were recovered,
`D_global` was partially recovered, and `D_cond` was not recoverable from
existing lawful pre-C7 authority. The historical frozen P20 calibration
architecture therefore could not be fully instantiated.

The historical architecture is retained as revision history and corrective
trigger evidence. It is superseded because its authority was incomplete, not
because P20 or any threshold was falsified by an experimental, C7, tracking,
or treatment outcome. No such outcome was read for this revision.

## Frozen corrective specification decisions

### CSD-C7-01

Different registered trajectory lengths must not be structurally penalized by
one unified high raw-count threshold. Exposure is used only for fairness and
feasibility.

### CSD-C7-02

The eligible-opportunity count gate is a minimum recurrence count. It asks
whether genuine C7 eligible redistribution opportunities recur enough to
exceed a one- or two-event accident. It is not proportional to trajectory
length.

### CSD-C7-03

Stale-present scenario support is independently gated and must satisfy
`T_den > T_count`, excluding high conditional fractions supported by extremely
thin denominators.

### CSD-C7-04

`T_count` is derived from minimum recurrence. `T_den` is derived from
conditional-rate resolution. A unified historical ruler is not restored.

### CSD-C7-05

```text
T_count = 5
N_eligible_windows >= 5
```

### CSD-C7-06

Five percentage points is the frozen minimum discrete resolution for the
conditional fraction. It is not a confidence interval.

```text
T_den = 20
N_stale_present_windows >= 20
```

### CSD-C7-07

The registered trajectory lengths are `P23=700`, `P44=360`, and `P66=300`.
Minimum recurrence is 5 and the shortest trajectory is 300 frames.

```text
T_global = 5/300 = 1/60
N_eligible_windows / N_all_windows >= 1/60
```

The canonical value is `1/60`, not rounded `1.67%`. Its mechanical count
consequences are P66 `>=5`, P44 `>=6`, and P23 `>=12`; those are not separate
thresholds.

### CSD-C7-08

```text
T_cond = 5/20 = 1/4
N_eligible_windows / N_stale_present_windows >= 1/4
```

The canonical value is `1/4`.

## Final conjunctive qualification rule

```text
N_eligible_windows >= 5
AND N_stale_present_windows >= 20
AND N_eligible_windows / N_all_windows >= 1/60
AND N_eligible_windows / N_stale_present_windows >= 1/4
```

All comparisons use `>=`, including equality boundaries. The four gates remain
distinct and unweighted. Qualification precedes selection; ranking or Pareto
comparison cannot qualify a failing cell.

## Mechanical fixture seal

```text
CASE_A_300_20_5 = COUNT_PASS,DEN_PASS,GLOBAL_PASS,CONDITIONAL_PASS,OVERALL_PASS
CASE_B_700_20_5 = COUNT_PASS,DEN_PASS,GLOBAL_FAIL,CONDITIONAL_PASS,OVERALL_FAIL
CASE_C_300_100_5 = COUNT_PASS,DEN_PASS,GLOBAL_PASS,CONDITIONAL_FAIL,OVERALL_FAIL
CASE_D_300_5_5 = COUNT_PASS,DEN_FAIL,GLOBAL_PASS,CONDITIONAL_NUMERIC_PASS,OVERALL_FAIL
CASE_E_300_0_0_COMPLETE_EVIDENCE = CELL_VALID_YES,CELL_QUALIFIED_NO,CONDITIONAL_NA
GLOBAL_GATE_P66_300 = CEIL_300_OVER_60_EQUALS_5
GLOBAL_GATE_P44_360 = CEIL_360_OVER_60_EQUALS_6
GLOBAL_GATE_P23_700 = CEIL_700_OVER_60_EQUALS_12
```

## Scope and firewall seal

```text
SCIENTIFIC_SCOPE_CHANGED = NO
ELIGIBILITY_DEFINITION_CHANGED = NO
PAIR_SET_CHANGED = NO
CAPACITY_GRID_CHANGED = NO
SELECTION_RULE_CHANGED = NO

TRACKING_OUTCOME_READ = NO
C7_OUTCOME_READ = NO
C6_FORMAL_SCIENTIFIC_OUTCOME_READ = NO
IMPLEMENTATION_STARTED = NO
C7_CENSUS_EXECUTED = NO
C7_DRY_RUN_EXECUTED = NO
QUALIFICATION_STARTED = NO
FORMAL_EXECUTED = NO
RESEARCH_PLANNER_INVOKED = NO
GIT_OBJECT_RECOVERY_OF_FORBIDDEN_FILES = NO
OTHER_WORKTREE_OUTCOME_READ = NO
```

This revision does not approve the Specification and does not authorize
implementation, qualification, census execution, or a Formal run. Its only
handoff state is `READY_FOR_INDEPENDENT_CORRECTIVE_AUDIT`.
