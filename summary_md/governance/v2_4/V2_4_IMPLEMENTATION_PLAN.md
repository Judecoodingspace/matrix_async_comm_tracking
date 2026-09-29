# MDMT / MIA Governance v2 — V2-4 Production Proof
## Implementation Plan — Revision 1

Status:

```text
V2_3_CLOSED_PASS = YES
V2_3_CLOSED_AUTHORITY_SHA =
415d9c7132d8203c7970e45a70b77981fc41fc3b

TEAM_B_V2_4_CONTRACT_REVISION_2_DELTA_REVIEW = PASS
P0 = 0
P1 = 0

TEAM_B_V2_4_IMPLEMENTATION_PLAN_REVIEW = CORRECTION_REQUIRED
P0 = 0
P1 = 1
P2 = 1

V2_4_IMPLEMENTATION_CONTRACT_ACCEPTED = YES
V2_4_IMPLEMENTATION_PLAN_STATUS = REVISION_1_FOR_DELTA_REVIEW

V2_4_IMPLEMENTATION_AUTHORIZED = NO
H_R_FORMAL_AUTHORIZED = NO
```

Revision 1 changes only two points from Draft 1:

```text
1. Fix the first-introduction review baseline so the complete
   415d9c... → implementation-candidate diff is independently reviewed.

2. Explicitly bind MIA_C7_EVIDENCE_ROOT in the H_R real-child environment
   so the accepted C7 passive observer writes its raw evidence.
```

All other accepted plan semantics remain unchanged.

---

# 1. Implementation objective

Implement the minimum production wiring:

```text
accepted C7 Pick-cell authority
→ exact selected H_R cell
→ H_R operator
→ V2-2 detached attempt
→ H_R real child
→ C7-derived real execution structure
→ frozen author wrapper
→ one generated PacketRuntime using:
   MIA_C7_SERVICE_CONFIG
   +
   MIA_C6_SUPPRESSION_CONFIG
→ real service + suppression evidence
→ canonical H_R RAW_EVIDENCE
→ canonical H_R NORMALIZED_EVIDENCE
→ structural validation
→ V2-2 terminal
→ V2-3 finalization
→ FORMAL_AUTHORIZATION_SUPPORT check_reuse
```

No scientific H_R outcome is read.

---

# 2. Resolve and pin the existing C7 Pick-cell authority

Before production implementation, resolve from accepted repository/artifact authority:

```text
C7 selection package path
C7 selection package SHA-256
C7 package validation path / identity
C7 package validation verdict
selected cell_id
selected pair_id
selected capacity_id
selected capacity_bytes
selection authority commit / package identity
```

Team B observed that the current validated C7 package selects:

```text
P66__P20
```

Implementation MUST verify this from frozen authority, not trust chat text.

If frozen authority disagrees:

```text
STOP
REPORT AUTHORITY MISMATCH
```

No C7 selection rerun is allowed.

---

# 3. Plan-only governance authority

A plan/governance-only commit may be created from:

```text
415d9c7132d8203c7970e45a70b77981fc41fc3b
```

containing only:

```text
accepted V2-4 Contract Revision 2
accepted/reviewed V2-4 Implementation Plan
Team B review records
```

Suggested paths:

```text
summary_md/governance/v2_4/V2_4_IMPLEMENTATION_CONTRACT_REV2.md
summary_md/governance/v2_4/V2_4_IMPLEMENTATION_PLAN.md
summary_md/governance/v2_4/V2_4_CONTRACT_TEAM_B_REVIEW.md
summary_md/governance/v2_4/V2_4_PLAN_TEAM_B_REVIEW.md
```

Call its SHA:

```text
V2_4_PLAN_AUTHORITY_SHA
```

No production source is allowed in this commit.

Implementation may branch from this plan authority.

Suggested:

```text
BRANCH = impl/20260929-v2-4-hr-production-proof
WORKTREE = /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/v2_4_hr_production_proof
```

---

# 4. Expected implementation files

Default new production files:

```text
scripts/run_mdmt_mia_hr_formal.py
scripts/run_mdmt_mia_hr_real_child.py
src/tracking/mdmt_mia_hr_evidence.py
```

Qualification/tests:

```text
scripts/qualify_mdmt_mia_hr_production_path.py
tests/test_mdmt_mia_hr_production_path.py
```

Historical source remains read-only by default:

```text
scripts/run_mdmt_mia_c7_real_child.py
scripts/run_mdmt_mia_c6_real_child.py
scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py
src/tracking/mdmt_mia_async_deadline_runtime.py
```

If any historical mechanism source requires semantic modification:

```text
STOP
REPORT EXACT BLOCKER
```

---

# 5. C7 real-child structure is the H_R mother template

Inspect the accepted C7 real-child path and classify reusable helpers as:

```text
SAFE_DIRECT_REUSE
STRUCTURAL_PATTERN_ONLY
NOT_REUSABLE
```

Preserve where applicable:

```text
authorization/source revalidation
clean Git/head observation
generated-source materialization
generated-source inventory
author-wrapper identity validation
controlled environment
author-wrapper execution
C7 passive raw observer
deterministic evidence derivation
tracking-outcome quarantine
child status
```

Do not refactor historical C7 merely for code sharing unless separately impact-reviewed.

Do not duplicate runtime mechanism logic.

---

# 6. H_R authorization and selected-cell binding

The H_R authorization exact-binds:

```text
schema/version
authorization hash
source implementation SHA

accepted C7 selection path/hash
accepted C7 package validation path/hash

selected:
  cell_id
  pair_id
  capacity_id
  capacity_bytes

H_R operator source identity
H_R real-child source identity

author-wrapper path/hash
generated-source preparation identity
generated-source manifest/seal identity

run_id
attempt_id
attempt root

service-config schema identity
suppression-config schema identity

expected evidence layout
V2-3 artifact purpose/policy
```

Caller-provided pair/capacity values must not override the frozen selection.

---

# 7. H_R operator

Implement:

```text
scripts/run_mdmt_mia_hr_formal.py
```

with:

```text
launch
inspect
finalize
preissue-check
```

## launch

Call:

```text
tracking.governance_v2_execution.launch(...)
```

with direct V2-2 child:

```text
scripts/run_mdmt_mia_hr_real_child.py
```

No direct author-workload launch from the operator.

## inspect

Delegate to accepted V2-2 inspection.

## finalize

Only after:

```text
V2-2 mechanically ended
canonical RAW exists
canonical NORMALIZED exists
structural PASS exists
```

Call accepted V2-3:

```text
governance_v2_artifacts.finalize(
    adopt=True,
    authority_boundary=True
)
```

## preissue-check

Call:

```text
governance_v2_artifacts.check_reuse(...)
```

with:

```text
consumption_class = FORMAL_AUTHORIZATION_SUPPORT
purpose = H_R_FORMAL_PREISSUANCE
```

Require:

```text
REUSE_ADMISSIBLE
```

No Formal authorization is issued here.

---

# 8. H_R real child

Implement:

```text
scripts/run_mdmt_mia_hr_real_child.py
```

Required flow:

```text
A. load H_R authorization
B. reread/verify selected-cell authority
C. observe clean source identity
D. verify wrapper/generated-source identities
E. materialize C7-evidence-capable generated source
F. inventory generated source pre-run
G. build controlled environment
H. invoke frozen author wrapper
I. inventory generated source post-run
J. fail on source mutation
K. collect runtime/service/suppression evidence
L. construct canonical RAW_EVIDENCE
M. derive NORMALIZED_EVIDENCE only from canonical RAW
N. structural validation
O. mechanical child status
P. exit
```

No tracking metrics may be read.

---

# 9. Exact runtime environment composition

The H_R controlled environment MUST remove/inhibit inherited conflicting `MIA_*` keys.

`MIA_C4_SERVICE_CONFIG` MUST be absent.

Set:

```text
MIA_C7_SERVICE_CONFIG
```

from the frozen selected cell:

```json
{
  "schema_version": "C7_REGISTERED_FIFO_SERVICE_V1",
  "mode": "fifo",
  "capacity_id": "<selected capacity_id>",
  "rate_logical_bytes_per_frame": "<selected capacity_bytes>",
  "ledger_enabled": true,
  "run_id": "<H_R run_id>",
  "pair_id": "<selected pair_id>"
}
```

Set simultaneously:

```text
MIA_C6_SUPPRESSION_CONFIG
```

as:

```json
{
  "enabled": true,
  "run_id": "<same H_R run_id>",
  "output_dir": "<attempt-local suppression directory>"
}
```

Also set:

```text
MIA_PACKET_CENSUS_RUN_ID = same H_R run_id
MIA_ACTIVE_PACKET_STAGES = all
MIA_OUTPUT_ROOT = attempt-local runtime output root
MIA_SOURCE_ROOT = generated source root
PYTHONNOUSERSITE = 1
PYTHONHASHSEED = 0
PYTHONDONTWRITEBYTECODE = 1
```

## Required C7 observer root — closes Plan-review P2

Because the C7 evidence-capable generated author entry persists its passive observer through:

```text
write_raw_observer_run(
    ...,
    os.environ["MIA_C7_EVIDENCE_ROOT"]
)
```

the H_R child MUST explicitly set:

```text
MIA_C7_EVIDENCE_ROOT =
<attempt-root>/output/hr/source_runtime/raw_c7
```

or an equivalent unique attempt-local canonical source-evidence directory.

Requirements:

```text
- path is beneath the V2-2 attempt output root;
- directory identity is deterministic from the attempt;
- no inherited parent MIA_C7_EVIDENCE_ROOT is accepted;
- absence/mismatch is fail-closed;
- raw observer output is included in source-evidence collection/canonicalization.
```

This environment binding is mandatory for the real production proof.

---

# 10. Real generated runtime execution

Invoke the same author-wrapper workload shape used by C7:

```text
<author wrapper> mia <split> <selected pair number>
```

The final V2-4 qualification MUST execute the real generated `PacketRuntime`.

No:

```text
dry run
mock runtime
environment-only assertion
synthetic replacement runtime
```

can close V2-4.

---

# 11. Runtime evidence families

Resolve exact attempt-local evidence, including:

```text
raw C7 observer under MIA_C7_EVIDENCE_ROOT
async packet manifest
shared FIFO service ledger
service summary
packet census emissions
packet census terminals
packet census finalization
packet census validation
C6 suppression decisions
C6 suppression seal
```

Fail on missing/ambiguous required family.

Cross-bind:

```text
run_id
pair_id
capacity_id/capacity_bytes
effective service rate
ledger state
suppression identity
packet identities
generated-runtime provenance
```

---

# 12. Direct V2-3 content binding

Team B's Contract-review P2 is closed by using directly hashable canonical evidence bytes.

Create:

```text
output/hr/H_R_RAW_EVIDENCE.jsonl
```

containing the minimal actual records required to reconstruct/validate the H_R mechanical production claim.

It must include/canonicalize the necessary facts from:

```text
C7 raw observer
service ledger/summary/finalization
packet census evidence
suppression decisions/seal
selected-cell authority binding
effective runtime configuration
generated-runtime provenance
```

The structural validator must validate the mechanical H_R claim from:

```text
H_R_RAW_EVIDENCE
+
frozen Git/provenance identities
```

without reopening mutable source runtime files.

Source runtime files remain diagnostic/source material.

Create:

```text
output/hr/H_R_NORMALIZED_EVIDENCE.json
```

deterministically from canonical RAW only.

V2-3 declaration directly uses:

```text
RAW_EVIDENCE = NODE_FILE(H_R_RAW_EVIDENCE.jsonl)
NORMALIZED_EVIDENCE = NODE_FILE(H_R_NORMALIZED_EVIDENCE.json)
```

so `finalize()` and `FORMAL_AUTHORIZATION_SUPPORT check_reuse()` re-hash the actual evidence bytes.

---

# 13. Effective config file

Create:

```text
output/hr/H_R_EFFECTIVE_CONFIG.json
```

from observed runtime evidence.

Bind:

```text
selected cell identity
run_id
pair_id
capacity_id
capacity_bytes
observed effective rate
observed FIFO mode
ledger enabled
suppression enabled
generated runtime/source identity
```

Use it as the V2-3 `effective_scientific_config` `NODE_FILE`.

This is mechanical configuration evidence, not a scientific outcome.

---

# 14. V2-3 provenance

Derivation provenance:

```text
raw_evidence
→ RAW NODE_FILE

extractor
→ exact GIT_BLOB

extraction_contract
→ exact accepted Contract Revision 2 GIT_BLOB

extraction_config
→ attempt-local NODE_FILE

normalized_evidence
→ NORMALIZED NODE_FILE
```

Validation provenance:

```text
normalized_evidence
→ NORMALIZED NODE_FILE

validator
→ exact GIT_BLOB

validation_contract
→ exact accepted Contract Revision 2 GIT_BLOB

validation_config
→ attempt-local NODE_FILE
```

No floating branch refs.

---

# 15. Structural validator

Fail closed unless:

```text
C7 selection authority exact
selected cell exact
run IDs consistent
pair exact
capacity exact
effective rate == selected capacity_bytes
FIFO active
ledger enabled
suppression enabled
suppression decision/seal internally consistent
packet/service reconciliation passes
generated runtime origin exact
RAW structure valid
NORMALIZED reproducible from RAW
tracking outcome read == false
```

Verdict:

```text
STRUCTURAL_VERDICT = PASS | FAIL
```

No H_R scientific verdict.

---

# 16. Negative tests

At minimum test failures for:

```text
wrong C7 selection hash
wrong selected cell/pair/capacity tuple
wrong authorization hash

MIA_C4_SERVICE_CONFIG present
MIA_C7_EVIDENCE_ROOT absent
MIA_C7_EVIDENCE_ROOT outside attempt
MIA_C7_EVIDENCE_ROOT inherited/mismatched
ledger disabled
suppression disabled
service/suppression run mismatch

wrong wrapper/generated-source identity
generated source mutation

effective rate mismatch
missing C7 raw observer
missing service evidence
missing suppression evidence
ambiguous evidence family

RAW missing required record
NORMALIZED not reproducible
validator reopens source runtime after RAW canonicalization

V2-3 RAW drift
V2-3 NORMALIZED drift
wrong finalization anchor
wrong provenance
V2-1 applicability failure
ambiguous/superseded lineage
```

No combinatorial explosion.

---

# 17. Test tiers

Focused tests may mock helpers for:

```text
authorization
selection binding
environment composition
MIA_C7_EVIDENCE_ROOT binding
raw canonicalization
normalized determinism
structural validation
V2-3 declaration
negative cases
```

Final V2-4 qualification must use:

```text
real operator
real V2-2
real H_R child
real author wrapper
real generated PacketRuntime
real C7 service config
real C6 suppression
real C7 observer
real canonical evidence
real V2-3 finalization
```

---

# 18. Qualification script

Implement:

```text
scripts/qualify_mdmt_mia_hr_production_path.py
```

It must:

```text
1. resolve exact frozen selected-cell authority
2. build qualification-only H_R authorization
3. invoke the same H_R operator launch entry
4. wait/inspect via V2-2
5. require completed child
6. require real generated runtime + C7 observer evidence
7. require structural PASS
8. invoke H_R operator finalize
9. inspect V2-3 finalization
10. record attempt/manifest/finalization identities
```

No tracking outcome.
No C7 census rerun.
No H_R Formal.

---

# 19. Correct first-introduction review sequence — closes Plan-review P1

The accepted V2-4 Contract requires first-introduction review against:

```text
V2_3_CLOSED_AUTHORITY_SHA =
415d9c7132d8203c7970e45a70b77981fc41fc3b
```

A plan-only governance commit MAY exist between that authority and implementation.

However, it MUST NOT narrow the introduction-review baseline.

Therefore independent implementation review MUST perform:

```text
FULL_INTRODUCTION_DIFF =
415d9c7132d8203c7970e45a70b77981fc41fc3b
→ V2_4_IMPLEMENTATION_CANDIDATE_SHA
```

This full diff is authoritative for first-introduction classification.

The review MUST verify separately that:

```text
415d9c... → V2_4_PLAN_AUTHORITY_SHA
```

contains governance/documentation only and no production/scientific behavior.

It may additionally inspect:

```text
V2_4_PLAN_AUTHORITY_SHA
→ V2_4_IMPLEMENTATION_CANDIDATE_SHA
```

as an implementation-focused convenience diff.

But that narrower diff does NOT replace the required full introduction review.

Required review record:

```text
FULL_INTRODUCTION_BASE_SHA = 415d9c...
FULL_INTRODUCTION_TARGET_SHA = implementation candidate
PLAN_ONLY_DELTA_VERIFIED = YES
IMPLEMENTATION_DELTA_REVIEWED = YES
FULL_COMPOSITE_DIFF_REVIEWED = YES
```

Any production behavior introduced in either segment is part of the full first-introduction review.

This directly restores consistency with the accepted Contract.

---

# 20. Prospective V2-4 dependency-map registration

Only after independent acceptance of the implementation candidate.

Do not mix first-introduction review with prospective registration.

Suggested minimal behavior units:

```text
v2_4.hr_operator
v2_4.hr_child_binding
v2_4.hr_runtime_composition
v2_4.hr_evidence_canonicalization
v2_4.hr_structural_validation
v2_4.hr_artifact_consumption
v2_4.qualification_protocol
tests.v2_4_production_path
```

Prefer one evidence family:

```text
V2_4_HR_PRODUCTION_PATH
```

No generic all-capacity platform registration.

---

# 21. Post-registration closure without runtime rerun

After prospective map registration and independent PASS:

```text
DO NOT rerun the real runtime merely because governance metadata changed.
```

Instead reuse the already-finalized V2-3 attempt and run a fresh:

```text
FORMAL_AUTHORIZATION_SUPPORT check_reuse
```

against the accepted new applicability/closure.

This re-hashes:

```text
RAW
NORMALIZED
provenance
effective config
```

at content depth.

Rerun the scientific/runtime path only if the established V2-3 A1/A2/B routing requires it.

---

# 22. Expected implementation report

```text
V2_4_IMPLEMENTATION_STATUS =
READY_FOR_INDEPENDENT_IMPLEMENTATION_REVIEW

V2_3_CLOSED_AUTHORITY_SHA =
415d9c7132d8203c7970e45a70b77981fc41fc3b

PLAN_AUTHORITY_SHA =
IMPLEMENTATION_CANDIDATE_SHA =
REMOTE_SHA =
REMOTE_SHA_VERIFIED =
WORKTREE_CLEAN =

FULL_INTRODUCTION_BASE_SHA =
415d9c7132d8203c7970e45a70b77981fc41fc3b
FULL_INTRODUCTION_TARGET_SHA =
PLAN_ONLY_DELTA_VERIFIED =
FULL_COMPOSITE_DIFF_REVIEW_READY = YES

C7_SELECTION_AUTHORITY_PATH =
C7_SELECTION_AUTHORITY_SHA256 =
C7_PACKAGE_VALIDATION =
SELECTED_CELL_ID =
SELECTED_PAIR_ID =
SELECTED_CAPACITY_ID =
SELECTED_CAPACITY_BYTES =

CHANGED_FILES =
...

HISTORICAL_C6_SOURCE_MODIFIED = NO
HISTORICAL_C7_SOURCE_MODIFIED = NO
V2_2_SOURCE_MODIFIED = NO
V2_3_SOURCE_MODIFIED = NO

H_R_OPERATOR_IMPLEMENTED =
H_R_REAL_CHILD_IMPLEMENTED =
C7_MOTHER_STRUCTURE_REUSED =
MIA_C7_EVIDENCE_ROOT_BOUND =
C7_SERVICE_PLUS_C6_SUPPRESSION =
REAL_GENERATED_RUNTIME_EXECUTED =

RAW_EVIDENCE_NODE_FILE =
RAW_EVIDENCE_SHA256 =
NORMALIZED_EVIDENCE_NODE_FILE =
NORMALIZED_EVIDENCE_SHA256 =
EFFECTIVE_CONFIG_NODE_FILE =
STRUCTURAL_VALIDATION =

V2_2_TERMINAL_STATE =
V2_3_FINALIZATION =
FINALIZATION_RECEIPT_SHA256 =

FOCUSED_TESTS =
REGRESSION_TESTS =
REAL_V2_4_QUALIFICATION =

TRACKING_OUTCOME_READ = NO
C7_CENSUS_RERUN = NO
H_R_FORMAL_EXECUTED = NO

PROSPECTIVE_V2_4_MAP_REGISTRATION = NOT_STARTED

READY_FOR_INDEPENDENT_IMPLEMENTATION_REVIEW = YES
V2_4_CLOSED_PASS = NO
H_R_FORMAL_AUTHORIZED = NO
```

---

# 23. Stop conditions

Stop if:

```text
frozen C7 selection cannot be resolved
selection package validation is not PASS
C7 mother structure requires runtime semantic changes
C7+C6 configs cannot coexist
MIA_C7_EVIDENCE_ROOT cannot remain attempt-local
real runtime/observer evidence is insufficient
canonical RAW cannot reconstruct the mechanical claim
V2-3 requires recursive multifile references
historical C6/C7/V2-2/V2-3 semantic source must change
tracking outcomes must be read
a new scientific decision is required
```

---

# 24. Maximum authority after Plan Revision 1 acceptance

```text
V2_4_IMPLEMENTATION_PLAN_ACCEPTED = YES
SAFE_TO_IMPLEMENT_V2_4 = YES
```

Still:

```text
V2_4_IMPLEMENTATION_AUTHORIZED = NO
H_R_FORMAL_AUTHORIZED = NO
```
