# C5 Shadow Census Execution Path Enablement Plan

```text
DOCUMENT_ROLE = C5_EXECUTION_PATH_ENABLEMENT_PLAN_DRAFT
PLAN_BASE_SHA = 413da31b3245c2d7b8bd94759fef89bc6173892f
PREVIOUS_QUALIFICATION_EVIDENCE = 413da31b3245c2d7b8bd94759fef89bc6173892f
SCIENTIFIC_EXECUTION_AUTHORIZED_BY_THIS_PLAN = NO
RUNNER_IMPLEMENTATION_AUTHORIZED_BY_THIS_PLAN = NO
```

## 1. Scope and current blocker

This is a runner-harness governance addendum, not a scientific redesign. The
qualified runner accepts only `--dry-run`; its constant execution authorization
is false and every non-dry-run invocation exits. Thus real execution currently
requires a runner source modification. No scientific data was accessed while
establishing this fact.

```text
E0-1 = source modification is required because no qualified real-execution route exists.
E0-2 = runtime remains byte-identical; no runtime change is required.
E0-3 = a runner-only change is sufficient in principle.
PRODUCTION_RUNTIME_CHANGE_REQUIRED = NO
```

## 2. Proposed fail-closed mechanism

The sole proposed execution interface is:

```bash
python scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py \
  --authorization-file <canonical_execution_authorization.json>
```

Without that artifact, or with `--dry-run`, the runner must not access data or
launch a cell. A successful authorization check is the only route to the
existing orchestration path; there is no bare `--execute` permission.

The canonical JSON artifact must contain exactly these governed bindings:

```text
schema_version
authorization_role = C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION
qualification_candidate_sha
qualification_evidence_authority
production_implementation_sha
contract_authority
implementation_plan_authority
cells = exact ordered frozen four-cell matrix with exact R
run_id
output_root
allowed_scientific_metrics = approved C5 opportunity metric/counter names only
tracking_evaluation_authorized = false
closed_loop_intervention_authorized = false
issued_for_exact_run = true
```

The runner must canonicalize and compare every value to its compiled frozen
authority/matrix, validate a fresh output root before data access, and reject
unknown keys, duplicate cells, any CLI cell/R/metric override, malformed run
identity, mismatched authority, or enabled evaluation/intervention. This binds
researcher authorization mechanically to one candidate and one run without
source editing at execution time.

```text
E0-4 = canonical authorization artifact is executable permission.
E0-5 = canonical fields bind candidate, qualification authority, matrix, R, and run.
E0-6 = absent/invalid/mismatched artifact stops before data access.
E0-7 = artifact and runner accept only exact frozen four cells/R/metrics.
E0-8 = --dry-run remains render-and-validate only, with no execution.
BARE_EXECUTION_SWITCH_SUFFICIENT = NO
DRY_RUN_SEMANTICS_CHANGED = NO
```

## 3. Candidate supersession and immutable scope

Changing the runner creates a new execution-enabled candidate. Qualification
evidence `413da31b...` remains correct historical evidence for candidate
`8f9b48df...`; it cannot authorize the changed runner. The new chain is:

```text
8f9b48df qualified candidate
-> runner-only authorization-gate delta
-> new execution-enabled candidate
-> independent runner delta audit
-> Q1–Q4 replay plus E1–E4 gate qualification
-> superseding qualification evidence and independent audit
-> separately issued scientific execution authorization
```

The implementation scope is expected to be the C5 runner and runner-specific
tests only. The runtime, predicate, PacketRuntime, C4 runner, patcher,
evaluator, Contract, approved Implementation Plan, scientific metrics,
denominators, Supplement scope, R values, and four-cell matrix remain frozen.

## 4. Required execution-gate qualification

New runner tests must cover, before any science:

| Gate | Required synthetic/mechanical proof |
| --- | --- |
| E1 | no artifact means no execution/data access |
| E2 | wrong candidate/qualification SHA, cell, R, run-id, tracking evaluation, or closed-loop value is rejected before data access |
| E3 | a valid synthetic artifact reaches only the intended orchestration route, using mock execution and no scientific data |
| E4 | valid artifacts instantiate exactly the frozen four-cell matrix and no additional cell |

The reviewed 42-test Q1–Q4 suite must be replayed against the new candidate.

```text
E0-9 = E1–E4 above.
E0-10 = Q1/Q2/Q3/Q4 replay is mandatory.
Q1_REPLAY_REQUIRED = YES
Q2_REPLAY_REQUIRED = YES
Q3_REPLAY_REQUIRED = YES
Q4_REPLAY_REQUIRED = YES
```

## 5. Output and audit boundaries

Before any future cell launch the authorization artifact binds a new output
root; existing or ambiguous artifacts produce `BLOCK_OUTPUT_COLLISION`, never
replacement. Validation finishes before dataset access, cell execution, or
outcome reading. Retry behavior, if later authorized, is governance-recorded
and cannot depend on results.

```text
E0-11 = expected files are the runner and runner-specific tests; final list requires implementation authorization.
E0-12 = Team B runner delta audit, Q1–Q4 replay/E1–E4 qualification, then independent qualification audit.
NEW_SCIENTIFIC_RULE_ADDED = NO
NEW_METRIC_ADDED = NO
NEW_THRESHOLD_ADDED = NO
FOUR_CELL_MATRIX_CHANGED = NO
RESEARCH_DECISION_REQUIRED = NO
```

## 6. Non-authorization

This plan neither modifies nor enables the runner. It authorizes no scientific
data access, no C5 outcome reading, no four-cell run, and no intervention.
