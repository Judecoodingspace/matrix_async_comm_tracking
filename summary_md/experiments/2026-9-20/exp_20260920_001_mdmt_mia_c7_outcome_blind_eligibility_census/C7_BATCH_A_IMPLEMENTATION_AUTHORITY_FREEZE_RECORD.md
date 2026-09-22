# C7 Batch A Implementation Authority Freeze Record

## A. Freeze identity

```text
DOCUMENT_ROLE =
C7_BATCH_A_IMPLEMENTATION_AUTHORITY_FREEZE_RECORD

FREEZE_STATUS =
APPROVED_AND_FROZEN

FINAL_IMPLEMENTATION_AUTHORITY =
f484ac5b886e68393c581936f1e764d4d08366d8

BATCH_A_SCOPE =
M1_M4

BATCH_A_SCOPE_ENDS_AT =
M4

BATCH_B_AUTHORIZED =
NO
```

This record freezes the independently audited C7 Batch A implementation as an
implementation authority for downstream governance. It creates no new
scientific decision and authorizes no new implementation.

## B. Authority chain

```text
SPECIFICATION_CONTENT_AUTHORITY =
67f9b07a00141d380952f6a6cc9ae23f34c1cd7d

SPECIFICATION_FREEZE_COMMIT =
0eda32c58871c1ec4b5b194c0c33608d7dd2a777

IMPLEMENTATION_PLAN_COMMIT =
b850b7fcbc026fbcb49de7c85cf9b43c41adcc0b

IMPLEMENTATION_PLAN_SHA256 =
6b7aeedf0b4215cd57b332fb9720d33e636d854230565d69ea6c8d3af3bc7465

BATCH_A_PLAN_BASE =
b850b7fcbc026fbcb49de7c85cf9b43c41adcc0b

INITIAL_BATCH_A_IMPLEMENTATION =
3a219b655e478ce6528065f175d2c25722bef848

CORRECTIVE_REVISION_1 =
a205d160fdb3b0dd54d532bec5e5d7f41374c77a

FINAL_CREDIT_AMOUNT_CORRECTIVE =
f484ac5b886e68393c581936f1e764d4d08366d8

FINAL_BATCH_A_IMPLEMENTATION_AUTHORITY =
f484ac5b886e68393c581936f1e764d4d08366d8

AUTHORITY_CHAIN_VERIFIED =
YES
```

The three required ancestry checks from Plan base through the initial
implementation and both corrective revisions returned success.

## C. Independent audit disposition

The following disposition is recorded as an external audit conclusion supplied
to this governance task. It was not generated or reinterpreted by this freeze
session.

```text
AUDIT_RESULT_SOURCE =
EXTERNAL_INDEPENDENT_TEAM_B_AUDIT_SUPPLIED_TO_FREEZE_TASK

TEAM_B_INDEPENDENT_C7_BATCH_A_FINAL_DELTA_AUDIT =
PASS

P0 = 0
P1 = 0
P2 = 0

P1_BA_01 = CLOSED
P1_BA_02 = CLOSED
P1_BA_02R = CLOSED
P2_BA_01 = CLOSED

NEW_RESEARCH_DECISION_REQUIRED = NO
PLAN_CHANGE_REQUIRED = NO
```

## D. Frozen file inventory

The hashes below were freshly computed from the clean worktree at
`f484ac5b886e68393c581936f1e764d4d08366d8`.

| Role | Frozen path | SHA-256 |
| --- | --- | --- |
| Passive C4 runtime observation | `src/tracking/mdmt_mia_async_deadline_runtime.py` | `86daa5c6c011843ddb418a89b7c16a819304b8a2526dd0457aeac6fc3d439520` |
| C7 Batch A producer | `src/tracking/mdmt_mia_c7_census.py` | `9a1887f39d8206a826a15717b84b97773f50a088eb8f507e9ce1921838360652` |
| Independent raw-evidence validator | `src/tracking/mdmt_mia_c7_validator.py` | `7922a1d82132e28586dfb3bdfa2b65bc12d8d7a961ddc14d5be747dc8a29552f` |
| Batch A tests | `tests/test_mdmt_mia_c7_batch_a_core.py` | `7f53ca65e639fc7c4af44f6bb1525108cf3ffa53f0ed536fad1c8e6aee30ba7f` |

```text
RUNTIME_SHA256 =
86daa5c6c011843ddb418a89b7c16a819304b8a2526dd0457aeac6fc3d439520

C7_CENSUS_SHA256 =
9a1887f39d8206a826a15717b84b97773f50a088eb8f507e9ce1921838360652

C7_VALIDATOR_SHA256 =
7922a1d82132e28586dfb3bdfa2b65bc12d8d7a961ddc14d5be747dc8a29552f

C7_BATCH_A_TEST_SHA256 =
7f53ca65e639fc7c4af44f6bb1525108cf3ffa53f0ed536fad1c8e6aee30ba7f
```

## E. Frozen schema identities and invariants

```text
C7_CORE_SEMANTICS_SCHEMA =
C7_CORE_SEMANTICS_V3

C7_CORE_VALIDATION_SCHEMA =
C7_CORE_VALIDATION_V3
```

The frozen Batch A semantic scope is exactly:

```text
M1 = DECLARATIVE_SCHEMA_AND_CONSTANTS
M2 = PASSIVE_C4_RUNTIME_OBSERVATION
M3 = STALE_CLASSIFICATION_AND_RECIPIENT_SERVICEABILITY_TRAJECTORY
M4 = SOURCE_REMOVABLE_WORK
     + RELEASED_CAPACITY_CREDIT
     + STRICT_FIFO_CONDITIONAL_ACCOUNTING
     + CAPACITY_CAUSED_COMPLETION_LOSS
     + INDEPENDENT_RAW_EVIDENCE_VALIDATION
```

The frozen invariants are:

```text
EFFECTIVE_SERVICE_WINDOW = ONE_FRAME
PARTIAL_BYTES_HAVE_SEMANTIC_EFFECT = NO
SEMANTIC_COMMIT = LOGICAL_PACKET_COMPLETION
TRUE_FIRST_SERVICE = AFTER_FIFO_SELECTION_BEFORE_FIRST_SERVICE_BYTE
STALE_CLASSIFICATION = ONCE_ONLY_AND_PACKET_STICKY
RECIPIENT_SERVICEABILITY = OBSERVED_BASELINE_RECEIVER_STATE_TRAJECTORY
FUTURE_STATE_ALLOWED = NO
COUNTERFACTUAL_RECEIVER_STATE_REPLAY = NO

SOURCE_REMOVABLE_WORK != RELEASED_CAPACITY_CREDIT
SOURCE_BASELINE_COMPLETION != RELEASED_CREDIT_EXPIRATION
INTRA_FRAME_UNUSED_RELEASED_CREDIT_REUSABLE = YES
INTER_FRAME_RELEASED_CREDIT_CARRYOVER = NO
STRICT_FIFO_PROPAGATION = YES
DIRECT_RECIPIENT_ASSIGNMENT = NO

SOURCE_START_RESIDUAL = RAW_BASELINE_DERIVED
SOURCE_FRAME_CLOSE_RESIDUAL = RAW_BASELINE_DERIVED
SOURCE_CURRENT_FRAME_BASELINE_SERVICE_BYTES =
SOURCE_START_RESIDUAL - SOURCE_FRAME_CLOSE_RESIDUAL
RELEASED_CREDIT_CREATED = SOURCE_CURRENT_FRAME_BASELINE_SERVICE_BYTES
RELEASED_CREDIT_CAN_EXCEED_CURRENT_FRAME_DISPLACED_SERVICE = NO
```

## F. Mechanical test attestation

The following already-authorized mechanical tests were rerun from the clean
frozen implementation worktree.

```bash
PYTHONPATH=src pytest -q tests/test_mdmt_mia_c7_batch_a_core.py
```

```text
ACTUAL_RESULT = 42 passed in 0.24s
```

```bash
PYTHONPATH=src pytest -q tests/test_mdmt_mia_c4_service_runtime.py
```

```text
ACTUAL_RESULT = 20 passed in 0.31s
```

```bash
PYTHONPATH=src pytest -q tests/test_mdmt_mia_async_deadline_runtime.py \
  -k 'not async_condition_matrix_matches_predeclared_experiment_grid'
```

```text
ACTUAL_RESULT = 12 passed, 1 deselected in 0.10s
```

## G. Known environment limitation

The sparse checkout omits:

```text
evaluation/mdmt_mia_paper.py
```

Consequently, the single neighboring test
`test_async_condition_matrix_matches_predeclared_experiment_grid` is unavailable
because importing the historical audit launcher raises:

```text
ModuleNotFoundError: No module named 'evaluation'
```

The unavailable test is not represented as passing.

```text
NEIGHBOR_ASYNC_RUNTIME_UNAVAILABLE_TESTS = 1
LIMITATION_CLASS = SPARSE_CHECKOUT_ENVIRONMENT_LIMITATION
BATCH_A_FREEZE_BLOCKER = NO
```

## H. Scope boundary

This freeze ends at M4 and does not authorize or cover:

```text
BATCH_B_AUTHORIZED_BY_THIS_FREEZE = NO
M5_M6 = NOT_AUTHORIZED
AGGREGATION = NOT_AUTHORIZED
QUALIFICATION = NOT_AUTHORIZED
SELECTION = NOT_AUTHORIZED
MVE = NOT_AUTHORIZED
TWENTY_ONE_CELL_CENSUS = NOT_AUTHORIZED
FORMAL_SUPPRESSION = NOT_AUTHORIZED
TRACKING_EVALUATION = NOT_AUTHORIZED
PRODUCTION_PACKAGING = NOT_AUTHORIZED
LAUNCHER = NOT_AUTHORIZED
SEAL = NOT_AUTHORIZED
RESUME = NOT_AUTHORIZED
```

No tracking outcomes or historical result artifacts were read for this freeze.

## I. Mutation rule after freeze

Any post-freeze byte change to one of the frozen Batch A implementation files
invalidates the frozen implementation identity for downstream reliance unless
separately reviewed and re-frozen under a new governance action.

```text
POST_FREEZE_SOURCE_MUTATION_REQUIRES_REAUTHORIZATION = YES
AMEND_FROZEN_IMPLEMENTATION_COMMIT = FORBIDDEN
REBASE_FROZEN_IMPLEMENTATION_HISTORY = FORBIDDEN
```
