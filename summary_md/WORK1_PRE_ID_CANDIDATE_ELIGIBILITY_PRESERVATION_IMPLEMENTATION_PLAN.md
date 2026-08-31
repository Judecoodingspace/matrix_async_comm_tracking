# WORK 1 PRE-ID CANDIDATE ELIGIBILITY PRESERVATION IMPLEMENTATION PLAN

## 1. IMPLEMENTATION_STATUS

```text
IMPLEMENTATION_PLAN_READY_FOR_REVIEW
```

Scope is `IMPLEMENTATION_PLANNING_ONLY`. This document authorizes neither
source modification nor fixture/MVE execution. Scientific role remains
`MECHANISM_EXISTENCE_PROBE`; Route A remains `PARKED_AFTER_PLANNING`.

XML-governance writeback status:

```text
GOVERNANCE_DECISION_ALREADY_FROZEN_BEFORE_WRITEBACK
WORK1_DECISION_GT_INDEPENDENT
THIS IS AN EXPLICIT GOVERNANCE AMENDMENT
```

The old full-runtime XML ban is superseded only for the frozen original-MIA
first-frame initialization. Work 1 direct oracle access and GT safety grading
remain forbidden. The implementation target is mechanism/non-interference
under that frozen initialization protocol, not a GT-free deployment runtime.

Frozen source preflight was performed read-only. All contract hashes match:

| Authority item | Frozen/current SHA-256 | Status |
| --- | --- | --- |
| `demo/supplement_MIA.py` | `4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616` | `MATCH` |
| `demo/utils/cascade_runtime.py` | `b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2` | `MATCH` |
| `demo/utils/supplement.py` | `415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6` | `MATCH` |
| `cascade_edge_manifest.json` | `0eb11be11898af2c8b9ba3de8140ca5beac9de3df5ba9213bdafe715b9b9e5ed` | `MATCH` |
| Formal `cascade_run_manifest.json` | `14d23ca17faef9d5f96769d771e02cb12eb615a5a2c96de9d072f47d450ab17e` | `MATCH` |

Implementation, if later authorized, must derive an isolated Work 1 variant
from this exact artifact. The parent v8 directory is immutable authority and
must never be edited in place.

## 2. Frozen source map

| File | Function | Relevant source region | Work 1 role | Access | Author-state mutation risk |
| --- | --- | --- | --- | --- | --- |
| `demo/supplement_MIA.py` | `main()` | 312-315 | Author `get_matched_ids()` produces pre-ID old-unmatched eligibility and payload | planned passive hook immediately after statement | `LOW` if hook receives copies and return is ignored |
| `demo/supplement_MIA.py` | `main()` | 339-351 | `capture_prebranch`, then first ID stage `new_A_to_B` | boundary proof only | `FORBIDDEN`: no Work 1 assignment or call inside ID stage |
| `demo/supplement_MIA.py` | `main()` | 359-404 | `new_B_to_A` and `old_unmatched_repair` | unchanged causal middle | read-only source audit | `FORBIDDEN` |
| `demo/supplement_MIA.py` | `main()` | 408-416 | Author recomputes post-ID membership and exposes actual lineages | planned passive post-ID observation hook after line 416 | `LOW` if all inputs are copied and return is ignored |
| `demo/supplement_MIA.py` | `main()` | 428-447 | Two author High-score helper calls | baseline input/output digest boundaries; author calls unchanged | planned hooks before 428 and after 447 | `HIGH`; no probe output may enter these calls |
| `demo/supplement_MIA.py` | `main()` | 448-518 | Supplement delivery, low-score path, NMS, tracker feedback | unchanged core plus terminal digest observation | planned passive digest/end-frame hook after feedback | `HIGH`; digest only, no returned core value |
| `demo/supplement_MIA.py` | `main()` | 570-577 | Author result serialization and runtime finalizers | observer finalization only after author finalizers | planned logging-only finalizer | `LOW`; output roots must be separate |
| `demo/utils/common.py` | `get_matched_ids()` | 162-243 | Author eligibility semantics used at pre/post boundaries | unchanged/read-only | none from Work 1 |
| `demo/utils/common.py` | `get_matched_ids_lineage()` | 565-634 | Existing author-equivalent row-index exposure | read-only dependency; compare its payload with author output before accepting lineage | no input mutation; fail closed on mismatch |
| `demo/utils/cascade_runtime.py` | `capture_prebranch()` | 162-217 | Proves prebranch occurs before ID mutation; not a Work 1 data source | unchanged/read-only source evidence | no Work 1 access to `_prebranch` or shadow fields |
| `demo/utils/cascade_runtime.py` | `_assert_conservation()` | 231-237 | Existing non-ID row conservation evidence | unchanged; Work 1 performs its own token-local check | none |
| `demo/utils/cascade_runtime.py` | `prepare_author_high_score()` | 347-388 | With edge/shadow disabled, returns actual delayed-branch lineage consumed by author | Work 1 reads only returned `A/B_high_lineage` copies | must reject edge/shadow-enabled environment |
| `demo/utils/supplement.py` | `not_matched_supplement()` | 9-132 | Frozen High-score decision path | no runtime modification; probe parity authority | `FORBIDDEN` |
| `demo/utils/supplement.py` | `not_matched_supplement()` | before line 133 | Frozen successful-path STOP boundary | test-only author line trace stops here | helper supplied objects must remain unchanged |
| `demo/utils/supplement.py` | `not_matched_supplement()` | 136-149 | diagnostic flag, bbox append, matched/confirmed append, supplement update | outside observer/probe boundary | `ABSOLUTELY_FORBIDDEN` |
| `demo/utils/async_deadline_runtime.py` | `deliver_id_state()`, `deliver_supplement()`, `commit_fused_state_to_tracker()` | 342-412 | Existing packet/stage/feedback digests for non-interference | unchanged/read-only artifacts | `FORBIDDEN` |

`demo/utils/common.py` is a transitive frozen dependency with manifest/current
SHA-256 `c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93`.
It is not a proposed modification.

### Exact insertion boundaries

- **Pre-ID creation:** after the completed assignment at
  `supplement_MIA.py:312-315`, before `capture_prebranch()` at 339 and before
  the first author mutation call at 345. `E_pre` is the already returned
  `A/B_old_not_matched_*`; the observer only adds canonical row indices.
- **Post-ID observation:** after `prepare_author_high_score()` has returned
  actual `A/B_high_lineage` at 412-416, with
  `MIA_CASCADE_EDGE_CUT=0` and `MIA_CASCADE_SHADOW=0`, and before author
  High-score calls at 430/439.
- **Lifecycle validation:** inside the post-ID observer call, against current
  `track_bboxes`/`track_bboxes2`; expiry is finalized by a passive frame-end
  call after the author feedback values have been constructed.
- **Opportunity STOP:** the Work 1 probe returns after the line-132-equivalent
  height decision. Its return goes only to `OPPORTUNITY_LEDGER`; it is never
  passed to lines 430-447 or any downstream author variable.

## 3. Proposed minimal file changes

### 3.1 New `src/tracking/mdmt_mia_work1_eligibility_observer.py`

Existing role: none.

Planned change: add one dependency-light module containing:

- immutable `EligibilityKey` and `EligibilityToken` records;
- `row_fingerprint(row[1:])` including dtype, shape and contiguous bytes;
- lifecycle enum with only the four frozen terminal transitions;
- `Work1EligibilityObserver.capture_pre_id(...)`;
- `Work1EligibilityObserver.record_author_initialization_complete(...)`,
  accepting only passive marker metadata and returning `None`;
- `Work1EligibilityObserver.observe_post_id_and_probe(...)`;
- `Work1EligibilityObserver.record_author_high_score_output(...)`;
- `Work1EligibilityObserver.end_frame(...)` and `finalize()`;
- pure `author_equivalent_high_score_probe(...)` and frozen trace schema;
- JSONL serialization and integrity counters.

Why required: token state and probe logic must be isolated from author source,
unit-testable, removable, and unable to return core-state replacements.

Observer-only proof strategy:

- public hook methods return `None`;
- signatures accept only explicit arrays/scalars, never runtime objects or
  `**kwargs`;
- every supplied array is copied before hashing or storage;
- pre/post hashes of supplied mutable objects must match;
- module has no imports from detector, ByteTrack, packet runtime, GT/XML,
  cascade shadow, Route A, ReID or evaluation code;
- all output paths are observer-only paths.

Removal test: delete this module and the exact generated hook blocks; the
derived entrypoint must hash back to frozen `supplement_MIA.py`.

### 3.2 New `scripts/prepare_mdmt_mia_work1_eligibility_variant.py`

Existing role: none. It may reuse only the isolated-copy/replace-once pattern
of the existing Route A variant preparer, not any Route A semantics.

Planned change:

1. verify the five frozen hashes in Section 1 plus `common.py`;
2. refuse an existing destination;
3. copy the frozen v8 artifact to an isolated proposed derivative such as
   `work1_pre_id_eligibility_observer_v1`;
4. copy the observer and XML-governance validity modules into `demo/utils/`;
5. apply exact single-match hook insertions only to the derivative
   `demo/supplement_MIA.py`;
6. write `work1_variant_manifest.json` with parent hashes, changed-file hashes,
   anchor counts and structure audit;
7. verify that `cascade_runtime.py`, `supplement.py`, `common.py`, ByteTrack and
   packet runtime remain byte-identical to the parent.

Why required: the frozen source authority must remain immutable, and the
planned derivative must be reproducible and auditable.

Observer-only proof strategy: static audit rejects any assignment of a hook
return to author variables and any hook inside ID/Supplement/feedback
functions.

Removal test: regenerate from the parent with Work 1 hooks disabled and require
the complete relevant-file hash set to equal the parent manifest.

### 3.3 Generated derivative `demo/supplement_MIA.py`

Existing role: E023 v8 author entrypoint.

Planned change: only the following passive integration blocks in the isolated
derivative:

1. import the Work 1 observer module;
2. create observer state after `CascadeEdgeRuntime` construction when
   `MIA_WORK1_OBSERVER=1`; otherwise bind `None`;
3. after frozen first-frame initialization, create a digest-only
   `AUTHOR_GT_INITIALIZATION_COMPLETE` marker and pass only its safe metadata
   to the observer; the marker-recording return is ignored;
4. call `capture_pre_id(...)` after lines 312-315;
5. call `observe_post_id_and_probe(...)` after lines 412-416;
6. call `record_author_high_score_output(...)` after line 447;
7. call `end_frame(...)` after feedback construction; skipped/initial frames
   may only expire an empty frame state;
8. call observer `finalize()` only after the author packet/cascade finalizers.

Every hook is guarded by `if work1_observer is not None`; every return is
ignored. No author call, threshold, argument order or assignment changes.

Why required: these are the only locations where pre-ID eligibility, post-ID
lineage, author High-score boundary and terminal core digests coexist.

Observer-only proof strategy: source-structure audit plus parent-vs-derivative
OFF and derivative OFF-vs-ON exact core comparisons.

Removal test: exact hook-block removal plus observer-import removal restores
parent entrypoint hash. Prefer clean regeneration over reverse editing.

### 3.4 New `scripts/run_mdmt_mia_work1_eligibility_mve.py`

Existing role: none.

Planned change: one fail-closed staged orchestrator with separately authorized
future modes:

- `manifest-preflight`: serialize only frozen pairs `23,25,27,28,29`, both
  directions, exact full frame sets and image-content hashes;
- `parity-preflight`: invoke the fixed non-GT fixture runner;
- `non-interference-preflight`: compare frozen parent, derivative OFF and
  derivative ON core artifacts;
- `mve`: future execution only after an explicit authorization flag/lock;
- `summarize`: derive aggregate counts and frozen decision labels.

It must not accept arbitrary pair IDs, frame ranges, delays, GT paths,
thresholds or candidate-set expansion. d5 is fixed. Existing author baseline
initialization remains an opaque controlled author dependency; no Work 1
module receives or serializes GT/XML content.

Why required: one process must enforce manifests, attempt isolation, gate
ordering and output completeness without relying on manual commands.

Observer-only proof strategy: orchestrator never imports MIA runtime state; it
launches processes, hashes outputs and reads only approved Work 1/author audit
artifacts.

Removal test: removing the orchestrator has no effect on frozen E023 source or
runtime behavior.

### 3.5 New `tests/test_mdmt_mia_work1_eligibility_mve.py`

Existing role: none.

Planned change: contain the contract-frozen fixture constants and tests for:

- all nine parity cases;
- author line-trace truncation before line 133;
- exact float32 trace equality;
- row fingerprint/conservation;
- each authorized lifecycle transition;
- no fifth invalidation reason;
- subset and exactly-once invariants;
- input immutability;
- forbidden import/schema/field names;
- variant structure and removal restoration.

Why required: probe parity and lifecycle integrity are scientific validity
gates, not optional style tests.

Observer-only proof strategy: author helper is loaded by exact hash, invoked
only on deep copies with `diagnostic_events=None`, and successful paths are
interrupted before line 133.

Removal test: tests import no detector/tracker and create no runtime outputs
outside a temporary directory.

### 3.6 XML-governance validity infrastructure

New files:

- `src/tracking/mdmt_mia_work1_xml_governance.py` implements pure G-XML1–5
  validators and digest-only marker construction;
- `scripts/audit_mdmt_mia_work1_xml_governance.py` validates pre-existing JSON
  evidence records but cannot open XML/GT or create expected baselines;
- `tests/test_mdmt_mia_work1_xml_governance.py` contains static/synthetic
  fail-closed gate tests;
- `summary_md/ABC_INITIALIZATION_EQUALITY_AUDIT_SCHEMA.json` freezes structure
  only and contains no runtime result.

This infrastructure is `EXECUTION_VALIDITY_EVIDENCE`, not mechanism logic.
None of its outputs may enter eligibility or opportunity metrics.

### 3.7 No-change list

The plan makes **no modification** to:

- frozen parent `packetized_id_supplement_cascade_v8`;
- `demo/utils/cascade_runtime.py`;
- `demo/utils/supplement.py`;
- `demo/utils/common.py`;
- `demo/utils/async_deadline_runtime.py`;
- ByteTrack/MMTrack;
- detector, NMS, packet, feedback or final prediction code;
- Route A documents or implementation.

## 4. Runtime data flow

```text
Frozen author get_matched_ids() at lines 312-315
        |
        | passive copies only; hook return ignored
        v
E_pre capture
  key = (frame, source_view, target_view, pre_id_row_index)
  payload = creation stage + digest(row[1:]) + existing center/corners
        |
        v
current-frame token ledger (observer state only)
        |
        +---------------- AUTHOR-STATE MUTATION FORBIDDEN ----------------+
        |                                                                |
        v                                                                |
new_A_to_B -> new_B_to_A -> old_unmatched_repair                          |
AUTHOR ID stages unchanged                                                |
        |                                                                |
        v                                                                |
post-ID author recomputation + actual A/B_high_lineage                    |
        | passive copies only                                             |
        v                                                                |
E_post observation                                                        |
        |                                                                |
        v                                                                |
lifecycle validation                                                      |
  index absent       -> INVALIDATED_ROW_LOST                              |
  digest mismatch    -> INVALIDATED_ROW_REPLACED                          |
  absent from E_post -> POST_ID_MEMBERSHIP_DISAPPEARED_ONLY (diagnostic)  |
        |                                                                |
        v                                                                |
E_int = surviving E_pre tokens only                                       |
  ASSERT E_int subset_of E_pre                                            |
  NEVER E_pre union E_post                                                |
        |                                                                |
        v                                                                |
read-only author-equivalent probe on copies                               |
  projection -> bounds -> clipping -> ordered IoU > 0.3                  |
  -> frozen selection/tie -> width -> height                              |
        |                                                                |
        v                                                                |
WRITEIN_OPPORTUNITY audit record                                           |
        |                                                                |
        v                                                                |
STOP -- no bbox/ID/matched/confirmed/NMS/feedback output                  |
        +---------------- AUTHOR-STATE MUTATION FORBIDDEN ----------------+

Meanwhile the original author calls at lines 430-447 continue unchanged,
then Supplement delivery -> low-score -> NMS -> feedback -> next frame.
Observer records digests only; it never supplies a value to that path.
```

### Frozen state model

Conceptual pseudocode only:

```text
capture_pre_id(author_pre_outputs, rows):
    lineage_bundle = author_equivalent_lineage_on_copies(...)
    assert lineage payload == author_pre_outputs
    create E_pre tokens in source-row order

observe_post_id_and_probe(author_post_lineages, current_rows, H, target_det):
    validate row index/fingerprint
    E_int = surviving E_pre
    assert E_int <= E_pre
    mark absence from E_post as diagnostic only
    probe E_post and E_int separately on copies
    consume each surviving E_pre token once
    return None
```

`E_post`-only rows may be observed for the baseline, but are never inserted
into `E_int`. `N_post_only_injected` measures this forbidden insertion, not the
mere legal existence of an `E_post`-only author candidate.

## 5. M1 plan

### M1.1 Isolated source derivation

- Implement the hash-guarded variant preparer.
- Require exact parent source/run/variant hashes before any copy.
- Generate a fresh derivative; never patch an existing directory.
- Structure audit must report only the observer module and derivative
  `supplement_MIA.py` as scientific integration changes.

### M1.2 Token capture

- In `capture_pre_id`, call existing `get_matched_ids_lineage()` on copies with
  canonical `range(len(rows))` lineage.
- Compare its IDs/points/corners to the already returned author
  `get_matched_ids()` pre-ID outputs. Any mismatch is
  `PRE_ID_LINEAGE_PAYLOAD_MISMATCH` and blocks execution.
- Create token key exactly
  `(frame_id, source_view_id, target_view_id, pre_id_row_index)`.
- Store only frozen payload fields; pre-ID confirmed/matched state used by the
  existing author extraction is not persisted.
- Reject duplicate key creation.

### M1.3 Post-ID and lifecycle

- Read copies of returned `A_high_lineage`/`B_high_lineage` only after proving
  cascade edge cut and shadow are disabled.
- Validate the original source index against the current row array.
- Out-of-range index becomes `INVALIDATED_ROW_LOST`.
- Any `row[1:]` fingerprint mismatch becomes
  `INVALIDATED_ROW_REPLACED`; no IoU/ID/appearance recovery is permitted.
- A surviving token absent from `E_post` receives only
  `POST_ID_MEMBERSHIP_DISAPPEARED_ONLY`.
- Surviving tokens are evaluated once and transition to `CONSUMED_ONCE`.
- If the legal boundary is not reached, `end_frame` applies
  `EXPIRED_FRAME_END`; no token crosses into the next frame.

### M1.4 Ledger state

Expected in-memory observer state is bounded to one frame:

```text
current_frame_id
tokens_by_frozen_key
e_post_lineage_by_direction
opportunity_trace_rows
integrity_counters
```

After `end_frame`, immutable audit rows may be streamed to observer-only files,
then all live token maps are cleared. No bbox/Kalman/appearance/history/future
state is retained.

### M1.5 Invariant checks

- creation boundary strictly precedes line 345;
- key contains no runtime ID;
- `E_int subset_of E_pre`;
- no pre/post union;
- only four terminal transitions;
- disappearance-only never invalidates;
- every survivor consumed exactly once;
- invalidated/expired token consumed zero times;
- input aliases and before/after input digests unchanged;
- no observer return assigned to author state.

### M1 completion gate

```text
SOURCE_HASHES_MATCH
AND VARIANT_STRUCTURE_AUDIT_PASS
AND TOKEN_SCHEMA_AUDIT_PASS
AND LIFECYCLE_STATE_MACHINE_PASS
AND SUBSET_EXACTLY_ONCE_PASS
AND AUTHOR_INPUT_IMMUTABILITY_PASS
```

M1 completion permits only M2 review/testing authorization, not MVE execution.

## 6. M2 plan

### M2.1 Read-only probe

Implement the exact source order using float32 arrays:

1. `reshape(-1,1,2).astype(np.float32)` for centers/corners;
2. `cv2.perspectiveTransform`;
3. raw corner min/max and the exact strict outside comparisons;
4. clipping to `0,0,1920,1080` in target-row order;
5. source-equivalent IoU formula including `1e-6`;
6. strict `max(iou)>0.3` and ordered `iou>0.3` indices;
7. unique max-IoU versus multi max-score branch;
8. first returned row on exact score tie;
9. width `<20`, then height `<20` rejection;
10. trace-only `WRITEIN_OPPORTUNITY` and return.

The probe signature contains no source runtime ID, matched/confirmed state,
GT, future state or Route A state.

### M2.2 Author trace plan

- Verify frozen helper hash before loading.
- Use a test-only line tracer restricted to exact path/function.
- Supply deep copies, `diagnostic_events=None`, fixed synthetic inputs.
- Capture locals at the frozen decision lines.
- On successful paths, raise a dedicated internal stop sentinel before line
  133 executes.
- On reject paths, allow natural return while recording the reached branches.
- Hash all supplied mutable objects before/after; any difference fails parity.
- The sentinel is accepted only from the exact success boundary; any other
  exception fails.

This produces the reference trace without editing or crossing the author
mutation boundary.

### M2.3 Fixture runner

Use only the nine contract-frozen cases:

```text
OUTSIDE, NO_IOU, UNIQUE, MULTI_SCORE, MULTI_TIE,
WIDTH_REJECT, HEIGHT_REJECT, CLIP_SUCCESS, SOURCE_ORDER
```

Compare exact field presence/order, scalar types, booleans, indices, branch
labels, target order, tie position and canonical float32 bytes. Do not use a
tolerance, GT, images, detector inference or tracker execution.

### M2.4 Oracle firewall

The audit must combine four independently machine-checkable layers:

1. **Import audit:** parse new module/runner imports and reject GT/XML/MDA,
   shadow/counterfactual, Route A, H/F/BEV/flow/ReID/evaluator dependencies.
2. **Schema audit:** recursively enumerate token, probe and ledger keys; reject
   forbidden names and undeclared fields.
3. **Runtime-field audit:** explicit typed hook inputs only; record the allowed
   field names actually passed. Reject `**kwargs`, runtime-object handles and
   any forbidden field access.
4. **Access/environment audit:** require
   `MIA_CASCADE_EDGE_CUT=0`, `MIA_CASCADE_SHADOW=0`; log zero Work 1 reads of
   `S_cf`, `Yec`, shadow/counterfactual, GT/XML/MDA, future/held-out, Route A or
   new geometry/ReID evidence.

The frozen author runtime's pre-existing initialization remains outside the
Work 1 observer data interface and is held constant; no observer/probe/ledger
branch can receive, inspect or serialize it. No GT grading is planned.

This paragraph is now enforced by `WORK1_DYNAMIC_M2_PREEXECUTION_GATE`, not by
the superseded absolute full-runtime XML ban. Ordinary author rows may enter
the observer only as `SHARED_FROZEN_AUTHOR_STATE`; raw XML/GT fields and
correctness semantics remain forbidden.

#### G-XML1 — Frozen initialization provenance

Before launch, compare an already-frozen expected record with the observed
record for:

```text
author_entrypoint_sha256
xml_reader_source_sha256
initialization_code_sha256
xml_view1_sha256
xml_view2_sha256
initialization_frame
```

The expected record cannot be regenerated from observed files. Any mismatch
is `G_XML1_INITIALIZATION_PROVENANCE_FAIL` and blocks launch.

#### G-XML2 — A/B/C initialization equality

Future `ABC_INITIALIZATION_EQUALITY_AUDIT.json` records exact A/B/C values for
the XML hashes, initialization-code hash/frame, both views' initial bbox/ID/
label output digests, and post-initialization tracker-state digest. All fields
must satisfy `A == B == C`; no tolerance is permitted. Failure is
`G_XML2_ABC_INITIALIZATION_MISMATCH` and invalidates the attempt before core
non-interference interpretation.

#### G-XML3 — Work 1 oracle firewall

The static layer audits Work 1 imports, explicit function signatures, schemas,
serialized keys, environment variables, and file-path interfaces. The dynamic
audit is sourced from actual registered Work 1 path/interface/serialization
observations, declares its observability boundary, and requires:

```text
xml_open_count_by_work1 = 0
gt_file_open_count_by_work1 = 0
gt_field_access_count_by_work1 = 0
gt_serialized_field_count = 0
```

Only frozen author initialization may access XML. Failure is
`G_XML3_WORK1_ORACLE_FIREWALL_FAIL`.

#### G-XML4 — Initialization boundary

An isolated derivative may add only a passive
`AUTHOR_GT_INITIALIZATION_COMPLETE` marker after first-frame initialization
and before any Work 1 record. It records frame, completion Boolean, author
state digest, and monotonically ordered sequence number. One shared counter is
advanced only by the actual second `read_xml_r` completion, marker hook and
first E_pre hook; hard-coded numbers are forbidden. Its return is ignored.
Required ordering is:

```text
last_author_GT_read
< AUTHOR_GT_INITIALIZATION_COMPLETE
< first_Work1_E_pre_record
```

Failure is `G_XML4_INITIALIZATION_BOUNDARY_FAIL`. The marker and its digest are
execution-validity evidence and may not enter mechanism metrics.

#### G-XML5 — Claim/output firewall

Validate eligibility/opportunity ledgers, aggregates, decision template, and
report template against forbidden correctness, candidate-truth, MDA, IDF1,
MOTA, IDSW, false/safe-write-in, deployment-ready, and GT-free-runtime fields
or claims. `GT_SAFETY_UNGRADED` remains the only safety status. Failure is
`G_XML5_CLAIM_BOUNDARY_FAIL`.

#### Frozen gate order

```text
M2_SYNTHETIC_PARITY_PASS
-> G-XML1
-> G-XML3 STATIC
-> SOURCE / DERIVATIVE HASH
-> execution authorization review
-> future A/B/C launch
-> G-XML2
-> G-XML4
-> G-XML3 DYNAMIC
-> CORE_OUTPUT_DIFF
-> B_VS_C_CORE_DIFF_COUNT
-> OBSERVER_GUARD_CHANGE_COUNT
-> G-XML5 FINAL
```

Prelaunch failures prevent process launch. Post-launch validity failures mark
the attempt invalid and stop before interpreting non-interference.

### M2.5 Non-interference audit

Future audit matrix, using identical cache/input/config/seed/d5:

```text
A = frozen parent v8 (no Work 1 code)
B = Work 1 derivative, observer OFF
C = Work 1 derivative, observer ON
```

Require `A == B` and `B == C`, excluding only declared Work 1 ledgers. Compare:

- detector cache/content hashes;
- final detector rows where already exposed;
- ByteTrack/final tracking rows and row order;
- existing packet trace and three ID-stage digests;
- author High-score input digest captured before calls;
- author High-score output digest captured after calls;
- existing high-/low-score Supplement packet digests;
- NMS/final track-row digest;
- feedback and next-frame input chain digests;
- packet emission/consumption accounting;
- final prediction files.

Required result:

```text
CORE_OUTPUT_DIFF = 0
B_VS_C_CORE_DIFF_COUNT = 0
OBSERVER_GUARD_CHANGE_COUNT = 0
```

Any timing difference is descriptive only; any scientific/core difference is
failure. No retry may change code, pair, delay or threshold.

### M2 required PASS gates

```text
G1_SOURCE_AND_INPUT_PROVENANCE_PASS
G2_CREATION_BOUNDARY_PASS
G3_ROW_IDENTITY_PASS
G4_SUBSET_PASS
G5_INVALIDATION_SEPARATION_PASS
G6_EXACTLY_ONCE_PASS
G7_PROBE_PARITY_PASS
G8_ORACLE_FIREWALL_PASS
G9_NON_INTERFERENCE_PASS
```

Any failure blocks `MVE_EXECUTION_AUTHORIZATION`. In particular, probe boundary
failure is `IMPLEMENTATION_PLAN_BLOCKED_BY_PROBE_BOUNDARY`; need for a new
invalidation predicate is `NEEDS_RESEARCH_DECISION`.

## 7. M3 execution preconditions

M3 remains future-only. A separate human `MVE_EXECUTION_AUTHORIZATION` may be
requested only when all conditions below are documented as PASS:

1. M1 implementation review and source-structure audit;
2. M2 frozen fixture parity;
3. exact E023 parent/run/variant/relevant-file hashes;
4. derivative manifest and removal restoration;
5. frozen `MVE_INPUT_MANIFEST.json` containing exactly pairs
   `23,25,27,28,29`, both directions and complete frame sets;
6. image filename-set and content-hash validation;
7. d5 ID-state delay only, all other frozen channels unchanged;
8. edge cut/shadow/oracle paths disabled;
9. oracle firewall PASS;
10. `G-XML1` and static `G-XML3` PASS before launch;
11. future `G-XML2`, `G-XML4`, and dynamic `G-XML3` PASS before interpreting A/B/C;
12. parent-vs-derivative-OFF and OFF-vs-ON non-interference PASS;
13. fresh isolated output root and attempt fingerprint;
14. explicit confirmation that GT safety remains `GT_SAFETY_UNGRADED`.

M3 may not replace/add a pair, shorten frames, run a delay sweep, access
held-out, use official-test pairs for selection, grade GT, or transition into
Formal. If all units have no activation, return
`MVE_MECHANISM_NOT_ACTIVATED` and stop the epoch.

### Future output ownership

| Required output | Future producer | Evidence source |
| --- | --- | --- |
| `MVE_INPUT_MANIFEST.json` | staged orchestrator preflight | frozen pair/frame table plus content hashes |
| `ELIGIBILITY_LEDGER.jsonl` | observer finalizer | one row per `E_pre` token |
| `OPPORTUNITY_LEDGER.jsonl` | observer finalizer | separate `E_post` and `E_int` probe traces |
| `ELIGIBILITY_AGGREGATE_BY_PAIR_DIRECTION.csv` | orchestrator summarize | eligibility ledger only |
| `TOKEN_LIFECYCLE_AUDIT.json` | observer/orchestrator audit | transition and exactly-once counters |
| `PROBE_PARITY_AUDIT.json` | M2 fixture runner | author/probe exact traces and input hashes |
| `ORACLE_FIREWALL_AUDIT.json` | static/runtime audit stage | imports, schemas, passed fields, environment/access log |
| `NON_INTERFERENCE_AUDIT.json` | M2 orchestrator | A/B/C core artifact comparisons |
| `MVE_DECISION.md` | summarize stage | frozen G1-G11 decision order only |

No real result file is generated during implementation planning.

## 8. Minimal-change audit

| Proposed change | Classification | Necessary/removable | Scientific effect | Non-interference risk/control |
| --- | --- | --- | --- | --- |
| isolated derivative instead of editing frozen parent | `REQUIRED_FOR_LOGGING` | necessary | none | prevents source-authority overwrite; hash guard |
| new observer/token/probe module | `REQUIRED_FOR_TOKEN_CAPTURE`, `REQUIRED_FOR_ROW_CONSERVATION`, `REQUIRED_FOR_PROBE`, `REQUIRED_FOR_LOGGING` | necessary | observes frozen causal variable only | explicit inputs, copies, ignored returns |
| derivative import/initialization hook | `REQUIRED_FOR_TOKEN_CAPTURE` | necessary | enables/disables passive observer | env guard; parent-vs-OFF audit |
| post-line-315 capture hook | `REQUIRED_FOR_TOKEN_CAPTURE` | necessary | records already legal `E_pre` | before first ID mutation; no assignment |
| post-line-416 observation/probe hook | `REQUIRED_FOR_ROW_CONSERVATION`, `REQUIRED_FOR_PROBE` | necessary | compares `E_pre/E_post/E_int` without union | copies; stop before author High-score |
| post-line-447 output-digest hook | `REQUIRED_FOR_LOGGING` | necessary for High-score non-interference proof | none | digest only; return ignored |
| post-feedback end-frame/digest hook | `REQUIRED_FOR_LOGGING` | necessary for lifecycle expiry and core proof | none | after author feedback construction |
| observer finalizer after author finalizers | `REQUIRED_FOR_LOGGING` | necessary | serializes audit only | separate observer output root |
| variant preparation script | `REQUIRED_FOR_LOGGING` | necessary | none | exact anchors/hashes; refuses overwrite |
| staged runner/aggregator | `REQUIRED_FOR_LOGGING` | necessary | enforces frozen inputs/gates | no runtime-state import; no free pair/delay args |
| combined lifecycle/parity test file | `REQUIRED_FOR_PROBE`, `REQUIRED_FOR_ROW_CONSERVATION` | necessary | validates measurement semantics | synthetic-only, temp outputs |
| modify `cascade_runtime.py` | `OPTIONAL` | **removed** | unnecessary | avoids shadow/oracle coupling |
| modify `supplement.py` | `OPTIONAL` | **removed** | would risk author semantics | parity uses immutable source + line trace |
| modify `common.py` | `OPTIONAL` | **removed** | unnecessary | existing lineage helper is read-only |
| modify ByteTrack/NMS/packet/feedback | `OPTIONAL` | **removed** | forbidden scientific change | existing digests plus entrypoint hooks suffice |
| new logical invalidation predicate | `OPTIONAL` | **removed / not authorized** | would change intervention | requires `NEEDS_RESEARCH_DECISION` |
| Route A lineage/tombstone/history/bridge | `OPTIONAL` | **removed / forbidden** | collapses scope into Route A | immediate stop if required |

The implementation changes one generated entrypoint and adds isolated support
files. It changes no author algorithm function. Deleting all Work 1 generated
hooks/module—or simply running the frozen parent—fully restores the exact E023
cascade. The removal/hash test makes this claim auditable rather than verbal.

## 9. Blockers

```text
NONE
```

Source hashes match, pre/post row lineage is exposed without post-ID identity
recovery, and the author trace can stop before mutation. The failed non-test GT
protocol is not an observer implementation blocker; it continues to block all
correctness, safety and performance claims.

## 10. Implementation authorization recommendation

```text
READY_FOR_IMPLEMENTATION_AUTHORIZATION_REVIEW
```

This recommendation permits only human review of the plan. It does not
authorize writing code, running the parity fixture, running detector/tracker,
running the MVE, accessing held-out data or entering Formal.

## 11. Dynamic M2 full-core comparison addendum

The earlier `DYNAMIC_M2_COMPARISON_COVERAGE_BLOCKER` is resolved at the
source-mapping plus synthetic/static implementation layer. Future A/B/C must
use the architecture and exact checkpoint/canonicalization rules frozen in:

- `WORK1_FULL_CORE_COMPARISON_SOURCE_MAP.md`
- `WORK1_FULL_CORE_COMPARISON_INSTRUMENTATION_SPEC.md`
- `WORK1_FULL_CORE_COMPARISON_INSTRUMENTATION_MANIFEST.json`

This addendum does not authorize persistent derivative generation or runtime.
The next governance state is:

```text
READY_TO_REPEAT_DYNAMIC_M2_EXECUTION_AUTHORIZATION_REVIEW
```

## 12. Dynamic M2 validity-repair addendum

The repeated authorization review requires the following engineering gates
before any scientific interpretation. They do not change the frozen causal
variable or observer treatment:

1. validate each trace independently against the exact schema, expected pair,
   externally frozen full frame count, and literal frame0/standard/final
   checkpoint profiles;
2. require exact parent-author-output versus A-traced-output parity;
3. run B twice in isolated roots and require exact trace repeatability;
4. machine-check normalized launch env/argv, allowing only the enumerated
   treatment and artifact-isolation differences;
5. build G-XML2 from passive initialization component digests plus the already
   frozen XML identity manifest;
6. emit and validate G-XML3 dynamic counters and the complete G-XML4 boundary
   ordering record;
7. count unique mutation boundaries so guard evidence is not double-counted.

Any missing/invalid artifact, incomplete profile, repeat mismatch, parent
parity mismatch, or unauthorized launch difference stops the attempt.
