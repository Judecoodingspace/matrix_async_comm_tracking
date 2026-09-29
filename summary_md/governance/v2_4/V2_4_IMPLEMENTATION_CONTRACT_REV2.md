# MDMT / MIA Governance v2 — V2-4 Production Proof
## Implementation Contract — Revision 2 (Final Candidate)

Status:

```text
V2_3_CLOSED_PASS = YES
V2_3_CLOSED_AUTHORITY_SHA = 415d9c7132d8203c7970e45a70b77981fc41fc3b

V2_4_DISCOVERY_STATUS = READ_ONLY_COMPLETE

TEAM_B_V2_4_CONTRACT_REVISION_1_DELTA_REVIEW = CORRECTION_REQUIRED
P0 = 0
P1 = 1

NEW_V2_4_RESEARCH_DECISION_REQUIRED = NO

V2_4_IMPLEMENTATION_CONTRACT_STATUS = REVISION_2_FOR_FINAL_TEAM_B_DELTA_REVIEW
V2_4_IMPLEMENTATION_AUTHORIZED = NO
H_R_FORMAL_AUTHORIZED = NO
```

Revision 2 closes the remaining contract issue by making the already-completed C7 Pick-cell result and the accepted C7 real-execution structure the explicit upstream basis for H_R.

The governing principle is:

```text
C7 has already answered:
"which registered communication cell should proceed to H_R?"

V2-4 must NOT answer that question again.

V2-4 starts from the exact frozen C7 selected-cell authority
and proves that the future H_R production path executes that selected cell
with real suppression, V2-2 execution governance, and V2-3 artifact governance.
```

---

# 1. V2-4 question

V2-4 proves only:

> the exact C7-selected H_R cell can traverse the real production path with the same accepted C7 FIFO/capacity execution structure, with C6 true-first-service suppression enabled in the same generated PacketRuntime, and with V2-2/V2-3 production governance actually wired.

Target chain:

```text
accepted C7 Pick-cell authority
→ exact selected H_R cell
→ H_R operator
→ V2-2 detached launch
→ H_R real child
→ C7 real-child execution structure as mother template
→ frozen author wrapper / generated PacketRuntime
      ├─ MIA_C7_SERVICE_CONFIG
      └─ MIA_C6_SUPPRESSION_CONFIG
→ real FIFO + real suppression evidence
→ H_R evidence cross-binding
→ H_R child exit
→ V2-2 terminal
→ V2-3 finalization
→ FORMAL_AUTHORIZATION_SUPPORT receipt gate
→ later H_R pre-issuance
```

---

# 2. C7 Pick-cell is an immutable upstream input

H_R must consume the exact accepted C7 selection/Pick-cell artifact.

It MUST NOT:

```text
rerun the 21-cell census
rerank cells
choose a new capacity
choose a "nearby" C6 cell
substitute another pair/capacity because implementation is easier
```

The H_R authorization must exact-bind:

```text
C7 selection artifact identity/hash
selected cell_id
selected pair_id
selected capacity_id
selected capacity_bytes
selection/eligibility authority identity
```

The implementation MUST resolve these values from the accepted repository/artifact authority.

Do not trust a value merely because it appears in this prompt or prior chat.

If the accepted C7 Pick-cell artifact resolves to the expected project-selected cell (for example `P66__P20` if and only if the frozen repository authority confirms it), bind to that exact value.

If repository authority and any prompt/chat value disagree:

```text
STOP
REPORT THE AUTHORITY MISMATCH
```

The repository's accepted frozen selection artifact wins.

---

# 3. No generic seven-capacity H_R requirement

V2-4 is NOT required to build a generic H_R runner for all seven C7 capacities.

The scientific selection stage is already complete.

Therefore the production proof needs to support and prove:

```text
the exact selected C7 cell
```

not:

```text
all possible cells that could have been selected before C7 was run
```

The implementation must still reject a cell/config that differs from the exact selected-cell authority.

This prevents unnecessary generalization and keeps V2-4 tied to the actual H_R scientific path.

---

# 4. C7 real-child structure is the H_R mother template

The accepted structural reference is:

```text
scripts/run_mdmt_mia_c7_real_child.py
```

The H_R child must preserve the same core execution pattern where applicable:

```text
1. reread and verify immutable authorization/source authority
2. observe/verify clean source identity
3. validate the registered scientific cell identity
4. verify author-wrapper identity
5. materialize/verify generated source
6. inventory generated source before execution
7. build a controlled wrapper environment
8. invoke the frozen author wrapper
9. execute the generated PacketRuntime path
10. inventory generated source after execution
11. collect communication-side raw evidence
12. derive normalized evidence deterministically
13. emit a mechanical child status
14. quarantine tracking outcomes from governance logic
```

This is a structural parent/template, not permission to mutate historical C7 files.

Historical C7 source remains unchanged by default.

---

# 5. H_R-specific delta from the C7 mother template

Relative to the accepted C7 real-execution structure, H_R should add only the minimum H_R-specific behavior:

```text
A. consume the frozen C7 Pick-cell authority instead of a census child spec

B. add:
   MIA_C6_SUPPRESSION_CONFIG.enabled = true

C. keep:
   MIA_C7_SERVICE_CONFIG
   for the exact selected C7 capacity

D. cross-bind C7 FIFO/service evidence
   with C6 suppression decision/seal evidence

E. create H_R-specific mechanical evidence/provenance

F. run under V2-2 detached execution

G. finalize/consume evidence through V2-3
```

H_R must not create a second FIFO server, second suppression predicate, or second capacity-selection mechanism.

---

# 6. Runtime mechanism composition

The same generated `PacketRuntime` instance must consume:

```text
MIA_C7_SERVICE_CONFIG
+
MIA_C6_SUPPRESSION_CONFIG
```

The H_R path MUST NOT set:

```text
MIA_C4_SERVICE_CONFIG
```

when `MIA_C7_SERVICE_CONFIG` is active.

Required C7 service binding:

```text
schema_version = C7_REGISTERED_FIFO_SERVICE_V1
mode = fifo
capacity_id = exact selected capacity_id
rate_logical_bytes_per_frame = exact selected capacity_bytes
ledger_enabled = true
run_id = exact H_R run_id
pair_id = exact selected pair_id
```

Required suppression binding:

```text
enabled = true
run_id = same exact H_R run_id
output_dir = attempt-local suppression evidence path
```

The runtime already owns:

```text
registered C7 capacity validation
FIFO queue/service semantics
C6 suppression predicate
true-first-service timing
service/suppression interaction
```

H_R must reuse those behaviors, not reimplement them.

---

# 7. Dedicated H_R operator

Create:

```text
scripts/run_mdmt_mia_hr_formal.py
```

as the sole H_R operator-facing production entry.

Required conceptual phases:

```text
launch
inspect
finalize
preissue-check
```

## launch

Must call:

```text
tracking.governance_v2_execution.launch
```

with direct child:

```text
scripts/run_mdmt_mia_hr_real_child.py
```

No direct scientific `subprocess.run` from the operator.

## inspect

Delegates to V2-2 inspection only.

## finalize

After mechanical child termination, invokes accepted:

```text
tracking.governance_v2_artifacts.finalize
```

## preissue-check

Invokes:

```text
tracking.governance_v2_artifacts.check_reuse
```

with:

```text
consumption_class = FORMAL_AUTHORIZATION_SUPPORT
```

V2-4 does not issue H_R Formal authorization.

---

# 8. H_R real child

Create:

```text
scripts/run_mdmt_mia_hr_real_child.py
```

The child must follow the C7 real-child mother structure while adding the H_R-specific suppression/evidence delta.

It must:

```text
1. load H_R authorization
2. resolve exact C7 Pick-cell authority
3. require exact selected-cell equality
4. verify source / wrapper / generated-source identities
5. build the controlled author-wrapper environment
6. set MIA_C7_SERVICE_CONFIG for the selected cell
7. set MIA_C6_SUPPRESSION_CONFIG enabled
8. execute the same frozen author-wrapper/generated-runtime path
9. prove the real PacketRuntime actually executed
10. recover effective FIFO/capacity evidence
11. recover suppression decision/seal evidence
12. cross-bind both evidence families to the same run/runtime
13. derive H_R normalized evidence
14. emit structural/mechanical status only
```

It must not read tracking-result metrics.

---

# 9. Reuse vs copy rule

Implementation Plan must first inspect whether stable C7 helpers can be safely reused by import without broadening historical authority or introducing fragile private-helper coupling.

Preferred order:

```text
1. reuse existing accepted helper directly, if cleanly reusable;

2. otherwise implement only minimal H_R orchestration glue
   following the accepted C7 real-child structure;

3. never copy/reimplement runtime mechanism logic.
```

Permitted new H_R glue may include:

```text
authorization parsing
selected-cell binding
controlled environment composition
evidence indexing/cross-binding
H_R structural validation
```

Forbidden duplication includes:

```text
C7 capacity validator
FIFO server
service accounting
C6 suppression classifier
true-first-service mechanics
PacketRuntime behavior
```

---

# 10. Real runtime proof is mandatory

The final V2-4 qualification MUST execute:

```text
frozen author wrapper
→ generated PacketRuntime
```

for the exact C7-selected cell.

It must observe enough real runtime evidence to prove:

```text
run_id
pair_id
selected capacity identity
effective rate == selected capacity_bytes
finite FIFO mode
ledger enabled
C6 suppression enabled
suppression evidence emitted
generated runtime origin/source identity
```

Environment construction or launch-spec inspection alone is insufficient.

If the generated PacketRuntime does not execute, or effective config cannot be proven:

```text
P4 = NOT_PROVEN
P5 = NOT_PROVEN
V2_4_PRODUCTION_PROOF = BLOCK
V2_4_CLOSED_PASS = NO
```

No "where feasible" exception.

---

# 11. Evidence reuse: C7 structure first, H_R composition second

V2-4 should reuse the existing C7 evidence structure wherever it already carries the required facts.

Existing C7-style evidence may include:

```text
raw observer evidence
service ledger
service summary
packet census evidence
normalized windows / deterministic window reconstruction
runtime/generated-source provenance
```

H_R additionally needs:

```text
C6 suppression decisions
C6 suppression seal
same-run cross-binding
exact selected-cell binding
```

Do NOT duplicate large C7 evidence merely to give it an H_R filename.

The preferred H_R evidence design is:

```text
canonical existing runtime/C7 evidence
+
canonical suppression evidence
+
small H_R provenance/index/cross-binding record
→ deterministic H_R normalized evidence
```

rather than copying every source record into a new large artifact.

The exact canonical-file layout is Implementation Plan work and must remain compatible with V2-3's one-authoritative-copy principle.

---

# 12. Canonical H_R semantic layers

V2-3 still requires H_R to expose:

```text
RAW_EVIDENCE
NORMALIZED_EVIDENCE
```

but these semantic layers may be composed through exact references to canonical attempt-local evidence rather than byte-copying all upstream files.

## RAW_EVIDENCE semantic layer

Must exact-bind at least:

```text
accepted C7 selected-cell authority
real runtime service evidence
real suppression evidence
generated-runtime/source identity
same-run identity
tracking_outcome_read = false
```

## NORMALIZED_EVIDENCE semantic layer

Must be deterministically derived and mechanically sufficient for H_R downstream validation/analysis.

It must not contain a scientific PASS/FAIL conclusion.

---

# 13. Attempt-root unification

The V2-2 attempt root is the H_R authoritative attempt root.

All evidence relied upon by H_R/V2-3 must reside beneath:

```text
<attempt_root>/output/
```

or be an exact immutable reference allowed by V2-3.

The H_R child must not run the workload in an unrelated scientific output tree and later associate it by narrative.

---

# 14. Structural validator

A small H_R evidence module may be added if needed:

```text
src/tracking/mdmt_mia_hr_evidence.py
```

It may:

```text
validate selected-cell authority binding
cross-bind service + suppression evidence
validate effective runtime configuration
derive normalized evidence
verify raw→normalized provenance
verify no tracking-outcome read
```

Its verdict is structural/mechanical only:

```text
PASS
FAIL
```

It must not judge H_R scientific effect.

---

# 15. V2-3 finalization and pre-issuance

After:

```text
H_R child exit
V2-2 valid terminal
RAW_EVIDENCE available
NORMALIZED_EVIDENCE available
structural validation PASS
```

the H_R operator calls:

```text
governance_v2_artifacts.finalize(...)
```

Then pre-issuance requires:

```text
check_reuse(
    consumption_class="FORMAL_AUTHORIZATION_SUPPORT"
)
```

with:

```text
decision = REUSE_ADMISSIBLE
```

Any refusal blocks later H_R Formal authorization.

V2-4 itself does not issue Formal authorization.

---

# 16. C6 Harness dynamic boundary

The H_R path must not use:

```text
run_harness_v2.py
C6 Formal dynamic load_runner()
```

as its mechanism boundary.

H_R directly composes the accepted runtime configuration mechanisms.

Therefore the old C6 Harness dynamic boundary is not automatically an H_R blocker.

If implementation discovers that dynamic boundary is unavoidable:

```text
STOP
REPORT
```

---

# 17. Minimum proof obligations

V2-4 qualification proves:

```text
P1 exact accepted C7 Pick-cell authority
   → exact H_R authorization / operator identity

P2 H_R operator
   → V2-2 launch

P3 V2-2 wrapper
   → exact H_R child argv/source identity

P4 H_R selected cell
   → MIA_C7_SERVICE_CONFIG
   + MIA_C6_SUPPRESSION_CONFIG
   → one real generated PacketRuntime
   → observed effective configuration

P5 real runtime/service/suppression evidence
   → canonical H_R RAW_EVIDENCE semantic layer

P6 RAW_EVIDENCE
   → deterministic NORMALIZED_EVIDENCE
   → structural validator provenance

P7 V2-2 terminal
   → V2-3 finalization

P8 V2-3 finalization receipt
   → FORMAL_AUTHORIZATION_SUPPORT consumer
```

---

# 18. Non-scientific production proof

The final V2-4 qualification uses the same real H_R production entry.

It uses an explicitly non-scientific qualification authorization that is bound to the SAME selected-cell schema/identity semantics as Formal H_R.

It must exercise:

```text
real H_R operator
real V2-2 wrapper
real H_R child
C7-derived real execution structure
frozen author wrapper
real generated PacketRuntime
exact selected C7 service config
real C6 suppression enabled
real service evidence
real suppression evidence
H_R cross-binding / normalization
structural validation
real V2-3 finalization
real FORMAL_AUTHORIZATION_SUPPORT reuse check
```

It does NOT:

```text
rerun C7 selection
run 21 cells
read tracking outcome
judge H_R scientific effect
run H_R Formal
```

---

# 19. Negative qualification cases

At minimum falsify:

```text
wrong C7 selection artifact/hash
wrong selected cell_id
wrong pair_id
wrong capacity_id
wrong capacity_bytes
unregistered/mismatched capacity tuple
wrong attempt ID
wrong H_R authorization hash
MIA_C4_SERVICE_CONFIG present with C7 config
ledger disabled
suppression disabled
service/suppression run_id mismatch
wrong wrapper identity
wrong generated-source/runtime identity
observed effective rate mismatch
suppression evidence absent
raw evidence/reference missing
normalized evidence missing
structural FAIL
V2-3 finalization refusal
wrong receipt/manifest pin
C4 applicability failure
ambiguous/superseded lineage
```

No all-seven-capacity production sweep is required.

---

# 20. Minimum implementation change surface

Expected new production files:

```text
scripts/run_mdmt_mia_hr_formal.py
scripts/run_mdmt_mia_hr_real_child.py
```

Optional:

```text
src/tracking/mdmt_mia_hr_evidence.py
```

Qualification/tests:

```text
scripts/qualify_mdmt_mia_hr_production_path.py
tests/test_mdmt_mia_hr_production_path.py
```

Historical source remains unchanged by default:

```text
scripts/run_mdmt_mia_c7_real_child.py
scripts/run_mdmt_mia_c6_real_child.py
scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py
src/tracking/mdmt_mia_async_deadline_runtime.py
```

If implementation requires semantic modification of any of these historical mechanism paths:

```text
STOP FOR IMPACT REVIEW
```

---

# 21. Implementation Plan responsibilities

The Plan must identify and freeze:

```text
exact accepted C7 selection artifact/path/hash
exact selected cell tuple
H_R authorization schema
C7 mother-structure helpers that can be safely reused
exact H_R child argv
controlled environment allowlist
author-wrapper invocation
generated-source verification
attempt-local output layout
exact C7 + C6 environment composition
runtime evidence files used for effective-config proof
H_R raw semantic-layer references/index
normalized evidence schema
structural validator
negative fixtures
V2-3 declaration
V2-1 applicability inputs for preissue check
```

These are implementation details, not new research decisions.

---

# 22. V2-1 governance

New H_R/V2-4 behavior is first reviewed as an exact-bound introduction from:

```text
415d9c7132d8203c7970e45a70b77981fc41fc3b
```

After implementation acceptance, prospectively register the V2-4/H_R behavior.

Do not mix introduction review and prospective registration.

---

# 23. Anti-overengineering

Do not add:

```text
new selection stage
new 21-cell census
generic all-capacity H_R platform without need
new FIFO implementation
new suppression implementation
daemon
supervisor
scheduler
artifact service
database
new authority layer
new governance skill
C7 Census refactor
C6 Formal rewrite
large evidence-copy hierarchy
```

---

# 24. Stop conditions

STOP if:

```text
accepted C7 selected-cell authority cannot be resolved exactly

C7 mother execution structure cannot be adapted without changing scientific/runtime semantics

MIA_C7_SERVICE_CONFIG + MIA_C6_SUPPRESSION_CONFIG cannot execute together in the accepted generated PacketRuntime

real runtime does not emit enough evidence to prove effective selected capacity + suppression

authoritative evidence cannot remain within the V2-2/V2-3 attempt architecture

V2-3 needs redesign

C6 Harness dynamic boundary becomes unavoidable

a new scientific decision becomes necessary
```

Do not rerun selection or weaken proof obligations to continue.

---

# 25. Maximum authority after Revision 2 acceptance

If Team B accepts this Revision 2:

```text
V2_4_IMPLEMENTATION_CONTRACT_ACCEPTED = YES
SAFE_TO_DRAFT_V2_4_IMPLEMENTATION_PLAN = YES
```

Still:

```text
V2_4_IMPLEMENTATION_AUTHORIZED = NO
H_R_FORMAL_AUTHORIZED = NO
```
