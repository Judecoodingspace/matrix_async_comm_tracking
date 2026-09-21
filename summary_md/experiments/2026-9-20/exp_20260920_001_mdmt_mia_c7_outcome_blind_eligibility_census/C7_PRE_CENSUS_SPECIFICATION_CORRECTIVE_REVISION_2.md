# C7 Pre-Census Specification Corrective Revision 2

```text
DOCUMENT_ROLE = C7_PRE_CENSUS_SPECIFICATION_CORRECTIVE_REVISION
REVISION_NUMBER = 2
PARENT_CANDIDATE_COMMIT = 73386375eaccb2fdf6cb20ad8c3a5cced82ff714
TEAM_B_AUDIT_1_VERDICT = CORRECTIVE_REVISION_REQUIRED
TEAM_B_P1 = T_COUNT_MATHEMATICAL_REDUNDANCY_CONFLICTED_WITH_WORDING_IMPLYING_FOUR_NON_REDUNDANT_GATES
CSD_C7_09 = FROZEN
RESOLUTION = RETAIN_T_COUNT_AS_INTENTIONAL_EXPLICIT_MINIMUM_RECURRENCE_INVARIANT_MATHEMATICALLY_REDUNDANT_OVER_FROZEN_DOMAIN
SPEC_STATUS = READY_FOR_TEAM_B_DELTA_AUDIT
```

## P1 finding

Revision #1 correctly froze the four numerical criteria and their conjunctive
qualification function, but described the four explanatory roles without
explicitly acknowledging that `T_count=5` has no independent mathematical
exclusion power over the current frozen registered domain.

For the frozen criteria:

```text
G1: N_eligible_windows >= 5
G2: N_stale_present_windows >= 20
G3: N_eligible_windows / N_all_windows >= 1/60
G4: N_eligible_windows / N_stale_present_windows >= 1/4
```

`G2 AND G4` implies `N_eligible_windows >= 20 * 1/4 = 5`, hence implies
`G1`. Separately, `G3` implies integer minimum eligible counts of 5, 6, and 12
for registered trajectory lengths 300, 360, and 700, respectively, hence also
implies `G1` throughout the frozen domain.

## Frozen resolution — CSD-C7-09

`T_count=5` is intentionally retained as the explicit
`MINIMUM_RECURRENCE_INVARIANT`. It states directly that fewer than five C7
eligible opportunities can never qualify. It retains an independent semantic
and traceability role, not a mathematically non-redundant filtering role in the
current frozen domain.

Retention is deliberate because it:

1. preserves the frozen minimum-recurrence scientific statement;
2. keeps “fewer than five is unacceptable” directly visible to reviewers;
3. prevents that semantic invariant from silently disappearing if a future
   domain or other threshold changes under separate formal governance; and
4. preserves traceability to `CSD-C7-02` and `CSD-C7-05`.

`CSD-C7-02` is clarified, not deleted or superseded. `CSD-C7-03` remains valid:
`T_den=20` independently protects against thin conditional denominators, while
`T_den > T_count` is not evidence that every criterion is mathematically
non-redundant.

## Gate redundancy audit

```text
GATE_REDUNDANCY_AUDIT = PASS
G2_AND_G4_IMPLIES_G1 = YES
G3_IMPLIES_G1_OVER_REGISTERED_DOMAIN = YES
T_COUNT_REDUNDANT_OVER_FROZEN_DOMAIN = YES
T_COUNT_REDUNDANCY_INTENTIONAL = YES
T_COUNT_RETAINED_AS_EXPLICIT_INVARIANT = YES
```

The arithmetic is exact:

```text
20 * 1/4 = 5
ceil(300/60) = 5
ceil(360/60) = 6
ceil(700/60) = 12
```

## Before/after behavior seal

Revision #2 changes interpretation and audit wording only. The four frozen
criteria, their `AND` composition, and their inclusive boundary operators are
logically unchanged from Revision #1.

```text
CASE_A_300_20_5 = QUALIFIED
CASE_B_700_20_5 = NOT_QUALIFIED_GLOBAL_GATE_FAIL
CASE_C_300_100_5 = NOT_QUALIFIED_CONDITIONAL_GATE_FAIL
CASE_D_300_5_5 = NOT_QUALIFIED_DENOMINATOR_GATE_FAIL

THRESHOLD_VALUES_CHANGED = NO
QUALIFICATION_FUNCTION_CHANGED = NO
QUALIFICATION_BEHAVIOR_CHANGED = NO
QUALIFICATION_BEHAVIOR_REV1_EQUALS_REV2 = YES
BOUNDARY_OPERATOR_CHANGED = NO
```

## Scope and firewall seal

```text
SCIENTIFIC_SCOPE_CHANGED = NO
ELIGIBILITY_CHANGED = NO
PAIR_SET_CHANGED = NO
CAPACITY_GRID_CHANGED = NO
SELECTION_RULE_CHANGED = NO

HISTORICAL_P20_ARCHITECTURE_STATUS = SUPERSEDED
REVISION_1_RECORD_CHANGED = NO
CONTRACT_CHANGED = NO
APPROVAL_RECORD_CHANGED = NO
INPUT_AUDIT_CHANGED = NO
RECOVERY_AUDIT_CHANGED = NO

CURRENT_STATUS_READ = NO
CURRENT_EXPERIMENT_STAGE_READ = NO
TRACKING_OUTCOME_READ = NO
C7_OUTCOME_READ = NO
C6_FORMAL_SCIENTIFIC_OUTCOME_READ = NO
GIT_OBJECT_RECOVERY_OF_FORBIDDEN_FILES = NO
OTHER_WORKTREE_OUTCOME_READ = NO
RESEARCH_PLANNER_INVOKED = NO

C7_CENSUS_EXECUTED = NO
C7_DRY_RUN_EXECUTED = NO
IMPLEMENTATION_STARTED = NO
QUALIFICATION_STARTED = NO
FORMAL_EXECUTED = NO
```

This revision does not approve or finally freeze the Specification and does
not authorize implementation, qualification, census execution, or a Formal
run. Its only next stage is `TEAM_B_CORRECTIVE_REVISION_2_DELTA_AUDIT`.
